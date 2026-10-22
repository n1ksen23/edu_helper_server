"""Repeatable import into concrete dates. Never overwrites subsequent edits."""

import asyncio, json, os
from pathlib import Path
from datetime import date, timedelta
from sqlalchemy import select
from .models import SessionLocal, Group, Homework, Day
from .auth import ph
from .schemas import DayIn


async def main():
    schedule = json.loads(Path("legacy/schedule.json").read_text(encoding="utf-8"))
    homework = json.loads(Path("legacy/data.json").read_text(encoding="utf-8"))
    async with SessionLocal() as db:
        group = await db.scalar(select(Group).where(Group.name == "4992"))
        if not group:
            password = os.environ.get("IMPORT_GROUP_PASSWORD")
            if not password or len(password) < 12:
                raise RuntimeError("Set IMPORT_GROUP_PASSWORD (12+ characters)")
            group = Group(
                name="4992",
                published=True,
                active=True,
                password_hash=ph.hash(password),
                anchor_monday=date.fromisoformat(schedule["anchorMonday"]),
                anchor_week=schedule["anchorWeek"],
                timezone="Europe/Moscow",
            )
            db.add(group)
            await db.flush()
        for h in homework:
            if not await db.scalar(
                select(Homework.id).where(
                    Homework.group_id == group.id, Homework.legacy_id == str(h["id"])
                )
            ):
                db.add(
                    Homework(
                        group_id=group.id,
                        legacy_id=str(h["id"]),
                        subject=h["subject"],
                        text=h["task"],
                        due_date=date.fromisoformat(h["due"]),
                    )
                )
        for n in range(18):
            for weekday in range(1, 7):
                day = group.anchor_monday + timedelta(days=weekday - 1, weeks=n)
                if await db.scalar(
                    select(Day.id).where(Day.group_id == group.id, Day.date == day)
                ):
                    continue
                # Preserve the original import's dated lessons, independently of
                # the automatic academic-year labels used by the live calendar.
                offset = (day - group.anchor_monday).days // 7
                week = (
                    group.anchor_week
                    if offset % 2 == 0
                    else ("upper" if group.anchor_week == "lower" else "lower")
                )
                lessons = [
                    {k: v for k, v in l.items() if k not in ("day", "week")}
                    for l in schedule["lessons"]
                    if l["day"] == weekday and l.get("week", "both") in ("both", week)
                ]
                data = DayIn(shortened=weekday == 6, lessons=lessons)
                db.add(
                    Day(
                        group_id=group.id,
                        date=day,
                        shortened=data.shortened,
                        lessons=[l.model_dump() for l in data.lessons],
                    )
                )
        await db.commit()
        print(
            f"Imported group {group.id}: {len(homework)} homework records; concrete dated schedule preserved"
        )


if __name__ == "__main__":
    asyncio.run(main())
