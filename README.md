# Luke

Luke est une application web SaaS de gestion de projet pensée pour les PME, les agences et les équipes qui souhaitent suivre simplement leur activité. Inspirée des outils comme Trello, Notion et ClickUp, elle rassemble les entreprises, les projets, les collaborateurs et les tâches dans une interface claire avec tableau Kanban.

Le projet a été développé avec **FastAPI**, **MongoDB** et une interface web en HTML, CSS et JavaScript. Il peut être entièrement démarré avec Docker Compose.

## Fonctionnalités demandées

- Gestion des entreprises
- Gestion des utilisateurs
- Gestion des projets
- Gestion des tâches et tableau Kanban

## Fonctionnalités supplémentaires

- **Filtres rapides** : affichage des tâches par membre, pour soi ou par niveau de priorité.
- **Jauge d'avancement** : pourcentage calculé automatiquement à partir des tâches terminées.
- **Étiquettes thématiques** : badges visuels associés aux tâches.
- **Priorités colorées** : distinction immédiate des tâches basse, moyenne ou haute priorité.
- **Indicateurs d'échéance** : date visible directement sur chaque tâche.
- **Sélecteur d'entreprise** : changement rapide d'espace de travail pour constater l'isolation des données.
- **Gestion des membres d'un projet** : ajout ou retrait des collaborateurs depuis les réglages.
- **Interface moderne et responsive** : tableau adapté aux grands écrans et mise en page simplifiée sur les écrans plus petits.
- **Données de démonstration** : premier lancement avec deux entreprises, des membres et un projet Kanban prêt à utiliser.

## Architecture

Luke utilise une architecture FastAPI légère avec quatre collections MongoDB :

- `companies` pour les entreprises ;
- `users` pour les utilisateurs ;
- `projects` pour les projets et leurs membres ;
- `tasks` pour les tâches du tableau Kanban.

Les projets, utilisateurs et tâches contiennent un champ `company_id`. Ce champ garantit l'isolation des données entre entreprises et prépare l'application à une montée en charge avec réplication ou sharding.

La connexion à MongoDB est externalisée dans la variable d'environnement `MONGO_URI`. Elle peut donc être adaptée à une instance standalone, à un replica set ou à un routeur `mongos` sans modifier le code Python.

## Démarrage du projet


### Lancement

Depuis la racine du projet, exécutez :

```sh
docker compose up -d --build
```

Puis ouvrez :

<http://localhost:8000>

Au premier démarrage, MongoDB reçoit automatiquement les données de démonstration. L'entreprise **Atelier Nova** contient notamment le projet **Refonte du site**.


## API

La documentation interactive générée automatiquement par FastAPI est disponible à l'adresse :

<http://localhost:8000/docs>

Elle permet de consulter les routes, les modèles de données et de tester les opérations CRUD directement depuis le navigateur.

## Organisation du projet

- `app/main.py` : API FastAPI et routes HTTP.
- `app/database.py` : connexion MongoDB et création des index.
- `app/models.py` : modèles Pydantic des données.
- `app/seed.py` : données de démonstration.
- `app/templates/` : template HTML principal.
- `app/static/` : feuilles de styles et logique JavaScript.
- `compose.yml` : services Docker de l'application et de MongoDB.
- `Dockerfile` : image du backend FastAPI.

