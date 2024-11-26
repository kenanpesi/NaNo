@echo off
echo Gerekli paketler yukleniyor...
pip install -r requirements.txt
python -m pip install pyinstaller

echo EXE olusturuluyor...
python -m PyInstaller --onefile --noconsole client.py
copy /Y "dist\client.exe" "remote_client.exe"
echo Executable olusturuldu: remote_client.exe

echo Kurulum tamamlandi!
echo EXE dosyasi: remote_client.exe
pause
