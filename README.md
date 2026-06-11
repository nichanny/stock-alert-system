# Stock Price Alert System

A real-time stock price monitoring system that sends Telegram alerts when stock prices reach target levels.

## Features

- ✅ Real-time stock price monitoring (checks every 1 minute)
- ✅ Telegram alerts when prices reach target levels
- ✅ Web dashboard to manage alerts
- ✅ Add/edit/delete stock alerts
- ✅ View alert history
- ✅ Free deployment on Render
- ✅ Responsive UI

## Architecture

```
┌──────────────────────────────────────┐
│  Render Web Service (Free Tier)      │
├──────────────────────────────────────┤
│                                      │
│  ┌──────────────────────────────┐   │
│  │ Flask Web Dashboard          │   │
│  │ - Manage alerts              │   │
│  │ - View prices                │   │
│  │ - View history               │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │ Python Polling Script        │   │
│  │ - Check prices every 1 min   │   │
│  │ - Send Telegram alerts       │   │
│  └──────────────────────────────┘   │
└──────────────────────────────────────┘
         ↓
    Finnhub API (Free)
         ↓
    Stock Prices
         ↓
    Telegram Bot API
         ↓
    Your Telegram Chat
```

## Prerequisites

- Python 3.9+
- Finnhub API key (free: https://finnhub.io/)
- Telegram Bot Token (create via @BotFather)
- Telegram Chat ID (get from bot)
- Git account
- Render account (free: https://render.com/)

## Setup

### 1. Clone or Create Repository

```bash
git clone <your-repo-url>
cd stock_alert_system
```

### 2. Create Environment File

```bash
cp .env.example .env
```

Edit `.env` and add your credentials:
```
FINNHUB_API_KEY=your_finnhub_api_key
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
FLASK_SECRET_KEY=your_secret_key
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Run Locally

**Terminal 1 - Web Dashboard:**
```bash
python app.py
```
Visit: http://localhost:5000

**Terminal 2 - Stock Monitor:**
```bash
python stock_alert_monitor.py
```

## Deployment on Render

### 1. Create GitHub Repository

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <your-github-repo-url>
git push -u origin main
```

### 2. Deploy on Render

1. Go to https://render.com/
2. Sign up/Login
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: stock-alert-dashboard
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: Free
6. Add Environment Variables:
   - `FINNHUB_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `FLASK_SECRET_KEY`
7. Click "Create Web Service"

### 3. Deploy Background Worker

1. Click "New +" → "Background Worker"
2. Connect same GitHub repository
3. Configure:
   - **Name**: stock-alert-monitor
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python stock_alert_monitor.py`
   - **Plan**: Free
4. Add same Environment Variables
5. Click "Create Background Worker"

## Usage

### Web Dashboard

1. Open: https://your-render-url.onrender.com/
2. **Add Alert**: Click "Add New Alert"
   - Enter stock symbol (e.g., AAPL)
   - Enter buy price target
   - Click "Save"
3. **Edit Alert**: Click "Edit" button
4. **Delete Alert**: Click "Delete" button
5. **View History**: Check "Recent Alerts" section

### Telegram Alerts

When a stock price reaches your target level, you'll receive a Telegram message:

```
🔔 Stock Alert

AAPL ลดลงถึง $150.00
ราคาเป้าหมาย: $150.00
เวลา: 2024-01-15 14:30:00

✅ ซื้อได้แล้ว!
```

## Stock List (Default)

| Symbol | Buy Price |
|--------|-----------|
| RKLB | 100 |
| CEG | 220 |
| PLTR | 126 |
| ETN | 363 |
| AMZN | 215 |
| INTC | 90 |
| TSM | 380 |
| ASTS | 70 |
| MSFT | 380 |
| META | 540 |
| V | 300 |

You can edit these in the web dashboard.

## API Endpoints

### Get All Alerts
```
GET /api/alerts
```

### Add New Alert
```
POST /api/alerts
Content-Type: application/json

{
  "symbol": "AAPL",
  "company_name": "Apple Inc.",
  "buy_price": 150.00
}
```

### Update Alert
```
PUT /api/alerts/{symbol}
Content-Type: application/json

{
  "buy_price": 150.00,
  "active": true
}
```

### Delete Alert
```
DELETE /api/alerts/{symbol}
```

### Get Stock Price
```
GET /api/price/{symbol}
```

### Get Alert History
```
GET /api/history
```

### Health Check
```
GET /health
```

## Configuration

Edit `stock_alerts.json` to manage alerts:

```json
{
  "alerts": [
    {
      "symbol": "AAPL",
      "company_name": "Apple Inc.",
      "buy_price": 150.0,
      "created_date": "2024-01-15",
      "active": true
    }
  ],
  "alert_history": []
}
```

## Logs

- **Web Dashboard**: Logs to console
- **Stock Monitor**: Logs to `stock_alerts.log` and console

## Troubleshooting

### No alerts received
1. Check Telegram bot token is correct
2. Check chat ID is correct
3. Check Finnhub API key is valid
4. Check stock symbol is correct (uppercase)
5. Check stock price is actually below target

### Price not updating
1. Check Finnhub API rate limit (60 calls/min)
2. Check internet connection
3. Check API key is valid
4. Check stock symbol exists

### Dashboard not loading
1. Check Render deployment status
2. Check environment variables are set
3. Check logs in Render dashboard

## Limitations

- **Finnhub Free Tier**: 60 API calls per minute
- **Render Free Tier**: 
  - Web service: 0.5 CPU, 512 MB RAM
  - Background worker: Limited runtime
  - May sleep after 15 minutes of inactivity
- **Stock Data**: Delayed by 15 minutes (free tier)

## Future Improvements

- [ ] Support for sell signals
- [ ] Multiple alert conditions (price range, percentage change)
- [ ] Email notifications
- [ ] SMS notifications
- [ ] Database integration (PostgreSQL)
- [ ] User authentication
- [ ] Multiple users support
- [ ] Mobile app
- [ ] Advanced charting

## License

MIT

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review logs
3. Check API documentation:
   - Finnhub: https://finnhub.io/docs/api
   - Telegram: https://core.telegram.org/bots/api

## Author

Created with ❤️ for long-term stock investors
