# 🚀 Stock Price Alert System - Setup Guide

ขั้นตอนการตั้งค่าระบบ Stock Price Alert บน Render (ฟรี 100%)

---

## 📋 ข้อมูลที่คุณเตรียมไว้

✅ **Finnhub API Key**: (ได้แล้ว)
✅ **Telegram Bot Token**: `8560558397:AAF8VNA8WvjNwbZXadbx6lZec0171IScuw4`
✅ **Telegram Chat ID**: `8472135977`

---

## ✅ ขั้นตอนที่ 1: เตรียม GitHub Repository

### 1.1 สร้าง GitHub Repository

1. ไปที่ https://github.com/new
2. ตั้งชื่อ repository: `stock-alert-system`
3. เลือก "Public" (สำคัญ: Render ต้องเข้าถึง)
4. Click "Create repository"

### 1.2 Push Code ไป GitHub

```bash
# ไปที่ project directory
cd /home/ubuntu/stock_alert_system

# Initialize Git
git init
git add .
git commit -m "Initial commit: Stock Price Alert System"

# Add remote repository
git remote add origin https://github.com/YOUR_USERNAME/stock-alert-system.git

# Push to GitHub
git branch -M main
git push -u origin main
```

---

## ✅ ขั้นตอนที่ 2: Deploy Web Dashboard บน Render

### 2.1 สร้าง Web Service

1. ไปที่ https://render.com/
2. Login/Sign up
3. Click "New +" → "Web Service"
4. Click "Connect" ถัดจาก GitHub repository ของคุณ
5. เลือก `stock-alert-system` repository
6. ตั้งค่า:
   - **Name**: `stock-alert-dashboard`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free

### 2.2 เพิ่ม Environment Variables

ใน Render dashboard:
1. Click "Environment" tab
2. เพิ่ม variables:

```
FINNHUB_API_KEY = your_finnhub_api_key_here
TELEGRAM_BOT_TOKEN = 8560558397:AAF8VNA8WvjNwbZXadbx6lZec0171IScuw4
TELEGRAM_CHAT_ID = 8472135977
FLASK_SECRET_KEY = (ให้ Render generate)
POLLING_INTERVAL = 60
```

3. Click "Create Web Service"

### 2.3 รอให้ Deploy เสร็จ

- ตรวจสอบ Logs
- เมื่อเห็น "Service is live" → Deploy สำเร็จ ✅
- Copy URL: `https://stock-alert-dashboard-xxxx.onrender.com`

---

## ✅ ขั้นตอนที่ 3: Deploy Stock Monitor (Background Worker)

### 3.1 สร้าง Background Worker

1. ใน Render dashboard
2. Click "New +" → "Background Worker"
3. Click "Connect" ถัดจาก GitHub repository
4. เลือก `stock-alert-system` repository
5. ตั้งค่า:
   - **Name**: `stock-alert-monitor`
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python stock_alert_monitor.py`
   - **Plan**: Free

### 3.2 เพิ่ม Environment Variables (เหมือนกับ Web Service)

```
FINNHUB_API_KEY = your_finnhub_api_key_here
TELEGRAM_BOT_TOKEN = 8560558397:AAF8VNA8WvjNwbZXadbx6lZec0171IScuw4
TELEGRAM_CHAT_ID = 8472135977
POLLING_INTERVAL = 60
CHECK_MARKET_HOURS_ONLY = true
```

3. Click "Create Background Worker"

### 3.3 รอให้ Deploy เสร็จ

- ตรวจสอบ Logs
- เมื่อเห็น "Service is live" → Deploy สำเร็จ ✅

---

## ✅ ขั้นตอนที่ 4: ทดสอบระบบ

### 4.1 เข้า Web Dashboard

1. ไปที่ URL ที่ได้จาก Render: `https://stock-alert-dashboard-xxxx.onrender.com`
2. ควรเห็น dashboard ที่สวยงาม
3. ดูรายการหุ้น 11 ตัว

### 4.2 ทดสอบ Add Alert

1. Click "Add New Alert"
2. ใส่:
   - Symbol: `AAPL`
   - Company Name: `Apple Inc.`
   - Buy Price: `150`
3. Click "Save"
4. ควรเห็น AAPL ปรากฏในรายการ

### 4.3 ทดสอบ Telegram Alert

**วิธีทดสอบ**: ตั้ง buy price ต่ำกว่าราคาปัจจุบัน

1. ค้นหา AAPL ราคาปัจจุบัน (เช่น $230)
2. ตั้ง buy price = $200 (ต่ำกว่าปัจจุบัน)
3. รอ 1-2 นาที
4. ควรได้ Telegram alert ใน chat ของคุณ

### 4.4 ทดสอบ Edit & Delete

1. Click "Edit" → เปลี่ยนราคา → "Save"
2. Click "Delete" → ยืนยัน → Alert ลบออก

---

## 📱 ตรวจสอบ Telegram Alerts

### ตรวจสอบว่าได้ Alert ไหม

1. เปิด Telegram
2. ค้นหา "Stock Alert Bot" (bot ที่คุณสร้าง)
3. ดูข้อความ alert

### Format ของ Alert

```
🔔 Stock Alert

AAPL ลดลงถึง $150.00
ราคาเป้าหมาย: $150.00
เวลา: 2024-01-15 14:30:00

✅ ซื้อได้แล้ว!
```

---

## 🔧 Troubleshooting

### ❌ Dashboard ไม่โหลด

**วิธีแก้**:
1. ตรวจสอบ Render logs
2. ตรวจสอบ environment variables ครบไหม
3. รอ 5 นาที (Render free tier อาจช้า)

### ❌ ไม่ได้ Telegram Alert

**วิธีแก้**:
1. ตรวจสอบ Bot Token ถูกไหม
2. ตรวจสอบ Chat ID ถูกไหม
3. ตรวจสอบ Finnhub API Key ถูกไหม
4. ดูที่ Background Worker logs

### ❌ ราคาไม่อัปเดต

**วิธีแก้**:
1. ตรวจสอบ Finnhub API rate limit (60 calls/min)
2. ตรวจสอบ symbol ถูกไหม (ต้องเป็น uppercase)
3. ตรวจสอบ internet connection

### ❌ Background Worker หยุดทำงาน

**วิธีแก้**:
1. Render free tier อาจหยุดหลังจาก 15 นาที inactivity
2. ให้ ping service เพื่อให้ตื่น
3. หรือ upgrade เป็น paid plan

---

## 📊 Monitoring & Logs

### ดู Logs ใน Render

1. ไปที่ Render dashboard
2. เลือก service (Web หรือ Worker)
3. Click "Logs" tab
4. ดูข้อมูล real-time

### Logs ที่ควรเห็น

**Web Service**:
```
INFO:werkzeug: * Running on http://0.0.0.0:5000
```

**Background Worker**:
```
INFO:root:Stock Alert Monitor started
INFO:root:Polling interval: 60 seconds
INFO:root:Monitoring 11 stocks
INFO:root:AAPL: $230.50 (target: $150.00)
```

---

## 🎯 ใช้งาน

### เพิ่ม Alert ใหม่

1. ไปที่ Dashboard
2. Click "Add New Alert"
3. ใส่ Symbol, Company Name, Buy Price
4. Click "Save"

### แก้ไข Alert

1. หา alert ในรายการ
2. Click "Edit"
3. เปลี่ยนราคา
4. Click "Save"

### ลบ Alert

1. หา alert ในรายการ
2. Click "Delete"
3. ยืนยัน

### ดู Alert History

ดูที่ sidebar "Recent Alerts" - แสดง 20 alert ล่าสุด

---

## 💰 ค่าใช้งาน

✅ **ฟรี 100%**

| ส่วนประกอบ | ราคา |
|----------|------|
| Render Web Service | ฟรี (free tier) |
| Render Background Worker | ฟรี (free tier) |
| Finnhub API | ฟรี (60 calls/min) |
| Telegram Bot | ฟรี |
| **รวม** | **ฟรี** ✅ |

---

## ⚠️ ข้อจำกัด (Limitations)

### Render Free Tier
- CPU: 0.5 vCPU
- RAM: 512 MB
- อาจหยุดหลังจาก 15 นาที inactivity
- ไม่มี persistent storage

### Finnhub Free Tier
- Rate limit: 60 calls/min
- Stock data delayed: 15 minutes
- ไม่มี real-time data

### Telegram
- ไม่มี limitation สำหรับ bot messages

---

## 🚀 Next Steps

1. ✅ Deploy บน Render
2. ✅ ทดสอบ Dashboard
3. ✅ ทดสอบ Telegram Alerts
4. ✅ เพิ่ม/แก้ไข alerts ตามต้องการ
5. ✅ Monitor logs

---

## 📞 Support

ถ้ามีปัญหา:
1. ตรวจสอบ logs ใน Render
2. ตรวจสอบ environment variables
3. ตรวจสอบ API keys ถูกไหม
4. อ่าน README.md สำหรับข้อมูลเพิ่มเติม

---

## 🎉 เสร็จแล้ว!

ระบบ Stock Price Alert ของคุณพร้อมใช้งาน! 🎊

- 📊 Dashboard: https://stock-alert-dashboard-xxxx.onrender.com
- 📱 Telegram: ได้รับ alerts ทุกครั้งที่ราคาถึงเป้าหมาย
- ✅ ตรวจสอบราคาทุก 1 นาที
- 🔔 ส่ง Telegram alerts ทันที

Happy investing! 📈
