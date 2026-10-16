import os
from dataclasses import dataclass
from functools import lru_cache


def _csv(name: str, default: str = "") -> tuple:
    return tuple(x.strip() for x in os.getenv(name, default).split(",") if x.strip())


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)).strip())
    except ValueError:
        return default


def _str(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


@dataclass(frozen=True)
class Settings:
    supabase_url: str
    supabase_service_key: str
    twelve_key: str
    finnhub_key: str
    allowed_origins: tuple
    allowed_origin_regex: str
    td_daily_limit: int
    td_per_minute: int
    td_reserve_on_demand: int
    td_burst: int
    td_symbols: tuple
    td_fast_symbols: tuple
    td_fast_tf: str
    td_slow_tf: str
    crypto_symbols: tuple
    crypto_tfs: tuple
    enable_scheduler: bool
    blackout_before_min: int
    blackout_after_min: int
    retention_days: int
    models_bucket: str

    @classmethod
    def load(cls) -> "Settings":
        return cls(
            supabase_url=_str("SUPABASE_URL"),
            supabase_service_key=_str("SUPABASE_SERVICE_KEY"),
            twelve_key=_str("TWELVE_KEY"),
            finnhub_key=_str("FINNHUB_KEY"),
            allowed_origins=_csv("ALLOWED_ORIGINS", "http://localhost:3000"),
            allowed_origin_regex=_str("ALLOWED_ORIGIN_REGEX", r"https://.*\.vercel\.app"),
            td_daily_limit=_int("TD_DAILY_LIMIT", 700),
            td_per_minute=_int("TD_PER_MINUTE", 8),
            td_reserve_on_demand=_int("TD_RESERVE", 40),
            td_burst=_int("TD_BURST", 100),
            td_symbols=_csv("TD_SYMBOLS"),
            td_fast_symbols=_csv("TD_FAST_SYMBOLS", "EURUSD,XAUUSD,GBPUSD,USDJPY"),
            td_fast_tf=_str("TD_FAST_TF", "M15"),
            td_slow_tf=_str("TD_SLOW_TF", "H1"),
            crypto_symbols=_csv("CRYPTO_SYMBOLS"),
            crypto_tfs=_csv("CRYPTO_TFS", "M5,M15,H1"),
            enable_scheduler=_str("ENABLE_SCHEDULER", "1") != "0",
            blackout_before_min=_int("BLACKOUT_BEFORE_MIN", 20),
            blackout_after_min=_int("BLACKOUT_AFTER_MIN", 10),
            retention_days=_int("RETENTION_DAYS", 45),
            models_bucket=_str("MODELS_BUCKET", "models"),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.load()
