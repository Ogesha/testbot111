import asyncio
from app.config import load_config
from app.db import init_engine
from app.mainbot_runtime import MainBotManager

async def main():
    cfg = load_config()
    init_engine(cfg.database_url)
    manager = MainBotManager(cfg)
    await manager.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
