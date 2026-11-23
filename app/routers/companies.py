import re
from datetime import datetime, timezone
from typing import List
from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.database import get_database, serialize_doc, serialize_docs
from app.dependencies import parse_object_id
from app.models.company import CompanyCreate, CompanyResponse, CompanyUpdate

router = APIRouter(prefix="/api/companies", tags=["Entreprises (Companies)"])


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    text = re.sub(r"^-+|-+$", "", text)
    return text or "company"


@router.get("", response_model=List[CompanyResponse])
async def list_companies():
    """
    Liste toutes les entreprises enregistrées avec statistiques (utilisateurs, projets, tâches).
    """
    db = get_database()
    companies_cursor = db.companies.find({}).sort("name", 1)
    companies = await companies_cursor.to_list(length=200)

    results = []
    for comp in companies:
        cid = comp["_id"]
        # Comptage agrégé des éléments rattachés
        u_count = await db.users.count_documents({"company_id": cid})
        p_count = await db.projects.count_documents({"company_id": cid})
        t_count = await db.tasks.count_documents({"company_id": cid})

        doc = serialize_doc(comp)
        doc["users_count"] = u_count
        doc["projects_count"] = p_count
        doc["tasks_count"] = t_count
        results.append(doc)

    return results


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(company_in: CompanyCreate):
    """
    Crée une nouvelle entreprise cliente.
    """
    db = get_database()
    now = datetime.now(timezone.utc)
    
    slug = company_in.slug or slugify(company_in.name)

    company_doc = {
        "name": company_in.name,
        "slug": slug,
        "plan": company_in.plan,
        "created_at": now,
        "updated_at": now
    }

    try:
        res = await db.companies.insert_one(company_doc)
        company_doc["_id"] = res.inserted_id
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Une entreprise avec le slug '{slug}' existe déjà."
        )

    out = serialize_doc(company_doc)
    out["users_count"] = 0
    out["projects_count"] = 0
    out["tasks_count"] = 0
    return out


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(company_id: str):
    """
    Détail d'une entreprise spécifique.
    """
    db = get_database()
    cid = parse_object_id(company_id, "company_id")

    comp = await db.companies.find_one({"_id": cid})
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entreprise introuvable.")

    u_count = await db.users.count_documents({"company_id": cid})
    p_count = await db.projects.count_documents({"company_id": cid})
    t_count = await db.tasks.count_documents({"company_id": cid})

    out = serialize_doc(comp)
    out["users_count"] = u_count
    out["projects_count"] = p_count
    out["tasks_count"] = t_count
    return out


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(company_id: str, company_in: CompanyUpdate):
    """
    Met à jour les informations d'une entreprise.
    """
    db = get_database()
    cid = parse_object_id(company_id, "company_id")

    update_fields = {}
    if company_in.name is not None:
        update_fields["name"] = company_in.name
    if company_in.slug is not None:
        update_fields["slug"] = slugify(company_in.slug)
    if company_in.plan is not None:
        update_fields["plan"] = company_in.plan

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun champ à modifier.")

    update_fields["updated_at"] = datetime.now(timezone.utc)

    try:
        updated = await db.companies.find_one_and_update(
            {"_id": cid},
            {"$set": update_fields},
            return_document=True
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Une entreprise avec le slug '{update_fields.get('slug')}' existe déjà."
        )

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entreprise introuvable.")

    u_count = await db.users.count_documents({"company_id": cid})
    p_count = await db.projects.count_documents({"company_id": cid})
    t_count = await db.tasks.count_documents({"company_id": cid})

    out = serialize_doc(updated)
    out["users_count"] = u_count
    out["projects_count"] = p_count
    out["tasks_count"] = t_count
    return out


@router.delete("/{company_id}", status_code=status.HTTP_200_OK)
async def delete_company(company_id: str):
    """
    Suppression en cascade d'une entreprise et de toutes ses entités :
    Supprime tous ses projets, utilisateurs et tâches associées (company_id).
    """
    db = get_database()
    cid = parse_object_id(company_id, "company_id")

    # Vérification de l'existence
    comp = await db.companies.find_one({"_id": cid})
    if not comp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entreprise introuvable.")

    # 1. Suppression en cascade des tâches
    tasks_res = await db.tasks.delete_many({"company_id": cid})
    # 2. Suppression en cascade des projets
    projects_res = await db.projects.delete_many({"company_id": cid})
    # 3. Suppression en cascade des utilisateurs
    users_res = await db.users.delete_many({"company_id": cid})
    # 4. Suppression de l'entreprise
    await db.companies.delete_one({"_id": cid})

    return {
        "message": f"Entreprise '{comp['name']}' et toutes ses ressources supprimées en cascade avec succès.",
        "deleted": {
            "companies": 1,
            "users": users_res.deleted_count,
            "projects": projects_res.deleted_count,
            "tasks": tasks_res.deleted_count
        }
    }
