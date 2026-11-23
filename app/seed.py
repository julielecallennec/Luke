import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database import get_database
from app.services.security import hash_password as hash_pw

logger = logging.getLogger("luke.seed")


async def seed_demo_data(database: Optional[AsyncIOMotorDatabase] = None) -> None:
    """
    Insère automatiquement deux entreprises complètes de démonstration
    si la base de données est vide au démarrage.
    """
    db = database if database is not None else get_database()
    existing_companies = await db.companies.count_documents({})
    if existing_companies > 0:
        await ensure_demo_accounts(db)
        logger.info(f"Base de données déjà initialisée ({existing_companies} entreprises trouvées). Pas de seed nécessaire.")
        return

    logger.info("Base de données vide détectée : injection des données de démonstration Luke...")

    now = datetime.now(timezone.utc)

    # =========================================================================
    # 1. ENTREPRISE 1 : Agence Web Créative (Plan PRO)
    # =========================================================================
    comp1 = {
        "name": "Agence Web Créative",
        "slug": "agence-web-creative",
        "plan": "PRO",
        "created_at": now - timedelta(days=30),
        "updated_at": now - timedelta(days=2)
    }
    c1_res = await db.companies.insert_one(comp1)
    c1_id = c1_res.inserted_id

    # Utilisateurs de l'entreprise 1
    users_c1 = [
        {
            "company_id": c1_id,
            "name": "Alice Martin",
            "email": "alice@agence-creative.fr",
            "password_hash": hash_pw("alice123"),
            "role": "ADMIN",
            "avatar_color": "#4F46E5",  # Indigo
            "created_at": now - timedelta(days=30)
        },
        {
            "company_id": c1_id,
            "name": "Bob Dupont",
            "email": "bob@agence-creative.fr",
            "password_hash": hash_pw("bob123"),
            "role": "MEMBER",
            "avatar_color": "#10B981",  # Emerald
            "created_at": now - timedelta(days=25)
        },
        {
            "company_id": c1_id,
            "name": "Clara Bernard",
            "email": "clara@agence-creative.fr",
            "password_hash": hash_pw("clara123"),
            "role": "MEMBER",
            "avatar_color": "#F59E0B",  # Amber
            "created_at": now - timedelta(days=20)
        }
    ]
    u1_res = await db.users.insert_many(users_c1)
    u_alice_id = u1_res.inserted_ids[0]
    u_bob_id = u1_res.inserted_ids[1]
    u_clara_id = u1_res.inserted_ids[2]

    # Projet 1 Entreprise 1
    p1_c1 = {
        "company_id": c1_id,
        "name": "Refonte Site E-commerce",
        "description": "Développement de la nouvelle boutique client mobile-first avec tunnel d'achat optimisé",
        "status": "ACTIVE",
        "member_ids": [u_alice_id, u_bob_id, u_clara_id],
        "created_at": now - timedelta(days=15),
        "updated_at": now - timedelta(hours=1)
    }
    p1_res = await db.projects.insert_one(p1_c1)
    p1_id = p1_res.inserted_id

    # Tâches du Projet 1 (4 colonnes Kanban)
    tasks_p1 = [
        # TODO
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_clara_id,
            "title": "Maquettage Figma du tunnel de commande",
            "description": "Concevoir les écrans du récapitulatif panier, sélection de livraison et paiement en 1 clic.",
            "status": "TODO",
            "priority": "HIGH",
            "position": 0,
            "tags": ["Design", "UX", "Mobile"],
            "due_date": now + timedelta(days=3),
            "subtasks": [
                {"id": "st101", "title": "Wireframes Desktop et Tablette", "done": True},
                {"id": "st102", "title": "Écran mobile panier et livraison", "done": False},
                {"id": "st103", "title": "Validation responsive avec le client", "done": False}
            ],
            "comments": [
                {
                    "id": "cm101",
                    "user_id": str(u_alice_id),
                    "user_name": "Alice Martin",
                    "user_avatar_color": "#4F46E5",
                    "content": "Penser au responsive pour les écrans iPhone 13/14 et au mode sombre.",
                    "created_at": (now - timedelta(days=2)).isoformat()
                }
            ],
            "created_at": now - timedelta(days=5),
            "updated_at": now - timedelta(days=5)
        },
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_bob_id,
            "title": "Sélection et contrat passerelle Stripe",
            "description": "Comparer les commissions et activer le compte de test Stripe Connect pour la marketplace.",
            "status": "TODO",
            "priority": "MEDIUM",
            "position": 1,
            "tags": ["Fintech", "Backend"],
            "due_date": now + timedelta(days=7),
            "subtasks": [
                {"id": "st104", "title": "Génération des clés API de test Stripe", "done": True},
                {"id": "st105", "title": "Signature du mandat SEPA de test", "done": False}
            ],
            "comments": [],
            "created_at": now - timedelta(days=4),
            "updated_at": now - timedelta(days=4)
        },
        # IN_PROGRESS
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_bob_id,
            "title": "Développement API catalogue produits (FastAPI)",
            "description": "Endpoints de recherche plein texte, filtres par catégorie, pagination et calcul de stock.",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "position": 0,
            "tags": ["Backend", "FastAPI", "MongoDB"],
            "due_date": now + timedelta(days=1),
            "subtasks": [
                {"id": "st201", "title": "Indexation texte sur les titres et tags", "done": True},
                {"id": "st202", "title": "Pagination avec curseur MongoDB", "done": True},
                {"id": "st203", "title": "Mise en cache Redis optionnelle", "done": False}
            ],
            "comments": [
                {
                    "id": "cm201",
                    "user_id": str(u_clara_id),
                    "user_name": "Clara Bernard",
                    "user_avatar_color": "#F59E0B",
                    "content": "J'ai testé les endpoints sur Swagger, la pagination marche impeccablement.",
                    "created_at": (now - timedelta(hours=3)).isoformat()
                }
            ],
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(hours=4)
        },
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_clara_id,
            "title": "Intégration de la page d'accueil avec TailwindCSS",
            "description": "Composant carrousel responsive, bandeau de promotions et section meilleures ventes.",
            "status": "IN_PROGRESS",
            "priority": "LOW",
            "position": 1,
            "tags": ["Frontend", "TailwindCSS"],
            "due_date": now + timedelta(days=4),
            "subtasks": [
                {"id": "st204", "title": "Carrousel héro dynamique", "done": True},
                {"id": "st205", "title": "Section grille produits phares", "done": False}
            ],
            "comments": [],
            "created_at": now - timedelta(days=3),
            "updated_at": now - timedelta(hours=2)
        },
        # IN_REVIEW
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_alice_id,
            "title": "Audit d'accessibilité RGAA / WCAG AA",
            "description": "Vérification des contrastes de couleur, navigation au clavier et balises aria sur le header.",
            "status": "IN_REVIEW",
            "priority": "MEDIUM",
            "position": 0,
            "tags": ["Audit", "Qualité"],
            "due_date": now - timedelta(days=1),
            "subtasks": [
                {"id": "st301", "title": "Lighthouse score > 95", "done": True},
                {"id": "st302", "title": "Vérification balises aria-label", "done": False}
            ],
            "comments": [],
            "created_at": now - timedelta(days=6),
            "updated_at": now - timedelta(hours=8)
        },
        # DONE
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_alice_id,
            "title": "Configuration CI/CD & conteneurs Docker",
            "description": "Mise en place de compose.yml, Dockerfile multi-stage et vérification des variables d'environnement.",
            "status": "DONE",
            "priority": "HIGH",
            "position": 0,
            "tags": ["DevOps", "Docker"],
            "due_date": now - timedelta(days=10),
            "subtasks": [
                {"id": "st401", "title": "Création Dockerfile Python 3.11", "done": True},
                {"id": "st402", "title": "Configuration compose.yml et bridge network", "done": True}
            ],
            "comments": [
                {
                    "id": "cm401",
                    "user_id": str(u_bob_id),
                    "user_name": "Bob Dupont",
                    "user_avatar_color": "#10B981",
                    "content": "Déploiement en 1 commande validé sans accroc.",
                    "created_at": (now - timedelta(days=10)).isoformat()
                }
            ],
            "created_at": now - timedelta(days=14),
            "updated_at": now - timedelta(days=10)
        },
        {
            "company_id": c1_id,
            "project_id": p1_id,
            "assignee_id": u_alice_id,
            "title": "Initialisation du dépôt Git & architecture",
            "description": "Définition de l'arborescence FastAPI, conventions de commit et documentation technique.",
            "status": "DONE",
            "priority": "LOW",
            "position": 1,
            "tags": ["Setup", "Git"],
            "due_date": now - timedelta(days=12),
            "subtasks": [
                {"id": "st403", "title": "Arborescence app/models et app/routers", "done": True}
            ],
            "comments": [],
            "created_at": now - timedelta(days=15),
            "updated_at": now - timedelta(days=12)
        }
    ]
    await db.tasks.insert_many(tasks_p1)

    # Projet 2 Entreprise 1
    p2_c1 = {
        "company_id": c1_id,
        "name": "Application Mobile iOS & Android",
        "description": "Application compagnon pour les clients VIP et notifications push d'expédition",
        "status": "ACTIVE",
        "member_ids": [u_alice_id, u_bob_id],
        "created_at": now - timedelta(days=10),
        "updated_at": now - timedelta(days=1)
    }
    p2_res = await db.projects.insert_one(p2_c1)
    p2_id = p2_res.inserted_id

    tasks_p2 = [
        {
            "company_id": c1_id,
            "project_id": p2_id,
            "assignee_id": u_bob_id,
            "title": "Initialisation projet React Native avec Expo",
            "description": "Configuration TypeScript, ESLint et navigation par onglets.",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "position": 0,
            "tags": ["Mobile", "React Native"],
            "due_date": now + timedelta(days=5),
            "subtasks": [
                {"id": "st501", "title": "Expo Router configuration", "done": True},
                {"id": "st502", "title": "Support notifications Push Expo", "done": False}
            ],
            "comments": [],
            "created_at": now - timedelta(days=2),
            "updated_at": now - timedelta(hours=3)
        },
        {
            "company_id": c1_id,
            "project_id": p2_id,
            "assignee_id": u_alice_id,
            "title": "Validation du cahier des charges client",
            "description": "Signature du périmètre V1 avec la direction marketing.",
            "status": "DONE",
            "priority": "LOW",
            "position": 0,
            "tags": ["Gestion", "Client"],
            "due_date": now - timedelta(days=5),
            "subtasks": [],
            "comments": [],
            "created_at": now - timedelta(days=10),
            "updated_at": now - timedelta(days=5)
        }
    ]
    await db.tasks.insert_many(tasks_p2)

    # =========================================================================
    # 2. ENTREPRISE 2 : TechNova Solutions (Plan ENTERPRISE)
    # =========================================================================
    comp2 = {
        "name": "TechNova Solutions",
        "slug": "technova-solutions",
        "plan": "ENTERPRISE",
        "created_at": now - timedelta(days=45),
        "updated_at": now - timedelta(days=1)
    }
    c2_res = await db.companies.insert_one(comp2)
    c2_id = c2_res.inserted_id

    # Utilisateurs Entreprise 2
    users_c2 = [
        {
            "company_id": c2_id,
            "name": "David Moreau",
            "email": "david@technova.io",
            "password_hash": hash_pw("david123"),
            "role": "ADMIN",
            "avatar_color": "#8B5CF6",
            "created_at": now - timedelta(days=45)
        },
        {
            "company_id": c2_id,
            "name": "Emma Leroy",
            "email": "emma@technova.io",
            "password_hash": hash_pw("emma123"),
            "role": "MEMBER",
            "avatar_color": "#EC4899",
            "created_at": now - timedelta(days=40)
        }
    ]
    u2_res = await db.users.insert_many(users_c2)
    u_david_id = u2_res.inserted_ids[0]
    u_emma_id = u2_res.inserted_ids[1]

    # Projet 1 Entreprise 2
    p1_c2 = {
        "company_id": c2_id,
        "name": "Plateforme Cloud & Observabilité",
        "description": "Mise en place de l'infrastructure multi-cloud haute disponibilité avec supervision temps réel",
        "status": "ACTIVE",
        "member_ids": [u_david_id, u_emma_id],
        "created_at": now - timedelta(days=20),
        "updated_at": now - timedelta(days=1)
    }
    p2_c2_res = await db.projects.insert_one(p1_c2)
    p_tech_id = p2_c2_res.inserted_id

    tasks_c2 = [
        {
            "company_id": c2_id,
            "project_id": p_tech_id,
            "assignee_id": u_emma_id,
            "title": "Déploiement du cluster Prometheus & Grafana",
            "description": "Collecte des métriques CPU, RAM et latences HTTP des microservices.",
            "status": "TODO",
            "priority": "HIGH",
            "position": 0,
            "tags": ["Cloud", "Monitoring"],
            "due_date": now + timedelta(days=6),
            "subtasks": [
                {"id": "st601", "title": "Helm chart Prometheus Stack", "done": True},
                {"id": "st602", "title": "Dashboard Grafana pour les métriques FastAPI", "done": False}
            ],
            "comments": [],
            "created_at": now - timedelta(days=4),
            "updated_at": now - timedelta(days=4)
        },
        {
            "company_id": c2_id,
            "project_id": p_tech_id,
            "assignee_id": u_david_id,
            "title": "Préparation Sharding MongoDB (Partie II)",
            "description": "Validation de la clé { company_id: 1, _id: 1 } sur mongos et tests de requêtes ciblées.",
            "status": "IN_PROGRESS",
            "priority": "HIGH",
            "position": 0,
            "tags": ["MongoDB", "Sharding", "Scalabilité"],
            "due_date": now + timedelta(days=2),
            "subtasks": [
                {"id": "st701", "title": "Vérification des Targeted Queries", "done": True},
                {"id": "st702", "title": "Tests de basculement Replica Set", "done": False}
            ],
            "comments": [
                {
                    "id": "cm701",
                    "user_id": str(u_david_id),
                    "user_name": "David Moreau",
                    "user_avatar_color": "#8B5CF6",
                    "content": "La clé composée est validée, aucun scatter-gather sur les requêtes Kanban.",
                    "created_at": (now - timedelta(days=1)).isoformat()
                }
            ],
            "created_at": now - timedelta(days=8),
            "updated_at": now - timedelta(hours=6)
        },
        {
            "company_id": c2_id,
            "project_id": p_tech_id,
            "assignee_id": u_david_id,
            "title": "Benchmark de charge et tests de résilience",
            "description": "Simulation de 10 000 requêtes/seconde pour éprouver la scalabilité horizontale.",
            "status": "DONE",
            "priority": "MEDIUM",
            "position": 0,
            "tags": ["Performance", "QA"],
            "due_date": now - timedelta(days=2),
            "subtasks": [],
            "comments": [],
            "created_at": now - timedelta(days=12),
            "updated_at": now - timedelta(days=2)
        }
    ]
    await db.tasks.insert_many(tasks_c2)

    logger.info("Données de démonstration injectées avec succès (2 entreprises, 5 utilisateurs, 3 projets, 12 tâches avec sous-tâches & commentaires).")


async def ensure_demo_accounts(database: AsyncIOMotorDatabase) -> None:
    """Add demo accounts to an existing database without deleting user data."""
    now = datetime.now(timezone.utc)
    demos = [
        ({"name": "Agence Web Creative", "slug": "agence-web-creative", "plan": "PRO"}, [
            ("Alice Martin", "alice@agence-creative.fr", "alice123", "ADMIN", "#4F46E5"),
            ("Bob Dupont", "bob@agence-creative.fr", "bob123", "MEMBER", "#10B981"),
        ]),
        ({"name": "TechNova Solutions", "slug": "technova-solutions", "plan": "ENTERPRISE"}, [
            ("David Moreau", "david@technova.io", "david123", "ADMIN", "#8B5CF6"),
            ("Emma Leroy", "emma@technova.io", "emma123", "MEMBER", "#EC4899"),
        ]),
    ]

    for company_data, users_data in demos:
        company = await database.companies.find_one({"slug": company_data["slug"]})
        if company is None:
            company_doc = {**company_data, "created_at": now, "updated_at": now}
            result = await database.companies.insert_one(company_doc)
            company = {**company_doc, "_id": result.inserted_id}

        member_ids = []
        for name, email, password, role, avatar_color in users_data:
            fields = {
                "company_id": company["_id"], "name": name, "email": email,
                "password_hash": hash_pw(password), "role": role, "avatar_color": avatar_color,
            }
            user = await database.users.find_one({"company_id": company["_id"], "email": email})
            if user:
                await database.users.update_one({"_id": user["_id"]}, {"$set": fields})
                member_ids.append(user["_id"])
            else:
                fields["created_at"] = now
                result = await database.users.insert_one(fields)
                member_ids.append(result.inserted_id)

        project = await database.projects.find_one({"company_id": company["_id"]})
        if project is None:
            project_doc = {
                "company_id": company["_id"], "name": "Demo project",
                "description": "Project for trying the Luke demo accounts.",
                "status": "ACTIVE", "member_ids": member_ids,
                "created_at": now, "updated_at": now,
            }
            result = await database.projects.insert_one(project_doc)
            await database.tasks.insert_one({
                "company_id": company["_id"], "project_id": result.inserted_id,
                "assignee_id": member_ids[-1], "title": "Try the Kanban board",
                "description": "Move this task between columns.", "status": "TODO",
                "priority": "MEDIUM", "position": 0, "tags": ["Demo"],
                "due_date": None, "subtasks": [], "comments": [],
                "created_at": now, "updated_at": now,
            })


async def seed_demo() -> None:
    """Alias pour compatibilité."""
    await seed_demo_data()
