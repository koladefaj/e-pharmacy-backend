import json
from decimal import Decimal

import pytest

from app.db.enums import OrderStatus


@pytest.mark.asyncio
async def test_full_order_checkout_flow(
    client, customer_token, test_customer, sample_product_otc, db_session, mock_redis
):
    user_id = test_customer.id
    product_id = str(sample_product_otc.id)

    # STOCK PREPARATION
    from datetime import datetime, timedelta, timezone

    from app.models.inventory import InventoryBatch

    batch = InventoryBatch(
        product_id=sample_product_otc.id,
        batch_number="BATCH-001",
        initial_quantity=100,
        current_quantity=100,
        price=Decimal("50.00"),
        expiry_date=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(batch)
    await db_session.commit()

    # REDIS CART PREPARATION
    cart_data = {"items": [{"product_id": product_id, "quantity": 2}]}
    await mock_redis.set(f"cart:{user_id}", json.dumps(cart_data))

    # CHECKOUT
    checkout_resp = await client.post("/api/v1/cart/checkout", headers=customer_token)
    assert checkout_resp.status_code == 200
    order_id = checkout_resp.json()["order_id"]

    # CREATE PAYMENT INTENT
    payment_resp = await client.post(
        f"/api/v1/payments/order/{order_id}", headers=customer_token
    )
    assert payment_resp.status_code == 200
    assert "client_secret" in payment_resp.json()

    # LIST ORDERS
    list_resp = await client.get("/api/v1/orders", headers=customer_token)
    assert list_resp.status_code == 200
    assert any(o["id"] == order_id for o in list_resp.json())

    # CANCEL ORDER
    cancel_resp = await client.post(
        f"/api/v1/orders/{order_id}/cancel", headers=customer_token
    )
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["status"] == OrderStatus.CANCELLED.value
