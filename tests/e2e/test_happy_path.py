import pytest
import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app.models.order import Order
from app.models.inventory import InventoryBatch
from app.db.enums import OrderStatus

@pytest.mark.asyncio
async def test_e2e_non_prescription_purchase_flow(
    client, 
    customer_token, 
    test_customer, 
    sample_product_otc, 
    db_session, 
    mock_redis
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
        expiry_date=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db_session.add(batch)
    await db_session.commit()

    await db_session.refresh(sample_product_otc)

    # REDIS CART PREPARATION
    cart_data = {"items": [{"product_id": product_id, "quantity": 1}]}
    await mock_redis.set(f"cart:{user_id}", json.dumps(cart_data))

    # CHECKOUT
    checkout_resp = await client.post("/api/v1/cart/checkout", headers=customer_token)
    assert checkout_resp.status_code == 200
    order_id = checkout_resp.json()["order_id"]

    # PREPARE REDIS FOR PAYMENT SERVICE
    checkout_session_data = {"order_id": order_id, "amount": "100.00"}
    await mock_redis.set(f"checkout:{user_id}", json.dumps(checkout_session_data), ex=900)

    # CREATE PAYMENT INTENT
    payment_resp = await client.post(f"/api/v1/payments/order/{order_id}", headers=customer_token)
    assert payment_resp.status_code == 200

    # Fetch the order from DB
    db_session.expire_all()
    order_in_db = await db_session.get(Order, uuid.UUID(order_id))

    # Make sure the payment_intent_id is unique
    pi_id = order_in_db.payment_intent_id
    assert pi_id is not None  # sanity check

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
                "metadata": {
                    "order_id": order_id,
                    "customer_id": str(user_id)
                }
            }
        }
    }

    webhook_resp = await client.post(
        "/api/v1/payments/webhooks/stripe",
        json=stripe_payload,
        headers={"stripe-signature": "mock_sig"}
    )
    
    assert webhook_resp.status_code == 200

