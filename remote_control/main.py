from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import json
import uuid
import logging
import os
from typing import Dict
from datetime import datetime, timedelta
import asyncio
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time
from collections import defaultdict
import jwt
import ssl
from config import *

# Logging ayarları
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Metrics
ws_connections = Counter('ws_connections_total', 'Total WebSocket connections')
ws_messages = Counter('ws_messages_total', 'Total WebSocket messages')
message_processing_time = Histogram('message_processing_seconds', 'Time spent processing messages')

# Güvenlik metriklerini ekleme
security_events = Counter('security_events_total', 'Total security events', ['event_type'])
failed_auth_attempts = Counter('failed_auth_attempts_total', 'Total failed authentication attempts')
active_sessions = Counter('active_sessions_total', 'Total active sessions')

# Rate limiting için bellek içi sayaç
rate_limit_counters = defaultdict(lambda: {"count": 0, "reset_time": 0})
RATE_LIMIT_REQUESTS = 100  # Maximum requests per window
RATE_LIMIT_WINDOW = 60  # Window in seconds

app = FastAPI(title="Remote Control Server", version="1.0.0")
security = HTTPBearer()

# CORS ve güvenli host ayarları
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Prodüksiyonda spesifik hostları belirtin
)

# IP kısıtlama middleware
@app.middleware("http")
async def ip_restriction(request: Request, call_next):
    client_ip = request.client.host
    if ALLOWED_IPS and client_ip not in ALLOWED_IPS:
        raise HTTPException(status_code=403, detail="IP address not allowed")
    return await call_next(request)

# Güvenlik middleware
@app.middleware("http")
async def security_middleware(request: Request, call_next):
    client_ip = request.client.host
    
    # IP bazlı güvenlik kontrolü
    if client_ip in BLOCKED_IPS:
        logger.warning(f"Blocked IP attempt: {client_ip}")
        security_events.labels(event_type="blocked_ip").inc()
        raise HTTPException(status_code=403, detail="IP address blocked")
    
    # Rate limiting kontrolü
    current_time = time.time()
    if rate_limit_counters[client_ip]["count"] >= RATE_LIMIT_REQUESTS:
        if current_time < rate_limit_counters[client_ip]["reset_time"]:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            security_events.labels(event_type="rate_limit_exceeded").inc()
            raise HTTPException(status_code=429, detail="Too many requests")
    
    response = await call_next(request)
    return response

# Rate limiting middleware
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host
    current_time = time.time()
    
    # Sayacı sıfırla
    if rate_limit_counters[client_ip]["reset_time"] < current_time:
        rate_limit_counters[client_ip] = {
            "count": 1,
            "reset_time": current_time + RATE_LIMIT_WINDOW
        }
    else:
        rate_limit_counters[client_ip]["count"] += 1
        
    if rate_limit_counters[client_ip]["count"] >= RATE_LIMIT_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests")
    
    response = await call_next(request)
    return response

# JWT token oluşturma
def create_jwt_token(client_id: str) -> str:
    expiration = datetime.utcnow() + timedelta(hours=24)
    return jwt.encode(
        {"client_id": client_id, "exp": expiration},
        SECRET_KEY,
        algorithm="HS256"
    )

# JWT token doğrulama
async def verify_jwt_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=403, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid token")

# Templates dizininin varlığını kontrol et
templates_dir = os.path.join(os.path.dirname(__file__), "templates")
if not os.path.exists(templates_dir):
    logger.error(f"Templates directory not found: {templates_dir}")
    os.makedirs(templates_dir, exist_ok=True)
    logger.info(f"Created templates directory: {templates_dir}")

templates = Jinja2Templates(directory="templates")

# Static dizininin varlığını kontrol et
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    logger.error(f"Static directory not found: {static_dir}")
    os.makedirs(static_dir, exist_ok=True)
    logger.info(f"Created static directory: {static_dir}")

app.mount("/static", StaticFiles(directory="static"), name="static")

# Bağlı bilgisayarları tutacak sözlük
connected_clients: Dict[str, WebSocket] = {}
# Kontrol paneli bağlantılarını tutacak liste
control_panels: Dict[str, WebSocket] = {}
# Yeniden bağlanma denemesi için maksimum sayı
MAX_RECONNECT_ATTEMPTS = 3
# Yeniden bağlanma bekleme süresi (saniye)
RECONNECT_WAIT_TIME = 5

async def notify_control_panels(message: dict):
    """Tüm kontrol panellerine mesaj gönder"""
    disconnected_panels = []
    for panel_id, panel in control_panels.items():
        try:
            await panel.send_json(message)
        except WebSocketDisconnect:
            disconnected_panels.append(panel_id)
        except Exception as e:
            logger.error(f"Error sending message to panel {panel_id}: {str(e)}")
            disconnected_panels.append(panel_id)
    
    # Bağlantısı kopan panelleri temizle
    for panel_id in disconnected_panels:
        del control_panels[panel_id]

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Server is running"}

@app.get("/control", response_class=HTMLResponse)
async def get_control_panel(request: Request, token: dict = Depends(verify_jwt_token)):
    logger.info("Control panel endpoint called")
    try:
        return templates.TemplateResponse("control_panel.html", {
            "request": request,
            "clients": list(connected_clients.keys())
        })
    except Exception as e:
        logger.error(f"Error rendering control panel: {str(e)}")
        return HTMLResponse(content="<h1>Error loading control panel</h1><p>Please check server logs.</p>")

@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    token = create_jwt_token(client_id)
    ws_connections.inc()
    
    try:
        await websocket.send_json({"type": "auth", "token": token})
        connected_clients[client_id] = websocket
        logger.info(f"New client connected: {client_id}")
        
        await notify_control_panels({
            "type": "client_connected",
            "client_id": client_id
        })
        
        last_heartbeat = datetime.now()
        
        while True:
            try:
                with message_processing_time.time():
                    data = await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=WS_HEARTBEAT_TIMEOUT
                    )
                    ws_messages.inc()
                    
                    if data == "ping":
                        await websocket.send_text("pong")
                        last_heartbeat = datetime.now()
                        continue
                        
                    if (datetime.now() - last_heartbeat).seconds > WS_HEARTBEAT_TIMEOUT:
                        logger.warning(f"Client {client_id} heartbeat timeout")
                        break
                    
                    await notify_control_panels({
                        "type": "client_data",
                        "client_id": client_id,
                        "data": data
                    })
                    
            except asyncio.TimeoutError:
                if (datetime.now() - last_heartbeat).seconds > WS_HEARTBEAT_TIMEOUT:
                    logger.warning(f"Client {client_id} heartbeat timeout")
                    break
            except Exception as e:
                logger.error(f"Error in client websocket loop: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"Unexpected error in client websocket: {str(e)}")
    finally:
        if client_id in connected_clients:
            del connected_clients[client_id]
            await notify_control_panels({
                "type": "client_disconnected",
                "client_id": client_id
            })
            ws_connections.dec()

@app.websocket("/ws/control")
async def control_websocket(websocket: WebSocket):
    await websocket.accept()
    control_id = str(uuid.uuid4())
    control_panels[control_id] = websocket
    logger.info(f"New control panel connected: {control_id}")
    
    try:
        while True:
            try:
                data = await websocket.receive_text()
                command = json.loads(data)
                client_id = command.get("client_id")
                logger.info(f"Received command for client {client_id}: {command}")
                
                if client_id and client_id in connected_clients:
                    await connected_clients[client_id].send_text(json.dumps(command))
                else:
                    logger.warning(f"Client {client_id} not found")
            except Exception as e:
                logger.error(f"Error in control websocket loop: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Control panel disconnected: {control_id}")
        del control_panels[control_id]

if __name__ == "__main__":
    import uvicorn
    
    # SSL/TLS sertifikalarını kontrol et
    ssl_context = None
    if os.path.exists("cert.pem") and os.path.exists("key.pem"):
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain("cert.pem", "key.pem")
        logger.info("SSL/TLS sertifikaları yüklendi")
    
    # Sunucuyu başlat
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Sunucu başlatılıyor: {SERVER_HOST}:{port}")
    
    if ssl_context:
        uvicorn.run(
            app,
            host=SERVER_HOST,
            port=port,
            ssl_keyfile="key.pem",
            ssl_certfile="cert.pem"
        )
    else:
        logger.warning("SSL/TLS sertifikaları bulunamadı, güvensiz modda başlatılıyor")
        uvicorn.run(app, host=SERVER_HOST, port=port)
