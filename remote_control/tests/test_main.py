import pytest
from fastapi.testclient import TestClient
from main import app, rate_limit_counters, RATE_LIMIT_REQUESTS, ALLOWED_IPS
import jwt
from datetime import datetime, timedelta
from config import SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES
import asyncio

client = TestClient(app)

@pytest.fixture
def valid_token():
    """Geçerli bir JWT token oluşturur"""
    expiration = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    token = jwt.encode(
        {"client_id": "test-client", "exp": expiration},
        SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )
    return token

def test_root_endpoint():
    """Ana endpoint testi"""
    response = client.get("/")
    assert response.status_code == 200
    assert "message" in response.json()
    assert response.json()["message"] == "Server is running"

def test_control_panel_endpoint(valid_token):
    """Kontrol paneli endpoint testi"""
    headers = {"Authorization": f"Bearer {valid_token}"}
    response = client.get("/control", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")

def test_invalid_token():
    """Geçersiz token testi"""
    headers = {"Authorization": "Bearer invalid-token"}
    response = client.get("/control", headers=headers)
    assert response.status_code == 403  # Geçersiz token için 403 dönmeli

@pytest.mark.asyncio
async def test_rate_limiting():
    """Rate limiting testi"""
    # Reset rate limit counters before test
    rate_limit_counters.clear()
    
    # Send requests until we hit the rate limit
    responses = []
    for _ in range(RATE_LIMIT_REQUESTS + 1):  # One over the limit
        responses.append(client.get("/"))
        await asyncio.sleep(0.01)  # Add small delay between requests
    
    # Check that we got a 429 response
    assert responses[-1].status_code == 429
    assert "Too many requests" in responses[-1].json()["detail"]

@pytest.mark.asyncio
async def test_websocket_connection():
    """WebSocket bağlantı testi"""
    with client.websocket_connect("/ws/client") as websocket:
        # First receive the auth message
        auth_msg = websocket.receive_json()
        assert auth_msg["type"] == "auth"
        assert "token" in auth_msg
        
        # Send ping message
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "pong"

@pytest.mark.asyncio
async def test_metrics():
    """Metrics endpoint testi"""
    # Add test client IP to allowed IPs
    ALLOWED_IPS.add("testclient")
    try:
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers["content-type"]
    finally:
        # Clean up
        ALLOWED_IPS.remove("testclient")
