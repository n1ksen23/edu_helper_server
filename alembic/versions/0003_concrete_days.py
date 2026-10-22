"""Keep only concrete dated lessons and two fixed subgroup labels.

Downgrade intentionally requires restoring the pre-migration backup: retired
recurrence variants are not the concrete schedule that users actually saw.
"""

from datetime import timedelta
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    meta = sa.MetaData()
    groups = sa.Table("groups", meta, autoload_with=conn)
    days = sa.Table("days", meta, autoload_with=conn)
    subgroups = sa.Table("subgroups", meta, autoload_with=conn)
    group_map = {g.id: g for g in conn.execute(sa.select(groups)).all()}
    subgroup_map = {}
    counts = {}
    for sg in conn.execute(sa.select(subgroups).order_by(subgroups.c.id)).all():
        counts[sg.group_id] = counts.get(sg.group_id, 0) + 1
        label = sg.name.lower().replace(" ", "")
        number = (
            1
            if label in ("пг1", "подгруппа1", "1")
            else 2
            if label in ("пг2", "подгруппа2", "2")
            else counts[sg.group_id]
        )
        subgroup_map[sg.id] = (number if number in (1, 2) else None, sg.name)
    for row in conn.execute(sa.select(days)).all():
        group = group_map[row.group_id]
        monday = row.date - timedelta(days=row.date.weekday())
        same = ((monday - group.anchor_monday).days // 7) % 2 == 0
        week = (
            group.anchor_week
            if same
            else ("upper" if group.anchor_week == "lower" else "lower")
        )
        concrete = []
        for original in row.lessons:
            if row.date.weekday() == 6 or original.get("week", "both") not in (
                "both",
                week,
            ):
                continue
            lesson = {
                k: v
                for k, v in original.items()
                if k not in ("week", "subgroup_name", "start", "end")
            }
            sid = lesson.get("subgroup_id")
            if sid is not None:
                number, label = subgroup_map.get(
                    sid, (sid if sid in (1, 2) else None, str(sid))
                )
                lesson["subgroup_id"] = number
                if number is None:
                    lesson["subject"] += " (" + label + ")"
            concrete.append(lesson)
        conn.execute(
            sa.update(days).where(days.c.id == row.id).values(lessons=concrete)
        )
    op.drop_table("templates")
    op.drop_table("subgroups")


def downgrade():
    raise RuntimeError(
        "Restore the pre-0003 database backup to recover the retired schema"
    )
