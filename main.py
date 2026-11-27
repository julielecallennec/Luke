import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import settings
from app.database import get_client, get_database, init_indexes, ping_database_with_retry
from app.routers import auth, cluster, companies, projects, tasks, users
from app.seed import seed_demo_data

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("luke.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Cycle de vie de l'application FastAPI :
    1. Connexion résiliente à MongoDB (avec retry pour Docker Compose).
    2. Création automatique des index requis.
    3. Injection des données de démonstration si la base est vide.
    """
    logger.info(f"Démarrage de {settings.APP_NAME}...")
    logger.info(f"Vérification de la connexion MongoDB via MONGO_URI...")

    # Attente active de MongoDB
    is_connected = await ping_database_with_retry(max_retries=15, delay_seconds=1.0)
    if is_connected:
        # Création des index
        await init_indexes()
        # Seed initial
        await seed_demo_data()
    else:
        logger.error("ATTENTION : MongoDB n'a pas répondu. L'application démarre en mode dégradé.")

    yield

    logger.info("Fermeture de l'application Luke et déconnexion MongoDB...")
    client = get_client()
    if client:
        client.close()


openapi_tags = [
    {
        "name": "Cluster & Sharding (Partie II)",
        "description": "Endpoints d'observabilité et de monitoring du cluster distribué : topologie des shards, Replica Sets, état du sharding et protocole de basculement (Failover)."
    },
    {
        "name": "Authentification & Profil",
        "description": "Gestion des sessions, connexion des collaborateurs de démonstration et profil actif."
    },
    {
        "name": "Entreprises (Companies)",
        "description": "Gestion des workspaces clients (Tenants), plans tarifaires et suppression en cascade multi-tenant."
    },
    {
        "name": "Utilisateurs (Collaborateurs)",
        "description": "Gestion des membres d'équipe, attribution des rôles (ADMIN / MEMBER) et avatars."
    },
    {
        "name": "Projets",
        "description": "Gestion des projets, assignation des membres, statistiques d'avancement et export CSV / JSON."
    },
    {
        "name": "Tâches Kanban",
        "description": "Opérations CRUD sur les tâches du tableau Kanban, réorganisation Drag & Drop, checklists de sous-tâches et commentaires."
    },
    {
        "name": "Système",
        "description": "Health checks et surveillance de la disponibilité applicative."
    }
]

app = FastAPI(
    title="Luke - SaaS Agile Kanban API",
    description="""
API REST Multi-tenant pour la gestion de projet agile par tableau Kanban.

Projet BUT3 Informatique :
- **Partie I (Standalone)** : Modélisation 4 collections (companies, users, projects, tasks), isolation multi-tenant stricte (`company_id`), index composés optimisés et requêtes ciblées.
- **Partie II (Scaleup Haute Disponibilité & Sharding)** : Cluster distribué MongoDB 12 conteneurs, 3 Replica Sets de 3 nœuds (Quorum N/2 + 1), routage intelligent `mongos`, Zone Sharding multi-tenant déterministe et tolérance aux pannes (Failover automatique transparent avec `retryWrites=true`).
    """,
    version="2.0.0",
    openapi_tags=openapi_tags,
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware anti-cache pour le développement local
@app.middleware("http")
async def add_no_cache_header(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

# Configuration des dossiers statiques et templates
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "app" / "static"
templates_dir = BASE_DIR / "app" / "templates"

app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
templates = Jinja2Templates(directory=str(templates_dir))

# Enregistrement des routeurs REST
app.include_router(auth.router)
app.include_router(companies.router)
app.include_router(users.router)
app.include_router(projects.router)
app.include_router(tasks.router)
app.include_router(cluster.router)


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_home(request: Request):
    """
    Sert l'interface Web SaaS Kanban interactive.
    """
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"app_name": settings.APP_NAME}
    )


@app.get("/health", tags=["Système"])
async def health_check():
    """
    Endpoint de surveillance de santé du service.
    """
    db_ok = False
    try:
        client = get_client()
        await client.admin.command("ping")
        db_ok = True
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "database_connected": db_ok,
        "app": settings.APP_NAME
    }
