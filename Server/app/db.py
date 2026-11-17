"""
MongoDB database connector and asynchronous helper for persisting trades, equity logs, and audit trails.
"""
import logging
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorClient
from app.config import config

log = logging.getLogger("db")


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None


db_manager = Database()


async def connect_mongo():
    clean_uri = config.mongodb_uri.strip().strip('"').strip("'")
    if "MONGO_URI=" in clean_uri:
        clean_uri = clean_uri.split("MONGO_URI=")[-1]

    # Mask password for safe logging
    masked_uri = clean_uri
    if "@" in clean_uri and "://" in clean_uri:
        prefix, rest = clean_uri.split("://", 1)
        if "@" in rest:
            credentials, host_part = rest.split("@", 1)
            if ":" in credentials:
                user = credentials.split(":", 1)[0]
                masked_uri = f"{prefix}://{user}:****@{host_part}"

    log.info("Attempting to connect to MongoDB at %s...", masked_uri)
    try:
        db_manager.client = AsyncIOMotorClient(clean_uri)
        db_manager.db = db_manager.client[config.mongodb_db_name]
        # Ping to test connection
        await db_manager.client.admin.command('ping')
        log.info("Connected to MongoDB successfully (DB: %s)", config.mongodb_db_name)
    except Exception as e:
        db_manager.db = None
        log.warning("Could not connect to MongoDB (running without DB persistence): %s", e)


async def close_mongo():
    if db_manager.client:
        db_manager.client.close()
        log.info("Closed MongoDB connection.")


async def save_trade(trade_doc: Dict[str, Any]):
    if db_manager.db is not None:
        try:
            await db_manager.db.trades.insert_one(trade_doc)
            log.info("Trade entry stored in MongoDB successfully.")
        except Exception as e:
            log.error("Failed to save trade to MongoDB: %s", e)


async def save_trade_exit(filter_query: Dict[str, Any], exit_doc: Dict[str, Any]):
    if db_manager.db is not None:
        try:
            await db_manager.db.trades.update_one(filter_query, {"$set": exit_doc}, upsert=True)
            log.info("Trade exit & PnL stored in MongoDB successfully.")
        except Exception as e:
            log.error("Failed to save trade exit to MongoDB: %s", e)


async def save_equity_snapshot(snapshot_doc: Dict[str, Any]):
    if db_manager.db is not None:
        try:
            await db_manager.db.equity_logs.insert_one(snapshot_doc)
        except Exception as e:
            log.error("Failed to save equity snapshot to MongoDB: %s", e)


async def get_recent_trades_from_db(limit: int = 100) -> List[Dict[str, Any]]:
    if db_manager.db is not None:
        try:
            cursor = db_manager.db.trades.find({}, {"_id": 0}).sort("ts", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as e:
            log.error("Failed to fetch trades from MongoDB: %s", e)
    return []
