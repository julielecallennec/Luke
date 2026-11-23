import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.database import get_database, serialize_doc, serialize_docs
from app.dependencies import get_current_company_id, parse_object_id
from app.models.user import UserCreate, UserResponse, UserUpdate

router = APIRouter(prefix="/api/users", tags=["Utilisateurs (Users)"])


def hash_password(password: str) -> str:
    """
    Hash sécurisé pour les mots de passe.
    """
    salt = "luke_salt_secure_2026"
    return hashlib.sha256((salt + password).encode("utf-8")).hexdigest()


@router.get("", response_model=List[UserResponse])
async def list_users(company_id: ObjectId = Depends(get_current_company_id)):
    """
    Liste les utilisateurs rattachés exclusivement à l'entreprise active (isolation stricte).
    """
    db = get_database()
    cursor = db.users.find({"company_id": company_id}).sort("name", 1)
    users = await cursor.to_list(length=300)
    return serialize_docs(users)


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_in: UserCreate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Crée un nouvel utilisateur pour l'entreprise active.
    Garantit l'unicité de l'email au sein de l'entreprise (Index: company_id + email).
    """
    db = get_database()
    now = datetime.now(timezone.utc)

    user_doc = {
        "company_id": company_id,
        "name": user_in.name,
        "email": user_in.email.lower().strip(),
        "password_hash": hash_password(user_in.password or "secret123"),
        "role": user_in.role,
        "avatar_color": user_in.avatar_color,
        "created_at": now
    }

    try:
        res = await db.users.insert_one(user_doc)
        user_doc["_id"] = res.inserted_id
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Un utilisateur avec l'email '{user_in.email}' existe déjà dans cette entreprise."
        )

    return serialize_doc(user_doc)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Récupère le profil d'un utilisateur de l'entreprise active.
    """
    db = get_database()
    uid = parse_object_id(user_id, "user_id")

    user = await db.users.find_one({"_id": uid, "company_id": company_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable dans cette entreprise."
        )

    return serialize_doc(user)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_in: UserUpdate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Met à jour les informations d'un utilisateur de l'entreprise active.
    """
    db = get_database()
    uid = parse_object_id(user_id, "user_id")

    update_fields = {}
    if user_in.name is not None:
        update_fields["name"] = user_in.name
    if user_in.email is not None:
        update_fields["email"] = user_in.email.lower().strip()
    if user_in.role is not None:
        update_fields["role"] = user_in.role
    if user_in.avatar_color is not None:
        update_fields["avatar_color"] = user_in.avatar_color
    if user_in.password is not None:
        update_fields["password_hash"] = hash_password(user_in.password)

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun champ à modifier.")

    try:
        updated = await db.users.find_one_and_update(
            {"_id": uid, "company_id": company_id},
            {"$set": update_fields},
            return_document=True
        )
    except DuplicateKeyError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un utilisateur utilise déjà cette adresse email dans cette entreprise."
        )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable dans cette entreprise."
        )

    return serialize_doc(updated)


@router.delete("/{user_id}", status_code=status.HTTP_200_OK)
async def delete_user(
    user_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Supprime un utilisateur de l'entreprise active et nettoie ses dépendances :
    1. Le retire des member_ids de tous les projets de l'entreprise.
    2. Passe assignee_id à null sur toutes ses tâches dans l'entreprise.
    3. Supprime l'utilisateur de la collection users.
    """
    db = get_database()
    uid = parse_object_id(user_id, "user_id")

    user = await db.users.find_one({"_id": uid, "company_id": company_id})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur introuvable dans cette entreprise."
        )

    # 1. Retrait de l'utilisateur des projets de l'entreprise
    proj_res = await db.projects.update_many(
        {"company_id": company_id, "member_ids": uid},
        {"$pull": {"member_ids": uid}}
    )

    # 2. Assignee_id à None sur toutes les tâches assignées à cet utilisateur
    tasks_res = await db.tasks.update_many(
        {"company_id": company_id, "assignee_id": uid},
        {"$set": {"assignee_id": None, "updated_at": datetime.now(timezone.utc)}}
    )

    # 3. Suppression du document utilisateur
    await db.users.delete_one({"_id": uid, "company_id": company_id})

    return {
        "message": f"Utilisateur '{user['name']}' supprimé avec succès.",
        "cleaned": {
            "projects_updated": proj_res.modified_count,
            "tasks_unassigned": tasks_res.modified_count
        }
    }
