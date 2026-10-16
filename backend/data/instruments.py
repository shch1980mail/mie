from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Instrument:
    symbol: str
    name: str
    asset_class: str            # fx|metal|energy|agri|stock|index|crypto|etf|bond
    provider: str               # twelvedata | binance
    ticker: str
    currencies: tuple = ()      # валюты, чувствительные к новостям (base, quote)
    cot_market: str = ""        # префикс названия рынка в CFTC
    cot_invert: bool = False    # True, если инструмент котируется «наоборот» (USDJPY и т.п.)
    session: str = "fx"         # fx|metal|energy|us|eu|asia|crypto
    kraken: str = ""
    coinbase: str = ""
    default_on: bool = False    # включён ли по умолчанию


def _fx(base, quote, cot="", inv=False, on=False):
    return Instrument(base + quote, f"{base}/{quote}", "fx", "twelvedata", f"{base}/{quote}",
                      (base, quote), cot, inv, "fx", default_on=on)


def _metal(code, name, cot="", on=False):
    return Instrument(code + "USD", name, "metal", "twelvedata", f"{code}/USD",
                      (code, "USD"), cot, False, "metal", default_on=on)


def _us(sym, name, cls, cot="", on=False, ccy=("USD",)):
    return Instrument(sym, name, cls, "twelvedata", sym, ccy, cot, False, "us", default_on=on)


def _crypto(sym, name, kraken="", coinbase="", on=True):
    return Instrument(sym, name, "crypto", "binance", sym, ("USD",), "", False, "crypto",
                      kraken, coinbase, on)


_LIST = [
    # --- Forex ---
    _fx("EUR", "USD", "EURO FX", on=True), _fx("GBP", "USD", "BRITISH POUND", on=True),
    _fx("USD", "JPY", "JAPANESE YEN", inv=True, on=True),
    _fx("AUD", "USD", "AUSTRALIAN DOLLAR", on=True),
    _fx("USD", "CAD", "CANADIAN DOLLAR", inv=True, on=True),
    _fx("USD", "CHF", "SWISS FRANC", inv=True), _fx("NZD", "USD", "NZ DOLLAR"),
    _fx("EUR", "GBP"), _fx("EUR", "JPY"), _fx("GBP", "JPY"),
    _fx("USD", "TRY"), _fx("USD", "MXN"), _fx("USD", "ZAR"),
    # --- Металлы ---
    _metal("XAU", "Золото XAU/USD", "GOLD", on=True),
    _metal("XAG", "Серебро XAG/USD", "SILVER", on=True),
    _metal("XPT", "Платина XPT/USD", "PLATINUM"), _metal("XPD", "Палладий XPD/USD", "PALLADIUM"),
    _metal("XCU", "Медь XCU/USD", "COPPER"),
    # --- Энергоносители ---
    Instrument("WTI", "Нефть WTI", "energy", "twelvedata", "WTI/USD", ("WTI", "USD"),
               "CRUDE OIL, LIGHT SWEET", False, "energy", default_on=True),
    Instrument("BRENT", "Нефть Brent", "energy", "twelvedata", "XBR/USD", ("BRENT", "USD"),
               "", False, "energy"),
    Instrument("NATGAS", "Природный газ", "energy", "twelvedata", "NG/USD", ("NG", "USD"),
               "NATURAL GAS", False, "energy"),
    # --- Индексы (ETF-прокси бесплатны; сами индексы часто платные) ---
    _us("SPY", "S&P 500 (ETF SPY)", "etf", "E-MINI S&P 500", on=True),
    _us("QQQ", "NASDAQ 100 (ETF QQQ)", "etf", "NASDAQ", on=True),
    _us("DIA", "Dow Jones (ETF DIA)", "etf"),
    _us("SPX", "S&P 500 (индекс)", "index", "E-MINI S&P 500"),
    _us("NDX", "NASDAQ 100 (индекс)", "index"), _us("DJI", "Dow Jones (индекс)", "index"),
    # --- ETF / облигации ---
    _us("GLD", "Золото (ETF GLD)", "etf", on=True), _us("USO", "Нефть (ETF USO)", "etf"),
    _us("TLT", "Облигации США 20+ (TLT)", "bond"), _us("IEF", "Облигации США 7-10 (IEF)", "bond"),
    _us("HYG", "High Yield облигации (HYG)", "bond"),
    # --- Сельхоз (ETF-прокси) ---
    _us("WEAT", "Пшеница (ETF WEAT)", "agri"), _us("CORN", "Кукуруза (ETF CORN)", "agri"),
    _us("SOYB", "Соя (ETF SOYB)", "agri"), _us("DBA", "Агро-корзина (ETF DBA)", "agri"),
    _us("CANE", "Сахар (ETF CANE)", "agri"),
    # --- Акции US ---
    _us("AAPL", "Apple", "stock", on=True), _us("NVDA", "NVIDIA", "stock", on=True),
    _us("MSFT", "Microsoft", "stock"), _us("TSLA", "Tesla", "stock"),
    _us("AMZN", "Amazon", "stock"), _us("GOOGL", "Alphabet", "stock"),
    # --- Крипта ---
    _crypto("BTCUSDT", "Bitcoin", "XBTUSD", "BTC-USD"),
    _crypto("ETHUSDT", "Ethereum", "ETHUSD", "ETH-USD"),
    _crypto("SOLUSDT", "Solana", "SOLUSD", "SOL-USD"),
    _crypto("BNBUSDT", "BNB"),
    _crypto("XRPUSDT", "XRP", "XRPUSD", "XRP-USD"),
    _crypto("ADAUSDT", "Cardano", "ADAUSD", "ADA-USD"),
    _crypto("DOGEUSDT", "Dogecoin", "DOGEUSD", "DOGE-USD"),
    _crypto("LINKUSDT", "Chainlink", "LINKUSD", "LINK-USD"),
]

INSTRUMENTS: dict[str, Instrument] = {i.symbol: i for i in _LIST}


def active_instruments(s) -> list[Instrument]:
    """Какие инструменты анализируются: либо env-списки, либо default_on из реестра."""
    td_sel, cr_sel = set(s.td_symbols), set(s.crypto_symbols)
    out = []
    for i in INSTRUMENTS.values():
        if i.provider == "binance":
            on = (i.symbol in cr_sel) if cr_sel else i.default_on
        else:
            on = (i.symbol in td_sel) if td_sel else i.default_on
        if on:
            out.append(i)
    return out


def is_open(inst: Instrument, t: datetime) -> bool:
    """Грубое окно торговой сессии в UTC (без праздников и перехода на летнее время)."""
    wd, m = t.weekday(), t.hour * 60 + t.minute
    ses = inst.session
    if ses == "crypto":
        return True
    if ses in ("fx", "metal", "energy"):
        if wd == 5:
            return False
        if wd == 6:
            return m >= 22 * 60
        if wd == 4:
            return m < 22 * 60
        if ses != "fx" and 22 * 60 <= m < 23 * 60:
            return False
        return True
    if wd >= 5:
        return False
    if ses == "us":
        return 13 * 60 + 30 <= m < 21 * 60
    if ses == "eu":
        return 7 * 60 <= m < 16 * 60 + 30
    if ses == "asia":
        return m < 7 * 60
    return True
