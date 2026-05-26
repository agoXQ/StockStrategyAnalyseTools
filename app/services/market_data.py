import hashlib
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from typing import Any, Optional

from app.config import DEFAULT_MARKET_TYPE_INDEX, DEFAULT_MARKET_TYPE_STOCK
from app.config_loader import get_market_data_config


@dataclass
class MarketCloseData:
    trade_date: date
    symbol: str
    market_type: str
    close_price: float
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    volume: Optional[int] = None
    source: str = "demo"

    def as_dict(self) -> dict[str, Any]:
        return {
            "trade_date": self.trade_date,
            "symbol": self.symbol,
            "market_type": self.market_type,
            "close_price": self.close_price,
            "open_price": self.open_price,
            "high_price": self.high_price,
            "low_price": self.low_price,
            "volume": self.volume,
            "source": self.source,
        }


class MarketDataProvider:
    name = "base"

    def fetch_close(self, trade_date: date, symbol: str, market_type: str) -> MarketCloseData:
        raise NotImplementedError


def _import_optional(module_name: str, install_hint: str):
    try:
        return __import__(module_name)
    except ImportError as exc:
        raise RuntimeError(f"{module_name} is not installed. Install it with: {install_hint}") from exc


def _date_yyyymmdd(value: date) -> str:
    return value.strftime("%Y%m%d")


def _plain_code(symbol: str) -> str:
    symbol = symbol.strip()
    if "." in symbol:
        return symbol.split(".")[0]
    return symbol


def _tushare_symbol(symbol: str, market_type: str) -> str:
    symbol = symbol.strip().upper()
    if "." in symbol:
        return symbol
    code = _plain_code(symbol)
    if market_type == DEFAULT_MARKET_TYPE_INDEX:
        return f"{code}.SH"
    if code.startswith(("6", "5", "9")):
        return f"{code}.SH"
    if code.startswith(("0", "2", "3")):
        return f"{code}.SZ"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return code


def _jqdata_symbol(symbol: str, market_type: str) -> str:
    symbol = symbol.strip().upper()
    if "." in symbol:
        return symbol
    code = _plain_code(symbol)
    if market_type == DEFAULT_MARKET_TYPE_INDEX:
        return f"{code}.XSHG"
    if code.startswith(("6", "5", "9")):
        return f"{code}.XSHG"
    if code.startswith(("0", "2", "3")):
        return f"{code}.XSHE"
    if code.startswith(("4", "8")):
        return f"{code}.XBJ"
    return code


def _index_alias(config: dict[str, Any], provider_name: str, symbol: str) -> str:
    aliases = config.get("index_aliases", {})
    alias = aliases.get(symbol.upper())
    if isinstance(alias, dict) and alias.get(provider_name):
        return alias[provider_name]
    return symbol


def _number(value, default: Optional[float] = None) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value) -> Optional[int]:
    parsed = _number(value)
    return int(parsed) if parsed is not None else None


def _first_record(data_frame):
    if data_frame is None or data_frame.empty:
        raise RuntimeError("No market data returned")
    return data_frame.iloc[0]


class DemoMarketDataProvider(MarketDataProvider):
    name = "demo"

    def fetch_close(self, trade_date: date, symbol: str, market_type: str) -> MarketCloseData:
        seed = int(hashlib.sha256(f"{symbol}:{trade_date.isoformat()}".encode("utf-8")).hexdigest()[:8], 16)
        base = 8 + (seed % 5000) / 100
        drift = ((trade_date.toordinal() % 23) - 11) / 1000
        close_price = round(base * (1 + drift), 4)
        open_price = round(close_price * (1 - ((seed % 17) - 8) / 1000), 4)
        high_price = round(max(open_price, close_price) * 1.01, 4)
        low_price = round(min(open_price, close_price) * 0.99, 4)
        return MarketCloseData(
            trade_date=trade_date,
            symbol=symbol,
            market_type=market_type,
            close_price=close_price,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            volume=0 if market_type == DEFAULT_MARKET_TYPE_INDEX else seed % 10000000,
            source=self.name,
        )


class AkshareMarketDataProvider(MarketDataProvider):
    name = "akshare"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.akshare = _import_optional("akshare", "pip install akshare")

    def fetch_close(self, trade_date: date, symbol: str, market_type: str) -> MarketCloseData:
        provider_symbol = _index_alias(self.config, self.name, symbol) if market_type == DEFAULT_MARKET_TYPE_INDEX else _plain_code(symbol)
        start = _date_yyyymmdd(trade_date)
        end = _date_yyyymmdd(trade_date)
        if market_type == DEFAULT_MARKET_TYPE_INDEX:
            data_frame = self.akshare.index_zh_a_hist(symbol=provider_symbol, period="daily", start_date=start, end_date=end)
        else:
            data_frame = self.akshare.stock_zh_a_hist(
                symbol=provider_symbol,
                period="daily",
                start_date=start,
                end_date=end,
                adjust=self.config.get("akshare", {}).get("adjust", ""),
            )
        row = _first_record(data_frame)
        return MarketCloseData(
            trade_date=trade_date,
            symbol=symbol,
            market_type=market_type,
            open_price=_number(row.get("开盘")),
            close_price=_number(row.get("收盘"), 0.0) or 0.0,
            high_price=_number(row.get("最高")),
            low_price=_number(row.get("最低")),
            volume=_integer(row.get("成交量")),
            source=self.name,
        )


class TushareMarketDataProvider(MarketDataProvider):
    name = "tushare"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        token = config.get("tushare", {}).get("token")
        if not token:
            raise RuntimeError("Tushare token is missing. Set market_data.tushare.token or TUSHARE_TOKEN.")
        self.tushare = _import_optional("tushare", "pip install tushare")
        self.tushare.set_token(token)
        self.pro = self.tushare.pro_api()

    def fetch_close(self, trade_date: date, symbol: str, market_type: str) -> MarketCloseData:
        provider_symbol = _index_alias(self.config, self.name, symbol) if market_type == DEFAULT_MARKET_TYPE_INDEX else _tushare_symbol(symbol, market_type)
        start = _date_yyyymmdd(trade_date)
        end = _date_yyyymmdd(trade_date)
        if market_type == DEFAULT_MARKET_TYPE_INDEX:
            data_frame = self.pro.index_daily(ts_code=provider_symbol, start_date=start, end_date=end)
        else:
            data_frame = self.pro.daily(ts_code=provider_symbol, start_date=start, end_date=end)
        row = _first_record(data_frame)
        return MarketCloseData(
            trade_date=trade_date,
            symbol=symbol,
            market_type=market_type,
            open_price=_number(row.get("open")),
            close_price=_number(row.get("close"), 0.0) or 0.0,
            high_price=_number(row.get("high")),
            low_price=_number(row.get("low")),
            volume=_integer(row.get("vol")),
            source=self.name,
        )

    def fetch_all_stocks_daily(self, trade_date: date) -> list[MarketCloseData]:
        trade_date_str = _date_yyyymmdd(trade_date)
        df = self.pro.daily(trade_date=trade_date_str)
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            ts_code = str(row["ts_code"])
            symbol = ts_code.split(".")[0]
            if ts_code.endswith(".SH"):
                symbol = f"{symbol}.SH"
            elif ts_code.endswith(".SZ"):
                symbol = f"{symbol}.SZ"
            elif ts_code.endswith(".BJ"):
                symbol = f"{symbol}.BJ"
            else:
                symbol = ts_code

            results.append(MarketCloseData(
                trade_date=trade_date,
                symbol=symbol,
                market_type=DEFAULT_MARKET_TYPE_STOCK,
                open_price=_number(row.get("open")),
                close_price=_number(row.get("close"), 0.0) or 0.0,
                high_price=_number(row.get("high")),
                low_price=_number(row.get("low")),
                volume=_integer(row.get("vol")),
                source=self.name,
            ))
        return results

    def is_trading_day(self, trade_date: date) -> bool:
        trade_date_str = _date_yyyymmdd(trade_date)
        cal_df = self.pro.trade_cal(
            exchange="SSE",
            start_date=trade_date_str,
            end_date=trade_date_str,
        )
        if cal_df is None or cal_df.empty:
            return False
        return cal_df.iloc[0].get("is_open", 0) == 1

    def get_trading_days(self, start_date: date, end_date: date) -> list[date]:
        start_str = _date_yyyymmdd(start_date)
        end_str = _date_yyyymmdd(end_date)
        cal_df = self.pro.trade_cal(
            exchange="SSE",
            start_date=start_str,
            end_date=end_str,
        )
        if cal_df is None or cal_df.empty:
            return []

        results = []
        for _, row in cal_df.iterrows():
            if row.get("is_open", 0) == 1:
                date_str = str(row["cal_date"])
                year, month, day = int(date_str[:4]), int(date_str[4:6]), int(date_str[6:8])
                results.append(date(year, month, day))
        return results

    def get_stock_basic_info(self, stock_code: str) -> dict:
        """获取单个股票的基本信息"""
        try:
            provider_symbol = _tushare_symbol(stock_code, DEFAULT_MARKET_TYPE_STOCK)
            df = self.pro.daily(ts_code=provider_symbol)
            if df is None or df.empty:
                return {}
            
            ts_code = str(df.iloc[0].get("ts_code", ""))
            if not ts_code:
                return {}
            
            basic_df = self.pro.stock_basic(ts_code=ts_code)
            if basic_df is None or basic_df.empty:
                return {}
            
            row = basic_df.iloc[0]
            return {
                "stock_code": stock_code,
                "stock_name": row.get("name", ""),
                "industry": row.get("industry", ""),
                "market": ts_code.split(".")[1] if "." in ts_code else "UNKNOWN",
                "list_date": row.get("list_date")
            }
        except Exception as e:
            return {}

    def get_all_stocks_basic_info(self) -> list[dict]:
        """获取所有股票的基本信息"""
        try:
            df = self.pro.stock_basic()
            if df is None or df.empty:
                return []
            
            results = []
            for _, row in df.iterrows():
                ts_code = str(row.get("ts_code", ""))
                if not ts_code or "." not in ts_code:
                    continue
                
                stock_code = ts_code.split(".")[0]
                results.append({
                    "stock_code": stock_code,
                    "stock_name": row.get("name", ""),
                    "industry": row.get("industry", ""),
                    "market": ts_code.split(".")[1],
                    "list_date": row.get("list_date")
                })
            return results
        except Exception as e:
            return []


class JqdataMarketDataProvider(MarketDataProvider):
    name = "jqdata"

    def __init__(self, config: dict[str, Any]):
        self.config = config
        username = config.get("jqdata", {}).get("username")
        password = config.get("jqdata", {}).get("password")
        if not username or not password:
            raise RuntimeError("JQData credentials are missing. Set market_data.jqdata username/password or JQDATA_USERNAME/JQDATA_PASSWORD.")
        self.jqdatasdk = _import_optional("jqdatasdk", "pip install jqdatasdk")
        self.jqdatasdk.auth(username, password)

    def fetch_close(self, trade_date: date, symbol: str, market_type: str) -> MarketCloseData:
        provider_symbol = _index_alias(self.config, self.name, symbol) if market_type == DEFAULT_MARKET_TYPE_INDEX else _jqdata_symbol(symbol, market_type)
        data_frame = self.jqdatasdk.get_price(
            provider_symbol,
            start_date=trade_date,
            end_date=trade_date,
            frequency="daily",
            fields=["open", "close", "high", "low", "volume"],
            panel=False,
        )
        row = _first_record(data_frame)
        return MarketCloseData(
            trade_date=trade_date,
            symbol=symbol,
            market_type=market_type,
            open_price=_number(row.get("open")),
            close_price=_number(row.get("close"), 0.0) or 0.0,
            high_price=_number(row.get("high")),
            low_price=_number(row.get("low")),
            volume=_integer(row.get("volume")),
            source=self.name,
        )


@lru_cache(maxsize=1)
def get_market_data_provider() -> MarketDataProvider:
    config = get_market_data_config()
    provider_name = str(config.get("provider", "demo")).lower()
    if provider_name == "demo":
        return DemoMarketDataProvider()
    if provider_name == "akshare":
        return AkshareMarketDataProvider(config)
    if provider_name == "tushare":
        return TushareMarketDataProvider(config)
    if provider_name in {"jqdata", "joinquant", "jqdatasdk", "聚宽", "巨宽"}:
        return JqdataMarketDataProvider(config)
    raise RuntimeError(f"Unsupported market data provider: {provider_name}")