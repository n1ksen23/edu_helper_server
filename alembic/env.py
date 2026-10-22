import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base
from app.config import settings
config=context.config
def run(connection):
    context.configure(connection=connection,target_metadata=Base.metadata)
    with context.begin_transaction(): context.run_migrations()
async def online():
    engine=create_async_engine(settings.database_url)
    async with engine.connect() as conn: await conn.run_sync(run)
    await engine.dispose()
if context.is_offline_mode():
    context.configure(url=settings.database_url,target_metadata=Base.metadata,literal_binds=True)
    with context.begin_transaction(): context.run_migrations()
else: asyncio.run(online())
