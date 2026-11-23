import random
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, Header, HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.database import get_database, serialize_doc
from app.models.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
)
from app.services.security import (
    generate_reset_code,
    generate_token,
    hash_password,
    slugify,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["Authentification (SaaS Auth)"])

AVATAR_COLORS = [
    "#4F46E5",  # Indigo
    "#10B981",  # Emerald
    "#F59E0B",  # Amber
    "#EF4444",  # Rose
    "#8B5CF6",  # Violet
    "#EC4899",  # Pink
    "#06B6D4",  # Cyan
    "#3B82F6",  # Blue
]


async def get_active_session(
    authorization: Optional[str] = Header(None),
    x_auth_token: Optional[str] = Header(None, alias="X-Auth-Token")
):
    """
    Extrait et valide la session active depuis l'entête HTTP.
    """
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()
    elif x_auth_token:
        token = x_auth_token.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session non authentifiée. Veuillez vous connecter."
        )

    db = get_database()
    now = datetime.now(timezone.utc)
    session = await db.sessions.find_one({
        "token": token,
        "expires_at": {"$gt": now}
    })

    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée ou invalide. Veuillez vous reconnecter."
        )

    return session


@router.post("/login", response_model=AuthResponse)
async def login(req: LoginRequest):
    """
    Authentifie un utilisateur SaaS par email et mot de passe.
    Supporte les organisations multi-tenant.
    """
    db = get_database()
    clean_email = req.email.lower().strip()

    query = {"email": clean_email}
    if req.company_slug:
        comp = await db.companies.find_one({"slug": req.company_slug.strip().lower()})
        if comp:
            query["company_id"] = comp["_id"]

    user = await db.users.find_one(query)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect."
        )

    if not verify_password(req.password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou mot de passe incorrect."
        )

    company = await db.companies.find_one({"_id": user["company_id"]})
    if not company:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organisation rattachée introuvable."
        )

    # Création du jeton de session
    now = datetime.now(timezone.utc)
    token = generate_token(32)
    session_doc = {
        "token": token,
        "user_id": user["_id"],
        "company_id": user["company_id"],
        "created_at": now,
        "expires_at": now + timedelta(days=7)
    }
    await db.sessions.insert_one(session_doc)

    return {
        "token": token,
        "user": serialize_doc(user),
        "company": serialize_doc(company),
        "message": f"Bienvenue, {user['name']} !"
    }


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """
    Inscription d'un nouvel utilisateur SaaS :
    - Soit crée sa propre entreprise (Tenant ADMIN)
    - Soit rejoint une entreprise existante via son slug (MEMBER)
    """
    db = get_database()
    clean_email = req.email.lower().strip()
    now = datetime.now(timezone.utc)

    # 1. Résolution de l'entreprise
    if req.company_slug:
        company = await db.companies.find_one({"slug": req.company_slug.strip().lower()})
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Aucune organisation trouvée avec le slug '{req.company_slug}'."
            )
        role = "MEMBER"
    else:
        # Création d'une nouvelle entreprise SaaS
        comp_name = (req.company_name or f"Workspace {req.name}").strip()
        base_slug = slugify(comp_name)
        slug = base_slug

        # Vérifier collision éventuelle de slug
        existing_comp = await db.companies.find_one({"slug": slug})
        if existing_comp:
            slug = f"{base_slug}-{secrets.token_hex(2)}"

        comp_doc = {
            "name": comp_name,
            "slug": slug,
            "plan": "PRO",
            "created_at": now,
            "updated_at": now
        }
        res_comp = await db.companies.insert_one(comp_doc)
        comp_doc["_id"] = res_comp.inserted_id
        company = comp_doc
        role = "ADMIN"

    # 2. Vérification unicité de l'email au sein de l'entreprise
    existing_user = await db.users.find_one({
        "company_id": company["_id"],
        "email": clean_email
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"L'adresse '{clean_email}' possède déjà un compte dans l'organisation '{company['name']}'."
        )

    # 3. Création de l'utilisateur
    avatar_color = random.choice(AVATAR_COLORS)
    user_doc = {
        "company_id": company["_id"],
        "name": req.name.strip(),
        "email": clean_email,
        "password_hash": hash_password(req.password),
        "role": role,
        "avatar_color": avatar_color,
        "created_at": now
    }
    res_user = await db.users.insert_one(user_doc)
    user_doc["_id"] = res_user.inserted_id

    # 4. Si nouvelle entreprise, initialiser un premier projet et des tâches de bienvenue
    if role == "ADMIN":
        project_doc = {
            "company_id": company["_id"],
            "name": "Démarrage & Onboarding",
            "description": "Projet d'introduction pour découvrir les fonctionnalités du Kanban Luke",
            "status": "ACTIVE",
            "member_ids": [user_doc["_id"]],
            "created_at": now,
            "updated_at": now
        }
        res_proj = await db.projects.insert_one(project_doc)
        p_id = res_proj.inserted_id

        starter_tasks = [
            {
                "company_id": company["_id"],
                "project_id": p_id,
                "title": "Bienvenue sur Luke SaaS !",
                "description": "Découvrez le tableau Kanban en glissant-déposant les cartes entre colonnes.",
                "status": "TODO",
                "priority": "HIGH",
                "position": 1000,
                "assignee_id": user_doc["_id"],
                "labels": ["Onboarding", "Docs"],
                "subtasks": [
                    {"id": "st-1", "title": "Personnaliser son profil", "done": False},
                    {"id": "st-2", "title": "Inviter des collaborateurs", "done": False}
                ],
                "comments": [],
                "created_at": now,
                "updated_at": now
            },
            {
                "company_id": company["_id"],
                "project_id": p_id,
                "title": "Explorer les métriques et l'export",
                "description": "Consultez les statistiques du projet et exportez en CSV ou JSON.",
                "status": "IN_PROGRESS",
                "priority": "MEDIUM",
                "position": 1000,
                "assignee_id": user_doc["_id"],
                "labels": ["Features"],
                "subtasks": [],
                "comments": [],
                "created_at": now,
                "updated_at": now
            }
        ]
        await db.tasks.insert_many(starter_tasks)

    # 5. Création de session
    token = generate_token(32)
    session_doc = {
        "token": token,
        "user_id": user_doc["_id"],
        "company_id": company["_id"],
        "created_at": now,
        "expires_at": now + timedelta(days=7)
    }
    await db.sessions.insert_one(session_doc)

    return {
        "token": token,
        "user": serialize_doc(user_doc),
        "company": serialize_doc(company),
        "message": f"Compte et organisation '{company['name']}' créés avec succès !"
    }


@router.post("/forgot-password")
async def forgot_password(req: ForgotPasswordRequest):
    """
    Génère une demande de réinitialisation de mot de passe.
    Retourne le code de sécurité pour permettre la validation immédiate (idéal en SaaS / démo sans serveur SMTP).
    """
    db = get_database()
    clean_email = req.email.lower().strip()

    user = await db.users.find_one({"email": clean_email})
    if not user:
        # Réponse générique pour éviter le scanning d'emails, mais code fictif
        return {
            "status": "success",
            "message": "Si cette adresse est enregistrée, un code de réinitialisation a été préparé.",
            "reset_code": None,
            "email": clean_email
        }

    now = datetime.now(timezone.utc)
    reset_code = generate_reset_code()

    # Enregistrement du code de réinitialisation valable 30 minutes
    reset_doc = {
        "token": reset_code,
        "user_id": user["_id"],
        "email": clean_email,
        "created_at": now,
        "expires_at": now + timedelta(minutes=30),
        "used": False
    }
    await db.password_resets.insert_one(reset_doc)

    return {
        "status": "success",
        "message": f"Code de réinitialisation généré pour {user['name']}.",
        "reset_code": reset_code,
        "email": clean_email,
        "expires_in_minutes": 30
    }


@router.post("/reset-password")
async def reset_password(req: ResetPasswordRequest):
    """
    Réinitialise le mot de passe d'un utilisateur à l'aide d'un code de vérification valide.
    """
    db = get_database()
    code = req.token.strip().upper()
    now = datetime.now(timezone.utc)

    reset_entry = await db.password_resets.find_one({
        "token": code,
        "used": False,
        "expires_at": {"$gt": now}
    })

    if not reset_entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Code de réinitialisation invalide, déjà utilisé ou expiré."
        )

    # Mise à jour du mot de passe
    new_hash = hash_password(req.new_password)
    await db.users.update_one(
        {"_id": reset_entry["user_id"]},
        {"$set": {"password_hash": new_hash}}
    )

    # Marquer le jeton comme utilisé
    await db.password_resets.update_one(
        {"_id": reset_entry["_id"]},
        {"$set": {"used": True}}
    )

    # Invalider toutes les anciennes sessions actives de cet utilisateur
    await db.sessions.delete_many({"user_id": reset_entry["user_id"]})

    return {
        "status": "success",
        "message": "Votre mot de passe a été mis à jour avec succès. Vous pouvez maintenant vous connecter."
    }


@router.get("/me")
async def get_me(session: dict = Depends(get_active_session)):
    """
    Retourne les informations du profil utilisateur et de l'entreprise pour la session active.
    """
    db = get_database()
    user = await db.users.find_one({"_id": session["user_id"]})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Utilisateur de la session introuvable."
        )

    company = await db.companies.find_one({"_id": session["company_id"]})
    return {
        "user": serialize_doc(user),
        "company": serialize_doc(company)
    }


@router.post("/logout")
async def logout(session: dict = Depends(get_active_session)):
    """
    Révoque la session active.
    """
    db = get_database()
    await db.sessions.delete_one({"_id": session["_id"]})
    return {"message": "Déconnexion réussie."}
