from datetime import date
import pytest
from sqlalchemy import select, func
from app.models import SessionLocal, Homework, Day
from app.main import P


@pytest.mark.asyncio
async def test_today_boundary_sql_and_dates(client, setup, monkeypatch):
    import app.services as services

    admin, editor, g, e = setup
    monkeypatch.setattr(services, "today", lambda group: date(2026, 10, 22))
    for d in ["2026-10-21", "2026-10-22", "2026-10-23"]:
        await client.post(
            f"{P}/groups/{g[0]}/homework",
            headers=editor,
            json={"subject": "X", "text": "X", "due_date": d},
        )
    active = (await client.get(f"{P}/groups/{g[0]}/homework")).json()["items"]
    archive = (await client.get(f"{P}/groups/{g[0]}/homework?archive=true")).json()[
        "items"
    ]
    assert [h["due_date"] for h in active] == ["2026-10-22", "2026-10-23"]
    assert [h["due_date"] for h in archive] == ["2026-10-21"]
    await client.put(
        f"{P}/groups/{g[0]}/days/2026-10-22",
        headers=editor,
        json={"shortened": True, "lessons": []},
    )
    assert (await client.get(f"{P}/groups/{g[0]}/homework")).json()["items"] == active


@pytest.mark.asyncio
async def test_unique_days_copy_and_hidden_admin(client, setup):
    admin, editor, g, e = setup
    body = {
        "shortened": True,
        "lessons": [
            {"slot": 1, "subject": "A", "subgroup_id": 1},
            {"slot": 1, "subject": "B", "subgroup_id": 2},
        ],
    }
    assert (
        await client.put(
            f"{P}/groups/{g[0]}/days/2026-10-24", headers=editor, json=body
        )
    ).status_code == 200
    assert (
        await client.post(
            f"{P}/groups/{g[0]}/days/2026-10-24/repeat",
            headers=editor,
            json={"start": "2026-10-31", "weeks": 2},
        )
    ).status_code == 200
    rows = (
        await client.get(f"{P}/groups/{g[0]}/calendar?start=2026-10-24&end=2026-11-07")
    ).json()
    assert rows[0]["week"] != rows[7]["week"]
    assert rows[0]["lessons"] == rows[7]["lessons"] == rows[14]["lessons"]
    changed = {"shortened": False, "lessons": [{"slot": 2, "subject": "Unique change"}]}
    await client.put(f"{P}/groups/{g[0]}/days/2026-10-31", headers=editor, json=changed)
    rows = (
        await client.get(f"{P}/groups/{g[0]}/calendar?start=2026-10-24&end=2026-11-07")
    ).json()
    assert rows[0]["lessons"][0]["subject"] == "A"
    assert rows[7]["lessons"][0]["subject"] == "Unique change"
    assert rows[14]["lessons"][0]["subject"] == "A"
    assert (
        await client.get(f"{P}/groups/{g[0]}/templates/6", headers=editor)
    ).status_code == 404
    assert (
        await client.post(
            f"{P}/groups/{g[0]}/subgroups", headers=editor, json={"name": "Пг 3"}
        )
    ).status_code == 405
    assert (
        await client.get(f"{P}/groups/{g[2]}/homework", headers=admin)
    ).status_code == 200
    assert (
        await client.get(f"{P}/groups/{g[2]}/homework", headers=editor)
    ).status_code == 404
    assert (
        await client.put(
            f"{P}/admin/groups/{g[0]}",
            headers=admin,
            json={"name": "4992", "active": False},
        )
    ).status_code == 200
    assert (await client.get(f"{P}/groups/{g[0]}")).status_code == 404
    assert (
        await client.get(f"{P}/groups/{g[0]}/days/2026-10-24", headers=editor)
    ).status_code == 401


@pytest.mark.asyncio
async def test_import_idempotent(client, monkeypatch):
    from app.import_legacy import main

    monkeypatch.setenv("IMPORT_GROUP_PASSWORD", "migration-password-123")
    await main()
    async with SessionLocal() as db:
        h = await db.scalar(select(Homework).limit(1))
        h.text = "Edited after import"
        await db.commit()
    await main()
    async with SessionLocal() as db:
        assert await db.scalar(select(func.count(Homework.id))) == 7
        assert await db.scalar(select(func.count(Day.id))) == 108
        assert (
            await db.scalar(select(Homework).order_by(Homework.id))
        ).text == "Edited after import"
