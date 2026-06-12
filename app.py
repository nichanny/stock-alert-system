#!/usr/bin/env python3
"""
Stock Alert Dashboard + Background Monitor
Multi-Level Buy Alert System with Cooldown & Reset Logic
"""

import os
import json
import requests
import logging
import time
import pytz
from datetime import datetime, timedelta
from threading import Thread
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────
FINNHUB_API_KEY    = os.getenv('FINNHUB_API_KEY')
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID   = os.getenv('TELEGRAM_CHAT_ID')
POLLING_INTERVAL   = int(os.getenv('POLLING_INTERVAL', 60))
FINNHUB_QUOTE_URL  = "https://finnhub.io/api/v1/quote"
ALERT_COOLDOWN_HRS = 4          # hours before same level can alert again
RESET_THRESHOLD_PCT = 10        # % above level to reset triggered state

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'stock-alert-secret-key-2024')

# ─── In-Memory State ──────────────────────────────────────────────────────────
_alerts_cache  = None
_history_cache = None
# { "PLTR_30.0": datetime_of_last_alert }
_level_last_alerted: dict = {}
# { "PLTR_30.0": True/False }  — True = triggered and still below reset threshold
_level_triggered: dict    = {}

# ─── Default Stock List (multi-level) ────────────────────────────────────────
DEFAULT_ALERTS = [
    {
        "symbol": "ETN",
        "company_name": "Eaton Corporation",
        "category": "core",
        "levels": [380.0, 360.0, 340.0, 315.0],
        "sizes":  ["small", "mid", "mid", "big"],
        "note": "AI Power Infra · 3 ตัว AXON/NOW/ETN Phon ทยอยสะสม",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "PLTR",
        "company_name": "Palantir Technologies Inc.",
        "category": "growth",
        "levels": [135.0, 125.0, 100.0],
        "sizes":  ["small", "mid", "big"],
        "note": "Phon ถือยาว · Top pick AI / Data",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "CEG",
        "company_name": "Constellation Energy Corporation",
        "category": "growth",
        "levels": [206.0, 200.0, 180.0, 170.0],
        "sizes":  ["small", "small", "mid", "big"],
        "note": "Nuclear Energy · ลงมา 27% YTD",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "AVAV",
        "company_name": "AeroVironment Inc.",
        "category": "core",
        "levels": [200.0],
        "sizes":  ["big"],
        "note": "Defense Drone · ต่ำกว่า 200 ซื้อได้เลย · รายได้โต 143%",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "LLY",
        "company_name": "Eli Lilly and Company",
        "category": "core",
        "levels": [870.0, 893.0, 900.0],
        "sizes":  ["small", "mid", "big"],
        "note": "GLP-1 Platform · 1 ใน 10 นางฟ้า Phon",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "NOW",
        "company_name": "ServiceNow Inc.",
        "category": "core",
        "levels": [100.0, 95.0, 80.0, 70.0],
        "sizes":  ["small", "mid", "mid", "big"],
        "note": "Phon: ห้ามมองข้ามเด็ดขาด · AI Control Tower",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "AXON",
        "company_name": "Axon Enterprise Inc.",
        "category": "growth",
        "levels": [400.0, 395.0, 365.0, 340.0],
        "sizes":  ["small", "small", "mid", "big"],
        "note": "Public Safety AI · Near-monopoly SaaS",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "META",
        "company_name": "Meta Platforms Inc.",
        "category": "core",
        "levels": [540.0, 500.0],
        "sizes":  ["small", "mid"],
        "note": "AI + Social Monopoly · Consumer Monopoly",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "AMZN",
        "company_name": "Amazon.com Inc.",
        "category": "core",
        "levels": [215.0, 200.0],
        "sizes":  ["small", "mid"],
        "note": "AWS + AI + Robotics · Physical AI + Cloud",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "MSFT",
        "company_name": "Microsoft Corporation",
        "category": "core",
        "levels": [380.0, 360.0],
        "sizes":  ["small", "mid"],
        "note": "AI + Azure Cloud · Phon เติมสะสมกลุ่มหลัก",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "GOOGL",
        "company_name": "Alphabet Inc.",
        "category": "core",
        "levels": [160.0, 150.0],
        "sizes":  ["small", "mid"],
        "note": "AI + Search Monopoly · Phon ซื้อ 3 มิ.ย.",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "ISRG",
        "company_name": "Intuitive Surgical Inc.",
        "category": "core",
        "levels": [425.0, 417.0, 400.0, 365.0],
        "sizes":  ["small", "small", "mid", "big"],
        "note": "Robot Surgery · Wide Moat · Phon เติมสะสม",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "SOFI",
        "company_name": "SoFi Technologies Inc.",
        "category": "growth",
        "levels": [16.0, 14.0, 12.0],
        "sizes":  ["small", "mid", "big"],
        "note": "Digital Bank · ⚠️ ระวัง Muddy Waters",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "HIMS",
        "company_name": "Hims & Hers Health Inc.",
        "category": "growth",
        "levels": [22.0, 18.0, 14.0],
        "sizes":  ["small", "mid", "big"],
        "note": "Phon ซื้อด้วยวินัย · โตต่ออีกยาว",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "KTOS",
        "company_name": "Kratos Defense & Security Solutions",
        "category": "growth",
        "levels": [28.0, 25.0, 22.0],
        "sizes":  ["small", "mid", "big"],
        "note": "AI Drone High Growth · Defense Tech",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "ZS",
        "company_name": "Zscaler Inc.",
        "category": "growth",
        "levels": [127.0, 125.0, 114.0, 100.0],
        "sizes":  ["small", "small", "mid", "big"],
        "note": "Cloud Security · เข้าบางๆ 125-127 ลงต่อถึง 114/100",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "NEE",
        "company_name": "NextEra Energy Inc.",
        "category": "defensive",
        "levels": [87.0, 78.0, 72.0, 65.0],
        "sizes":  ["small", "mid", "mid", "big"],
        "note": "Clean Energy · หุ้นดีนักลงทุนระดับโลกถือ",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "OKLO",
        "company_name": "Oklo Inc.",
        "category": "speculative",
        "levels": [20.0, 15.0],
        "sizes":  ["small", "mid"],
        "note": "Nuclear SMR · Pre-revenue · High Risk",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "RKLB",
        "company_name": "Rocket Lab USA Inc.",
        "category": "speculative",
        "levels": [20.0, 15.0],
        "sizes":  ["small", "mid"],
        "note": "Space Launch · High Growth High Risk",
        "active": True,
        "created_date": "2024-01-15"
    },
    {
        "symbol": "ASTS",
        "company_name": "AST SpaceMobile Inc.",
        "category": "speculative",
        "levels": [25.0, 20.0],
        "sizes":  ["small", "mid"],
        "note": "Space Mobile · High Risk High Reward",
        "active": True,
        "created_date": "2024-01-15"
    },
]

SIZE_LABEL = {"small": "ไม้เล็ก", "mid": "ไม้กลาง", "big": "ไม้หนัก"}
SIZE_EMOJI = {"small": "🟡", "mid": "🟠", "big": "🔴"}
CATEGORY_LABEL = {"core": "🏛️ Core", "growth": "🚀 Growth", "defensive": "🛡️ Defensive", "speculative": "🎲 Spec"}
CATEGORY_COLOR = {"core": "#2563eb", "growth": "#16a34a", "defensive": "#d97706", "speculative": "#dc2626"}


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
            logger.info(f"Loaded {len(_alerts_cache)} alerts from env")
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


def add_to_history(history, symbol, price, level, level_idx, total_levels, size, category, message):
    history.append({
        'symbol': symbol,
        'price': price,
        'level': level,
        'level_idx': level_idx,
        'total_levels': total_levels,
        'size': size,
        'category': category,
        'message': message,
        'timestamp': datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%Y-%m-%d %H:%M:%S')
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
            pc = data.get('pc', data['c'])
            return {
                'price': data['c'],
                'high': data.get('h', 0),
                'low': data.get('l', 0),
                'open': data.get('o', 0),
                'previous_close': pc,
                'change': round(data['c'] - pc, 2),
                'change_pct': round(((data['c'] - pc) / pc) * 100, 2) if pc > 0 else 0
            }
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None


# ─── Telegram ─────────────────────────────────────────────────────────────────

def send_telegram_alert(symbol, current_price, level, level_idx, total_levels, size, category, company_name, note=""):
    try:
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            logger.warning("Telegram not configured")
            return False

        now_thai = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')
        cat_label = CATEGORY_LABEL.get(category, category.upper())
        size_label = SIZE_LABEL.get(size, size)
        size_emoji = SIZE_EMOJI.get(size, "🟡")
        diff_pct = round(((level - current_price) / level) * 100, 1)

        # Build remaining levels string
        remaining = total_levels - (level_idx + 1)
        remaining_str = f"เหลืออีก {remaining} แนว" if remaining > 0 else "แนวสุดท้าย ✅"

        message = (
            f"🔔 *BUY SIGNAL — {symbol}*\n"
            f"{cat_label} | {company_name}\n\n"
            f"💰 ราคา: *${current_price:.2f}* ถึงแนว *${level:.2f}*\n"
            f"{size_emoji} ขนาด: *{size_label}* (ไม้ {level_idx+1}/{total_levels})\n"
            f"📉 ต่ำกว่าแนว: {diff_pct:.1f}%\n"
            f"🔔 {remaining_str}\n"
            f"📝 {note}\n"
            f"⏰ {now_thai} (TH)"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.info(f"✅ Telegram: {symbol} @ ${current_price:.2f} (level {level_idx+1}/{total_levels})")
        return True
    except Exception as e:
        logger.error(f"Telegram error: {e}")
        return False


# ─── Market Hours ─────────────────────────────────────────────────────────────

def is_market_open():
    try:
        est = pytz.timezone('US/Eastern')
        now = datetime.now(est)
        if now.weekday() >= 5:
            return False
        open_t  = now.replace(hour=9,  minute=30, second=0, microsecond=0)
        close_t = now.replace(hour=16, minute=0,  second=0, microsecond=0)
        return open_t <= now <= close_t
    except Exception:
        return True


# ─── Multi-Level Alert Logic ──────────────────────────────────────────────────

def _level_key(symbol, level):
    return f"{symbol}_{level:.2f}"


def check_cooldown(symbol, level):
    """Return True if OK to alert (not in cooldown)."""
    key = _level_key(symbol, level)
    last = _level_last_alerted.get(key)
    if last is None:
        return True
    return datetime.now() - last > timedelta(hours=ALERT_COOLDOWN_HRS)


def mark_alerted(symbol, level):
    key = _level_key(symbol, level)
    _level_last_alerted[key] = datetime.now()
    _level_triggered[key] = True


def check_reset(symbol, level, current_price):
    """Reset triggered flag if price recovered above level + RESET_THRESHOLD_PCT%."""
    key = _level_key(symbol, level)
    if _level_triggered.get(key):
        reset_price = level * (1 + RESET_THRESHOLD_PCT / 100)
        if current_price >= reset_price:
            _level_triggered[key] = False
            _level_last_alerted.pop(key, None)
            logger.info(f"🔄 Reset alert: {symbol} @ ${current_price:.2f} (level ${level:.2f} reset at ${reset_price:.2f})")


# ─── Background Monitor ───────────────────────────────────────────────────────

def monitor_loop():
    logger.info(f"🚀 Monitor started (interval: {POLLING_INTERVAL}s)")
    time.sleep(10)

    while True:
        try:
            if not is_market_open():
                logger.debug("Market closed")
                time.sleep(POLLING_INTERVAL)
                continue

            alerts, history = load_alerts()
            logger.info(f"🔍 Checking {len(alerts)} stocks...")

            for alert in alerts:
                if not alert.get('active', True):
                    continue

                symbol       = alert['symbol']
                company_name = alert.get('company_name', symbol)
                category     = alert.get('category', 'growth')
                note         = alert.get('note', '')
                levels       = alert.get('levels', [])
                sizes        = alert.get('sizes', ['mid'] * len(levels))

                if not levels:
                    continue

                price_data = get_stock_price(symbol)
                if not price_data:
                    time.sleep(1)
                    continue

                current_price = price_data['price']
                total_levels  = len(levels)

                for idx, level in enumerate(levels):
                    size = sizes[idx] if idx < len(sizes) else 'mid'

                    # Check reset first
                    check_reset(symbol, level, current_price)

                    # Alert condition: price at or below this level
                    if current_price <= level:
                        if check_cooldown(symbol, level):
                            success = send_telegram_alert(
                                symbol, current_price, level, idx, total_levels,
                                size, category, company_name, note
                            )
                            if success:
                                mark_alerted(symbol, level)
                                msg = (f"🔔 {symbol} ถึงแนว ${level:.2f} "
                                       f"(ไม้ {idx+1}/{total_levels} · {SIZE_LABEL.get(size,size)})")
                                history = add_to_history(
                                    history, symbol, current_price, level,
                                    idx, total_levels, size, category, msg
                                )
                                save_alerts(alerts, history)

                time.sleep(1)

        except Exception as e:
            logger.error(f"Monitor error: {e}")

        time.sleep(POLLING_INTERVAL)


# ─── Enrich Alerts for Dashboard ─────────────────────────────────────────────

def enrich_alert(alert):
    """Add live price data and level status to an alert dict."""
    a = alert.copy()
    levels = a.get('levels', [])
    sizes  = a.get('sizes', ['mid'] * len(levels))

    price_data = get_stock_price(a['symbol']) if a.get('active', True) else None

    if price_data:
        cp = price_data['price']
        a['current_price'] = cp
        a['change']        = price_data.get('change', 0)
        a['change_pct']    = price_data.get('change_pct', 0)
        a['prev_close']    = price_data.get('previous_close', 0)

        # Build per-level status
        level_statuses = []
        for idx, lv in enumerate(levels):
            sz  = sizes[idx] if idx < len(sizes) else 'mid'
            key = _level_key(a['symbol'], lv)
            triggered = _level_triggered.get(key, False)
            in_cooldown = not check_cooldown(a['symbol'], lv)
            dist_pct = round(((cp - lv) / lv) * 100, 1)

            if cp <= lv:
                status = 'hit'
            elif dist_pct <= 5:
                status = 'near'
            else:
                status = 'waiting'

            level_statuses.append({
                'level': lv,
                'size': sz,
                'size_label': SIZE_LABEL.get(sz, sz),
                'size_emoji': SIZE_EMOJI.get(sz, '🟡'),
                'idx': idx,
                'total': len(levels),
                'status': status,
                'triggered': triggered,
                'in_cooldown': in_cooldown,
                'dist_pct': dist_pct,
            })

        a['level_statuses'] = level_statuses
        # Overall status = closest level status
        if any(ls['status'] == 'hit' for ls in level_statuses):
            a['overall_status'] = 'hit'
        elif any(ls['status'] == 'near' for ls in level_statuses):
            a['overall_status'] = 'near'
        else:
            a['overall_status'] = 'waiting'

        # Distance to nearest level
        nearest = min(levels, key=lambda lv: abs(cp - lv))
        a['nearest_level'] = nearest
        a['nearest_dist_pct'] = round(((cp - nearest) / nearest) * 100, 1)
    else:
        a['current_price']   = None
        a['change']          = 0
        a['change_pct']      = 0
        a['level_statuses']  = []
        a['overall_status']  = 'error'
        a['nearest_level']   = levels[0] if levels else 0
        a['nearest_dist_pct'] = 0

    a['category_label'] = CATEGORY_LABEL.get(a.get('category', ''), '')
    a['category_color'] = CATEGORY_COLOR.get(a.get('category', ''), '#888')
    return a


# ─── Flask Routes ─────────────────────────────────────────────────────────────

@app.route('/')
def index():
    alerts, history = load_alerts()
    enriched = [enrich_alert(a) for a in alerts]
    # Sort: hit first, then near, then waiting; within same status sort by symbol
    order = {'hit': 0, 'near': 1, 'waiting': 2, 'error': 3}
    enriched.sort(key=lambda a: (order.get(a['overall_status'], 9), a['symbol']))
    now_thai = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M:%S')
    return render_template(
        'dashboard.html',
        alerts=enriched,
        history=history[-30:],
        market_open=is_market_open(),
        now=now_thai,
        category_colors=CATEGORY_COLOR,
        size_labels=SIZE_LABEL,
    )


@app.route('/api/alerts', methods=['GET'])
def get_alerts_api():
    alerts, _ = load_alerts()
    return jsonify(alerts)


@app.route('/api/alerts', methods=['POST'])
def add_alert():
    try:
        data = request.json
        alerts, history = load_alerts()
        symbol = data['symbol'].upper().strip()
        if any(a['symbol'] == symbol for a in alerts):
            return jsonify({'error': 'Symbol already exists'}), 400

        # Support both old single buy_price and new levels array
        if 'levels' in data:
            levels = [float(x) for x in data['levels']]
            sizes  = data.get('sizes', ['mid'] * len(levels))
        elif 'buy_price' in data:
            levels = [float(data['buy_price'])]
            sizes  = ['mid']
        else:
            return jsonify({'error': 'levels or buy_price required'}), 400

        new_alert = {
            'symbol':       symbol,
            'company_name': data.get('company_name', symbol),
            'category':     data.get('category', 'growth'),
            'levels':       levels,
            'sizes':        sizes,
            'note':         data.get('note', ''),
            'active':       True,
            'created_date': datetime.now().strftime('%Y-%m-%d'),
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
                for field in ('company_name', 'category', 'note', 'active'):
                    if field in data:
                        alert[field] = data[field]
                if 'levels' in data:
                    alert['levels'] = [float(x) for x in data['levels']]
                if 'sizes' in data:
                    alert['sizes'] = data['sizes']
                if 'buy_price' in data:   # backward compat
                    alert['levels'] = [float(data['buy_price'])]
                save_alerts(alerts, history)
                return jsonify(alert), 200
        return jsonify({'error': 'Symbol not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/alerts/<symbol>', methods=['DELETE'])
def delete_alert(symbol):
    try:
        alerts, history = load_alerts()
        orig = len(alerts)
        alerts = [a for a in alerts if a['symbol'] != symbol.upper()]
        if len(alerts) == orig:
            return jsonify({'error': 'Symbol not found'}), 404
        save_alerts(alerts, history)
        return jsonify({'message': f'{symbol.upper()} deleted'}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/price/<symbol>', methods=['GET'])
def get_price(symbol):
    price_data = get_stock_price(symbol.upper())
    if price_data:
        return jsonify(price_data), 200
    return jsonify({'error': 'Failed to fetch price'}), 400


@app.route('/api/history', methods=['GET'])
def get_history():
    _, history = load_alerts()
    return jsonify(history[-50:])


@app.route('/api/test-telegram', methods=['POST'])
def test_telegram():
    try:
        now_thai = datetime.now(pytz.timezone('Asia/Bangkok')).strftime('%d/%m/%Y %H:%M')
        message = (
            f"✅ *Stock Alert System — Test*\n\n"
            f"ระบบ Multi-Level Alert ทำงานปกติ\n"
            f"🕐 เวลา: {now_thai} (TH)\n\n"
            f"คุณจะได้รับ alert เมื่อราคาถึงแต่ละแนวซื้อ!"
        )
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': message, 'parse_mode': 'Markdown'}
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return jsonify({'success': True, 'message': 'Test sent!'}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400


@app.route('/api/market-status', methods=['GET'])
def market_status():
    return jsonify({'is_open': is_market_open(), 'timestamp': datetime.now().isoformat()})


@app.route('/health', methods=['GET'])
def health():
    alerts, _ = load_alerts()
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'alerts_count': len(alerts),
        'market_open': is_market_open(),
        'finnhub_configured': bool(FINNHUB_API_KEY),
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
    }), 200


@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Internal server error'}), 500


# ─── Start Background Monitor ─────────────────────────────────────────────────

def start_background_monitor():
    t = Thread(target=monitor_loop, daemon=True)
    t.start()
    logger.info("✅ Background monitor started")


if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    start_background_monitor()

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.getenv('PORT', 5000)))
