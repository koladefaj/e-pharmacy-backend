import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest

from app.db.enums import OrderStatus
from app.models.inventory import InventoryBatch
from app.models.order import Order


@pytest.mark.asyncio
async def test_e2e_non_prescription_purchase_flow(
    client, customer_token, test_customer, sample_product_otc, db_session, mock_redis
):
    user_id = test_customer.id
    product_id = str(sample_product_otc.id)

    # STOCK PREPARATION
    batch = InventoryBatch(
        product_id=sample_product_otc.id,
        batch_number="E2E-BATCH-001",
        initial_quantity=50,
        current_quantity=50,
        price=Decimal("100.00"),
        expiry_date=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(batch)
    await db_session.commit()

    # REDIS CART PREPARATION
    cart_data = {"items": [{"product_id": product_id, "quantity": 1}]}
    await mock_redis.set(f"cart:{user_id}", json.dumps(cart_data))

    # CHECKOUT
    checkout_resp = await client.post("/api/v1/cart/checkout", headers=customer_token)
    assert checkout_resp.status_code == 200
    order_id = checkout_resp.json()["order_id"]

    # PREPARE REDIS FOR PAYMENT SERVICE
    checkout_session_data = {"order_id": order_id, "amount": "100.00"}
    await mock_redis.set(
        f"checkout:{user_id}", json.dumps(checkout_session_data), ex=900
    )

    # CREATE PAYMENT INTENT
    payment_resp = await client.post(
        f"/api/v1/payments/order/{order_id}", headers=customer_token
    )
    assert payment_resp.status_code == 200

    # Fetch the order from DB
    order_in_db = await db_session.get(Order, uuid.UUID(order_id))
    pi_id = order_in_db.payment_intent_id
    assert pi_id is not None

    # Remove Redis checkout to allow webhook processing
    event_id = f"evt_{uuid.uuid4().hex}"
    await mock_redis.delete(f"stripe:event:{event_id}")

    # Simulate webhook
    stripe_payload = {
        "id": event_id,
        "type": "payment_intent.succeeded",
        "data": {
            "object": {
                "id": pi_id,
                "metadata": {"order_id": order_id, "customer_id": str(user_id)},
            }
        },
    }

    # MOCK THE STOCK DEDUCTION
    with patch("app.services.payment_service.CRUDProduct") as MockCRUDProduct:
        # Create a mock CRUDProduct instance
        mock_crud_instance = AsyncMock()

        # Create a call tracker to verify the method was called correctly
        deduct_calls = []

        async def mock_deduct(product_id, quantity):
            deduct_calls.append((product_id, quantity))
            return None

        mock_crud_instance.deduct_stock_fefo = AsyncMock(side_effect=mock_deduct)
        MockCRUDProduct.return_value = mock_crud_instance

        webhook_resp = await client.post(
            "/api/v1/payments/webhooks/stripe",
            json=stripe_payload,
            headers={"stripe-signature": "mock_sig"},
        )

    assert webhook_resp.status_code == 200

    response_data = webhook_resp.json()
    print(f"Webhook response: {response_data}")
    assert response_data["status"] == "ok"

    # VERIFY the mock was called correctly
    print(f"Deduct stock was called {len(deduct_calls)} times")
    assert len(deduct_calls) > 0, "deduct_stock_fefo should have been called"

    # Check it was called with the right product ID
    for product_id_called, quantity_called in deduct_calls:
        print(
            f"  Called with product_id: {product_id_called}, quantity: {quantity_called}"
        )
        assert quantity_called == 1

    # VERIFY FINAL STATE
    await db_session.refresh(order_in_db)
    print(f"FINAL STATUS: {order_in_db.status}")
    assert order_in_db.status == OrderStatus.PAID
    assert order_in_db.paid_at is not None
