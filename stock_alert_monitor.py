#!/usr/bin/env python3
"""
Stock Price Alert Monitor
Monitors stock prices and sends Telegram alerts when prices reach target levels
"""

import os
import json
import time
import logging
import requests
from datetime import datetime
from dotenv import load_dotenv
from threading import Thread

# Load environment variables
load_dotenv()

# Configuration
FINNHUB_API_KEY = os.getenv('FINNHUB_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
POLLING_INTERVAL = int(os.getenv('POLLING_INTERVAL', 60))
CHECK_MARKET_HOURS_ONLY = os.getenv('CHECK_MARKET_HOURS_ONLY', 'true').lower() == 'true'

# API Endpoints
FINNHUB_QUOTE_URL = "https://finnhub.io/api/v1/quote"
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('stock_alerts.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class StockAlertMonitor:
    def __init__(self, config_file='stock_alerts.json'):
        self.config_file = config_file
        self.alerts = self.load_alerts()
        self.alert_history = self.load_alert_history()
        self.last_alert_prices = {}  # Track last price we alerted at to avoid duplicate alerts
        
    def load_alerts(self):
        """Load alerts from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return data.get('alerts', [])
        except FileNotFoundError:
            logger.error(f"Config file {self.config_file} not found")
            return []
    
    def load_alert_history(self):
        """Load alert history from JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                return data.get('alert_history', [])
        except FileNotFoundError:
            return []
    
    def save_alert_history(self):
        """Save alert history to JSON file"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            data['alert_history'] = self.alert_history
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving alert history: {e}")
    
    def is_market_open(self):
        """Check if US stock market is open (9:30 AM - 4:00 PM EST)"""
        if not CHECK_MARKET_HOURS_ONLY:
            return True
        
        from datetime import datetime, timezone
        import pytz
        
        # Get current time in EST
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        
        # Check if it's a weekday (Monday=0, Friday=4)
        if now.weekday() >= 5:  # Saturday or Sunday
            return False
        
        # Check if time is between 9:30 AM and 4:00 PM
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now <= market_close
    
    def get_stock_price(self, symbol):
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
                return data['c']  # current price
            else:
                logger.warning(f"No price data for {symbol}: {data}")
                return None
        except Exception as e:
            logger.error(f"Error fetching price for {symbol}: {e}")
            return None
    
    def send_telegram_alert(self, symbol, current_price, buy_price):
        """Send alert to Telegram"""
        try:
            message = f"🔔 *Stock Alert*\n\n"
            message += f"*{symbol}* ลดลงถึง *${current_price:.2f}*\n"
            message += f"ราคาเป้าหมาย: ${buy_price:.2f}\n"
            message += f"เวลา: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            message += "✅ ซื้อได้แล้ว!"
            
            payload = {
                'chat_id': TELEGRAM_CHAT_ID,
                'text': message,
                'parse_mode': 'Markdown'
            }
            
            response = requests.post(TELEGRAM_API_URL, json=payload, timeout=10)
            response.raise_for_status()
            
            logger.info(f"Alert sent for {symbol} at ${current_price:.2f}")
            
            # Record in history
            alert_record = {
                'symbol': symbol,
                'current_price': current_price,
                'buy_price': buy_price,
                'timestamp': datetime.now().isoformat(),
                'status': 'sent'
            }
            self.alert_history.append(alert_record)
            self.save_alert_history()
            
            return True
        except Exception as e:
            logger.error(f"Error sending Telegram alert: {e}")
            return False
    
    def check_alerts(self):
        """Check all alerts and send notifications if conditions are met"""
        if not self.is_market_open():
            logger.debug("Market is closed, skipping check")
            return
        
        for alert in self.alerts:
            if not alert.get('active', True):
                continue
            
            symbol = alert['symbol']
            buy_price = alert['buy_price']
            
            # Get current price
            current_price = self.get_stock_price(symbol)
            if current_price is None:
                continue
            
            logger.info(f"{symbol}: ${current_price:.2f} (target: ${buy_price:.2f})")
            
            # Check if price has reached target
            if current_price <= buy_price:
                # Avoid duplicate alerts for the same price
                last_price = self.last_alert_prices.get(symbol)
                if last_price is None or abs(current_price - last_price) > 0.5:  # Only alert if price changed by more than $0.50
                    self.send_telegram_alert(symbol, current_price, buy_price)
                    self.last_alert_prices[symbol] = current_price
    
    def run(self):
        """Main monitoring loop"""
        logger.info("Stock Alert Monitor started")
        logger.info(f"Polling interval: {POLLING_INTERVAL} seconds")
        logger.info(f"Monitoring {len(self.alerts)} stocks")
        
        try:
            while True:
                self.check_alerts()
                time.sleep(POLLING_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Stock Alert Monitor stopped")
        except Exception as e:
            logger.error(f"Unexpected error in monitoring loop: {e}")
            raise


def start_monitor():
    """Start the monitoring service"""
    monitor = StockAlertMonitor()
    monitor.run()


if __name__ == '__main__':
    start_monitor()
