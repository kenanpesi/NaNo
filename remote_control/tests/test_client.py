import pytest
from unittest.mock import Mock, patch
from client import RemoteClient
import websockets
import json

@pytest.fixture
def mock_websocket():
    """Mock WebSocket bağlantısı oluşturur"""
    return Mock()

@pytest.fixture
def remote_client():
    """Test için RemoteClient örneği oluşturur"""
    return RemoteClient("ws://localhost:8000")

@patch('websockets.connect')
async def test_client_connection(mock_connect, remote_client, mock_websocket):
    """İstemci bağlantı testi"""
    mock_connect.return_value = mock_websocket
    
    await remote_client.connect()
    assert remote_client.connected is True
    mock_connect.assert_called_once()

@patch('websockets.connect')
async def test_client_send_message(mock_connect, remote_client, mock_websocket):
    """Mesaj gönderme testi"""
    mock_connect.return_value = mock_websocket
    test_message = {"type": "test", "data": "test_data"}
    
    await remote_client.connect()
    await remote_client.send_message(test_message)
    
    mock_websocket.send.assert_called_with(json.dumps(test_message))

@patch('websockets.connect')
async def test_client_receive_message(mock_connect, remote_client, mock_websocket):
    """Mesaj alma testi"""
    mock_connect.return_value = mock_websocket
    test_message = json.dumps({"type": "test", "data": "test_data"})
    mock_websocket.recv.return_value = test_message
    
    await remote_client.connect()
    message = await remote_client.receive_message()
    
    assert message == json.loads(test_message)
    mock_websocket.recv.assert_called_once()

@patch('websockets.connect')
async def test_client_disconnect(mock_connect, remote_client, mock_websocket):
    """Bağlantı kesme testi"""
    mock_connect.return_value = mock_websocket
    
    await remote_client.connect()
    await remote_client.disconnect()
    
    assert remote_client.connected is False
    mock_websocket.close.assert_called_once()

@patch('websockets.connect')
async def test_client_reconnect(mock_connect, remote_client, mock_websocket):
    """Yeniden bağlanma testi"""
    mock_connect.return_value = mock_websocket
    
    await remote_client.connect()
    await remote_client.disconnect()
    await remote_client.connect()
    
    assert remote_client.connected is True
    assert mock_connect.call_count == 2
