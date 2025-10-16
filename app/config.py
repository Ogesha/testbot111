import os, yaml
from dataclasses import dataclass
from typing import List, Dict, Any
from dotenv import load_dotenv

load_dotenv()

@dataclass
class SelectorSet:
    card: List[str]
    title: List[str]
    price: List[str]
    link_from_title: bool = True

@dataclass
class ScrapeConfig:
    urls: list[str]
    daily_time: str
    selectors: SelectorSet

@dataclass
class CategoryConf:
    name: str
    keywords: List[str]

@dataclass
class BroadcastConf:
    autosend_daily_time: str | None
    message_template: str

@dataclass
class AppConfig:
    scrape: ScrapeConfig
    categories: List[CategoryConf]
    broadcast: BroadcastConf
    bot_token: str
    admin_ids: list[int]
    database_url: str
    tz: str
    control_bot_token: str
    control_admin_ids: list[int]

def _read_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_config(yaml_path: str = "config.yaml") -> AppConfig:
    y = _read_yaml(yaml_path)

    bot_token = os.getenv("BOT_TOKEN", "")
    if not bot_token:
        raise RuntimeError("BOT_TOKEN не задан в .env")

    control_bot_token = os.getenv("CONTROL_BOT_TOKEN", "")
    control_admin_ids = [int(x.strip()) for x in os.getenv("CONTROL_ADMINS", "").split(",") if x.strip().isdigit()]
    if not control_bot_token or not control_admin_ids:
        print("[WARN] CONTROL_BOT_TOKEN / CONTROL_ADMINS не заданы — контрольный бот работать не будет.")

    return AppConfig(
        scrape=ScrapeConfig(
            urls=y["scrape"]["urls"],
            daily_time=y["scrape"]["daily_time"],
            selectors=SelectorSet(**y["scrape"]["selectors"])
        ),
        categories=[CategoryConf(**c) for c in y.get("categories", [])],
        broadcast=BroadcastConf(
            autosend_daily_time=y.get("broadcast", {}).get("autosend_daily_time"),
            message_template=y.get("broadcast", {}).get("message_template", "Новости: {count}")
        ),
        bot_token=bot_token,
        admin_ids=[int(x.strip()) for x in os.getenv("ADMIN_IDS","").split(",") if x.strip().isdigit()],
        database_url=os.getenv("DATABASE_URL", "postgresql+asyncpg://shopbot:shopbot@localhost:5432/shopbot"),
        tz=os.getenv("TZ", "UTC"),
        control_bot_token=control_bot_token,
        control_admin_ids=control_admin_ids,
    )
