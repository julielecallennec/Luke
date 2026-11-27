import asyncio
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config import settings

logger = logging.getLogger("luke.database")

client: Optional[AsyncIOMotorClient] = None
db: Optional[AsyncIOMotorDatabase] = None


def get_client() -> AsyncIOMotorClient:
    global client
    if client is None:
        client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=5000)
    return client


def get_database() -> AsyncIOMotorDatabase:
    """
    Récupère l'instance de la base de données configurée via MONGO_URI.
    Si le nom de la base n'est pas spécifié dans l'URI, 'luke_db' est utilisé par défaut.
    """
    global db
    if db is None:
        c = get_client()
        try:
            db = c.get_default_database()
        except Exception:
            db = c["luke_db"]
    return db


def connect() -> None:
    get_database()


def close() -> None:
    global client
    if client:
        client.close()
        client = None


async def ping_database_with_retry(max_retries: int = 15, delay_seconds: float = 1.0) -> bool:
    """
    Vérifie la disponibilité de MongoDB au démarrage avec tentatives successives.
    Permet à docker compose up -d --build de démarrer le backend et la base
    sans conflit de timing si MongoDB met quelques secondes à s'initialiser.
    """
    c = get_client()
    for attempt in range(1, max_retries + 1):
        try:
            await c.admin.command("ping")
            logger.info("Connexion à MongoDB établie avec succès via MONGO_URI.")
            return True
        except Exception as exc:
            logger.warning(
                f"Tentative de connexion à MongoDB ({attempt}/{max_retries}) en cours... Attente de {delay_seconds}s : {exc}"
            )
            await asyncio.sleep(delay_seconds)
    logger.error("Impossible de joindre le serveur MongoDB après plusieurs tentatives.")
    return False


async def init_indexes(database: Optional[AsyncIOMotorDatabase] = None) -> None:
    """
    Crée automatiquement les index obligatoires au démarrage, compatibles à la fois
    avec l'architecture Standalone (Partie I) et l'architecture Shardée distribuée (Partie II) :
    - companies : { slug: 1 } (Unique en standalone, index standard en shardé avec unicité applicative)
    - users     : { company_id: 1, email: 1 } (Unique, préfixé par la Shard Key)
    - projects  : { company_id: 1, _id: 1 } et { company_id: 1, member_ids: 1 }
    - tasks     : { company_id: 1, _id: 1 } et { company_id: 1, project_id: 1, status: 1, position: 1 }
    """
    target_db = database if database is not None else get_database()
    try:
        # Détection du mode (routeur mongos vs standalone)
        is_sharded = False
        try:
            hello_res = await target_db.command("hello")
            is_sharded = (hello_res.get("msg") == "isdbgrid")
        except Exception:
            pass

        # 1. Index sur companies.slug
        # En cluster shardé ({ _id: "hashed" }), MongoDB restreint les index uniques aux préfixes de la Shard Key.
        # L'unicité du slug est garantie par FastAPI (routers/companies.py), accélérée par cet index.
        # En mode standalone (Partie I), l'index peut être déclaré unique directement au niveau moteur.
        if is_sharded:
            await target_db.companies.create_index([("slug", 1)])
        else:
            try:
                await target_db.companies.create_index([("slug", 1)], unique=True)
            except Exception:
                await target_db.companies.create_index([("slug", 1)])

        # 2. Index unique sur l'email par entreprise (Shard Key { company_id: 1, email: 1 } compatible)
        await target_db.users.create_index([("company_id", 1), ("email", 1)], unique=True)

        # 3. Index de Sharding et de requête sur projects
        await target_db.projects.create_index([("company_id", 1), ("_id", 1)])
        await target_db.projects.create_index([("company_id", 1), ("member_ids", 1)])

        # 4. Index de Sharding et composé Kanban sur tasks
        await target_db.tasks.create_index([("company_id", 1), ("_id", 1)])
        await target_db.tasks.create_index([
            ("company_id", 1),
            ("project_id", 1),
            ("status", 1),
            ("position", 1)
        ])
        await target_db.tasks.create_index([("company_id", 1), ("assignee_id", 1)])

        # 5. Index pour les sessions et réinitialisation de mot de passe (avec TTL)
        try:
            await target_db.sessions.create_index([("token", 1)], unique=True)
        except Exception:
            await target_db.sessions.create_index([("token", 1)])
        await target_db.sessions.create_index([("expires_at", 1)], expireAfterSeconds=0)

        try:
            await target_db.password_resets.create_index([("token", 1)], unique=True)
        except Exception:
            await target_db.password_resets.create_index([("token", 1)])
        await target_db.password_resets.create_index([("expires_at", 1)], expireAfterSeconds=0)

        logger.info(f"Index MongoDB initialisés avec succès (Mode: {'Shardé (Partie II)' if is_sharded else 'Standalone (Partie I)'}).")
    except Exception as exc:
        logger.error(f"Erreur lors de la création des index MongoDB : {exc}")


async def ensure_indexes() -> None:
    await init_indexes()


def serialize_doc(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Convertit récursivement les types BSON (ObjectId, datetime) en types JSON compatibles.
    """
    if doc is None:
        return None
    res = {}
    for key, value in doc.items():
        if key == "_id":
            res["id"] = str(value)
        elif isinstance(value, ObjectId):
            res[key] = str(value)
        elif isinstance(value, datetime):
            res[key] = value.isoformat()
        elif isinstance(value, list):
            res[key] = [
                str(item) if isinstance(item, ObjectId)
                else item.isoformat() if isinstance(item, datetime)
                else serialize_doc(item) if isinstance(item, dict)
                else item
                for item in value
            ]
        elif isinstance(value, dict):
            res[key] = serialize_doc(value)
        else:
            res[key] = value
    return res


def serialize_docs(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [serialize_doc(doc) for doc in docs if doc is not None]
