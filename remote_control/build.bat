@echo off
pip install -r requirements.txt
pyinstaller --onefile --noconsole remote_client.py
