#!/usr/bin/env python3
"""
Stock Alert Dashboard
Web interface for managing stock alerts
Data stored in environment variable STOCK_ALERTS_DATA to persist on Render free tier
"""

import os
import json
import requests
import logging
import subprocess
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
RENDER_API_KEY = os.getenv('RENDER_API_KEY', '')
RENDER_SERVICE_ID = os.getenv('RENDER_SERVICE_ID', '')

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'stock-alert-secret-key-2024')

# In-memory storage (loaded from env var at startup)
_alerts_cache = None
_history_cache = None

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


def load_alerts():
    """Load alerts from environment variable or use defaults"""
    global _alerts_cache, _history_cache
    
    if _alerts_cache is not None:
        return _alerts_cache, _history_cache
    
    # Try loading from env var
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
    
    # Use defaults
    _alerts_cache = DEFAULT_ALERTS.copy()
    _history_cache = []
    logger.info(f"Using default {len(_alerts_cache)} alerts")
    return _alerts_cache, _history_cache


def save_alerts(alerts, history=None):
    """Save alerts to in-memory cache (and optionally update Render env var)"""
    global _alerts_cache, _history_cache
    
    _alerts_cache = alerts
    if history is not None:
        _history_cache = history
    
    # Also save to local file as backup
    try:
        data = {
            'alerts': alerts,
            'alert_history': _history_cache or []
        }
        with open('stock_alerts.json', 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not save to file: {e}")
    
    return True


def add_to_history(history, symbol, price, buy_price, message):
    """Add alert to history"""
    history.append({
        'symbol': symbol,
        'price': price,
        'buy_price': buy_price,
        'message': message,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
    # Keep only last 100 history items
    return history[-100:]


def get_stock_price(symbol):
    """Fetch current stock price from Finnhub API"""
    try:
        params = {
            'symbol': symbol,
            'token': FINNHUB_API_KEY
        }
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


@app.route('/')
def index():
    """Main dashboard page"""
    alerts, history = load_alerts()
    
    # Get current prices for all stocks
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
    
    return render_template('dashboard.html', alerts=enriched_alerts, history=history[-20:])


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """API endpoint to get all alerts"""
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
    """API endpoint to add new alert"""
    try:
        data = request.json
        alerts, history = load_alerts()
        
        symbol = data['symbol'].upper().strip()
        
        # Check if symbol already exists
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
        logger.error(f"Error adding alert: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['PUT'])
def update_alert(symbol):
    """API endpoint to update alert"""
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
        logger.error(f"Error updating alert: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['DELETE'])
def delete_alert(symbol):
    """API endpoint to delete alert"""
    try:
        alerts, history = load_alerts()
        original_count = len(alerts)
        alerts = [a for a in alerts if a['symbol'] != symbol.upper()]
        
        if len(alerts) == original_count:
            return jsonify({'error': 'Symbol not found'}), 404
        
        save_alerts(alerts, history)
        return jsonify({'message': f'Alert for {symbol.upper()} deleted'}), 200
    except Exception as e:
        logger.error(f"Error deleting alert: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/price/<symbol>', methods=['GET'])
def get_price(symbol):
    """API endpoint to get current price for a symbol"""
    try:
        price_data = get_stock_price(symbol.upper())
        if price_data:
            return jsonify(price_data), 200
        else:
            return jsonify({'error': 'Failed to fetch price or market closed'}), 400
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    """API endpoint to get alert history"""
    _, history = load_alerts()
    return jsonify(history[-50:])


@app.route('/api/check', methods=['POST'])
def check_alerts():
    """Manually trigger alert check"""
    try:
        alerts, history = load_alerts()
        triggered = []
        
        for alert in alerts:
            if not alert.get('active', True):
                continue
            
            price_data = get_stock_price(alert['symbol'])
            if price_data and price_data['price'] <= alert['buy_price']:
                msg = f"🔔 BUY ALERT: {alert['symbol']} is at ${price_data['price']:.2f} (target: ${alert['buy_price']:.2f})"
                triggered.append({
                    'symbol': alert['symbol'],
                    'current_price': price_data['price'],
                    'buy_price': alert['buy_price'],
                    'message': msg
                })
                history = add_to_history(history, alert['symbol'], price_data['price'], alert['buy_price'], msg)
        
        save_alerts(alerts, history)
        return jsonify({'triggered': triggered, 'count': len(triggered)}), 200
    except Exception as e:
        logger.error(f"Error checking alerts: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint - also keeps service alive"""
    alerts, _ = load_alerts()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'alerts_count': len(alerts),
        'finnhub_configured': bool(FINNHUB_API_KEY)
    }), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
