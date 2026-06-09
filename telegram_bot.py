import requests
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def send_telegram_alert(symbol: str, signal_type: str, price: float, momento: str, tendencia: str):
    """signal_type: 'BUY' o 'SELL'"""
    if signal_type == 'BUY':
        titulo = "🟢 MACD PRO: Compra Detectada"
    else:
        titulo = "🔴 MACD PRO: Venta Detectada"
    
    mensaje = f"""{titulo}
📌 Símbolo: {symbol}
💰 Precio: {price:.4f}
📈 Momento: {momento}
📊 Tendencia: {tendencia}
    """
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': mensaje,
        'parse_mode': 'HTML'
    }
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")