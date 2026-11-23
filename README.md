# Luke - SaaS de Gestion de Projet Agile Multi-Tenant 🚀

> Application SaaS de gestion de projet agile inspirée de Trello, Notion et ClickUp, propulsée par **FastAPI** et **MongoDB**, dotée d'un tableau Kanban interactif avec Drag & Drop temps réel et d'une isolation multi-tenant stricte préparée pour le Sharding horizontal.

---

## Table des Matières
1. [Aperçu & Fonctionnalités Clés](#-aperçu--fonctionnalités-clés)
2. [Lancement Rapide en 1 Commande](#-lancement-rapide-en-1-commande)
3. [Architecture MongoDB & Multi-Tenancy Stricte](#-architecture-mongodb--multi-tenancy-stricte)
4. [Schémas JSON des 4 Collections](#-schémas-json-des-4-collections)
5. [Stratégie d'Indexation](#-stratégie-dindexation)
6. [Préparation Native au Sharding (Partie II)](#-préparation-native-au-sharding-partie-ii)
7. [Données de Démonstration (Seed Data)](#-données-de-démonstration-seed-data)
8. [Documentation de l'API REST](#-documentation-de-lapi-rest)

---

## Aperçu & Fonctionnalités Clés

Luke offre une expérience utilisateur moderne servie directement par FastAPI avec TailwindCSS et SortableJS :

* **Tableau Kanban 4 Colonnes** : `À faire (TODO)`, `En cours (IN_PROGRESS)`, `En révision (IN_REVIEW)`, `Terminé (DONE)`.
* **Drag & Drop ultra-fluide** : Déplacement de cartes entre colonnes et réorganisation verticale instantanée avec mise à jour automatique des positions et statuts via `PATCH /api/tasks/{id}/move`.
* **Vue Tableau / Liste (Notion/ClickUp style)** : Basculez entre la vue Kanban et une vue tableau avec sélecteurs de statut direct, vue des sous-tâches et tri.
* **Sous-tâches & Checklists interactives** : Ajout de critères d'acceptation cochables directement sur les tâches avec jauge de complétion temps réel.
* **Commentaires & Échanges d'équipe** : Fil de discussion collaboratif intégré sur chaque tâche avec horodatage et auteur.
* **Tableau de bord Métriques & Analytics** : Dépliable en 1 clic pour suivre la répartition des tâches, l'avancement et la charge de travail par collaborateur.
* **Export de Données CSV & JSON** : Téléchargement instantané des données de projet pour reporting et réunions.
* **Ajout Rapide Inline (Trello style)** : Bouton "+ Ajouter une carte" au pied de chaque colonne pour créer des tâches au clavier.
* **Raccourcis Clavier intégrés** : `N` pour nouvelle tâche, `F` pour recherche en direct, `Esc` pour fermer les modales, `?` pour l'aide.
* **Workspace Switcher** : Bascule en 1 clic entre les entreprises abonnées (`Agence Web Créative`, `TechNova Solutions`...) pour démontrer visuellement l'isolation stricte des données.
* **Simulateur de Rôles (User Switcher)** : Permet d'endosser le profil d'un collaborateur `ADMIN` ou `MEMBER` avec pastille d'avatar personnalisée.
* **Jauge d'Avancement Dynamique** : Barre de progression animée calculant en temps réel le pourcentage et le ratio de tâches complétées (`DONE`) sur le projet actif.
* **Filtres Rapides Intelligents** :
  * Bouton **"Mes tâches"** filtrant instantanément sur le collaborateur connecté.
  * Filtrage par membre d'équipe assigné.
  * Filtrage par priorité (`HIGH`, `MEDIUM`, `LOW`).
  * Filtrage interactif au clic sur n'importe quel badge de tag.
  * Recherche plein texte en direct dans les titres, descriptions et tags.
* **Indicateurs Visuels** : Badges de priorités avec code couleur, tags multiples, et alertes visuelles sur les dates d'échéance dépassées (badges rouges `(En retard)`).
* **Suppression en Cascade Sécurisée** : La suppression d'une entreprise détruit en cascade tous ses projets, utilisateurs et tâches. La suppression d'un utilisateur désassigne ses tâches et le retire des projets de l'organisation.

---

## Lancement Rapide en 1 Commande

Le déploiement complet (FastAPI + MongoDB 7.0 + Seed automatique + Interface Web) s'effectue sans aucune action manuelle préalable.

Assurez-vous que Docker est démarré, puis lancez :

```bash
docker compose up -d --build
```

### URLs d'Accès :
* **Interface Web Luke** : [http://localhost:8000](http://localhost:8000)
* **Documentation Swagger interactive** : [http://localhost:8000/docs](http://localhost:8000/docs)
* **Spécification OpenAPI (JSON)** : [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)
* **Health Check** : [http://localhost:8000/health](http://localhost:8000/health)

Pour arrêter les conteneurs :
```bash
docker compose down
```

---

## Architecture MongoDB & Multi-Tenancy Stricte

### 1. Référencement (Normalized Data Model) vs Imbrication (Embedded)
Les données sont réparties en **4 collections distinctes** : `companies`, `users`, `projects`, `tasks`.
* **Évite la limite des 16 Mo BSON** : Les projets et tâches peuvent croître sans risquer de saturer le document parent de l'entreprise.
* **Concurrence & Performances Kanban** : Chaque déplacement de carte met à jour un document unitaire léger dans `tasks` sans poser de verrou sur tout le projet.

### 2. Dénormalisation Stratégique de `company_id`
Le champ `company_id` (`ObjectId`) est **obligatoirement présent et dénormalisé** dans `users`, `projects` et `tasks`.
* **Sécurité Backend Infaillible** : 100% des requêtes MongoDB (lecture, écriture, suppression) filtrent systématiquement par `{"company_id": current_company_id}`. Même si un utilisateur tente de manipuler un `_id` de tâche ou de projet dans l'URL, aucune fuite inter-entreprises n'est possible.
* L'identifiant d'entreprise est transmis automatiquement par le frontend via le header HTTP `X-Company-Id` (avec fallback fluide sur la première entreprise pour tester dans Swagger).

---

## Schémas JSON des 4 Collections

### 1. `companies` (Entreprises)
```json
{
  "_id": ObjectId("652a1b2c3d4e5f6a7b8c9d01"),
  "name": "Agence Web Créative",
  "slug": "agence-web-creative",
  "plan": "PRO",
  "created_at": "2026-10-14T18:00:00Z",
  "updated_at": "2026-10-14T18:00:00Z"
}
```

### 2. `users` (Collaborateurs)
```json
{
  "_id": ObjectId("652a1b2c3d4e5f6a7b8c9d02"),
  "company_id": ObjectId("652a1b2c3d4e5f6a7b8c9d01"),
  "name": "Alice Martin",
  "email": "alice@agence-creative.fr",
  "password_hash": "b2f69e...secure_hash",
  "role": "ADMIN",
  "avatar_color": "#4F46E5",
  "created_at": "2026-10-14T18:05:00Z"
}
```

### 3. `projects` (Projets)
```json
{
  "_id": ObjectId("652a1b2c3d4e5f6a7b8c9d03"),
  "company_id": ObjectId("652a1b2c3d4e5f6a7b8c9d01"),
  "name": "Refonte Site E-commerce",
  "description": "Développement de la boutique en ligne mobile-first",
  "status": "ACTIVE",
  "member_ids": [
    ObjectId("652a1b2c3d4e5f6a7b8c9d02")
  ],
  "created_at": "2026-10-14T18:10:00Z",
  "updated_at": "2026-10-14T18:10:00Z"
}
```

### 4. `tasks` (Tâches Kanban)
```json
{
  "_id": ObjectId("652a1b2c3d4e5f6a7b8c9d04"),
  "company_id": ObjectId("652a1b2c3d4e5f6a7b8c9d01"),
  "project_id": ObjectId("652a1b2c3d4e5f6a7b8c9d03"),
  "assignee_id": ObjectId("652a1b2c3d4e5f6a7b8c9d02"),
  "title": "Intégration du paiement Stripe",
  "description": "Mise en place du formulaire et du tunnel d'achat",
  "status": "IN_PROGRESS",
  "priority": "HIGH",
  "position": 0,
  "tags": ["Backend", "Fintech"],
  "due_date": "2026-11-10T18:00:00Z",
  "created_at": "2026-10-14T18:15:00Z",
  "updated_at": "2026-10-14T18:30:00Z"
}
```

---

## Stratégie d'Indexation

Les index sont créés automatiquement au démarrage de l'application FastAPI (`lifespan`) :

| Collection | Définition de l'Index | Propriété | Rôle & Performance |
|---|---|---|---|
| `companies` | `{ "slug": 1 }` | `Unique` | Accès instantané par URL et unicité du slug |
| `users` | `{ "company_id": 1, "email": 1 }` | `Unique` | Unicité de l'email au sein d'une même organisation |
| `projects` | `{ "company_id": 1, "member_ids": 1 }` | Standard | Accélération de la recherche des projets par membre |
| `tasks` | `{ "company_id": 1, "project_id": 1, "status": 1, "position": 1 }` | Composé | Couvre 100% de la requête d'affichage et de tri du tableau Kanban |

---

## Préparation Native au Sharding (Partie II)

Conformément au cahier des charges, l'application est conçue dès la Partie I pour évoluer vers un cluster distribué sans refonte :

1. **Aucune IP ni Port en dur** :
   Toute la configuration s'appuie sur la variable d'environnement `MONGO_URI` :
   * *Partie I (Standalone)* : `MONGO_URI=mongodb://mongodb:27017/luke_db`
   * *Partie II (Cluster Shardé avec mongos)* : `MONGO_URI=mongodb://mongos1:27017,mongos2:27017/luke_db?retryWrites=true&w=majority`
2. **Co-localisation des données par Shard Key** :
   En utilisant la clé `{ "company_id": 1, "_id": 1 }`, toutes les entités (`users`, `projects`, `tasks`) d'une même entreprise résideront sur le même Shard.
   * Les requêtes de l'application seront des **Targeted Queries** directes dirigées par `mongos` vers un serveur unique, évitant le surcoût d'un balayage global (*Scatter-Gather*).

---

## Données de Démonstration (Seed Data)

Au premier lancement, si la base est vide, deux entreprises complètes et indépendantes sont automatiquement créées :

### 1. Agence Web Créative (`slug`: `agence-web-creative`, `plan`: `PRO`)
* **Utilisateurs** :
  * **Alice Martin** (`alice@agence-creative.fr`, rôle `ADMIN`, avatar `#4F46E5`)
  * **Bob Dupont** (`bob@agence-creative.fr`, rôle `MEMBER`, avatar `#10B981`)
  * **Clara Bernard** (`clara@agence-creative.fr`, rôle `MEMBER`, avatar `#F59E0B`)
* **Projet 1** : *"Refonte Site E-commerce"* (7 tâches complètes réparties dans les 4 colonnes).
* **Projet 2** : *"Application Mobile iOS & Android"* (2 tâches en cours/terminées).

### 2. TechNova Solutions (`slug`: `technova-solutions`, `plan`: `ENTERPRISE`)
* **Utilisateurs** :
  * **David Moreau** (`david@technova.io`, rôle `ADMIN`, avatar `#8B5CF6`)
  * **Emma Leroy** (`emma@technova.io`, rôle `MEMBER`, avatar `#EC4899`)
* **Projet 1** : *"Plateforme Cloud & Observabilité"* (3 tâches techniques Sharding / Prometheus).

---



---

## Documentation de l'API REST

| Méthode | Endpoint | Description | Sécurité & Cascade |
|---|---|---|---|
| `GET` | `/api/companies` | Liste toutes les entreprises | Vue SaaS globale |
| `POST` | `/api/companies` | Crée une entreprise | Génération automatique de slug |
| `GET` | `/api/companies/{id}` | Détail d'une entreprise | Décompte agrégé |
| `PUT` | `/api/companies/{id}` | Mise à jour d'une entreprise | Nom, slug, plan |
| `DELETE` | `/api/companies/{id}` | Supprime une entreprise | **Suppression en cascade** (`projects`, `users`, `tasks`) |
| `GET` | `/api/users` | Liste les utilisateurs du workspace | Filtré par `company_id` |
| `POST` | `/api/users` | Ajoute un collaborateur | `company_id` obligatoire, email unique |
| `PUT` | `/api/users/{id}` | Met à jour un utilisateur | Filtré par `company_id` |
| `DELETE` | `/api/users/{id}` | Supprime un collaborateur | Nettoyage des `member_ids` et tâches |
| `GET` | `/api/projects` | Liste les projets avec progression | Filtré par `company_id` |
| `POST` | `/api/projects` | Crée un projet | Validation des `member_ids` |
| `GET` | `/api/projects/{id}` | Détail d'un projet | Filtré par `company_id` |
| `GET` | `/api/projects/{id}/stats` | **Analytics & Métriques du projet** | Tâches par statut/priorité, retards, charge équipe |
| `GET` | `/api/projects/{id}/export` | **Export CSV / JSON** | Téléchargement des données de projet |
| `PUT` | `/api/projects/{id}` | Met à jour un projet | Filtré par `company_id` |
| `DELETE` | `/api/projects/{id}` | Supprime un projet | **Suppression en cascade** de ses tâches |
| `GET` | `/api/tasks` | Tâches ordonnées du Kanban | Filtres `project_id`, `status`, `assignee`, `priority`, `tag`, `search` |
| `POST` | `/api/tasks` | Crée une tâche Kanban | Calcul automatique de `position` |
| `GET` | `/api/tasks/{id}` | Détail d'une tâche avec sous-tâches | Filtré par `company_id` |
| `PUT` | `/api/tasks/{id}` | Modifie une tâche | Filtré par `company_id` |
| `PATCH` | `/api/tasks/{id}/move` | **Drag & Drop Kanban** | Réorganisation ordonnée des positions |
| `POST` | `/api/tasks/{id}/duplicate` | **Dupliquer une tâche** | Clone la tâche avec ses sous-tâches |
| `POST` | `/api/tasks/{id}/subtasks` | **Ajout d'une sous-tâche** | Ajout d'un critère d'acceptation cochable |
| `PATCH` | `/api/tasks/{id}/subtasks/{sid}` | **Bascule état sous-tâche** | Coche ou décoche une sous-tâche |
| `DELETE` | `/api/tasks/{id}/subtasks/{sid}` | Supprime une sous-tâche | Retrait de la checklist |
| `POST` | `/api/tasks/{id}/comments` | **Ajout d'un commentaire** | Fil d'échange d'équipe horodaté |
| `DELETE` | `/api/tasks/{id}/comments/{cid}` | Supprime un commentaire | Nettoyage du fil |
| `DELETE` | `/api/tasks/{id}` | Supprime une tâche | Filtré par `company_id` |

---

*Développé dans le cadre du projet BUT3 Informatique - SaaS Luke.*
