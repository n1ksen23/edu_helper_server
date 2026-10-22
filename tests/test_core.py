from datetime import date
from types import SimpleNamespace
import pytest
from app.services import week_type, slot_time
from app.main import P


def test_week_new_year():
    g = SimpleNamespace(anchor_monday=date(2026, 12, 28), anchor_week="upper")
    assert week_type(g, date(2027, 1, 3)) == "upper"
    assert week_type(g, date(2027, 1, 4)) == "lower"
    assert week_type(g, date(2026, 12, 21)) == "lower"


@pytest.mark.parametrize(
    "slot,short,start,end",
    [
        (1, False, "08:30", "10:10"),
        (3, False, "12:45", "14:25"),
        (6, False, "18:15", "19:55"),
        (3, True, "10:50", "11:50"),
        (6, True, "14:20", "15:20"),
        (7, True, "15:30", "16:30"),
    ],
)
def test_times(slot, short, start, end):
    assert slot_time(slot, short) == {"start": start, "end": end}


@pytest.mark.asyncio
async def test_permissions_password_revoke(client, setup):
    admin, editor, g, e = setup
    assert len((await client.get(P + "/groups")).json()) == 2
    assert (await client.get(f"{P}/groups/{g[2]}")).status_code == 404
    body = {"subject": "Math", "text": "Task", "due_date": "2026-11-01"}
    assert (
        await client.post(f"{P}/groups/{g[0]}/homework", json=body)
    ).status_code == 401
    assert (
        await client.post(f"{P}/groups/{g[1]}/homework", headers=editor, json=body)
    ).status_code == 403
    assert (await client.get(P + "/admin/groups", headers=editor)).status_code == 403
    assert (
        await client.put(
            f"{P}/admin/groups/{g[0]}",
            headers=admin,
            json={"name": "4992", "password": "new-password-123", "published": True},
        )
    ).status_code == 200
    assert (
        await client.post(f"{P}/groups/{g[0]}/homework", headers=editor, json=body)
    ).status_code == 401
    assert (
        await client.post(
            P + "/auth/refresh", json={"refresh_token": e["refresh_token"]}
        )
    ).status_code == 401


@pytest.mark.asyncio
async def test_archive_calendar_and_isolation(client, setup):
    admin, editor, g, e = setup
    for i in range(45):
        r = await client.post(
            f"{P}/groups/{g[0]}/homework",
            headers=editor,
            json={"subject": "Math", "text": str(i), "due_date": "2020-01-05"},
        )
        assert r.status_code == 201
    for i in range(25):
        await client.post(
            f"{P}/groups/{g[0]}/homework",
            headers=editor,
            json={"subject": "Future", "text": str(i), "due_date": "2099-01-04"},
        )
    assert len((await client.get(f"{P}/groups/{g[0]}/homework")).json()["items"]) == 25
    ids = []
    cursor = None
    while True:
        page = (
            await client.get(
                f"{P}/groups/{g[0]}/homework",
                params={"archive": True, **({"cursor": cursor} if cursor else {})},
            )
        ).json()
        ids.extend(h["id"] for h in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(ids) == len(set(ids)) == 45
    cal = (
        await client.get(f"{P}/groups/{g[0]}/calendar?start=2020-01-05&end=2020-01-05")
    ).json()
    assert len(cal[0]["homework"]) == 45 and cal[0]["lessons"] == []
    assert (await client.get(f"{P}/groups/{g[1]}/homework")).json()["items"] == []
    assert (
        await client.put(
            f"{P}/groups/{g[1]}/homework/{ids[0]}",
            headers=admin,
            json={"subject": "X", "text": "X", "due_date": "2027-01-01"},
        )
    ).status_code == 404


@pytest.mark.asyncio
async def test_schedule_repeat_parallel_sunday(client, setup):
    admin, editor, g, e = setup
    sid = (
        await client.post(
            f"{P}/groups/{g[0]}/subgroups", headers=editor, json={"name": "Пг 1"}
        )
    ).json()["id"]
    sid2 = (
        await client.post(
            f"{P}/groups/{g[0]}/subgroups", headers=editor, json={"name": "Пг 2"}
        )
    ).json()["id"]
    body = {
        "shortened": True,
        "lessons": [
            {"slot": 6, "subject": "A", "subgroup_id": sid},
            {"slot": 6, "subject": "B", "subgroup_id": sid2},
        ],
    }
    assert (
        await client.put(
            f"{P}/groups/{g[0]}/days/2026-10-24", headers=editor, json=body
        )
    ).status_code == 200
    assert (
        await client.put(
            f"{P}/groups/{g[0]}/days/2026-10-25", headers=editor, json=body
        )
    ).status_code == 422
    assert (
        await client.post(
            f"{P}/groups/{g[0]}/days/2026-10-24/repeat",
            headers=editor,
            json={"start": "2026-10-31", "weeks": 3},
        )
    ).status_code == 200
    rows = (
        await client.get(f"{P}/groups/{g[0]}/calendar?start=2026-10-31&end=2026-11-14")
    ).json()
    assert len(rows[0]["lessons"]) == 2 and rows[0]["lessons"][0]["start"] == "14:20"
    assert rows[1]["lessons"] == [] and len(rows[14]["lessons"]) == 2
    assert (
        await client.delete(f"{P}/groups/{g[0]}/subgroups/{sid}", headers=editor)
    ).status_code == 409
    body["lessons"][0]["subgroup_id"] = 999
    assert (
        await client.put(
            f"{P}/groups/{g[0]}/days/2026-10-24", headers=editor, json=body
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_refresh_rotation(client, setup):
    _, _, _, e = setup
    r = await client.post(
        P + "/auth/refresh", json={"refresh_token": e["refresh_token"]}
    )
    assert r.status_code == 200
    assert r.json()["refresh_token"] != e["refresh_token"]
    assert (
        await client.post(
            P + "/auth/refresh", json={"refresh_token": e["refresh_token"]}
        )
    ).status_code == 401
