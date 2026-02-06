import uuid

import pytest
from fastapi import status


@pytest.mark.parametrize(
    "method, endpoint, payload",
    [
        ("post", "/api/v1/payments/refund/{id}", {"amount": 10.0}),
        (
            "post",
            "/api/v1/pharmacist/register",
            {
                "email": "new@pharma.com",
                "full_name": "Pharma",
                "password": "pass",
                "phone_number": "+123",
                "date_of_birth": "1990-01-01",
                "address": "addr",
                "license_number": "LN1",
            },
        ),
        ("get", "/api/v1/pharmacist/all", None),
        ("patch", "/api/v1/pharmacist/{id}/approve", {"license_verified": True}),
        (
            "post",
            "/api/v1/product/create",
            {
                "name": "Drug",
                "slug": "drug",
                "category": "otc",
                "active_ingredients": "X",
                "prescription_required": False,
            },
        ),
        ("delete", "/api/v1/product/inventory/batches/BATCH123", None),
    ],
)
async def test_admin_endpoints_access_denied_for_customers(
    client, customer_token, method, endpoint, payload
):
    """Verify that a CUSTOMER cannot access any admin routes."""
    url = endpoint.format(id=uuid.uuid4())

    # Logic to handle different HTTP methods without passing forbidden arguments
    kwargs = {"headers": customer_token}
    if payload and method not in ["get", "delete"]:
        kwargs["json"] = payload

    func = getattr(client, method)
    response = await func(url, **kwargs)

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json()["detail"] == "Admin access required"
