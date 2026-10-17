"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-10 18:05:19.507865+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "airports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("iata_code", sa.String(length=3), nullable=False),
        sa.Column("icao_code", sa.String(length=4), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=128), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.String(length=4), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("altitude_m", sa.Float(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_airports")),
        sa.UniqueConstraint("icao_code", name=op.f("uq_airports_icao_code")),
    )
    op.create_index(op.f("ix_airports_city"), "airports", ["city"], unique=False)
    op.create_index(op.f("ix_airports_country"), "airports", ["country"], unique=False)
    op.create_index(op.f("ix_airports_country_code"), "airports", ["country_code"], unique=False)
    op.create_index(op.f("ix_airports_iata_code"), "airports", ["iata_code"], unique=True)
    op.create_table(
        "stations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_uuid", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("homepage_url", sa.String(length=1024), nullable=True),
        sa.Column("favicon_url", sa.String(length=1024), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("country_code", sa.String(length=8), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("language", sa.String(length=100), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "latitude IS NULL OR latitude BETWEEN -90 AND 90",
            name=op.f("ck_stations_latitude_range"),
        ),
        sa.CheckConstraint(
            "longitude IS NULL OR longitude BETWEEN -180 AND 180",
            name=op.f("ck_stations_longitude_range"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_stations")),
    )
    op.create_index(op.f("ix_stations_country"), "stations", ["country"], unique=False)
    op.create_index(op.f("ix_stations_country_code"), "stations", ["country_code"], unique=False)
    op.create_index(op.f("ix_stations_language"), "stations", ["language"], unique=False)
    op.create_index(op.f("ix_stations_name"), "stations", ["name"], unique=False)
    op.create_index(op.f("ix_stations_station_uuid"), "stations", ["station_uuid"], unique=True)
    op.create_index(
        "ix_stations_tags_gin", "stations", ["tags"], unique=False, postgresql_using="gin"
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column(
            "role",
            sa.Enum(
                "user",
                "admin",
                name="user_role",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_username"), "users", ["username"], unique=True)
    op.create_table(
        "auth_flows",
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("purpose", sa.String(length=16), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("code_verifier_enc", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_auth_flows_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("token_hash", name=op.f("pk_auth_flows")),
    )
    op.create_index(op.f("ix_auth_flows_expires_at"), "auth_flows", ["expires_at"], unique=False)
    op.create_index(op.f("ix_auth_flows_user_id"), "auth_flows", ["user_id"], unique=False)
    op.create_table(
        "favorites",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name=op.f("fk_favorites_station_id_stations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_favorites_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_favorites")),
        sa.UniqueConstraint("user_id", "station_id", name="uq_favorites_user_station"),
    )
    op.create_index(op.f("ix_favorites_station_id"), "favorites", ["station_id"], unique=False)
    op.create_table(
        "flight_routes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flight_number", sa.String(length=16), nullable=False),
        sa.Column("airline", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("origin_airport_id", sa.Integer(), nullable=False),
        sa.Column("destination_airport_id", sa.Integer(), nullable=False),
        sa.Column("distance_km", sa.Float(), nullable=False),
        sa.Column("real_duration_minutes", sa.Integer(), nullable=False),
        sa.Column("cruising_altitude_m", sa.Float(), nullable=False),
        sa.Column("cruising_speed_kmh", sa.Float(), nullable=False),
        sa.Column("recommended_vibe", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False),
        sa.Column("waypoints", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["destination_airport_id"],
            ["airports.id"],
            name=op.f("fk_flight_routes_destination_airport_id_airports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["origin_airport_id"],
            ["airports.id"],
            name=op.f("fk_flight_routes_origin_airport_id_airports"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_flight_routes")),
    )
    op.create_index(
        op.f("ix_flight_routes_destination_airport_id"),
        "flight_routes",
        ["destination_airport_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_flight_routes_flight_number"), "flight_routes", ["flight_number"], unique=False
    )
    op.create_index(
        op.f("ix_flight_routes_is_featured"), "flight_routes", ["is_featured"], unique=False
    )
    op.create_index(
        op.f("ix_flight_routes_origin_airport_id"),
        "flight_routes",
        ["origin_airport_id"],
        unique=False,
    )
    op.create_table(
        "station_streams",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("station_id", sa.Integer(), nullable=False),
        sa.Column("stream_url", sa.String(length=1024), nullable=False),
        sa.Column("codec", sa.String(length=32), nullable=False),
        sa.Column("bitrate", sa.Integer(), nullable=False),
        sa.Column("is_primary", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["station_id"],
            ["stations.id"],
            name=op.f("fk_station_streams_station_id_stations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_station_streams")),
        sa.UniqueConstraint("stream_url", name=op.f("uq_station_streams_stream_url")),
    )
    op.create_index(
        op.f("ix_station_streams_station_id"), "station_streams", ["station_id"], unique=False
    )
    op.create_table(
        "user_identities",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("provider_uid", sa.String(length=255), nullable=False),
        sa.Column("secret_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_identities_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_identities")),
        sa.UniqueConstraint("provider", "provider_uid", name="uq_user_identities_provider_uid"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_identities_user_provider"),
    )
    op.create_index(
        op.f("ix_user_identities_user_id"), "user_identities", ["user_id"], unique=False
    )
    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=64), nullable=False),
        sa.Column("previous_token_hash", sa.String(length=64), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("device_name", sa.String(length=64), nullable=True),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("is_revoked", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_sessions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_sessions")),
    )
    op.create_index(
        op.f("ix_user_sessions_expires_at"), "user_sessions", ["expires_at"], unique=False
    )
    op.create_index(
        op.f("ix_user_sessions_is_revoked"), "user_sessions", ["is_revoked"], unique=False
    )
    op.create_index(
        op.f("ix_user_sessions_previous_token_hash"),
        "user_sessions",
        ["previous_token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_user_sessions_refresh_token_hash"),
        "user_sessions",
        ["refresh_token_hash"],
        unique=True,
    )
    op.create_index(op.f("ix_user_sessions_user_id"), "user_sessions", ["user_id"], unique=False)
    op.create_table(
        "oauth_credentials",
        sa.Column("identity_id", sa.Integer(), nullable=False),
        sa.Column("access_token_enc", sa.Text(), nullable=False),
        sa.Column("refresh_token_enc", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scope", sa.String(length=512), nullable=False),
        sa.Column("playlist_id", sa.String(length=64), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["identity_id"],
            ["user_identities.id"],
            name=op.f("fk_oauth_credentials_identity_id_user_identities"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("identity_id", name=op.f("pk_oauth_credentials")),
    )
    op.create_table(
        "stream_health",
        sa.Column("stream_id", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("check_fail_count", sa.Integer(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["stream_id"],
            ["station_streams.id"],
            name=op.f("fk_stream_health_stream_id_station_streams"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("stream_id", name=op.f("pk_stream_health")),
    )
    op.create_index(
        op.f("ix_stream_health_is_active"), "stream_health", ["is_active"], unique=False
    )
    op.create_index(
        op.f("ix_stream_health_last_checked_at"), "stream_health", ["last_checked_at"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_stream_health_last_checked_at"), table_name="stream_health")
    op.drop_index(op.f("ix_stream_health_is_active"), table_name="stream_health")
    op.drop_table("stream_health")
    op.drop_table("oauth_credentials")
    op.drop_index(op.f("ix_user_sessions_user_id"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_refresh_token_hash"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_previous_token_hash"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_is_revoked"), table_name="user_sessions")
    op.drop_index(op.f("ix_user_sessions_expires_at"), table_name="user_sessions")
    op.drop_table("user_sessions")
    op.drop_index(op.f("ix_user_identities_user_id"), table_name="user_identities")
    op.drop_table("user_identities")
    op.drop_index(op.f("ix_station_streams_station_id"), table_name="station_streams")
    op.drop_table("station_streams")
    op.drop_index(op.f("ix_flight_routes_origin_airport_id"), table_name="flight_routes")
    op.drop_index(op.f("ix_flight_routes_is_featured"), table_name="flight_routes")
    op.drop_index(op.f("ix_flight_routes_flight_number"), table_name="flight_routes")
    op.drop_index(op.f("ix_flight_routes_destination_airport_id"), table_name="flight_routes")
    op.drop_table("flight_routes")
    op.drop_index(op.f("ix_favorites_station_id"), table_name="favorites")
    op.drop_table("favorites")
    op.drop_index(op.f("ix_auth_flows_user_id"), table_name="auth_flows")
    op.drop_index(op.f("ix_auth_flows_expires_at"), table_name="auth_flows")
    op.drop_table("auth_flows")
    op.drop_index(op.f("ix_users_username"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    op.drop_index("ix_stations_tags_gin", table_name="stations", postgresql_using="gin")
    op.drop_index(op.f("ix_stations_station_uuid"), table_name="stations")
    op.drop_index(op.f("ix_stations_name"), table_name="stations")
    op.drop_index(op.f("ix_stations_language"), table_name="stations")
    op.drop_index(op.f("ix_stations_country_code"), table_name="stations")
    op.drop_index(op.f("ix_stations_country"), table_name="stations")
    op.drop_table("stations")
    op.drop_index(op.f("ix_airports_iata_code"), table_name="airports")
    op.drop_index(op.f("ix_airports_country_code"), table_name="airports")
    op.drop_index(op.f("ix_airports_country"), table_name="airports")
    op.drop_index(op.f("ix_airports_city"), table_name="airports")
    op.drop_table("airports")
