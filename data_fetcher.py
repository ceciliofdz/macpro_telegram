import ccxt
import pandas as pd
from datetime import datetime, timezone

exchange = ccxt.binance({
    'enableRateLimit': True,
})

def get_exchange_time():
    """Retorna la hora actual del servidor de Binance en milisegundos UTC."""
    try:
        # Consulta la hora del servidor (evita desfases del reloj local)
        server_time = exchange.fetch_time()
        return server_time
    except Exception:
        # Fallback a UTC local (menos preciso pero funcional)
        return int(datetime.now(timezone.utc).timestamp() * 1000)

def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    """Retorna DataFrame con velas (timestamp, open, high, low, close, volume)."""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df