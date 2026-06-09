import ccxt
import pandas as pd
import time
from datetime import datetime, timezone

exchange = ccxt.binance({
    'enableRateLimit': True,
})

def retry_on_failure(func, max_retries=3, base_delay=1):
    """
    Ejecuta una función que llama a la API de Binance. Si falla con excepción de red/intercambio,
    reintenta con backoff exponencial. Lanza la excepción si se agotan los reintentos.
    """
    for attempt in range(max_retries):
        try:
            return func()
        except (ccxt.NetworkError, ccxt.ExchangeError, ccxt.RateLimitExceeded) as e:
            print(f"[Reintento {attempt+1}/{max_retries}] Error: {e}. Esperando {base_delay * (2**attempt)}s...")
            time.sleep(base_delay * (2**attempt))
        except Exception as e:
            # Otra excepción inesperada, no reintentamos
            print(f"Error inesperado (no reintento): {e}")
            raise e
    raise Exception(f"Fallo después de {max_retries} reintentos.")

def get_exchange_time():
    """Retorna la hora actual del servidor de Binance en milisegundos UTC, con reintentos."""
    def _fetch_time():
        return exchange.fetch_time()
    return retry_on_failure(_fetch_time)

def fetch_ohlcv(symbol: str, timeframe: str, limit: int = 300) -> pd.DataFrame:
    """Retorna DataFrame con velas (timestamp, open, high, low, close, volume). Con reintentos."""
    def _fetch():
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    return retry_on_failure(_fetch)