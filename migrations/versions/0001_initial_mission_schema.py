"""Initial mission, AOI and job schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create PostgreSQL enum types explicitly below.  ``create_type=False`` is
    # essential because SQLAlchemy otherwise attempts a second CREATE TYPE when
    # the table is created, which fails on databases initialized by create_all().
    mission_status = sa.Enum("DRAFT", "QUEUED", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="missionstatus", create_type=False)
    job_status = sa.Enum("PENDING", "RUNNING", "COMPLETED", "FAILED", "CANCELLED", name="jobstatus", create_type=False)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        mission_status.create(bind, checkfirst=True)
        job_status.create(bind, checkfirst=True)
    inspector = sa.inspect(bind)
    if not inspector.has_table("missions"):
        op.create_table("missions", sa.Column("id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("description", sa.String()), sa.Column("status", mission_status, nullable=False), sa.Column("aoi_ids", sa.JSON(), nullable=False), sa.Column("organisation_id", sa.String(), nullable=False), sa.Column("created_by", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    if not inspector.has_table("aois"):
        op.create_table("aois", sa.Column("id", sa.String(), nullable=False), sa.Column("name", sa.String(), nullable=False), sa.Column("description", sa.String()), sa.Column("geometry", sa.JSON(), nullable=False), sa.Column("organisation_id", sa.String(), nullable=False), sa.Column("created_by", sa.String(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.PrimaryKeyConstraint("id"))
    if not inspector.has_table("jobs"):
        op.create_table("jobs", sa.Column("id", sa.String(), nullable=False), sa.Column("mission_id", sa.String(), nullable=False), sa.Column("status", job_status, nullable=False), sa.Column("organisation_id", sa.String(), nullable=False), sa.Column("submitted_by", sa.String(), nullable=False), sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False), sa.Column("started_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)), sa.Column("trace_id", sa.String()), sa.Column("error_message", sa.String()), sa.PrimaryKeyConstraint("id"))
    inspector = sa.inspect(bind)
    for table, columns in (("missions", ("id", "organisation_id")), ("aois", ("id", "organisation_id")), ("jobs", ("id", "mission_id", "organisation_id"))):
        existing = {index["name"] for index in inspector.get_indexes(table)}
        for col in columns:
            index_name = f"ix_{table}_{col}"
            if index_name not in existing:
                op.create_index(index_name, table, [col])


def downgrade() -> None:
    for col in ("id", "mission_id", "organisation_id"):
        op.drop_index(f"ix_jobs_{col}", table_name="jobs")
    op.drop_table("jobs")
    for table in ("aois", "missions"):
        op.drop_index(f"ix_{table}_organisation_id", table_name=table)
        op.drop_index(f"ix_{table}_id", table_name=table)
        op.drop_table(table)
