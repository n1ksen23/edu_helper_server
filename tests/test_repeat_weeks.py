import pytest
from app.main import P


@pytest.mark.asyncio
async def test_alternating_week_copies_are_independent_and_preserve_dates(
    client, setup
):
    _, editor, groups, _ = setup
    base = f"{P}/groups/{groups[0]}"
    upper = {
        "shortened": True,
        "lessons": [{"slot": 1, "subject": "Upper", "subgroup_id": 1}],
    }
    lower = {"lessons": [{"slot": 2, "subject": "Lower", "subgroup_id": 2}]}
    for date, payload in [
        ("2026-10-19", upper),
        ("2026-10-20", {"lessons": []}),
        ("2026-10-26", lower),
        ("2026-11-02", lower),
    ]:
        assert (
            await client.put(f"{base}/days/{date}", headers=editor, json=payload)
        ).status_code == 200
    path = f"{base}/weeks/2026-10-19/repeat"
    body = {"start": "2026-11-02", "weeks": 2, "interval_weeks": 2, "overwrite": False}
    assert (await client.post(path, json=body)).status_code == 401
    response = await client.post(path, headers=editor, json=body)
    assert response.status_code == 200
    assert response.json() == {"count": 3, "skipped": 1}

    async def day(d):
        return (await client.get(f"{base}/days/{d}", headers=editor)).json()

    assert (await day("2026-11-02"))["lessons"][0]["subject"] == "Lower"
    assert (await day("2026-11-16"))["lessons"][0]["subject"] == "Upper"
    assert (await day("2026-11-16"))["shortened"] is True
    await client.put(f"{base}/days/2026-11-16", headers=editor, json=lower)
    assert (await day("2026-10-19"))["lessons"][0]["subject"] == "Upper"
    # Intervening lower week is untouched; no implicit lessons on unsaved source days.
    assert (await day("2026-10-26"))["lessons"][0]["subject"] == "Lower"
    assert (await day("2026-11-04"))["lessons"] == []
    assert (
        await client.post(path, headers=editor, json={**body, "overwrite": True})
    ).json() == {"count": 4, "skipped": 0}
    assert (await day("2026-11-02"))["lessons"][0]["subject"] == "Upper"
    assert (
        await client.post(path, headers=editor, json={**body, "start": "2026-11-03"})
    ).status_code == 422
    assert (
        await client.post(path, headers=editor, json={**body, "interval_weeks": 3})
    ).status_code == 422
    # The day action supports the same two-week cadence.
    response = await client.post(
        f"{base}/days/2026-10-19/repeat",
        headers=editor,
        json={
            "start": "2027-02-01",
            "weeks": 2,
            "interval_weeks": 2,
            "overwrite": False,
        },
    )
    assert response.json() == {"count": 2, "skipped": 0}
    assert (await day("2027-02-15"))["lessons"][0]["subject"] == "Upper"
    assert (await day("2027-02-08"))["lessons"] == []
