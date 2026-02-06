import pytest
import json
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from app.models.order import Order
from app.models.inventory import InventoryBatch
from app.models.prescription import Prescription
from app.db.enums import OrderStatus, PrescriptionStatus

@pytest.mark.asyncio
async def test_e2e_prescription_rejection_and_order_cancellation(
    client, 
    customer_token, 
    pharmacist_token,
    test_customer, 
    sample_product_rx, 
    db_session, 
    mock_redis,
    mock_storage_service
):
    user_id = test_customer.id
    product_id = str(sample_product_rx.id)

    # STOCK PREPARATION
    batch = InventoryBatch(
        product_id=sample_product_rx.id,
        batch_number="RX-BATCH-FAIL",
        initial_quantity=50,
        current_quantity=50,
        price=Decimal("150.00"),
        expiry_date=datetime.now(timezone.utc) + timedelta(days=365),
    )
    db_session.add(batch)
    await db_session.commit()

    await db_session.refresh(sample_product_rx)

    # REDIS CART PREPARATION
    cart_data = {"items": [{"product_id": product_id, "quantity": 1}]}
    await mock_redis.set(f"cart:{user_id}", json.dumps(cart_data))

    # CHECKOUT 
    # Since it's an RX product, status should be AWAITING_PRESCRIPTION
    checkout_resp = await client.post("/api/v1/cart/checkout", headers=customer_token)
    assert checkout_resp.status_code == 200
    order_id = checkout_resp.json()["order_id"]
    
    # Verify initial DB state
    order_in_db = await db_session.get(Order, uuid.UUID(order_id))
    assert order_in_db.status == OrderStatus.AWAITING_PRESCRIPTION

    # CUSTOMER UPLOADS PRESCRIPTION (The "Wrong" One)
    file_content = b"%PDF-1.4 Fake/Wrong Prescription Content"
    upload_resp = await client.post(
        f"/api/v1/prescriptions/upload?order_id={order_id}",
        files={"file": ("wrong_prescription.pdf", file_content, "application/pdf")},
        headers=customer_token
    )
    assert upload_resp.status_code == 200
    prescription_id = upload_resp.json()["id"]

    # PHARMACIST REJECTS THE PRESCRIPTION
    rejection_payload = {
        "prescription_id": prescription_id,
        "reason": "The prescription is expired and for the wrong patient."
    }
    reject_resp = await client.post(
        "/api/v1/prescriptions/reject",
        json=rejection_payload,
        headers=pharmacist_token
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "rejected"

    # VERIFY FINAL STATE
    # Refresh to see the cascade effect from Rejection -> Order Cancellation
    await db_session.refresh(order_in_db)
    
    print(f"FINAL ORDER STATUS: {order_in_db.status}")
    
    # The order should now be cancelled because the required prescription was rejected
    assert order_in_db.status == OrderStatus.CANCELLED
    
    # Verify Prescription status in DB
    presc_in_db = await db_session.get(Prescription, uuid.UUID(prescription_id))
    assert presc_in_db.status == PrescriptionStatus.REJECTED
    assert presc_in_db.rejection_reason == "The prescription is expired and for the wrong patient."

    # VERIFY INVENTORY (Stock should NOT have been deducted)
    await db_session.refresh(batch)
    assert batch.current_quantity == 50



@pytest.mark.asyncio
async def test_e2e_prescription_success_path(
    client, 
    customer_token, 
    pharmacist_token,
    test_customer, 
    sample_product_rx, 
    db_session, 
    mock_redis,
    mock_storage_service
):
    user_id = test_customer.id
    product_id = str(sample_product_rx.id)

    # STOCK PREPARATION
    batch = InventoryBatch(
        product_id=sample_product_rx.id,
        batch_number="RX-HAPPY-BATCH",
        initial_quantity=50,
        current_quantity=50,
        price=Decimal("200.00"),
        expiry_date=datetime.now(timezone.utc) + timedelta(days=365)
    )
    db_session.add(batch)
    await db_session.commit()

    # CART PREPARATION
    cart_data = {"items": [{"product_id": product_id, "quantity": 1}]}
    await mock_redis.set(f"cart:{user_id}", json.dumps(cart_data))

    # CHECKOUT
    checkout_resp = await client.post("/api/v1/cart/checkout", headers=customer_token)
    assert checkout_resp.status_code == 200
    order_id = checkout_resp.json()["order_id"]
    
    # Verify order is waiting for prescription
    order_in_db = await db_session.get(Order, uuid.UUID(order_id))
    assert order_in_db.status == OrderStatus.AWAITING_PRESCRIPTION

    # CUSTOMER UPLOADS VALID PRESCRIPTION
    file_content = b"%PDF-1.4 Valid Prescription Content"
    upload_resp = await client.post(
        f"/api/v1/prescriptions/upload?order_id={order_id}",
        files={"file": ("valid_rx.pdf", file_content, "application/pdf")},
        headers=customer_token
    )
    assert upload_resp.status_code == 200
    prescription_id = upload_resp.json()["id"]

    # PHARMACIST APPROVES PRESCRIPTION
    approve_resp = await client.post(
        f"/api/v1/prescriptions/approve?prescription_id={prescription_id}",
        headers=pharmacist_token
    )
    assert approve_resp.status_code == 200
    
    # Verify transition to READY_FOR_PAYMENT
    await db_session.refresh(order_in_db)
    assert order_in_db.status == OrderStatus.READY_FOR_PAYMENT

    # CREATE PAYMENT INTENT
    # This requires the order to be in READY_FOR_PAYMENT state
    payment_resp = await client.post(f"/api/v1/payments/order/{order_id}", headers=customer_token)
    assert payment_resp.status_code == 200
    pi_id = order_in_db.payment_intent_id

    # SIMULATE SUCCESSFUL STRIPE WEBHOOK
    event_id = f"evt_{uuid.uuid4().hex}"
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
