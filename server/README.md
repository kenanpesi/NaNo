# Uzaktan Masaüstü Kontrol Sunucusu

Bu proje, web üzerinden birden fazla bilgisayarı kontrol etmenizi sağlayan bir kontrol paneli sunar.

## Özellikler

- Birden fazla bilgisayarı aynı anda yönetebilme
- Gerçek zamanlı ekran görüntüsü
- Fare ve klavye kontrolü
- Otomatik bağlantı yönetimi

## Railway Kurulumu

1. Bu projeyi Railway'e yükleyin
2. Railway'in size verdiği URL'i not alın

## İstemci Kurulumu

1. Python'u bilgisayara kurun
2. Gerekli paketleri yükleyin: `pip install -r requirements.txt`
3. İstemciyi çalıştırın: `python client.py http://your-railway-app.railway.app`

## Güvenlik

Bu uygulama güvenlik amacıyla sadece test ortamında kullanılmalıdır. Gerçek ortamda kullanmadan önce:

1. SSL/TLS ekleyin
2. Kullanıcı doğrulaması ekleyin
3. IP kısıtlaması ekleyin
