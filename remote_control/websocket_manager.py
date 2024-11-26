from typing import Dict, Set, Optional
from fastapi import WebSocket
import asyncio
import logging
from datetime import datetime
from prometheus_client import Counter, Gauge
from config import WS_HEARTBEAT_INTERVAL, WS_TIMEOUT

logger = logging.getLogger(__name__)

# Metrics
ws_connections_gauge = Gauge('ws_connections_current', 'Current WebSocket connections')
ws_messages_total = Counter('ws_messages_total', 'Total WebSocket messages', ['direction'])
ws_errors_total = Counter('ws_errors_total', 'Total WebSocket errors', ['type'])

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.client_last_heartbeat: Dict[str, datetime] = {}
        self.control_connections: Set[WebSocket] = set()
        self._cleanup_task: Optional[asyncio.Task] = None

    async def connect(self, client_id: str, websocket: WebSocket):
        """Yeni bir WebSocket bağlantısı ekler"""
        try:
            await websocket.accept()
            self.active_connections[client_id] = websocket
            self.client_last_heartbeat[client_id] = datetime.utcnow()
            ws_connections_gauge.inc()
            logger.info(f"New connection established: {client_id}")
            
            if not self._cleanup_task or self._cleanup_task.done():
                self._cleanup_task = asyncio.create_task(self._cleanup_inactive_connections())
                
        except Exception as e:
            ws_errors_total.labels(type="connection_error").inc()
            logger.error(f"Connection error for {client_id}: {str(e)}")
            raise

    async def disconnect(self, client_id: str):
        """Bir WebSocket bağlantısını kapatır"""
        try:
            if client_id in self.active_connections:
                await self.active_connections[client_id].close()
                del self.active_connections[client_id]
                del self.client_last_heartbeat[client_id]
                ws_connections_gauge.dec()
                logger.info(f"Connection closed: {client_id}")
        except Exception as e:
            ws_errors_total.labels(type="disconnection_error").inc()
            logger.error(f"Disconnection error for {client_id}: {str(e)}")

    async def send_message(self, client_id: str, message: dict):
        """Belirli bir istemciye mesaj gönderir"""
        try:
            if client_id in self.active_connections:
                await self.active_connections[client_id].send_json(message)
                ws_messages_total.labels(direction="outbound").inc()
                logger.debug(f"Message sent to {client_id}: {message}")
        except Exception as e:
            ws_errors_total.labels(type="send_error").inc()
            logger.error(f"Error sending message to {client_id}: {str(e)}")
            await self.disconnect(client_id)

    async def broadcast(self, message: dict, exclude: Optional[str] = None):
        """Tüm bağlı istemcilere mesaj yayınlar"""
        disconnected_clients = []
        for client_id, connection in self.active_connections.items():
            if client_id != exclude:
                try:
                    await connection.send_json(message)
                    ws_messages_total.labels(direction="broadcast").inc()
                except Exception as e:
                    ws_errors_total.labels(type="broadcast_error").inc()
                    logger.error(f"Broadcast error for {client_id}: {str(e)}")
                    disconnected_clients.append(client_id)

        # Bağlantısı kopan istemcileri temizle
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

    async def update_heartbeat(self, client_id: str):
        """İstemci heartbeat zamanını günceller"""
        self.client_last_heartbeat[client_id] = datetime.utcnow()

    async def _cleanup_inactive_connections(self):
        """Aktif olmayan bağlantıları temizler"""
        while True:
            try:
                current_time = datetime.utcnow()
                disconnected_clients = []

                for client_id, last_heartbeat in self.client_last_heartbeat.items():
                    if (current_time - last_heartbeat).total_seconds() > WS_TIMEOUT:
                        disconnected_clients.append(client_id)
                        logger.warning(f"Client {client_id} timed out")

                for client_id in disconnected_clients:
                    await self.disconnect(client_id)

                await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
            except Exception as e:
                ws_errors_total.labels(type="cleanup_error").inc()
                logger.error(f"Error in cleanup task: {str(e)}")
                await asyncio.sleep(5)  # Hata durumunda kısa bir bekleme

    def get_connection(self, client_id: str) -> Optional[WebSocket]:
        """Belirli bir istemci ID'si için WebSocket bağlantısını döndürür"""
        return self.active_connections.get(client_id)

    def is_connected(self, client_id: str) -> bool:
        """İstemcinin bağlı olup olmadığını kontrol eder"""
        return client_id in self.active_connections
