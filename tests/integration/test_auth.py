import uuid

import pytest
from fastapi import status


@pytest.mark.asyncio
async def test_register_customer_success(client):
    """Test the user can register successfully."""
    payload = {
        "full_name": "test user",
        "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
        "phone_number": "+1230000000000",
        "address": "example street 123",
        "date_of_birth": "1999-01-01",
        "password": "strongpassword123",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    if response.status_code == 422:
        print(f"\nVALIDATION ERROR: {response.json()}")

    if response.status_code != 201:
        print(f"Error detail: {response.json()}")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["email"] == payload["email"]
    assert "user" in response.json()
    assert "role" in response.json()


async def test_register_pharmacist_success(client, admin_token):
    """Test if the admin can register a user"""

    payload = {
        "full_name": "testpharmacist",
        "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
        "phone_number": "+12300000000",
        "address": "example street 000",
        "date_of_birth": "2000-02-02",
        "license_number": "zkszks00",
        "license_verified": True,
        "password": "strongpassword000",
    }

    response = await client.post(
        "/api/v1/pharmacist/register", json=payload, headers=admin_token
    )

    if response.status_code == 401:
        print(f"\nVALIDATION ERROR: {response.json()}")

    if response.status_code != 201:
        print(f"Error detail: {response.json()}")

    assert response.status_code == status.HTTP_201_CREATED
    assert payload["email"] in response.text


@pytest.mark.asyncio
async def test_login(client):
    """Test that the registered user can login and get a jwt"""
    # First, register user
    user_data = {
        "full_name": "test user",
        "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
        "phone_number": "+1230000000000",
        "address": "example street 123",
        "date_of_birth": "1999-01-01",
        "password": "strongpassword123",
    }

    await client.post("/api/v1/auth/register", json=user_data)

    # Try login
    login_data = {"email": user_data["email"], "password": user_data["password"]}
    response = await client.post("/api/v1/auth/login", json=login_data)

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh(client):
    """Test that the registered user can login and get a jwt"""
    # First, register user
    user_data = {
        "full_name": "test user",
        "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
        "phone_number": "+1230000000000",
        "address": "example street 123",
        "date_of_birth": "1999-01-01",
        "password": "strongpassword123",
    }

    signup_res = await client.post("/api/v1/auth/register", json=user_data)
    assert signup_res.status_code == 201

    refresh_token = signup_res.json()["refresh_token"]

    # Request access token
    refresh_res = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )

    assert refresh_res.status_code == 200
    assert "access_token" in refresh_res.json()
    assert refresh_res.json()["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_change_password_all_roles(client, customer_token, pharmacist_token):
    # Map tokens to their respective current passwords defined in your fixtures
    password_map = [
        (customer_token, "strongpassword123"),
        (pharmacist_token, "strongpassword123"),
    ]

    for token_header, current_pwd in password_map:
        payload = {"old_password": current_pwd, "new_password": "NewSecurePassword123!"}

        response = await client.post(
            "/api/v1/me/change-password",
            json=payload,
            headers=token_header,  # Explicitly pass as headers
        )

        assert response.status_code == 204
        assert response.content == b""
