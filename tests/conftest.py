import os
os.environ['DATABASE_URL']='sqlite+aiosqlite://'
os.environ['SECRET_KEY']='test-key-with-at-least-thirty-two-characters'
from argon2 import PasswordHasher
os.environ['ADMIN_PASSWORD_HASH']=PasswordHasher().hash('administrator-password')
import pytest,pytest_asyncio
from httpx import AsyncClient,ASGITransport
from app.main import app,attempts
from app.models import Base,engine
@pytest_asyncio.fixture
async def client():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    attempts.clear()
    async with AsyncClient(transport=ASGITransport(app=app),base_url='https://test') as c: yield c
@pytest_asyncio.fixture
async def setup(client):
    a=(await client.post('/api/v1/auth/login',json={'password':'administrator-password'})).json()
    admin={'Authorization':'Bearer '+a['access_token']}
    groups=[]
    for name in ['4992','5000','hidden']:
        r=await client.post('/api/v1/admin/groups',headers=admin,json={'name':name,'password':'group-password-123','published':name!='hidden'})
        assert r.status_code==201,r.text
        groups.append(r.json()['id'])
    e=(await client.post('/api/v1/auth/login',json={'password':'group-password-123','group_id':groups[0]})).json()
    return admin,{'Authorization':'Bearer '+e['access_token']},groups,e
