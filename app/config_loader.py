import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.config import CONFIG_FILE


DEFAULT_APP_CONFIG: dict[str, Any] = {
    "market_data": {
        "provider": "demo",
        "index_aliases": {
            "CSI300": {
                "akshare": "000300",
                "tushare": "000300.SH",
                "jqdata": "000300.XSHG",
            },
            "SZ50": {
                "akshare": "000016",
                "tushare": "000016.SH",
                "jqdata": "000016.XSHG",
            },
            "SSE": {
                "akshare": "000001",
                "tushare": "000001.SH",
                "jqdata": "000001.XSHG",
            },
        },
        "akshare": {"adjust": ""},
        "tushare": {"token": ""},
        "jqdata": {"username": "", "password": ""},
    }
}


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def load_app_config() -> dict[str, Any]:
    config_path = Path(CONFIG_FILE)
    config = DEFAULT_APP_CONFIG
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file_obj:
            loaded = yaml.safe_load(file_obj) or {}
        if not isinstance(loaded, dict):
            raise RuntimeError(f"Invalid YAML config: {config_path}")
        config = _deep_merge(config, loaded)

    market_data = config.setdefault("market_data", {})
    if os.getenv("MARKET_DATA_PROVIDER"):
        market_data["provider"] = os.getenv("MARKET_DATA_PROVIDER")
    market_data.setdefault("tushare", {})["token"] = os.getenv(
        "TUSHARE_TOKEN",
        market_data.get("tushare", {}).get("token", ""),
    )
    market_data.setdefault("jqdata", {})["username"] = os.getenv(
        "JQDATA_USERNAME",
        market_data.get("jqdata", {}).get("username", ""),
    )
    market_data.setdefault("jqdata", {})["password"] = os.getenv(
        "JQDATA_PASSWORD",
        market_data.get("jqdata", {}).get("password", ""),
    )
    return config


def get_market_data_config() -> dict[str, Any]:
    return load_app_config().get("market_data", {})
