#!/usr/bin/env python3
"""
Stock Alert Dashboard + Background Monitor
Web interface for managing stock alerts + real-time Telegram alerts
"""

import os
import json
import requests
import logging
import time
import pytz
from datetime import datetime
from threading import Thread
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', 60))
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'stock-alert-secret-key-2024')

# In-memory storage
_alerts_cache = None
_history_cache = None
_last_alert_prices = {}  # Prevent duplicate alerts

# Default stock list
DEFAULT_ALERTS = [
    {"symbol": "RKLB", "company_name": "Rocket Lab USA Inc.", "buy_price": 100.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "CEG", "company_name": "Constellation Energy Corporation", "buy_price": 220.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "PLTR", "company_name": "Palantir Technologies Inc.", "buy_price": 126.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "ETN", "company_name": "Eaton PLC", "buy_price": 363.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "AMZN", "company_name": "Amazon.com Inc.", "buy_price": 215.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "INTC", "company_name": "Intel Corporation", "buy_price": 90.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "TSM", "company_name": "Taiwan Semiconductor Manufacturing", "buy_price": 380.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "ASTS", "company_name": "AST SpaceMobile Inc.", "buy_price": 70.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "MSFT", "company_name": "Microsoft Corporation", "buy_price": 380.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "META", "company_name": "Meta Platforms Inc.", "buy_price": 540.0, "active": True, "created_date": "2024-01-15"},
    {"symbol": "V", "company_name": "Visa Inc.", "buy_price": 300.0, "active": True, "created_date": "2024-01-15"},
]


# ─── Data Management ──────────────────────────────────────────────────────────

def load_alerts():
    global _alerts_cache, _history_cache
    if _alerts_cache is not None:
        return _alerts_cache, _history_cache

    alerts_data = os.getenv('STOCK_ALERTS_DATA', '')
    if alerts_data:
        try:
            data = json.loads(alerts_data)
            _alerts_cache = data.get('alerts', DEFAULT_ALERTS)
            _history_cache = data.get('alert_history', [])
            logger.info(f"Loaded {len(_alerts_cache)} alerts from environment variable")
            return _alerts_cache, _history_cache
        except Exception as e:
            logger.error(f"Error parsing STOCK_ALERTS_DATA: {e}")

    _alerts_cache = [a.copy() for a in DEFAULT_ALERTS]
    _history_cache = []
    logger.info(f"Using default {len(_alerts_cache)} alerts")
    return _alerts_cache, _history_cache


def save_alerts(alerts, history=None):
    global _alerts_cache, _history_cache
    _alerts_cache = alerts
    if history is not None:
        _history_cache = history
    return True


def add_to_history(history, symbol, price, buy_price, message):
    history.append({
        'symbol': symbol,
        'price': price,
        'buy_price': buy_price,
        'message': message,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    return history[-100:]


# ─── Stock Price ──────────────────────────────────────────────────────────────

def get_stock_price(symbol):
    try:
        params = {'symbol': symbol, 'token': FINNHUB_API_KEY}
        response = requests.get(FINNHUB_QUOTE_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        if 'c' in data and data['c'] > 0:
            return {
                'price': data['c'],
                'high': data.get('h', 0),
                'low': data.get('l', 0),
                'open': data.get('o', 0),
                'previous_close': data.get('pc', 0),
                'change': round(data['c'] - data.get('pc', data['c']), 2),
                'change_pct': round(((data['c'] - data.get('pc', data['c'])) / data.get('pc', data['c'])) * 100, 2) if data.get('pc', 0) > 0 else 0
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching price for {symbol}: {e}")
        return None


# ─── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram_alert(symbol, current_price, buy_price, company_name=""):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram not configured")
            return False

        change_pct = round(((current_price - buy_price) / buy_price) * 100, 2)
        now_thai = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')

        message = (
            f"🔔 *STOCK BUY ALERT*\n\n"
            f"📌 *{symbol}* - {company_name}\n"
            f"💰 ราคาปัจจุบัน: *${current_price:.2f}*\n"
            f"🎯 ราคาเป้าหมาย: ${buy_price:.2f}\n"
            f"📊 ต่ำกว่าเป้า: {abs(change_pct):.1f}%\n"
            f"🕐 เวลา: {now_thai} (TH)\n\n"
            f"✅ *ถึงราคาซื้อแล้ว!*"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            'chat_id': TELEGRAM_CHAT_ID,
            'text': message,
            'parse_mode': 'Markdown'
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Telegram alert sent: {symbol} @ ${current_price:.2f}")
        return True
    except Exception as e:
        logger.error(f"Error sending Telegram alert: {e}")
        return False


# ─── Market Hours ─────────────────────────────────────────────────────────────

def is_market_open():
    try:
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        return market_open <= now <= market_close
    except Exception:
        return True  # Default to True if timezone check fails


# ─── Background Monitor Thread ────────────────────────────────────────────────

def monitor_loop():
    """Background thread: checks prices every POLLING_INTERVAL seconds"""
    global _last_alert_prices
    logger.info(f"🚀 Background monitor started (interval: {POLLING_INTERVAL}s)")

    # Wait for Flask to start
    time.sleep(10)

    while True:
        try:
            if not is_market_open():
                logger.debug("Market closed, skipping check")
                time.sleep(POLLING_INTERVAL)
                continue

            alerts, history = load_alerts()
            logger.info(f"🔍 Checking {len(alerts)} stocks...")

            for alert in alerts:
                if not alert.get('active', True):
                    continue

                symbol = alert['symbol']
                buy_price = alert['buy_price']
                company_name = alert.get('company_name', symbol)

                price_data = get_stock_price(symbol)
                if not price_data:
                    continue

                current_price = price_data['price']
                logger.info(f"  {symbol}: ${current_price:.2f} (target: ${buy_price:.2f})")

                if current_price <= buy_price:
                    last_price = _last_alert_prices.get(symbol)
                    # Only alert if first time or price changed by more than $0.50
                    if last_price is None or abs(current_price - last_price) > 0.50:
                        success = send_telegram_alert(symbol, current_price, buy_price, company_name)
                        if success:
                            _last_alert_prices[symbol] = current_price
                            msg = f"🔔 {symbol} ถึงราคาซื้อ ${current_price:.2f} (เป้า: ${buy_price:.2f})"
                            history = add_to_history(history, symbol, current_price, buy_price, msg)
                            save_alerts(alerts, history)
                else:
                    # Reset last alert price when price goes back above target
                    if symbol in _last_alert_prices:
                        del _last_alert_prices[symbol]

                time.sleep(1)  # Small delay between API calls to avoid rate limit

        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")

        time.sleep(POLLING_INTERVAL)


# ─── Flask Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    alerts, history = load_alerts()
    enriched_alerts = []
    for alert in alerts:
        alert_copy = alert.copy()
        if alert_copy.get('active', True):
            price_data = get_stock_price(alert_copy['symbol'])
            if price_data:
                alert_copy['current_price'] = price_data['price']
                alert_copy['change'] = price_data.get('change', 0)
                alert_copy['change_pct'] = price_data.get('change_pct', 0)
                alert_copy['distance_pct'] = round(((price_data['price'] - alert_copy['buy_price']) / alert_copy['buy_price']) * 100, 1)
                alert_copy['status'] = 'below_target' if price_data['price'] <= alert_copy['buy_price'] else 'above_target'
            else:
                alert_copy['current_price'] = None
                alert_copy['change'] = 0
                alert_copy['change_pct'] = 0
                alert_copy['distance_pct'] = 0
                alert_copy['status'] = 'error'
        enriched_alerts.append(alert_copy)
    now_thai = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
    return render_template('dashboard.html', alerts=enriched_alerts, history=history[-20:], market_open=is_market_open(), now=now_thai)


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    alerts, _ = load_alerts()
    result = []
    for alert in alerts:
        alert_copy = alert.copy()
        price_data = get_stock_price(alert_copy['symbol'])
        if price_data:
            alert_copy['current_price'] = price_data['price']
        result.append(alert_copy)
    return jsonify(result)


@app.route('/api/alerts', methods=['POST'])
def add_alert():
    try:
        data = request.json
        alerts, history = load_alerts()
        symbol = data['symbol'].upper().strip()
        if any(a['symbol'] == symbol for a in alerts):
            return jsonify({'error': 'Symbol already exists'}), 400
        new_alert = {
            'symbol': symbol,
            'company_name': data.get('company_name', symbol),
            'buy_price': float(data['buy_price']),
            'created_date': datetime.now().strftime('%Y-%m-%d'),
            'active': True
        }
        alerts.append(new_alert)
        save_alerts(alerts, history)
        return jsonify(new_alert), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['PUT'])
def update_alert(symbol):
    try:
        data = request.json
        alerts, history = load_alerts()
        for alert in alerts:
            if alert['symbol'] == symbol.upper():
                if 'buy_price' in data:
                    alert['buy_price'] = float(data['buy_price'])
                if 'active' in data:
                    alert['active'] = data['active']
                if 'company_name' in data:
                    alert['company_name'] = data['company_name']
                save_alerts(alerts, history)
                return jsonify(alert), 200
        return jsonify({'error': 'Symbol not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['DELETE'])
def delete_alert(symbol):
    try:
        alerts, history = load_alerts()
        original_count = len(alerts)
        alerts = [a for a in alerts if a['symbol'] != symbol.upper()]
        if len(alerts) == original_count:
            return jsonify({'error': 'Symbol not found'}), 404
        save_alerts(alerts, history)
        return jsonify({'message': f'Alert for {symbol.upper()} deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/price/<symbol>', methods=['GET'])
def get_price(symbol):
    try:
        price_data = get_stock_price(symbol.upper())
        if price_data:
            return jsonify(price_data), 200
        return jsonify({'error': 'Failed to fetch price'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    _, history = load_alerts()
    return jsonify(history[-50:])


@app.route('/api/test-telegram', methods=['POST'])
def test_telegram():
    """Test Telegram connection"""
    try:
        now_thai = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')
        message = (
            f"✅ *Stock Alert System - Test*\n\n"
            f"ระบบ Price Alert ทำงานปกติ\n"
            f"🕐 เวลา: {now_thai} (TH)\n\n"
            f"คุณจะได้รับ alert เมื่อราคาหุ้นถึงเป้าหมาย!"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return jsonify({'success': True, 'message': 'Test message sent to Telegram!'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/market-status', methods=['GET'])
def market_status():
    return jsonify({
        'is_open': is_market_open(),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/health', methods=['GET'])
def health():
    alerts, _ = load_alerts()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'alerts_count': len(alerts),
        'market_open': is_market_open(),
        'finnhub_configured': bool(FINNHUB_API_KEY),
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)
    }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


# ─── Start Background Monitor ─────────────────────────────────────────────────

def start_background_monitor():
    """Start the background monitoring thread"""
    monitor_thread = Thread(target=monitor_loop, daemon=True)
    monitor_thread.start()
    logger.info("✅ Background monitor thread started")


# Start monitor when app loads (not in debug reloader child process)
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    start_background_monitor()


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
