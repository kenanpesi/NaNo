@echo off
echo Remote Control Client Kurulumu
echo ----------------------------

set /p server_url="Railway URL'sini girin: "

echo.
echo %server_url% adresine baglaniliyor...
echo.

start "" "dist\remote_client.exe" "%server_url%"
echo Uygulama baslatildi!
pause
