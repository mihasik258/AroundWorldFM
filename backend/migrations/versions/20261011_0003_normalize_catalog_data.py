"""normalize station languages and placeholder coordinates

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-11 10:00:00.000000+00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LANGUAGE_ALIASES: dict[str, str | None] = {
    "american english": "english",
    "british english": "english",
    "#english": "english",
    "englsih": "english",
    "egnlish": "english",
    "engilsh": "english",
    "us": "english",
    "español internacional": "spanish",
    "espanish": "spanish",
    "castellano. español": "spanish",
    "español - latinoamerica": "spanish",
    "español argentina": "spanish",
    "espaňol": "spanish",
    "castilian": "spanish",
    "francaise": "french",
    "ger": "german",
    "gernan": "german",
    "deutsch fränkisch": "german",
    "brazilian portuguese": "portuguese",
    "язык: русский": "russian",
    "rus": "russian",
    "arabic.": "arabic",
    "العربية": "arabic",
    "bahasa indonesia": "indonesian",
    "croatia": "croatian",
    "norsk": "norwegian",
    "bangla": "bengali",
    "kurdish.": "kurdish",
    "tagalog": "filipino",
    "moldovian": "romanian",
    "türkisch": "turkish",
    "english hindi": "hindi",
    "oromo amharic somali": "amharic",
    "africa": None,
}

COUNTRY_CAPITALS: dict[str, tuple[float, float]] = {
    "Albania": (41.3275, 19.8187),
    "American Samoa": (-14.2756, -170.7020),
    "Bangladesh": (23.8103, 90.4125),
    "Barbados": (13.0975, -59.6165),
    "Benin": (6.4969, 2.6289),
    "Bolivia": (-16.4897, -68.1193),
    "Bosnia And Herzegovina": (43.8563, 18.4131),
    "Chad": (12.1348, 15.0557),
    "Croatia": (45.8150, 15.9819),
    "Ecuador": (-0.1807, -78.4678),
    "El Salvador": (13.6929, -89.2182),
    "Equatorial Guinea": (3.7504, 8.7371),
    "Estonia": (59.4370, 24.7536),
    "French Guiana": (4.9224, -52.3135),
    "Ghana": (5.6037, -0.1870),
    "Guadeloupe": (16.2650, -61.5510),
    "Guatemala": (14.6349, -90.5069),
    "Guinea Bissau": (11.8817, -15.6178),
    "Haiti": (18.5944, -72.3074),
    "Honduras": (14.0723, -87.1921),
    "Hong Kong": (22.3193, 114.1694),
    "Jamaica": (18.0179, -76.8099),
    "Jordan": (31.9454, 35.9284),
    "Kenya": (-1.2921, 36.8219),
    "Latvia": (56.9496, 24.1052),
    "Libya": (32.8872, 13.1913),
    "Lithuania": (54.6872, 25.2797),
    "Malawi": (-13.9626, 33.7741),
    "Malaysia": (3.1390, 101.6869),
    "Mali": (12.6392, -8.0029),
    "Malta": (35.8989, 14.5146),
    "Mauritius": (-20.1609, 57.5012),
    "Mayotte": (-12.7806, 45.2279),
    "Mozambique": (-25.9692, 32.5732),
    "Myanmar": (16.8409, 96.1735),
    "Nepal": (27.7172, 85.3240),
    "Nicaragua": (12.1150, -86.2362),
    "Qatar": (25.2854, 51.5310),
    "Republic Of North Macedonia": (41.9981, 21.4254),
    "Reunion": (-20.8821, 55.4507),
    "Rwanda": (-1.9441, 30.0619),
    "Serbia": (44.7866, 20.4489),
    "Slovakia": (48.1486, 17.1077),
    "Slovenia": (46.0569, 14.5058),
    "Syria": (33.5138, 36.2765),
    "Thailand": (13.7563, 100.5018),
    "The Democratic Republic Of The Congo": (-4.4419, 15.2663),
    "The Dominican Republic": (18.4861, -69.9312),
    "The Republic Of Korea": (37.5665, 126.9780),
    "The Republic Of Moldova": (47.0105, 28.8638),
    "Togo": (6.1319, 1.2228),
    "Trinidad And Tobago": (10.6549, -61.5019),
    "United Republic Of Tanzania": (-6.7924, 39.2083),
    "Vietnam": (21.0278, 105.8342),
    "Yemen": (15.3694, 44.1910),
    "Zimbabwe": (-17.8252, 31.0335),
}


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE stations SET language = NULLIF(lower(regexp_replace(trim(language), '\\s+', ' ', 'g')), '') "
            "WHERE language IS NOT NULL"
        )
    )
    for alias, canonical in LANGUAGE_ALIASES.items():
        conn.execute(
            sa.text("UPDATE stations SET language = :canonical WHERE language = :alias"),
            {"canonical": canonical, "alias": alias},
        )
    for country, (lat, lon) in COUNTRY_CAPITALS.items():
        conn.execute(
            sa.text(
                "UPDATE stations SET latitude = :lat, longitude = :lon "
                "WHERE latitude = 20 AND longitude = 0 AND country = :country"
            ),
            {"lat": lat, "lon": lon, "country": country},
        )
    conn.execute(
        sa.text(
            "UPDATE stations SET latitude = NULL, longitude = NULL WHERE latitude = 20 AND longitude = 0"
        )
    )


def downgrade() -> None:
    pass
