"""forex/data — Módulos de datos del Roadmap VI."""
try:
    from forex.data.rolling_dataset import RollingDataset, get_rolling_dataset
    from forex.data.indicator_delta import recalculate_tail_indicators
    from forex.data.csv_migrator import migrate_csv, list_active_csvs, scan_csv_directory
    from forex.data.data_router import DataRouter, fetch_data
    from forex.data.yahoo_provider import YahooProvider, get_yahoo_provider
    from forex.data.binance_provider import BinanceProvider, get_binance_provider, is_crypto_pair
    from forex.data.mt5_provider import MT5Provider, get_mt5_provider
except ImportError:
    pass
