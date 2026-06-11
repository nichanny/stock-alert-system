#!/usr/bin/env python3
"""
Stock Alert Dashboard
Web interface for managing stock alerts
"""

import os
import json
import requests
import logging
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')

# Config file path
CONFIG_FILE = 'stock_alerts.json'


def load_alerts():
    """Load alerts from JSON file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
            return data.get('alerts', []), data.get('alert_history', [])
    except FileNotFoundError:
        return [], []


def save_alerts(alerts):
    """Save alerts to JSON file"""
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        data['alerts'] = alerts
        with open(CONFIG_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving alerts: {e}")
        return False


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
        
        if 'c' in data:
            return {
                'price': data['c'],
                'high': data.get('h', 0),
                'low': data.get('l', 0),
                'open': data.get('o', 0),
                'previous_close': data.get('pc', 0)
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
    for alert in alerts:
        price_data = get_stock_price(alert['symbol'])
        if price_data:
            alert['current_price'] = price_data['price']
            alert['status'] = 'below_target' if price_data['price'] <= alert['buy_price'] else 'above_target'
        else:
            alert['current_price'] = None
            alert['status'] = 'error'
    
    return render_template('dashboard.html', alerts=alerts, history=history[:20])  # Show last 20 alerts


@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """API endpoint to get all alerts"""
    alerts, _ = load_alerts()
    
    # Get current prices
    for alert in alerts:
        price_data = get_stock_price(alert['symbol'])
        if price_data:
            alert['current_price'] = price_data['price']
    
    return jsonify(alerts)


@app.route('/api/alerts', methods=['POST'])
def add_alert():
    """API endpoint to add new alert"""
    try:
        data = request.json
        alerts, _ = load_alerts()
        
        # Check if symbol already exists
        if any(a['symbol'] == data['symbol'] for a in alerts):
            return jsonify({'error': 'Symbol already exists'}), 400
        
        new_alert = {
            'symbol': data['symbol'].upper(),
            'company_name': data.get('company_name', ''),
            'buy_price': float(data['buy_price']),
            'created_date': datetime.now().strftime('%Y-%m-%d'),
            'active': True
        }
        
        alerts.append(new_alert)
        if save_alerts(alerts):
            return jsonify(new_alert), 201
        else:
            return jsonify({'error': 'Failed to save alert'}), 500
    except Exception as e:
        logger.error(f"Error adding alert: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['PUT'])
def update_alert(symbol):
    """API endpoint to update alert"""
    try:
        data = request.json
        alerts, _ = load_alerts()
        
        for alert in alerts:
            if alert['symbol'] == symbol.upper():
                alert['buy_price'] = float(data.get('buy_price', alert['buy_price']))
                alert['active'] = data.get('active', alert['active'])
                
                if save_alerts(alerts):
                    return jsonify(alert), 200
                else:
                    return jsonify({'error': 'Failed to save alert'}), 500
        
        return jsonify({'error': 'Symbol not found'}), 404
    except Exception as e:
        logger.error(f"Error updating alert: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['DELETE'])
def delete_alert(symbol):
    """API endpoint to delete alert"""
    try:
        alerts, _ = load_alerts()
        alerts = [a for a in alerts if a['symbol'] != symbol.upper()]
        
        if save_alerts(alerts):
            return jsonify({'message': 'Alert deleted'}), 200
        else:
            return jsonify({'error': 'Failed to delete alert'}), 500
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
            return jsonify({'error': 'Failed to fetch price'}), 400
    except Exception as e:
        logger.error(f"Error getting price: {e}")
        return jsonify({'error': str(e)}), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    """API endpoint to get alert history"""
    _, history = load_alerts()
    return jsonify(history[-50:])  # Return last 50 alerts


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.now().isoformat()}), 200


@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(error):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
