"""Create the initial gateway schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=20), nullable=False),
        sa.Column("key_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_api_keys"),
        sa.UniqueConstraint("name", name="uq_api_keys_name"),
    )
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_revoked", "api_keys", ["revoked"])
    op.create_index("ix_api_keys_role", "api_keys", ["role"])

    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("buyer_reference", sa.String(length=255), nullable=True),
        sa.Column("currency", sa.String(length=16), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_snapshot", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_orders"),
        sa.UniqueConstraint("source_id", name="uq_orders_source_id"),
    )
    op.create_index("ix_orders_buyer_reference", "orders", ["buyer_reference"])
    op.create_index("ix_orders_source_id", "orders", ["source_id"])
    op.create_index("ix_orders_source_updated_at", "orders", ["source_updated_at"])
    op.create_index("ix_orders_status", "orders", ["status"])

    op.create_table(
        "order_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("source_line_id", sa.String(length=255), nullable=False),
        sa.Column("sku", sa.String(length=255), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("raw_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], name="fk_order_lines_order_id_orders", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_order_lines"),
        sa.UniqueConstraint("order_id", "source_line_id", name="uq_order_lines_order_id"),
    )
    op.create_index("ix_order_lines_order_id", "order_lines", ["order_id"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("buyer_reference", sa.String(length=255), nullable=True),
        sa.Column("inquiry_subject", sa.Text(), nullable=True),
        sa.Column("unread", sa.Boolean(), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_snapshot", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
        sa.UniqueConstraint("source_id", name="uq_conversations_source_id"),
    )
    op.create_index("ix_conversations_buyer_reference", "conversations", ["buyer_reference"])
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])
    op.create_index("ix_conversations_source_id", "conversations", ["source_id"])
    op.create_index("ix_conversations_source_updated_at", "conversations", ["source_updated_at"])
    op.create_index("ix_conversations_unread", "conversations", ["unread"])

    op.create_table(
        "sync_checkpoints",
        sa.Column("resource", sa.String(length=100), nullable=False),
        sa.Column("source_cursor", sa.Text(), nullable=True),
        sa.Column("updated_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("overlap_seconds", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False),
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
        sa.Column("paused_reason", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("resource", name="pk_sync_checkpoints"),
    )

    op.create_table(
        "outbox_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column("payload_digest", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("intent", sa.String(length=64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("caller_reference", sa.String(length=255), nullable=True),
        sa.Column("caller_key_id", sa.Uuid(), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=False),
        sa.Column("state", sa.String(length=32), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_code", sa.String(length=100), nullable=True),
        sa.Column("safe_result_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["caller_key_id"], ["api_keys.id"], name="fk_outbox_jobs_caller_key_id_api_keys"
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_outbox_jobs_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_jobs"),
        sa.UniqueConstraint("idempotency_key", name="uq_outbox_jobs_idempotency_key"),
    )
    op.create_index("ix_outbox_jobs_caller_key_id", "outbox_jobs", ["caller_key_id"])
    op.create_index("ix_outbox_jobs_conversation_id", "outbox_jobs", ["conversation_id"])
    op.create_index("ix_outbox_jobs_idempotency_key", "outbox_jobs", ["idempotency_key"])
    op.create_index("ix_outbox_jobs_next_attempt_at", "outbox_jobs", ["next_attempt_at"])
    op.create_index("ix_outbox_jobs_request_id", "outbox_jobs", ["request_id"])
    op.create_index("ix_outbox_jobs_state", "outbox_jobs", ["state"])

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=True),
        sa.Column("fallback_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=16), nullable=False),
        sa.Column("sender_label", sa.String(length=255), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("attachment_metadata", sa.JSON(), nullable=False),
        sa.Column("source_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("outbound_job_id", sa.Uuid(), nullable=True),
        sa.Column("raw_snapshot", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_messages_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outbound_job_id"], ["outbox_jobs.id"], name="fk_messages_outbound_job_id_outbox_jobs"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_messages"),
        sa.UniqueConstraint(
            "conversation_id",
            "fallback_fingerprint",
            name="uq_messages_conversation_id",
        ),
        sa.UniqueConstraint(
            "conversation_id",
            "source_id",
            name="uq_messages_conversation_id_source_id",
        ),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])
    op.create_index("ix_messages_direction", "messages", ["direction"])
    op.create_index("ix_messages_outbound_job_id", "messages", ["outbound_job_id"])
    op.create_index("ix_messages_source_created_at", "messages", ["source_created_at"])

    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("caller_key_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=True),
        sa.Column("entity_id", sa.String(length=255), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["caller_key_id"], ["api_keys.id"], name="fk_audit_events_caller_key_id_api_keys"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
    )
    op.create_index("ix_audit_events_caller_key_id", "audit_events", ["caller_key_id"])
    op.create_index("ix_audit_events_entity_id", "audit_events", ["entity_id"])
    op.create_index("ix_audit_events_event_type", "audit_events", ["event_type"])
    op.create_index("ix_audit_events_request_id", "audit_events", ["request_id"])

    op.create_table(
        "runtime_status",
        sa.Column("component", sa.String(length=100), nullable=False),
        sa.Column("state", sa.String(length=64), nullable=False),
        sa.Column("detail_code", sa.String(length=100), nullable=True),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("component", name="pk_runtime_status"),
    )
    op.create_index("ix_runtime_status_state", "runtime_status", ["state"])


def downgrade() -> None:
    op.drop_table("runtime_status")
    op.drop_table("audit_events")
    op.drop_table("messages")
    op.drop_table("outbox_jobs")
    op.drop_table("sync_checkpoints")
    op.drop_table("conversations")
    op.drop_table("order_lines")
    op.drop_table("orders")
    op.drop_table("api_keys")
