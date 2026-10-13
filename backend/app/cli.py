import argparse
import asyncio
import getpass
import os
import sys

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import AsyncSessionLocal, engine
from app.models.user import User, UserRole
from app.services import catalog_import
from app.services.flight_service import FlightService
from app.services.seed_service import create_user, seed_catalog, seed_demo_users
from app.services.stream_checker import run_due_stream_checks, run_stream_health_check

MIN_PASSWORD_LENGTH = 12


async def cmd_seed(_: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as db:
        await seed_catalog(db)
        await FlightService.seed_flight_data(db)
        if settings.SEED_DEMO_USERS:
            await seed_demo_users(db)
    return 0


async def cmd_create_admin(args: argparse.Namespace) -> int:
    password = os.environ.get("ADMIN_PASSWORD") or getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"Password must be at least {MIN_PASSWORD_LENGTH} characters", file=sys.stderr)
        return 1
    async with AsyncSessionLocal() as db:
        taken = await db.execute(
            select(User.id).where((User.username == args.username) | (User.email == args.email))
        )
        if taken.first():
            print("Username or email already taken", file=sys.stderr)
            return 1
        await create_user(db, args.username, args.email.lower(), password, UserRole.ADMIN)
    print(f"Admin {args.username} created")
    return 0


async def cmd_check_streams(_: argparse.Namespace) -> int:
    async with AsyncSessionLocal() as db:
        result = await run_stream_health_check(db)
    print(f"Alive {result['alive']}/{result['checked']}")
    return 0


def _codes(raw: str | None) -> list[str]:
    return [c.strip().upper() for c in (raw or "").split(",") if c.strip()]


async def cmd_import_stations(args: argparse.Namespace) -> int:
    countries = catalog_import.load_countries()
    codes = _codes(args.countries)
    continents = set(_codes(args.continents))
    if continents:
        codes += [cc for cc, c in countries.items() if c["continent"] in continents]
    async with AsyncSessionLocal() as db:
        report = await catalog_import.collect(
            db, sorted(set(codes)) or None, per_country_fetch=args.per_country
        )
        print(f"Fetched {report.fetched}, selected {len(report.selected)}")
        print("By continent:", dict(report.by_continent.most_common()))
        print("Top countries:", dict(report.by_country.most_common(15)))
        print("Rejected:", dict(report.rejected.most_common()))
        if report.failed_countries:
            print("Failed countries:", ",".join(report.failed_countries))
        if args.dry_run:
            print("Dry run, nothing saved")
            return 0
        saved = await catalog_import.save(db, report.selected)
        print(f"Saved {saved} stations, they go on air after the first successful check")
        if args.verify:
            total = {"checked": 0, "alive": 0}
            while True:
                result = await run_due_stream_checks(db)
                total["checked"] += result["checked"]
                total["alive"] += result["alive"]
                if result["checked"] == 0 or total["checked"] >= saved:
                    break
            print(f"Verified {total['checked']}, alive {total['alive']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed").set_defaults(handler=cmd_seed)
    admin = sub.add_parser("create-admin")
    admin.add_argument("--username", required=True)
    admin.add_argument("--email", required=True)
    admin.set_defaults(handler=cmd_create_admin)
    sub.add_parser("check-streams").set_defaults(handler=cmd_check_streams)
    imp = sub.add_parser("import-stations")
    imp.add_argument("--countries", help="ISO codes, e.g. KE,NG,BR")
    imp.add_argument("--continents", help="AF,AS,EU,NA,OC,SA")
    imp.add_argument("--per-country", type=int, default=300)
    imp.add_argument("--dry-run", action="store_true")
    imp.add_argument("--verify", action="store_true")
    imp.set_defaults(handler=cmd_import_stations)
    args = parser.parse_args()

    configure_logging(settings.LOG_LEVEL, settings.LOG_JSON)

    async def run() -> int:
        try:
            return await args.handler(args)
        finally:
            await engine.dispose()

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
