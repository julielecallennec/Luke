"""MongoDB connection and tenant-aware indexes."""
import os
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

client: AsyncIOMotorClient | None = None
db: AsyncIOMotorDatabase | None = None


def connect() -> None:
    global client, db
    mongo_uri = os.getenv("MONGO_URI")
    if not mongo_uri:
        raise RuntimeError("MONGO_URI must be set")
    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    db = client.get_default_database()
    if db is None:
        raise RuntimeError("MONGO_URI must include a database name")


async def ensure_indexes() -> None:
    assert db is not None
    await db.companies.create_index("slug", unique=True)
    await db.users.create_index([("company_id", 1), ("email", 1)], unique=True)
    await db.projects.create_index([("company_id", 1), ("member_ids", 1)])
    await db.tasks.create_index([("company_id", 1), ("project_id", 1), ("status", 1), ("position", 1)])
    await db.tasks.create_index([("company_id", 1), ("assignee_id", 1)])


def close() -> None:
    if client:
        client.close()
