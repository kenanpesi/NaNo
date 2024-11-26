import asyncio
import json
import base64
import pyautogui
import websockets
from pynput import mouse, keyboard
import io
from PIL import Image
import time

class RemoteClient:
    def __init__(self, server_url):
        self.server_url = server_url
        self.mouse_controller = mouse.Controller()
        self.keyboard_controller = keyboard.Controller()
        
    async def capture_screen(self):
        screenshot = pyautogui.screenshot()
        img_byte_arr = io.BytesIO()
        screenshot.save(img_byte_arr, format='JPEG', quality=50)
        img_byte_arr = img_byte_arr.getvalue()
        return base64.b64encode(img_byte_arr).decode()

    async def handle_command(self, command_data):
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

    async def connect(self):
        while True:
            try:
                async with websockets.connect(f"{self.server_url}/ws/client") as websocket:
                    print("Sunucuya bağlandı!")
                    
                    while True:
                        # Ekran görüntüsü al ve gönder
                        screen_data = await self.capture_screen()
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
                        
                        await asyncio.sleep(0.1)  # CPU kullanımını azaltmak için
                        
            except Exception as e:
                print(f"Bağlantı hatası: {e}")
                await asyncio.sleep(5)  # Yeniden bağlanmadan önce bekle

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Kullanım: python client.py <sunucu_adresi>")
        print("Örnek: python client.py http://your-railway-app.railway.app")
        sys.exit(1)
        
    server_url = sys.argv[1]
    client = RemoteClient(server_url)
    asyncio.get_event_loop().run_until_complete(client.connect())
