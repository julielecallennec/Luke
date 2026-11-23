import uuid
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import get_database, serialize_doc, serialize_docs
from app.dependencies import get_current_company_id, get_current_user_id, parse_object_id
from app.models.task import (
    SubTask,
    SubTaskCreate,
    SubTaskToggle,
    TaskComment,
    TaskCommentCreate,
    TaskCreate,
    TaskMove,
    TaskResponse,
    TaskUpdate
)
from app.services.discord import send_discord_notification

router = APIRouter(prefix="/api/tasks", tags=["Tâches & Kanban (Tasks)"])


async def enrich_task(task: dict, db) -> dict:
    """
    Enrichit une tâche avec les données de l'assigné (nom, email, couleur d'avatar),
    et s'assure de l'existence des listes subtasks et comments.
    """
    assignee_id = task.get("assignee_id")
    assignee = None
    if assignee_id:
        user_doc = await db.users.find_one({"_id": assignee_id, "company_id": task["company_id"]})
        if user_doc:
            assignee = serialize_doc(user_doc)

    doc = serialize_doc(task)
    doc["assignee"] = assignee
    if "subtasks" not in doc or doc["subtasks"] is None:
        doc["subtasks"] = []
    if "comments" not in doc or doc["comments"] is None:
        doc["comments"] = []
    return doc


@router.get("", response_model=List[TaskResponse])
async def list_tasks(
    project_id: Optional[str] = Query(None, description="Filtrer par projet"),
    status: Optional[str] = Query(None, description="Filtrer par statut Kanban"),
    assignee_id: Optional[str] = Query(None, description="Filtrer par collaborateur assigné"),
    priority: Optional[str] = Query(None, description="Filtrer par priorité"),
    tag: Optional[str] = Query(None, description="Filtrer par tag précis"),
    search: Optional[str] = Query(None, description="Recherche textuelle dans le titre, description ou tags"),
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Récupère les tâches de l'entreprise active, triées par position dans le Kanban.
    Applique systématiquement le filtre d'isolation Multi-Tenant : {"company_id": current_company_id}.
    """
    db = get_database()
    mongo_filter: dict = {"company_id": company_id}

    if project_id:
        mongo_filter["project_id"] = parse_object_id(project_id, "project_id")

    if status:
        mongo_filter["status"] = status.upper()

    if assignee_id:
        if assignee_id.lower() in ("null", "none", "unassigned"):
            mongo_filter["assignee_id"] = None
        else:
            mongo_filter["assignee_id"] = parse_object_id(assignee_id, "assignee_id")

    if priority:
        mongo_filter["priority"] = priority.upper()

    if tag:
        mongo_filter["tags"] = {"$in": [tag]}

    if search:
        s_regex = {"$regex": search, "$options": "i"}
        mongo_filter["$or"] = [
            {"title": s_regex},
            {"tags": s_regex},
            {"description": s_regex}
        ]

    # Tri par colonne puis position verticale ordonnée
    cursor = db.tasks.find(mongo_filter).sort([("status", 1), ("position", 1)])
    tasks = await cursor.to_list(length=500)

    enriched = [await enrich_task(t, db) for t in tasks]
    return enriched


@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Crée une nouvelle tâche Kanban au sein d'un projet de l'entreprise active.
    Calcule automatiquement sa position verticale dans la colonne si non spécifiée.
    """
    db = get_database()
    now = datetime.now(timezone.utc)

    pid = parse_object_id(task_in.project_id, "project_id")
    # Vérification que le projet existe bien dans cette entreprise
    project = await db.projects.find_one({"_id": pid, "company_id": company_id})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Le projet cible n'existe pas dans cette entreprise."
        )

    # Vérification de l'assigné s'il est spécifié
    aid = None
    if task_in.assignee_id:
        aid = parse_object_id(task_in.assignee_id, "assignee_id")
        user = await db.users.find_one({"_id": aid, "company_id": company_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="L'utilisateur assigné n'appartient pas à cette entreprise."
            )

    # Calcul de la position : insérer à la suite des tâches existantes dans la colonne
    last_task = await db.tasks.find_one(
        {"company_id": company_id, "project_id": pid, "status": task_in.status},
        sort=[("position", -1)]
    )
    next_position = (last_task["position"] + 1) if last_task and "position" in last_task else 0

    subtasks_data = [st.model_dump() for st in task_in.subtasks]

    task_doc = {
        "company_id": company_id,
        "project_id": pid,
        "assignee_id": aid,
        "title": task_in.title.strip(),
        "description": task_in.description.strip(),
        "status": task_in.status,
        "priority": task_in.priority,
        "position": next_position,
        "tags": [t.strip() for t in task_in.tags if t.strip()],
        "due_date": datetime.fromisoformat(task_in.due_date.replace("Z", "+00:00")) if task_in.due_date else None,
        "subtasks": subtasks_data,
        "comments": [],
        "created_at": now,
        "updated_at": now
    }

    res = await db.tasks.insert_one(task_doc)
    task_doc["_id"] = res.inserted_id

    # Notification Discord informative
    await send_discord_notification(
        title=f"Nouvelle tâche créée : {task_doc['title']}",
        description=f"Projet : **{project['name']}** | Statut : `{task_doc['status']}` | Priorité : `{task_doc['priority']}`",
        color=0x4F46E5
    )

    return await enrich_task(task_doc, db)


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Détail d'une tâche de l'entreprise active.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    task = await db.tasks.find_one({"_id": tid, "company_id": company_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tâche introuvable dans cette entreprise."
        )

    return await enrich_task(task, db)


@router.put("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    task_in: TaskUpdate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Met à jour les informations d'une tâche de l'entreprise active.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    task = await db.tasks.find_one({"_id": tid, "company_id": company_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tâche introuvable dans cette entreprise."
        )

    update_fields = {}
    if task_in.title is not None:
        update_fields["title"] = task_in.title.strip()
    if task_in.description is not None:
        update_fields["description"] = task_in.description.strip()
    if task_in.status is not None:
        update_fields["status"] = task_in.status
    if task_in.priority is not None:
        update_fields["priority"] = task_in.priority
    if task_in.position is not None:
        update_fields["position"] = task_in.position
    if task_in.tags is not None:
        update_fields["tags"] = [t.strip() for t in task_in.tags if t.strip()]
    if task_in.due_date is not None:
        if task_in.due_date == "":
            update_fields["due_date"] = None
        else:
            update_fields["due_date"] = datetime.fromisoformat(task_in.due_date.replace("Z", "+00:00"))

    if task_in.assignee_id is not None:
        if task_in.assignee_id == "" or task_in.assignee_id.lower() in ("null", "none"):
            update_fields["assignee_id"] = None
        else:
            aid = parse_object_id(task_in.assignee_id, "assignee_id")
            user = await db.users.find_one({"_id": aid, "company_id": company_id})
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="L'utilisateur assigné n'appartient pas à cette entreprise."
                )
            update_fields["assignee_id"] = aid

    if task_in.subtasks is not None:
        update_fields["subtasks"] = [st.model_dump() for st in task_in.subtasks]

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun champ à modifier.")

    update_fields["updated_at"] = datetime.now(timezone.utc)

    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {"$set": update_fields},
        return_document=True
    )

    # Si passage en DONE, notification Discord
    if task_in.status == "DONE" and task.get("status") != "DONE":
        await send_discord_notification(
            title=f"Tâche terminée : {updated['title']} 🎉",
            description=f"La tâche vient d'être déplacée dans **DONE** !",
            color=0x10B981
        )

    return await enrich_task(updated, db)


@router.patch("/{task_id}/move", response_model=TaskResponse)
async def move_task(
    task_id: str,
    move_in: TaskMove,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Endpoint spécialisé pour le Drag & Drop Kanban :
    Met à jour instantanément la colonne (status) et la position ordonnée au sein de la colonne.
    Réordonne automatiquement les tâches adjacentes pour préserver un positionnement continu.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    task = await db.tasks.find_one({"_id": tid, "company_id": company_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tâche introuvable dans cette entreprise."
        )

    pid = task["project_id"]
    old_status = task["status"]
    new_status = move_in.status
    new_pos = move_in.position
    now = datetime.now(timezone.utc)

    # Si changement de colonne ou déplacement dans la même colonne
    if old_status != new_status:
        # Décale vers le haut les tâches de l'ancienne colonne après l'ancienne position
        await db.tasks.update_many(
            {
                "company_id": company_id,
                "project_id": pid,
                "status": old_status,
                "position": {"$gt": task["position"]}
            },
            {"$inc": {"position": -1}}
        )

        # Fait de la place dans la nouvelle colonne à partir de new_pos
        await db.tasks.update_many(
            {
                "company_id": company_id,
                "project_id": pid,
                "status": new_status,
                "position": {"$gte": new_pos}
            },
            {"$inc": {"position": 1}}
        )
    else:
        # Déplacement intra-colonne
        old_pos = task["position"]
        if new_pos > old_pos:
            await db.tasks.update_many(
                {
                    "company_id": company_id,
                    "project_id": pid,
                    "status": old_status,
                    "position": {"$gt": old_pos, "$lte": new_pos}
                },
                {"$inc": {"position": -1}}
            )
        elif new_pos < old_pos:
            await db.tasks.update_many(
                {
                    "company_id": company_id,
                    "project_id": pid,
                    "status": old_status,
                    "position": {"$gte": new_pos, "$lt": old_pos}
                },
                {"$inc": {"position": 1}}
            )

    # Mise à jour effective de la tâche cible
    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {"$set": {"status": new_status, "position": new_pos, "updated_at": now}},
        return_document=True
    )

    # Notification Discord lors du passage en DONE
    if new_status == "DONE" and old_status != "DONE":
        await send_discord_notification(
            title=f"Tâche terminée : {updated['title']} 🎉",
            description=f"La tâche vient d'être complétée sur le Kanban !",
            color=0x10B981
        )

    return await enrich_task(updated, db)


# =============================================================================
# NOUVELLES FONCTIONNALITÉS SAAS : SOUS-TÂCHES, COMMENTAIRES & DUPLICATION
# =============================================================================

@router.post("/{task_id}/duplicate", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def duplicate_task(
    task_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Duplique instantanément une tâche au sein du même projet et statut.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    task = await db.tasks.find_one({"_id": tid, "company_id": company_id})
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    now = datetime.now(timezone.utc)

    # Calcul position
    last_task = await db.tasks.find_one(
        {"company_id": company_id, "project_id": task["project_id"], "status": task["status"]},
        sort=[("position", -1)]
    )
    next_pos = (last_task["position"] + 1) if last_task and "position" in last_task else 0

    # Duplication des sous-tâches avec nouveaux IDs
    cloned_subtasks = []
    for st in task.get("subtasks", []):
        cloned_subtasks.append({
            "id": str(uuid.uuid4())[:8],
            "title": st.get("title", ""),
            "done": False
        })

    new_task = {
        "company_id": company_id,
        "project_id": task["project_id"],
        "assignee_id": task.get("assignee_id"),
        "title": f"{task['title']} (Copie)",
        "description": task.get("description", ""),
        "status": task["status"],
        "priority": task["priority"],
        "position": next_pos,
        "tags": list(task.get("tags", [])),
        "due_date": task.get("due_date"),
        "subtasks": cloned_subtasks,
        "comments": [],
        "created_at": now,
        "updated_at": now
    }

    res = await db.tasks.insert_one(new_task)
    new_task["_id"] = res.inserted_id

    return await enrich_task(new_task, db)


@router.post("/{task_id}/subtasks", response_model=TaskResponse)
async def add_subtask(
    task_id: str,
    subtask_in: SubTaskCreate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Ajoute une sous-tâche / checklist à une tâche existante.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    new_subtask = {
        "id": str(uuid.uuid4())[:8],
        "title": subtask_in.title.strip(),
        "done": False
    }

    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {
            "$push": {"subtasks": new_subtask},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        return_document=True
    )

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    return await enrich_task(updated, db)


@router.patch("/{task_id}/subtasks/{subtask_id}", response_model=TaskResponse)
async def toggle_subtask(
    task_id: str,
    subtask_id: str,
    toggle_in: Optional[SubTaskToggle] = None,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Bascule l'état (done) d'une sous-tâche.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    task = await db.tasks.find_one({"_id": tid, "company_id": company_id})
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    target_done = toggle_in.done if (toggle_in is not None and toggle_in.done is not None) else None

    subtasks = task.get("subtasks", [])
    found = False
    for st in subtasks:
        if st.get("id") == subtask_id:
            found = True
            st["done"] = not st.get("done", False) if target_done is None else target_done
            break

    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sous-tâche introuvable.")

    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {
            "$set": {
                "subtasks": subtasks,
                "updated_at": datetime.now(timezone.utc)
            }
        },
        return_document=True
    )

    return await enrich_task(updated, db)


@router.delete("/{task_id}/subtasks/{subtask_id}", response_model=TaskResponse)
async def delete_subtask(
    task_id: str,
    subtask_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Supprime une sous-tâche d'une tâche.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {
            "$pull": {"subtasks": {"id": subtask_id}},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        return_document=True
    )

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    return await enrich_task(updated, db)


@router.post("/{task_id}/comments", response_model=TaskResponse)
async def add_task_comment(
    task_id: str,
    comment_in: TaskCommentCreate,
    company_id: ObjectId = Depends(get_current_company_id),
    user_id: Optional[ObjectId] = Depends(get_current_user_id)
):
    """
    Ajoute un commentaire collaboratif sur une tâche.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    user_name = "Collaborateur"
    user_avatar = "#4F46E5"
    uid_str = str(user_id) if user_id else "unknown"

    if user_id:
        user_doc = await db.users.find_one({"_id": user_id, "company_id": company_id})
        if user_doc:
            user_name = user_doc.get("name", "Collaborateur")
            user_avatar = user_doc.get("avatar_color", "#4F46E5")

    new_comment = {
        "id": str(uuid.uuid4())[:8],
        "user_id": uid_str,
        "user_name": user_name,
        "user_avatar_color": user_avatar,
        "content": comment_in.content.strip(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {
            "$push": {"comments": new_comment},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        return_document=True
    )

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    return await enrich_task(updated, db)


@router.delete("/{task_id}/comments/{comment_id}", response_model=TaskResponse)
async def delete_task_comment(
    task_id: str,
    comment_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Supprime un commentaire d'une tâche.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    updated = await db.tasks.find_one_and_update(
        {"_id": tid, "company_id": company_id},
        {
            "$pull": {"comments": {"id": comment_id}},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        },
        return_document=True
    )

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tâche introuvable.")

    return await enrich_task(updated, db)


@router.delete("/{task_id}", status_code=status.HTTP_200_OK)
async def delete_task(
    task_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Supprime une tâche de l'entreprise active.
    """
    db = get_database()
    tid = parse_object_id(task_id, "task_id")

    task = await db.tasks.find_one({"_id": tid, "company_id": company_id})
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tâche introuvable dans cette entreprise."
        )

    # Réajustement des positions suivantes dans la colonne
    await db.tasks.update_many(
        {
            "company_id": company_id,
            "project_id": task["project_id"],
            "status": task["status"],
            "position": {"$gt": task["position"]}
        },
        {"$inc": {"position": -1}}
    )

    await db.tasks.delete_one({"_id": tid, "company_id": company_id})
    return {"message": f"Tâche '{task['title']}' supprimée avec succès."}
