import pytest
import uuid
from app.db.enums import PrescriptionStatus, OrderStatus

@pytest.mark.asyncio
async def test_upload_prescription_success(client, customer_token, sample_order, mock_storage_service):
    order_id = sample_order.id
    file_content = b"%PDF-1.4 test content"

    response = await client.post(
        f"/api/v1/prescriptions/upload?order_id={order_id}",
        files={"file": ("prescription.pdf", file_content, "application/pdf")},
        headers=customer_token
    )
  
    assert response.status_code == 200
    
    data = response.json()
    
    assert "id" in data
    assert data["status"] == "pending"
    assert data["order_id"] == str(order_id)

@pytest.mark.asyncio
async def test_pharmacist_list_pending(client, pharmacist_token, db_session, test_customer, sample_order):
    """Test pharmacist can see pending prescriptions."""
    from app.models.prescription import Prescription
    presc = Prescription(
        id=uuid.uuid4(),
        user_id=test_customer.id,
        order_id=sample_order.id,
        file_path="prescriptions/test.pdf",
        filename="test.pdf",
        status=PrescriptionStatus.PENDING
    )
    db_session.add(presc)
    await db_session.commit()

    response = await client.get("/api/v1/prescriptions/pending", headers=pharmacist_token)
    
    assert response.status_code == 200
    assert len(response.json()) > 0
    assert response.json()[0]["status"] == "pending"

@pytest.mark.asyncio
async def test_approve_prescription_flow(client, pharmacist_token, db_session, test_customer, sample_order):
    from app.models.prescription import Prescription
    
    # Setup - Prescription matches PrescriptionStatus.PENDING
    presc = Prescription(
        id=uuid.uuid4(),
        user_id=test_customer.id,
        order_id=sample_order.id,
        file_path="prescriptions/test.pdf",
        filename="test.pdf",
        status=PrescriptionStatus.PENDING 
    )
    db_session.add(presc)
    await db_session.commit()

    response = await client.post(
        f"/api/v1/prescriptions/approve?prescription_id={presc.id}",
        headers=pharmacist_token
    )

    assert response.status_code == 200
    await db_session.refresh(sample_order)
    assert sample_order.status == OrderStatus.READY_FOR_PAYMENT


@pytest.mark.asyncio
async def test_reject_prescription_flow(client, pharmacist_token, db_session, test_customer, sample_order):
    """Test rejection flow: Order is cancelled and reason is recorded."""
    from app.models.prescription import Prescription
    presc = Prescription(
        id=uuid.uuid4(),
        user_id=test_customer.id,
        order_id=sample_order.id,
        file_path="prescriptions/test.pdf",
        filename="test.pdf",
        status=PrescriptionStatus.PENDING
    )
    db_session.add(presc)
    await db_session.commit()

    payload = {
        "prescription_id": str(presc.id),
        "reason": "Image is too blurry"
    }

    response = await client.post(
        "/api/v1/prescriptions/reject",
        json=payload,
        headers=pharmacist_token
    )

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert response.json()["rejection_reason"] == "Image is too blurry"

    # Verify Order status
    await db_session.refresh(sample_order)
    assert sample_order.status == OrderStatus.CANCELLED