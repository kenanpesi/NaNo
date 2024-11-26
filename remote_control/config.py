import os
from dotenv import load_dotenv
from typing import Set, Optional

# .env dosyasını yükle
load_dotenv()

# Sunucu ayarları
SERVER_HOST = os.getenv('SERVER_HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8000'))
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Güvenlik ayarları
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set!")

# IP güvenliği
ALLOWED_IPS: Set[str] = set(os.getenv('ALLOWED_IPS', '').split(',')) if os.getenv('ALLOWED_IPS') else set()
BLOCKED_IPS: Set[str] = set(os.getenv('BLOCKED_IPS', '').split(',')) if os.getenv('BLOCKED_IPS') else set()

# Rate limiting
MAX_CONNECTIONS_PER_IP = int(os.getenv('MAX_CONNECTIONS_PER_IP', '3'))
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
RATE_LIMIT_WINDOW = int(os.getenv('RATE_LIMIT_WINDOW', '60'))

# SSL/TLS ayarları
SSL_CERT_FILE: Optional[str] = os.getenv('SSL_CERT_FILE')
SSL_KEY_FILE: Optional[str] = os.getenv('SSL_KEY_FILE')
SSL_ENABLED = bool(SSL_CERT_FILE and SSL_KEY_FILE)

# İstemci ayarları
SCREEN_QUALITY = int(os.getenv('SCREEN_QUALITY', '70'))
SCREEN_SCALE = float(os.getenv('SCREEN_SCALE', '0.75'))
SCREEN_UPDATE_INTERVAL = float(os.getenv('SCREEN_UPDATE_INTERVAL', '0.1'))

# JWT ayarları
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 30

# Logging ayarları
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FILE = os.getenv('LOG_FILE', 'remote_control.log')

# WebSocket ayarları
WS_HEARTBEAT_INTERVAL = 30  # saniye
WS_TIMEOUT = 60  # saniye

# Metrics ayarları
ENABLE_METRICS = os.getenv('ENABLE_METRICS', 'True').lower() == 'true'
METRICS_PORT = int(os.getenv('METRICS_PORT', '9090'))
