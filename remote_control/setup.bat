@echo off
echo Remote Control Client Kurulumu
echo ----------------------------

if not exist "remote_client.exe" (
    echo remote_client.exe bulunamadi!
    echo Lutfen once build_exe.bat dosyasini calistirin.
    pause
    exit /b
)

set /p server_url="Railway URL'sini girin: "
start remote_client.exe %server_url%

echo.
echo %server_url% adresine baglaniliyor...
echo.
pause
