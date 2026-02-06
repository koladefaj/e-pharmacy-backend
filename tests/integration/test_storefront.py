import pytest


@pytest.mark.asyncio
async def test_customer_list_products_filter_by_category(client, storefront_data):
    # Test filtering by 'supplement'
    response = await client.get("/api/v1/customer/store?category=supplement")

    assert response.status_code == 200
    data = response.json()

    # Assertions
    assert len(data) >= 1
    assert data[0]["name"] == "Vitamin C 1000mg"

    # Ensure Amoxicillin (Antibiotic) is NOT in these results
    assert all(item["category"] == "supplement" for item in data)


@pytest.mark.asyncio
async def test_customer_search_products(client, storefront_data):
    # Test search query
    response = await client.get("/api/v1/customer/store?search=Amox")

    assert response.status_code == 200
    assert response.json()[0]["name"] == "Amoxicillin 500mg"
