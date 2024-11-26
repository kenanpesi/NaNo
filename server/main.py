from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import json
import uuid
from typing import Dict

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Bağlı bilgisayarları tutacak sözlük
connected_clients: Dict[str, WebSocket] = {}
# Kontrol paneli bağlantılarını tutacak liste
control_panels: Dict[str, WebSocket] = {}

@app.get("/", response_class=HTMLResponse)
async def get_control_panel(request: Request):
    # Bağlı bilgisayarların listesini göster
    return templates.TemplateResponse("control_panel.html", {
        "request": request,
        "clients": list(connected_clients.keys())
    })

@app.websocket("/ws/client")
async def client_websocket(websocket: WebSocket):
    await websocket.accept()
    client_id = str(uuid.uuid4())
    connected_clients[client_id] = websocket
    
    try:
        # Tüm kontrol panellerine yeni bağlantıyı bildir
        for panel in control_panels.values():
            await panel.send_json({
                "type": "client_connected",
                "client_id": client_id
            })
        
        while True:
            data = await websocket.receive_text()
            # Ekran görüntüsünü tüm kontrol panellerine ilet
            for panel in control_panels.values():
                await panel.send_text(data)
                
    except WebSocketDisconnect:
        del connected_clients[client_id]
        # Bağlantı koptuğunu bildir
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
    
    try:
        while True:
            data = await websocket.receive_text()
            command = json.loads(data)
            client_id = command.get("client_id")
            
            if client_id and client_id in connected_clients:
                # Komutu ilgili client'a ilet
                await connected_clients[client_id].send_text(json.dumps(command))
                
    except WebSocketDisconnect:
        del control_panels[control_id]
