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


async def get_current_company_id(
    x_company_id: Optional[str] = Header(None, alias="X-Company-Id"),
    company_id: Optional[str] = Query(None)
) -> ObjectId:
    """
    Dépendance centrale d'isolation Multi-Tenant :
    Récupère le company_id actif à partir du header HTTP 'X-Company-Id' ou du paramètre d'URL.
    Si aucun n'est fourni (ex: test dans Swagger /docs), sélectionne automatiquement la première entreprise trouvée.
    Vérifie ensuite que l'entreprise existe réellement en base.
    """
    db = get_database()
    cid_str = x_company_id or company_id
    
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
    x_user_id: Optional[str] = Header(None, alias="X-User-Id")
) -> Optional[ObjectId]:
    """
    Récupère l'identifiant de l'utilisateur actif simulé pour filtrage ou audit.
    """
    if not x_user_id:
        return None
    return parse_object_id(x_user_id, "user_id")
