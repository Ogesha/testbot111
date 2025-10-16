from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from .models import User, ChatLog

async def admins_bootstrap(s: AsyncSession, admin_ids: list[int]):
    if not admin_ids:
        return
    for aid in admin_ids:
        res = await s.execute(select(User).where(User.tg_id == aid))
        u = res.scalar_one_or_none()
        if u is None:
            s.add(User(tg_id=aid, is_admin=True, subscribed=True, accepted_terms=True))
    await s.commit()

async def get_or_create_user(s: AsyncSession, tg_id: int, username: str | None, display_name: str | None):
    res = await s.execute(select(User).where(User.tg_id == tg_id))
    u = res.scalar_one_or_none()
    if u is None:
        u = User(tg_id=tg_id, username=username, display_name=display_name, subscribed=True, accepted_terms=False)
        s.add(u)
        await s.commit()
    return u

async def log_message(s: AsyncSession, tg_id: int, username: str | None, message: str):
    s.add(ChatLog(tg_id=tg_id, username=username, message=message))
    await s.commit()
