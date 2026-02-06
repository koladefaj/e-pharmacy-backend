import uuid

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_add_inventory_batch_success(client, pharmacist_token, sample_product):
    """Test that a verified pharmacist can add a batch to an existing product"""

    product_id = sample_product.id
    payload = {
        "batch_number": f"BATCH-{uuid.uuid4().hex[:6].upper()}",
        "initial_quantity": 100,
        "price": 45.50,
        "expiry_date": "2026-12-31T23:59:59",
    }

    response = await client.post(
        f"/api/v1/pharmacist/{product_id}/batches",
        json=payload,
        headers=pharmacist_token,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "success"
    assert "batch_id" in data["data"]
    assert data["data"]["current_stock"] == 100


@pytest.mark.asyncio
async def test_add_inventory_batch_unauthorized(client, customer_token, sample_product):
    """Test that a regular customer CANNOT add a batch (RBAC check)"""

    product_id = sample_product.id
    payload = {
        "batch_number": "ILLEGAL-BATCH",
        "initial_quantity": 50,
        "price": 10.0,
        "expiry_date": "2026-12-31T23:59:59",
    }

    response = await client.post(
        f"/api/v1/pharmacist/{product_id}/batches", json=payload, headers=customer_token
    )

    # Should be 403 Forbidden because get_current_active_pharmacist checks role
    assert response.status_code == status.HTTP_403_FORBIDDEN
