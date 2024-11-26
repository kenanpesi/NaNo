from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import json
import uuid
import logging
import os
from typing import Dict

# Logging ayarları
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

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

@app.get("/")
async def root():
    logger.info("Root endpoint called")
    return {"message": "Server is running"}

@app.get("/control", response_class=HTMLResponse)
async def get_control_panel(request: Request):
    logger.info("Control panel endpoint called")
    try:
        return templates.TemplateResponse("control_panel.html", {
            "request": request,
            "clients": list(connected_clients.keys())
        })
    except Exception as e:
        logger.error(f"Error rendering control panel: {str(e)}")
        return HTMLResponse(content="<h1>Error loading control panel</h1><p>Please check server logs.</p>")

@app.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    connected_clients[client_id] = websocket
    logger.info(f"New client connected: {client_id}")
    
    try:
        for panel in control_panels.values():
            await panel.send_json({
                "type": "client_connected",
                "client_id": client_id
            })
        
        while True:
            try:
                data = await websocket.receive_text()
                for panel in control_panels.values():
                    await panel.send_text(data)
            except Exception as e:
                logger.error(f"Error in client websocket loop: {str(e)}")
                break
                
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {client_id}")
        del connected_clients[client_id]
        for panel in control_panels.values():
            await panel.send_json({
                "type": "client_disconnected",
                "client_id": client_id
            })

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

# Debug bilgisi
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting server on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
