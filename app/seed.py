"""Idempotent sample workspace used for a first run."""
from datetime import datetime, timezone
from bson import ObjectId
from app import database

async def seed_demo() -> None:
    db = database.db
    assert db is not None
    if await db.companies.count_documents({}) > 0:
        return
    now = datetime.now(timezone.utc)
    company_id, second_company_id = ObjectId(), ObjectId()
    alice_id, sam_id = ObjectId(), ObjectId()
    project_id = ObjectId()
    await db.companies.insert_many([
        {"_id": company_id, "name": "Atelier Nova", "slug": "atelier-nova", "plan": "PRO", "created_at": now, "updated_at": now},
        {"_id": second_company_id, "name": "Studio Pixel", "slug": "studio-pixel", "plan": "STARTER", "created_at": now, "updated_at": now},
    ])
    await db.users.insert_many([
        {"_id": alice_id, "company_id": company_id, "name": "Alice Martin", "email": "alice@atelier-nova.fr", "role": "ADMIN", "avatar_color": "#6757D9", "created_at": now},
        {"_id": sam_id, "company_id": company_id, "name": "Sam Bernard", "email": "sam@atelier-nova.fr", "role": "MEMBER", "avatar_color": "#E07A5F", "created_at": now},
        {"_id": ObjectId(), "company_id": second_company_id, "name": "Noa Petit", "email": "noa@studio-pixel.fr", "role": "ADMIN", "avatar_color": "#2A9D8F", "created_at": now},
    ])
    await db.projects.insert_one({"_id": project_id, "company_id": company_id, "name": "Refonte du site", "description": "Un site plus clair, rapide et accessible.", "status": "ACTIVE", "member_ids": [alice_id, sam_id], "created_at": now, "updated_at": now})
    samples = [
        ("Cartographier les pages", "Lister les parcours et les contenus à conserver.", "TODO", "MEDIUM", alice_id, ["Produit", "Contenu"]),
        ("Créer la maquette mobile", "Préparer les écrans clés en format mobile.", "IN_PROGRESS", "HIGH", sam_id, ["Design", "Mobile"]),
        ("Relire les textes", "Vérifier le ton et les appels à l’action.", "IN_REVIEW", "LOW", alice_id, ["Contenu"]),
        ("Installer le socle du projet", "Structure initiale et environnement de travail.", "DONE", "MEDIUM", sam_id, ["Technique"]),
    ]
    await db.tasks.insert_many([{"_id": ObjectId(), "company_id": company_id, "project_id": project_id, "title": title, "description": desc, "status": status, "priority": priority, "assignee_id": assignee, "position": pos, "tags": tags, "due_date": None, "created_at": now, "updated_at": now} for pos, (title, desc, status, priority, assignee, tags) in enumerate(samples)])
