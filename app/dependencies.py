from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from fastapi import Header, HTTPException, Query, status
from app.database import get_database


def parse_object_id(id_str: str, name: str = "ID") -> ObjectId:
    """
    Valide et convertit une chaîne hexadécimale en ObjectId MongoDB.
    """
    if not id_str or not ObjectId.is_valid(id_str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{name} invalide : '{id_str}' n'est pas un ObjectId MongoDB valide."
        )
    return ObjectId(id_str)


def extract_token(authorization: Optional[str], x_auth_token: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    if x_auth_token:
        return x_auth_token.strip()
    return None


async def get_current_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token"),
    company_id: Optional[str] = Query(None)
) -> ObjectId:
    """
    Dépendance centrale d'isolation Multi-Tenant :
    1. Si un token de session est fourni dans Authorization/X-Auth-Token, récupère la company de la session.
    2. Si 'X-Company-Id' ou 'company_id' en query est fourni, il a priorité.
    3. Fallback pour Swagger et facilité de test : première entreprise trouvée.
    """
    db = get_database()
    cid_str = x_company_id or company_id
    
    # Vérification d'une session active
    token = extract_token(authorization, x_auth_token)
    if token and not cid_str:
        now = datetime.now(timezone.utc)
        session = await db.sessions.find_one({"token": token, "expires_at": {"$gt": now}})
        if session:
            return session["company_id"]

    if not cid_str:
        # Fallback pour Swagger et facilité de test
        first_company = await db.companies.find_one({}, sort=[("created_at", 1)])
        if first_company:
            return first_company["_id"]
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune entreprise trouvée dans le système. Veuillez en créer une d'abord."
        )

    cid = parse_object_id(cid_str, "company_id")
    exists = await db.companies.find_one({"_id": cid}, {"_id": 1})
    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entreprise introuvable pour l'identifiant {cid_str}."
        )
    return cid


async def get_current_user_id(
    x_user_id: Optional[str] = Header(None, alias="X-User-Id"),
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")
) -> Optional[ObjectId]:
    """
    Récupère l'identifiant de l'utilisateur actif via le header de simulation ou la session authentifiée.
    """
    if x_user_id:
        return parse_object_id(x_user_id, "user_id")

    token = extract_token(authorization, x_auth_token)
    if token:
        db = get_database()
        now = datetime.now(timezone.utc)
        session = await db.sessions.find_one({"token": token, "expires_at": {"$gt": now}})
        if session:
            return session["user_id"]

    return None
