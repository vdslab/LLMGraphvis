"""
Tests for authentication endpoints.
"""

import pytest
from fastapi import status

def test_register_user_success(client, test_user_data):
    """Test successful user registration."""
    response = client.post("/auth/register", json=test_user_data)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["username"] == test_user_data["username"]
    assert "id" in data
    assert data["is_active"] is True

def test_register_user_duplicate_username(client, test_user, test_user_data):
    """Test registration with duplicate username fails."""
    response = client.post("/auth/register", json=test_user_data)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "already registered" in response.json()["detail"]

def test_register_user_invalid_data(client):
    """Test registration with invalid data."""
    # Missing password
    response = client.post("/auth/register", json={"username": "testuser"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Missing username
    response = client.post("/auth/register", json={"password": "testpass"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Empty strings
    response = client.post("/auth/register", json={"username": "", "password": ""})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_login_success(client, test_user, test_user_data):
    """Test successful login."""
    response = client.post(
        "/auth/token",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_invalid_credentials(client, test_user):
    """Test login with invalid credentials."""
    # Wrong password
    response = client.post(
        "/auth/token",
        data={
            "username": test_user.username,
            "password": "wrongpassword"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    # Non-existent user
    response = client.post(
        "/auth/token",
        data={
            "username": "nonexistent",
            "password": "password"
        }
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_login_missing_data(client):
    """Test login with missing data."""
    # Missing password
    response = client.post("/auth/token", data={"username": "testuser"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    # Missing username
    response = client.post("/auth/token", data={"password": "testpass"})
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

def test_get_current_user_success(client, auth_headers):
    """Test getting current user information."""
    response = client.get("/auth/users/me", headers=auth_headers)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "id" in data
    assert "username" in data
    assert data["is_active"] is True

def test_get_current_user_no_token(client):
    """Test accessing protected endpoint without token."""
    response = client.get("/auth/users/me")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_get_current_user_invalid_token(client):
    """Test accessing protected endpoint with invalid token."""
    headers = {"Authorization": "Bearer invalid_token"}
    response = client.get("/auth/users/me", headers=headers)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_token_format(client, test_user, test_user_data):
    """Test that token format is correct."""
    response = client.post(
        "/auth/token",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"]
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    
    # Token should be a string and have 3 parts separated by dots (JWT format)
    token = data["access_token"]
    assert isinstance(token, str)
    assert len(token.split(".")) == 3

def test_password_hashing(db_session, test_user_data):
    """Test that passwords are properly hashed."""
    import auth
    import models
    
    # Create user
    hashed_password = auth.get_password_hash(test_user_data["password"])
    user = models.User(
        username=test_user_data["username"],
        hashed_password=hashed_password
    )
    db_session.add(user)
    db_session.commit()
    
    # Verify password is hashed (not stored in plain text)
    assert user.hashed_password != test_user_data["password"]
    
    # Verify password verification works
    assert auth.verify_password(test_user_data["password"], user.hashed_password)
    assert not auth.verify_password("wrongpassword", user.hashed_password)