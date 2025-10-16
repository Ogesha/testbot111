from sqlalchemy.ext.asyncio import (
    create_async_engine, async_sessionmaker, AsyncEngine, AsyncSession
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

_engine: AsyncEngine | None = None
Session: async_sessionmaker[AsyncSession] | None = None
_db_url: str | None = None

def init_engine(db_url: str):
    """Явная инициализация движка/сессии (однократная)."""
    global _engine, Session, _db_url
    if _engine is not None:
        return _engine, Session

    _engine = create_async_engine(
        db_url,
        echo=False,
        future=True,
        pool_pre_ping=True,  # проверка соединения перед выдачей из пула
        pool_recycle=900,  # рецикл раз в 15 мин
        pool_size=10,
        max_overflow=20,
        connect_args={  # улучшаем поведение asyncpg
            "timeout": 10,  # таймаут установления соединения
            "command_timeout": 60,  # таймаут команд
            # "statement_cache_size": 0,  # если вдруг глючит кэш (обычно не нужно)
        },
    )

    Session = async_sessionmaker(_engine, expire_on_commit=False)
    _db_url = db_url
    return _engine, Session

def _lazy_init_if_needed():
    global _engine, Session
    if Session is None or _engine is None:
        from .config import load_config
        cfg = load_config()
        init_engine(cfg.database_url)

def get_sessionmaker():
    _lazy_init_if_needed()
    if Session is None:
        raise RuntimeError("Session не инициализирован")
    return Session

def get_engine():
    _lazy_init_if_needed()
    if _engine is None:
        raise RuntimeError("Engine не инициализирован")
    return _engine
