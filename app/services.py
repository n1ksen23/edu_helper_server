from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select, tuple_
from .models import Group, Homework, Template, Day, Subgroup

def today(group): return datetime.now(ZoneInfo(group.timezone)).date()
def week_type(group,day):
    offset=((day-timedelta(days=day.weekday()))-group.anchor_monday).days//7
    return group.anchor_week if offset%2==0 else ('upper' if group.anchor_week=='lower' else 'lower')
def slot_time(slot,shortened):
    start=510+(slot-1)*(70 if shortened else 110)+(35 if not shortened and slot>=3 else 0)
    end=start+(60 if shortened else 100)
    return {'start':f'{start//60:02}:{start%60:02}','end':f'{end//60:02}:{end%60:02}'}
async def public_group(database,gid,actor=None):
    g=await database.get(Group,gid)
    if not g: raise HTTPException(404,'Группа не найдена')
    allowed=actor and (actor.role=='admin' or (actor.group_id==gid and g.active))
    if not allowed and (not g.active or not g.published): raise HTTPException(404,'Группа не найдена')
    return g
async def validate_day(database,gid,data,day=None):
    if day and day.weekday()==6 and data.lessons: raise HTTPException(422,'В воскресенье занятия запрещены')
    ids={l.subgroup_id for l in data.lessons if l.subgroup_id is not None}
    if ids:
        found=set((await database.scalars(select(Subgroup.id).where(Subgroup.group_id==gid,Subgroup.id.in_(ids)))).all())
        if ids!=found: raise HTTPException(422,'Подгруппа не принадлежит группе')
async def schedule_range(database,group,start,end,preview=None):
    days=(await database.scalars(select(Day).where(Day.group_id==group.id,Day.date.between(start,end)))).all()
    mapping={d.date:d for d in days}
    subgroups={s.id:s.name for s in await database.scalars(select(Subgroup).where(Subgroup.group_id==group.id))}
    result=[]
    for offset in range((end-start).days+1):
        current=start+timedelta(days=offset); row=mapping.get(current); week=preview or week_type(group,current)
        shortened=row.shortened if row else current.weekday()==5
        lessons=[] if current.weekday()==6 or not row else [l for l in row.lessons if l['week'] in ('both',week)]
        lessons=[{**l,'subgroup_name':subgroups.get(l.get('subgroup_id')),**slot_time(l['slot'],shortened)} for l in sorted(lessons,key=lambda l:l['slot'])]
        result.append({'date':current,'week':week,'shortened':shortened,'lessons':lessons})
    return result
async def homework_page(database,group,archive=False,cursor=None):
    query=select(Homework).where(Homework.group_id==group.id)
    if not archive:
        rows=(await database.scalars(query.where(Homework.due_date>=today(group)).order_by(Homework.due_date,Homework.id))).all()
        return {'items':rows,'next_cursor':None}
    query=query.where(Homework.due_date<today(group))
    if cursor:
        try:
            d,i=cursor.split(':'); d=date.fromisoformat(d); i=int(i)
        except Exception: raise HTTPException(422,'Некорректный курсор')
        query=query.where(tuple_(Homework.due_date,Homework.id)<tuple_(d,i))
    rows=(await database.scalars(query.order_by(Homework.due_date.desc(),Homework.id.desc()).limit(21))).all()
    return {'items':rows[:20],'next_cursor':f'{rows[19].due_date}:{rows[19].id}' if len(rows)>20 else None}
async def put_day(database,gid,day,data):
    await validate_day(database,gid,data,day)
    row=await database.scalar(select(Day).where(Day.group_id==gid,Day.date==day))
    if not row: row=Day(group_id=gid,date=day); database.add(row)
    row.shortened=data.shortened; row.lessons=[l.model_dump() for l in data.lessons]
    return row
