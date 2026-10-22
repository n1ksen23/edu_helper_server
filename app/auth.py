from datetime import datetime, timedelta, timezone
import hashlib, secrets, jwt
from argon2 import PasswordHasher
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select, update
from .config import settings
from .models import Session, Group, db
ph = PasswordHasher()
bearer = HTTPBearer(auto_error=False)
def digest(value): return hashlib.sha256(value.encode()).hexdigest()
def verify(hashed,password):
    try: return ph.verify(hashed,password)
    except Exception: return False
async def issue(database, role, group_id):
    refresh = secrets.token_urlsafe(48)
    s = Session(id=secrets.token_hex(24),role=role,group_id=group_id,refresh_hash=digest(refresh),expires_at=datetime.now(timezone.utc)+timedelta(days=settings.refresh_days))
    database.add(s)
    await database.commit()
    return tokens(s,refresh)
def tokens(s,refresh):
    return {'access_token':jwt.encode({'sid':s.id,'exp':datetime.now(timezone.utc)+timedelta(minutes=settings.access_minutes),'iss':'eduhelper','aud':'eduhelper'},settings.secret_key,algorithm='HS256'),'refresh_token':refresh,'token_type':'bearer','group_id':s.group_id,'role':s.role}
async def principal(credentials: HTTPAuthorizationCredentials = Depends(bearer), database=Depends(db)):
    try:
        if not credentials: raise ValueError()
        payload=jwt.decode(credentials.credentials,settings.secret_key,algorithms=['HS256'],issuer='eduhelper',audience='eduhelper')
        s=await database.get(Session,payload['sid'])
        if not s or s.revoked or s.expires_at.replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc): raise ValueError()
        if s.group_id:
            g=await database.get(Group,s.group_id)
            if not g or not g.active: raise ValueError()
        return s
    except Exception: raise HTTPException(401,'Сессия истекла. Войдите снова')
def authorize(s,group_id):
    if s.role!='admin' and s.group_id!=group_id: raise HTTPException(403,'Нет доступа к этой группе')
async def admin(s=Depends(principal)):
    if s.role!='admin': raise HTTPException(403,'Требуются права администратора')
    return s
async def revoke(database,group_id):
    await database.execute(update(Session).where(Session.group_id==group_id).values(revoked=True))

async def optional_principal(credentials: HTTPAuthorizationCredentials = Depends(bearer), database=Depends(db)):
    if credentials is None: return None
    return await principal(credentials,database)
