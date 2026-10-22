"""Initial relational schema."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None
def upgrade():
    op.create_table('groups',sa.Column('id',sa.Integer,primary_key=True),sa.Column('name',sa.String(100),nullable=False,unique=True),sa.Column('published',sa.Boolean,nullable=False),sa.Column('active',sa.Boolean,nullable=False),sa.Column('password_hash',sa.Text,nullable=False),sa.Column('timezone',sa.String(80),nullable=False),sa.Column('anchor_monday',sa.Date,nullable=False),sa.Column('anchor_week',sa.String(5),nullable=False))
    op.create_table('subgroups',sa.Column('id',sa.Integer,primary_key=True),sa.Column('group_id',sa.Integer,sa.ForeignKey('groups.id',ondelete='CASCADE'),nullable=False),sa.Column('name',sa.String(100),nullable=False),sa.UniqueConstraint('group_id','name'))
    op.create_index('ix_subgroups_group_id','subgroups',['group_id'])
    op.create_table('homework',sa.Column('id',sa.Integer,primary_key=True),sa.Column('group_id',sa.Integer,sa.ForeignKey('groups.id',ondelete='CASCADE'),nullable=False),sa.Column('subject',sa.String(300),nullable=False),sa.Column('text',sa.Text,nullable=False),sa.Column('due_date',sa.Date,nullable=False),sa.Column('legacy_id',sa.String(100)),sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint('group_id','legacy_id'))
    op.create_index('ix_homework_group_due_id','homework',['group_id','due_date','id'])
    for table,key,kind in [('templates','weekday',sa.Integer),('days','date',sa.Date)]:
        args=[sa.Column('id',sa.Integer,primary_key=True),sa.Column('group_id',sa.Integer,sa.ForeignKey('groups.id',ondelete='CASCADE'),nullable=False),sa.Column(key,kind,nullable=False),sa.Column('shortened',sa.Boolean,nullable=False),sa.Column('lessons',sa.JSON,nullable=False),sa.UniqueConstraint('group_id',key)]
        if table=='templates': args.append(sa.CheckConstraint('weekday BETWEEN 1 AND 6'))
        op.create_table(table,*args)
    op.create_table('sessions',sa.Column('id',sa.String(64),primary_key=True),sa.Column('group_id',sa.Integer,sa.ForeignKey('groups.id',ondelete='CASCADE')),sa.Column('role',sa.String(10),nullable=False),sa.Column('refresh_hash',sa.String(64),nullable=False),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('revoked',sa.Boolean,nullable=False))
    op.create_index('ix_sessions_group_id','sessions',['group_id'])
def downgrade():
    for table in ['sessions','days','templates','homework','subgroups','groups']: op.drop_table(table)
