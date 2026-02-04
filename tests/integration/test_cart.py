import pytest
from uuid import uuid4
from unittest.mock import AsyncMock
from fastapi import HTTPException

@pytest.mark.asyncio
async def test_add_item_success(client, customer_token, storefront_data, mock_redis):
    """Test adding a valid product to cart."""
    product = storefront_data["otc"]
    product_id = str(product.id)

    payload = {
        "product_id": product_id,
        "quantity": 2
    }

    # Calling the API endpoint (assumes /api/v1/cart/add)
    response = await client.post(
        "/api/v1/cart/add",
        json=payload,
        headers=customer_token
    )

    assert response.status_code == 200
    data = response.json()

    # Access the nested 'cart' key
    cart = data["cart"] 
    assert cart["total_items"] == 2
    assert cart["items"][0]["product_id"] == product_id

@pytest.mark.asyncio
async def test_add_rx_product_no_stock_fails(client, customer_token, storefront_data, mock_redis):
    """Test that adding the Rx product (which has no batch) fails with 400."""
    product = storefront_data["rx"]
    payload = {
        "product_id": str(product.id),
        "quantity": 1
    }

    response = await client.post(
        "/api/v1/cart/add",
        json=payload,
        headers=customer_token
    )

    # This should fail because storefront_data didn't create a batch for p2
    assert response.status_code == 400
    assert "exceeds available stock" in response.json()["detail"]

@pytest.mark.asyncio
async def test_increment_existing_item(client, customer_token, storefront_data, mock_redis):
    """Test that adding the same product twice increments the quantity."""
    product_id = str(storefront_data["otc"].id)
    
    # Add 2 items
    await client.post("/api/v1/cart/add", json={"product_id": product_id, "quantity": 2}, headers=customer_token)
    
    # Add 3 more of the same
    response = await client.post("/api/v1/cart/add", json={"product_id": product_id, "quantity": 3}, headers=customer_token)
    
    assert response.status_code == 200
    data = response.json()
    
    # Total should be 5, and only 1 unique product in the list
    # Access the nested 'cart' key
    cart = data["cart"] 
    assert cart["total_items"] == 5
    assert cart["items"][0]["quantity"] == 5

@pytest.mark.asyncio
async def test_add_item_insufficient_stock(client, customer_token, storefront_data, mock_redis):
    """Test that adding more than available stock fails."""
    product_id = str(storefront_data["otc"].id)
    # If your fixture creates 100 items, try to add 101
    payload = {
        "product_id": product_id,
        "quantity": 101
    }

    response = await client.post(
        "/api/v1/cart/add",
        json=payload,
        headers=customer_token
    )

    assert response.status_code == 400
    assert "exceeds available stock" in response.json()["detail"]

@pytest.mark.asyncio
async def test_removes_product(client, customer_token, storefront_data, mock_redis):
    """Test that updating quantity to 0 removes the item."""
    product_id = str(storefront_data["otc"].id)
    
    # 1. Add first
    await client.post("/api/v1/cart/add", json={"product_id": product_id, "quantity": 5}, headers=customer_token)
    
    # 2. Update to 0
    response = await client.delete(
        f"/api/v1/cart/remove/{product_id}",
        headers=customer_token
    )

    assert response.status_code == 204
    
    get_res = await client.get("/api/v1/cart", headers=customer_token)
    assert get_res.json()["total_items"] == 0

@pytest.mark.asyncio
async def test_clear_cart(client, customer_token, storefront_data, mock_redis):
    """Test clearing the entire cart."""
    product_id = str(storefront_data["otc"].id)
    await client.post("/api/v1/cart/add", json={"product_id": product_id, "quantity": 1}, headers=customer_token)

    response = await client.delete("/api/v1/cart/clear", headers=customer_token)
    
    assert response.status_code == 200 # Or 200 depending on your router