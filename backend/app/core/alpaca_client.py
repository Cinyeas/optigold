from __future__ import annotations

"""
Alpaca API client singleton.

Provides shared Trading and Data clients used across services.
"""

from alpaca.trading.client import TradingClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.historical.option import OptionHistoricalDataClient

from app.config import settings
from app.utils.logging_config import get_logger

logger = get_logger(__name__)

_trading_client: TradingClient | None = None
_stock_data_client: StockHistoricalDataClient | None = None
_option_data_client: OptionHistoricalDataClient | None = None


def get_trading_client() -> TradingClient:
    global _trading_client
    if _trading_client is None:
        _trading_client = TradingClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
            paper=settings.ALPACA_PAPER,
        )
        logger.info("Alpaca TradingClient initialised (paper=%s)", settings.ALPACA_PAPER)
    return _trading_client


def get_stock_data_client() -> StockHistoricalDataClient:
    global _stock_data_client
    if _stock_data_client is None:
        _stock_data_client = StockHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )
    return _stock_data_client


def get_option_data_client() -> OptionHistoricalDataClient:
    global _option_data_client
    if _option_data_client is None:
        _option_data_client = OptionHistoricalDataClient(
            api_key=settings.ALPACA_API_KEY,
            secret_key=settings.ALPACA_SECRET_KEY,
        )
    return _option_data_client
