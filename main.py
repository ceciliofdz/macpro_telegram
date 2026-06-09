import os
import csv
import threading
import time
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from data_fetcher import fetch_ohlcv
from macd_logic import detect_signals, get_last_signal
from telegram_bot import send_telegram_alert

load_dotenv()

import time
from datetime import datetime, timezone
from data_fetcher import fetch_ohlcv, get_exchange_time

# ... resto de imports ...

def timeframe_to_milliseconds(timeframe: str) -> int:
    """Convierte timeframe de Binance (ej: '1h', '15m', '4h') a milisegundos."""
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    if unit == 'm':
        return value * 60 * 1000
    elif unit == 'h':
        return value * 60 * 60 * 1000
    elif unit == 'd':
        return value * 24 * 60 * 60 * 1000
    else:
        raise ValueError(f"Timeframe no soportado: {timeframe}")

def get_last_closed_candle(df: pd.DataFrame, timeframe_ms: int, current_time_ms: int):
    """
    Retorna el índice (entero) de la última fila del DataFrame cuya vela está cerrada.
    Una vela está cerrada si: timestamp + timeframe_ms <= current_time_ms.
    Si no hay ninguna, retorna None.
    """
    for idx in range(len(df)-1, -1, -1):
        candle_time_ms = int(df.index[idx].timestamp() * 1000)
        close_time_ms = candle_time_ms + timeframe_ms
        if close_time_ms <= current_time_ms:
            return idx  # índice posicional en el DataFrame
    return None

# Parámetros globales (desde .env)
PARAMS = {
    'fast_len': int(os.getenv('FAST_LEN', 12)),
    'slow_len': int(os.getenv('SLOW_LEN', 26)),
    'signal_len': int(os.getenv('SIGNAL_LEN', 9)),
    'source_type': os.getenv('SOURCE_TYPE', 'close'),
    'osc_ma_type': os.getenv('OSC_MA_TYPE', 'EMA'),
    'signal_ma_type': os.getenv('SIGNAL_MA_TYPE', 'EMA'),
    'use_trend_filter': os.getenv('USE_TREND_FILTER', 'true').lower() == 'true',
    'trend_filter_mode': os.getenv('TREND_FILTER_MODE', 'Ambas'),
    'trend_len': int(os.getenv('TREND_EMA_LEN', 200)),
}

DEFAULT_TIMEFRAME = os.getenv('TIMEFRAME', '1h')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL_MINUTES', 5))

CSV_FILE = 'tickers.csv'

# Para evitar múltiples alertas de una misma señal
last_alert = {}

# --------------------- Funciones del CSV ---------------------
def read_tickers():
    """Lee el CSV y devuelve lista de dicts con symbol, active, timeframe"""
    tickers = []
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['symbol', 'active', 'timeframe'])
    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tickers.append(row)
    return tickers

def write_tickers(tickers):
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['symbol', 'active', 'timeframe'])
        writer.writeheader()
        writer.writerows(tickers)

def add_ticker(symbol, active, timeframe):
    tickers = read_tickers()
    # evitar duplicados
    if not any(t['symbol'] == symbol for t in tickers):
        tickers.append({'symbol': symbol, 'active': active, 'timeframe': timeframe})
        write_tickers(tickers)

def update_ticker(old_symbol, new_symbol, active, timeframe):
    tickers = read_tickers()
    for t in tickers:
        if t['symbol'] == old_symbol:
            t['symbol'] = new_symbol
            t['active'] = active
            t['timeframe'] = timeframe
            break
    write_tickers(tickers)

def delete_ticker(symbol):
    tickers = read_tickers()
    tickers = [t for t in tickers if t['symbol'] != symbol]
    write_tickers(tickers)

# --------------------- Lógica de monitoreo ---------------------
# Diccionario para recordar la última vela cerrada que ya generó alerta (por símbolo)
last_alerted_candle = {}  # key: symbol, value: timestamp (ms) de la vela cerrada

def analyze_and_alert():
    global last_alerted_candle
    tickers = read_tickers()
    active_tickers = [t for t in tickers if t['active'].lower() == 'true']
    try:
        current_time_ms = get_exchange_time()  # ya con reintentos internos
    except Exception as e:
        print(f"[{datetime.now()}] No se pudo obtener la hora del servidor: {e}. Se omite este ciclo.")
        return

    for ticker in active_tickers:
        symbol = ticker['symbol']
        timeframe = ticker.get('timeframe', DEFAULT_TIMEFRAME)
        timeframe_ms = timeframe_to_milliseconds(timeframe)
        
        try:
            # fetch_ohlcv ya tiene reintentos internos
            df = fetch_ohlcv(symbol, timeframe, limit=300)
            if df.empty:
                continue
            
            last_closed_idx = get_last_closed_candle(df, timeframe_ms, current_time_ms)
            # ... resto del código sin cambios ...
            
        except Exception as e:
            print(f"[{datetime.now()}] Error crítico procesando {symbol}: {e}. Se pasa al siguiente ticker.")
            # Pequeña pausa antes del siguiente ticker para no sobrecargar
            time.sleep(0.5)
            continue
        
        # Pequeña pausa entre tickers exitosos también
        time.sleep(0.5)
# --------------------- Web (Flask) ---------------------
app = Flask(__name__)

@app.route('/')
def index():
    tickers = read_tickers()
    return render_template('index.html', tickers=tickers)

@app.route('/add', methods=['POST'])
def add():
    symbol = request.form['symbol']
    active = request.form['active']
    timeframe = request.form['timeframe']
    add_ticker(symbol, active, timeframe)
    return redirect(url_for('index'))

@app.route('/edit/<old_symbol>', methods=['GET', 'POST'])
def edit(old_symbol):
    if request.method == 'POST':
        new_symbol = request.form['symbol']
        active = request.form['active']
        timeframe = request.form['timeframe']
        update_ticker(old_symbol, new_symbol, active, timeframe)
        return redirect(url_for('index'))
    tickers = read_tickers()
    ticker = next((t for t in tickers if t['symbol'] == old_symbol), None)
    return render_template('edit.html', ticker=ticker)

@app.route('/delete/<symbol>')
def delete(symbol):
    delete_ticker(symbol)
    return redirect(url_for('index'))

# --------------------- Arranque ---------------------
def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=analyze_and_alert, trigger='interval', minutes=CHECK_INTERVAL)
    scheduler.start()
    print(f"Scheduler iniciado. Revisando cada {CHECK_INTERVAL} minuto(s).")
    # Ejecutar inmediatamente al inicio
    threading.Timer(5, analyze_and_alert).start()

if __name__ == '__main__':
    start_scheduler()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)