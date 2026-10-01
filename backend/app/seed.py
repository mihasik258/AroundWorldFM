import asyncio

from app.db.session import AsyncSessionLocal
from app.services.seed_service import seed_initial_data


async def main():
    print("Seeding")
    async with AsyncSessionLocal() as db:
        await seed_initial_data(db)
    print("Done")


if __name__ == "__main__":
    asyncio.run(main())
