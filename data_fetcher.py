import ccxt
import pandas as pd

exchange = ccxt.binance()

def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    """Retorna DataFrame con columnas: timestamp, open, high, low, close, volume"""
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df.set_index('timestamp', inplace=True)
    return df