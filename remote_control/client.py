import asyncio
import json
import base64
import pyautogui
import websockets
from pynput import mouse, keyboard
import io
from PIL import Image
import time
import logging
import jwt
from config import *

# Logging ayarları
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class RemoteClient:
    def __init__(self, server_url):
        self.server_url = self._normalize_url(server_url)
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()
        self.token = None
        self.screen_quality = SCREEN_QUALITY
        self.screen_scale = SCREEN_SCALE
        self.update_interval = SCREEN_UPDATE_INTERVAL
        self.last_screen = None
        self.last_screen_time = 0
        
    def _normalize_url(self, url):
        """URL'yi normalize et"""
        url = url.rstrip('/')
        if url.startswith('http://'):
            url = url[7:]
        elif url.startswith('https://'):
            url = url[8:]
        return f"ws://{url}/ws/client"
        
    async def capture_screen(self):
        """Optimize edilmiş ekran görüntüsü yakalama"""
        try:
            current_time = time.time()
            if self.last_screen and current_time - self.last_screen_time < self.update_interval:
                return self.last_screen
                
            screenshot = pyautogui.screenshot()
            
            # Görüntüyü yeniden boyutlandır
            if self.screen_scale != 1.0:
                new_size = (
                    int(screenshot.width * self.screen_scale),
                    int(screenshot.height * self.screen_scale)
                )
                screenshot = screenshot.resize(new_size, Image.LANCZOS)
            
            img_byte_arr = io.BytesIO()
            screenshot.save(img_byte_arr, format='JPEG', 
                          quality=self.screen_quality, 
                          optimize=True)
            img_byte_arr = img_byte_arr.getvalue()
            
            encoded_image = base64.b64encode(img_byte_arr).decode()
            self.last_screen = encoded_image
            self.last_screen_time = current_time
            
            return encoded_image
        except Exception as e:
            logger.error(f"Ekran görüntüsü alınırken hata: {str(e)}")
            return None

    async def handle_command(self, command_data):
        """Komut işleme"""
        try:
            cmd = json.loads(command_data)
            cmd_type = cmd.get('type')
            
            if cmd_type == 'mouse_move':
                screen_width, screen_height = pyautogui.size()
                x = int(cmd['x'] * screen_width)
                y = int(cmd['y'] * screen_height)
                self.mouse_controller.position = (x, y)
            elif cmd_type == 'mouse_click':
                screen_width, screen_height = pyautogui.size()
                x = int(cmd['x'] * screen_width)
                y = int(cmd['y'] * screen_height)
                self.mouse_controller.position = (x, y)
                self.mouse_controller.click(mouse.Button.left)
            elif cmd_type == 'key_press':
                with self.keyboard_controller.pressed(cmd['key']):
                    pass
            elif cmd_type == 'config':
                if 'screen_quality' in cmd:
                    self.screen_quality = max(1, min(100, int(cmd['screen_quality'])))
                if 'screen_scale' in cmd:
                    self.screen_scale = max(0.1, min(1.0, float(cmd['screen_scale'])))
                if 'update_interval' in cmd:
                    self.update_interval = max(0.1, float(cmd['update_interval']))
        except json.JSONDecodeError:
            logger.error("Geçersiz komut formatı")
        except Exception as e:
            logger.error(f"Komut işlenirken hata: {str(e)}")

    async def heartbeat(self, websocket):
        """Heartbeat gönderme"""
        while True:
            try:
                await websocket.send("ping")
                await asyncio.sleep(WS_HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Heartbeat hatası: {str(e)}")
                break

    async def connect(self):
        """Sunucuya bağlan ve iletişimi yönet"""
        reconnect_delay = 1
        
        while True:
            try:
                async with websockets.connect(self.server_url) as websocket:
                    logger.info("Sunucuya bağlandı!")
                    
                    # Token al
                    auth_response = await websocket.recv()
                    auth_data = json.loads(auth_response)
                    if auth_data.get('type') == 'auth':
                        self.token = auth_data.get('token')
                        logger.info("Kimlik doğrulama başarılı")
                    
                    # Heartbeat başlat
                    heartbeat_task = asyncio.create_task(self.heartbeat(websocket))
                    
                    while True:
                        try:
                            # Ekran görüntüsü al ve gönder
                            screen_data = await self.capture_screen()
                            if screen_data:
                                await websocket.send(json.dumps({
                                    'type': 'screen',
                                    'data': screen_data
                                }))
                            
                            # Komutları al ve işle
                            try:
                                command = await asyncio.wait_for(websocket.recv(), timeout=0.1)
                                await self.handle_command(command)
                            except asyncio.TimeoutError:
                                pass
                            except Exception as e:
                                logger.error(f"Komut alınırken hata: {str(e)}")
                            
                            await asyncio.sleep(self.update_interval)
                            
                        except Exception as e:
                            logger.error(f"İletişim döngüsünde hata: {str(e)}")
                            break
                    
                    heartbeat_task.cancel()
                    
            except Exception as e:
                logger.error(f"Bağlantı hatası: {str(e)}")
                await asyncio.sleep(reconnect_delay)
                reconnect_delay = min(reconnect_delay * 2, 60)  # Maksimum 60 saniye
            else:
                reconnect_delay = 1  # Başarılı bağlantıda sıfırla

async def start_client(server_url):
    print(f"Sunucuya bağlanılıyor: {server_url}")
    try:
        async with websockets.connect(f"ws://{server_url}/ws/client") as websocket:
            print("WebSocket bağlantısı başarılı!")
            client = RemoteClient(server_url)
            await client.connect()
    except Exception as e:
        logger.error(f"Bağlantı hatası: {str(e)}")
        input("Devam etmek için bir tuşa basın...")

if __name__ == "__main__":
    import sys
    
    # Komut satırı argümanı yoksa varsayılan olarak localhost'u kullan
    server_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    asyncio.get_event_loop().run_until_complete(start_client(server_url))

    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        print("\nProgram kapatılıyor...")
    except Exception as e:
        logger.error(f"Hata: {e}")
        input("Devam etmek için bir tuşa basın...")
