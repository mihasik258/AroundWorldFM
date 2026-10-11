"""station location precision

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 12:30:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CAPITAL_PLACEMENTS: list[tuple[float, float]] = [
    (41.3275, 19.8187),
    (-14.2756, -170.7020),
    (23.8103, 90.4125),
    (13.0975, -59.6165),
    (6.4969, 2.6289),
    (-16.4897, -68.1193),
    (43.8563, 18.4131),
    (12.1348, 15.0557),
    (45.8150, 15.9819),
    (-0.1807, -78.4678),
    (13.6929, -89.2182),
    (3.7504, 8.7371),
    (59.4370, 24.7536),
    (4.9224, -52.3135),
    (5.6037, -0.1870),
    (16.2650, -61.5510),
    (14.6349, -90.5069),
    (11.8817, -15.6178),
    (18.5944, -72.3074),
    (14.0723, -87.1921),
    (22.3193, 114.1694),
    (18.0179, -76.8099),
    (31.9454, 35.9284),
    (-1.2921, 36.8219),
    (56.9496, 24.1052),
    (32.8872, 13.1913),
    (54.6872, 25.2797),
    (-13.9626, 33.7741),
    (3.1390, 101.6869),
    (12.6392, -8.0029),
    (35.8989, 14.5146),
    (-20.1609, 57.5012),
    (-12.7806, 45.2279),
    (-25.9692, 32.5732),
    (16.8409, 96.1735),
    (27.7172, 85.3240),
    (12.1150, -86.2362),
    (25.2854, 51.5310),
    (41.9981, 21.4254),
    (-20.8821, 55.4507),
    (-1.9441, 30.0619),
    (44.7866, 20.4489),
    (48.1486, 17.1077),
    (46.0569, 14.5058),
    (33.5138, 36.2765),
    (13.7563, 100.5018),
    (-4.4419, 15.2663),
    (18.4861, -69.9312),
    (37.5665, 126.9780),
    (47.0105, 28.8638),
    (6.1319, 1.2228),
    (10.6549, -61.5019),
    (-6.7924, 39.2083),
    (21.0278, 105.8342),
    (15.3694, 44.1910),
    (-17.8252, 31.0335),
]


def upgrade() -> None:
    op.add_column(
        "stations",
        sa.Column(
            "location_precision", sa.String(length=8), server_default="exact", nullable=False
        ),
    )
    conn = op.get_bind()
    for lat, lon in CAPITAL_PLACEMENTS:
        conn.execute(
            sa.text(
                "UPDATE stations SET location_precision = 'country' "
                "WHERE latitude = :lat AND longitude = :lon"
            ),
            {"lat": lat, "lon": lon},
        )


def downgrade() -> None:
    op.drop_column("stations", "location_precision")
