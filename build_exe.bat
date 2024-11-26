@echo off
echo Gerekli paketler yukleniyor...
pip install -r requirements.txt
python -m pip install pyinstaller

echo EXE olusturuluyor...
python -m PyInstaller --onefile --noconsole --name remote_client client.py

echo Kurulum tamamlandi!
echo EXE dosyasi: dist/remote_client.exe
pause
