import pytest
from app.main import P, attempts


@pytest.mark.asyncio
async def test_accept_application_creates_group_atomically(client, setup):
    admin, editor, _, _ = setup
    await client.post(
        P + "/group-requests",
        json={"group_number": "5102", "contacts": "head@example.org"},
    )
    row = (await client.get(P + "/admin/group-requests", headers=admin)).json()[
        "items"
    ][0]
    path = P + f"/admin/group-requests/{row['id']}/accept"
    body = {"name": "5102", "password": "new-group-password", "published": True}
    assert (await client.post(path, json=body)).status_code == 401
    assert (await client.post(path, json=body, headers=editor)).status_code == 403
    # Failed creation leaves the request pending and no partial group.
    assert (
        await client.post(path, json={**body, "name": "4992"}, headers=admin)
    ).status_code == 409
    assert (
        await client.post(path, json={**body, "password": None}, headers=admin)
    ).status_code == 422
    pending = (
        await client.get(P + "/admin/group-requests?status=pending", headers=admin)
    ).json()["items"]
    assert len(pending) == 1
    created = await client.post(path, json=body, headers=admin)
    assert created.status_code == 201
    gid = created.json()["id"]
    assert (await client.post(path, json=body, headers=admin)).status_code == 409
    assert (
        await client.get(P + "/admin/group-requests?status=pending", headers=admin)
    ).json()["items"] == []
    assert (
        len(
            (
                await client.get(
                    P + "/admin/group-requests?status=approved", headers=admin
                )
            ).json()["items"]
        )
        == 1
    )
    assert (
        await client.post(
            P + "/auth/login", json={"group_id": gid, "password": body["password"]}
        )
    ).status_code == 200
    assert any(g["id"] == gid for g in (await client.get(P + "/groups")).json())


@pytest.mark.asyncio
async def test_group_application_privacy_and_processing(client, setup):
    admin, editor, groups, _ = setup
    body = {"group_number": " 5101 ", "contacts": " test@example.org "}
    r = await client.post(P + "/group-requests", json=body)
    assert r.status_code == 202
    assert "test@example.org" not in r.text
    assert (await client.post(P + "/group-requests", json=body)).status_code == 202
    assert (await client.get(P + "/admin/group-requests")).status_code == 401
    assert (
        await client.get(P + "/admin/group-requests", headers=editor)
    ).status_code == 403
    page = (await client.get(P + "/admin/group-requests", headers=admin)).json()
    assert len(page["items"]) == 1
    row = page["items"][0]
    assert row["contacts"] == "test@example.org" and row["group_number"] == "5101"
    assert (
        await client.patch(
            P + f"/admin/group-requests/{row['id']}",
            headers=editor,
            json={"status": "approved"},
        )
    ).status_code == 403
    assert (
        await client.patch(
            P + f"/admin/group-requests/{row['id']}",
            headers=admin,
            json={"status": "approved"},
        )
    ).status_code == 200
    assert (
        await client.get(P + "/admin/group-requests?status=pending", headers=admin)
    ).json()["items"] == []
    assert (
        len((await client.get(P + "/groups")).json()) == 2
    )  # Applying never creates/publishes a group.


@pytest.mark.asyncio
async def test_application_validation_and_rate_limit(client):
    assert (
        await client.post(
            P + "/group-requests",
            json={"group_number": "   ", "contacts": "test@example.org"},
        )
    ).status_code == 422
    assert (
        await client.post(
            P + "/group-requests", json={"group_number": "5101", "contacts": "  "}
        )
    ).status_code == 422
    attempts.clear()
    for n in range(5):
        assert (
            await client.post(
                P + "/group-requests",
                json={"group_number": str(5100 + n), "contacts": "test@example.org"},
            )
        ).status_code == 202
    assert (
        await client.post(
            P + "/group-requests",
            json={"group_number": "5106", "contacts": "test@example.org"},
        )
    ).status_code == 429
