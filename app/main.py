from datetime import date, datetime, timedelta, timezone
from collections import defaultdict, deque
import secrets
from fastapi import FastAPI, Depends, HTTPException, Request, Query
from fastapi.responses import FileResponse
from fastapi.encoders import jsonable_encoder
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, delete
from .models import db, Group, Homework, Template, Subgroup, Session
from .schemas import GroupIn, Login, Refresh, HomeworkIn, DayIn, Repeat, NameIn
from .auth import ph, verify, issue, principal, admin, authorize, revoke, digest, tokens
from .config import settings
from .services import public_group, homework_page, schedule_range, put_day, validate_day
app=FastAPI(title='EduHelper',version='1.0.0')
P='/api/v1'
attempts=defaultdict(deque)
@app.middleware('http')
async def security(request:Request, call_next):
    if request.url.path==P+'/auth/login':
        key=request.client.host; queue=attempts[key]; now=datetime.now().timestamp()
        while queue and queue[0]<now-60: queue.popleft()
        if len(queue)>=10:
            from fastapi.responses import JSONResponse
            return JSONResponse({'detail':'Слишком много попыток. Повторите через минуту'},status_code=429)
        queue.append(now)
        if len(attempts)>10000:
            for old in list(attempts):
                if not attempts[old] or attempts[old][-1]<now-60: attempts.pop(old,None)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['Cache-Control']='no-store'
    return response
@app.get(P+'/health')
async def health(database=Depends(db)):
    from sqlalchemy import text
    await database.execute(text('SELECT 1'))
    return {'status':'ok'}
@app.post(P+'/auth/login')
async def login(data:Login,database=Depends(db)):
    if data.group_id is None:
        if not verify(settings.admin_password_hash,data.password): raise HTTPException(401,'Неверный пароль')
        return await issue(database,'admin',None)
    g=await database.get(Group,data.group_id)
    if not g or not g.active or not verify(g.password_hash,data.password): raise HTTPException(401,'Неверный пароль')
    return await issue(database,'editor',g.id)
@app.post(P+'/auth/refresh')
async def refresh(data:Refresh,database=Depends(db)):
    s=await database.scalar(select(Session).where(Session.refresh_hash==digest(data.refresh_token)).with_for_update())
    if not s or s.revoked or s.expires_at.replace(tzinfo=timezone.utc)<=datetime.now(timezone.utc): raise HTTPException(401,'Сессия истекла')
    if s.group_id:
        g=await database.get(Group,s.group_id)
        if not g or not g.active: raise HTTPException(401,'Группа отключена')
    new=secrets.token_urlsafe(48); s.refresh_hash=digest(new); await database.commit()
    return tokens(s,new)
@app.post(P+'/auth/logout',status_code=204)
async def logout(s=Depends(principal),database=Depends(db)):
    current=await database.get(Session,s.id); current.revoked=True; await database.commit()
def group_out(g):
    return {k:getattr(g,k) for k in ('id','name','published','active','timezone','anchor_monday','anchor_week')}
@app.get(P+'/groups')
async def groups(q:str=Query('',max_length=100),database=Depends(db)):
    rows=await database.scalars(select(Group).where(Group.published==True,Group.active==True,Group.name.contains(q,autoescape=True)).order_by(Group.name))
    return [group_out(g) for g in rows]
@app.get(P+'/groups/{gid}')
async def group(gid:int,database=Depends(db)): return group_out(await public_group(database,gid))
@app.get(P+'/admin/groups',dependencies=[Depends(admin)])
async def admin_groups(database=Depends(db)): return [group_out(g) for g in await database.scalars(select(Group).order_by(Group.name))]
@app.post(P+'/admin/groups',dependencies=[Depends(admin)],status_code=201)
async def create_group(data:GroupIn,database=Depends(db)):
    if not data.password: raise HTTPException(422,'Укажите пароль длиной от 12 символов')
    if await database.scalar(select(Group.id).where(Group.name==data.name)): raise HTTPException(409,'Такая группа уже существует')
    g=Group(**data.model_dump(exclude={'password'}),password_hash=ph.hash(data.password)); database.add(g); await database.commit(); return group_out(g)
@app.put(P+'/admin/groups/{gid}',dependencies=[Depends(admin)])
async def update_group(gid:int,data:GroupIn,database=Depends(db)):
    g=await database.get(Group,gid)
    if not g: raise HTTPException(404,'Группа не найдена')
    duplicate=await database.scalar(select(Group.id).where(Group.name==data.name,Group.id!=gid))
    if duplicate: raise HTTPException(409,'Такая группа уже существует')
    for k,v in data.model_dump(exclude={'password'}).items(): setattr(g,k,v)
    if data.password: g.password_hash=ph.hash(data.password)
    if data.password or not data.active: await revoke(database,gid)
    await database.commit(); return group_out(g)
@app.post(P+'/admin/groups/{gid}/revoke',dependencies=[Depends(admin)],status_code=204)
async def revoke_sessions(gid:int,database=Depends(db)): await revoke(database,gid); await database.commit()
@app.get(P+'/groups/{gid}/homework')
async def homework(gid:int,archive:bool=False,cursor:str|None=None,database=Depends(db)):
    return jsonable_encoder(await homework_page(database,await public_group(database,gid),archive,cursor))
@app.post(P+'/groups/{gid}/homework',status_code=201)
async def add_homework(gid:int,data:HomeworkIn,s=Depends(principal),database=Depends(db)):
    authorize(s,gid)
    if not await database.get(Group,gid): raise HTTPException(404,'Группа не найдена')
    row=Homework(group_id=gid,**data.model_dump()); database.add(row); await database.commit(); return jsonable_encoder(row)
async def owned_homework(database,gid,hid):
    row=await database.scalar(select(Homework).where(Homework.id==hid,Homework.group_id==gid))
    if not row: raise HTTPException(404,'Задание не найдено')
    return row
@app.put(P+'/groups/{gid}/homework/{hid}')
async def edit_homework(gid:int,hid:int,data:HomeworkIn,s=Depends(principal),database=Depends(db)):
    authorize(s,gid); row=await owned_homework(database,gid,hid)
    for k,v in data.model_dump().items(): setattr(row,k,v)
    await database.commit(); return jsonable_encoder(row)
@app.delete(P+'/groups/{gid}/homework/{hid}',status_code=204)
async def delete_homework(gid:int,hid:int,s=Depends(principal),database=Depends(db)):
    authorize(s,gid); await database.delete(await owned_homework(database,gid,hid)); await database.commit()
@app.get(P+'/groups/{gid}/calendar')
async def calendar(gid:int,start:date,end:date,preview:str|None=Query(None,pattern='^(upper|lower)$'),database=Depends(db)):
    if end<start or (end-start).days>92: raise HTTPException(422,'Диапазон должен быть от 1 до 93 дней')
    g=await public_group(database,gid)
    days=await schedule_range(database,g,start,end,preview)
    hw=(await database.scalars(select(Homework).where(Homework.group_id==gid,Homework.due_date.between(start,end)).order_by(Homework.due_date,Homework.id))).all()
    for day in days: day['homework']=[h for h in hw if h.due_date==day['date']]
    return jsonable_encoder(days)
@app.put(P+'/groups/{gid}/days/{day}')
async def save_day(gid:int,day:date,data:DayIn,s=Depends(principal),database=Depends(db)):
    authorize(s,gid); row=await put_day(database,gid,day,data); await database.commit(); return jsonable_encoder(row)
@app.post(P+'/groups/{gid}/days/{day}/repeat')
async def repeat_day(gid:int,day:date,data:Repeat,s=Depends(principal),database=Depends(db)):
    from .models import Day
    authorize(s,gid)
    source=await database.scalar(select(Day).where(Day.group_id==gid,Day.date==day))
    if not source: raise HTTPException(404,'Сначала сохраните расписание дня')
    if data.start.weekday()!=day.weekday(): raise HTTPException(422,'Выберите тот же день недели')
    payload=DayIn(shortened=source.shortened,lessons=source.lessons)
    for n in range(data.weeks): await put_day(database,gid,data.start+timedelta(weeks=n),payload)
    await database.commit(); return {'count':data.weeks}
@app.get(P+'/groups/{gid}/templates/{weekday}')
async def get_template(gid:int,weekday:int,s=Depends(principal),database=Depends(db)):
    authorize(s,gid)
    row=await database.scalar(select(Template).where(Template.group_id==gid,Template.weekday==weekday))
    return jsonable_encoder(row) if row else {'shortened':weekday==6,'lessons':[]}
@app.put(P+'/groups/{gid}/templates/{weekday}')
async def save_template(gid:int,weekday:int,data:DayIn,s=Depends(principal),database=Depends(db)):
    authorize(s,gid)
    if weekday not in range(1,7): raise HTTPException(422,'День недели должен быть от 1 до 6')
    await validate_day(database,gid,data)
    row=await database.scalar(select(Template).where(Template.group_id==gid,Template.weekday==weekday))
    if not row: row=Template(group_id=gid,weekday=weekday); database.add(row)
    row.shortened=data.shortened; row.lessons=[l.model_dump() for l in data.lessons]; await database.commit(); return jsonable_encoder(row)
@app.post(P+'/groups/{gid}/templates/{weekday}/repeat')
async def repeat_template(gid:int,weekday:int,data:Repeat,s=Depends(principal),database=Depends(db)):
    authorize(s,gid)
    row=await database.scalar(select(Template).where(Template.group_id==gid,Template.weekday==weekday))
    if not row: raise HTTPException(404,'Шаблон не найден')
    if data.start.isoweekday()!=weekday: raise HTTPException(422,'День недели не совпадает')
    for n in range(data.weeks): await put_day(database,gid,data.start+timedelta(weeks=n),DayIn(shortened=row.shortened,lessons=row.lessons))
    await database.commit(); return {'count':data.weeks}
@app.get(P+'/groups/{gid}/subgroups')
async def subgroups(gid:int,database=Depends(db)):
    await public_group(database,gid)
    return jsonable_encoder((await database.scalars(select(Subgroup).where(Subgroup.group_id==gid).order_by(Subgroup.id))).all())
@app.post(P+'/groups/{gid}/subgroups',status_code=201)
async def add_subgroup(gid:int,data:NameIn,s=Depends(principal),database=Depends(db)):
    authorize(s,gid)
    if await database.scalar(select(Subgroup.id).where(Subgroup.group_id==gid,Subgroup.name==data.name)): raise HTTPException(409,'Подгруппа уже существует')
    row=Subgroup(group_id=gid,name=data.name); database.add(row); await database.commit(); return jsonable_encoder(row)
@app.put(P+'/groups/{gid}/subgroups/{sid}')
async def edit_subgroup(gid:int,sid:int,data:NameIn,s=Depends(principal),database=Depends(db)):
    authorize(s,gid); row=await database.get(Subgroup,sid)
    if not row or row.group_id!=gid: raise HTTPException(404,'Подгруппа не найдена')
    duplicate=await database.scalar(select(Subgroup.id).where(Subgroup.group_id==gid,Subgroup.name==data.name,Subgroup.id!=sid))
    if duplicate: raise HTTPException(409,'Подгруппа уже существует')
    row.name=data.name; await database.commit(); return jsonable_encoder(row)
@app.delete(P+'/groups/{gid}/subgroups/{sid}',status_code=204)
async def delete_subgroup(gid:int,sid:int,s=Depends(principal),database=Depends(db)):
    from .models import Day
    authorize(s,gid); row=await database.get(Subgroup,sid)
    if not row or row.group_id!=gid: raise HTTPException(404,'Подгруппа не найдена')
    for model in (Day,Template):
        for day in await database.scalars(select(model).where(model.group_id==gid)):
            if any(l.get('subgroup_id')==sid for l in day.lessons): raise HTTPException(409,'Подгруппа используется в расписании')
    await database.delete(row); await database.commit()
app.mount('/admin',StaticFiles(directory='admin',html=True),name='admin')
@app.get(P+'/groups/{gid}/days/{day}')
async def raw_day(gid:int,day:date,s=Depends(principal),database=Depends(db)):
    from .models import Day
    authorize(s,gid)
    row=await database.scalar(select(Day).where(Day.group_id==gid,Day.date==day))
    return jsonable_encoder(row) if row else {'date':day,'shortened':day.weekday()==5,'lessons':[]}
