import csv
import io
import json
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.database import get_database, serialize_doc, serialize_docs
from app.dependencies import get_current_company_id, parse_object_id, require_admin
from app.models.project import ProjectCreate, ProjectResponse, ProjectUpdate

router = APIRouter(prefix="/api/projects", tags=["Projets (Projects)"])


async def enrich_project(project: dict, db) -> dict:
    """
    Enrichit un document projet avec :
    - La liste des membres avec leurs informations de profil
    - Le décompte des tâches totales et terminées (DONE)
    - Le pourcentage d'avancement
    """
    cid = project["company_id"]
    pid = project["_id"]

    # Récupération des détails des membres assignés au projet
    member_ids = project.get("member_ids", [])
    members = []
    if member_ids:
        users_cursor = db.users.find({"_id": {"$in": member_ids}, "company_id": cid})
        users_list = await users_cursor.to_list(length=100)
        members = serialize_docs(users_list)

    # Statistiques de tâches pour la jauge d'avancement
    total_tasks = await db.tasks.count_documents({"company_id": cid, "project_id": pid})
    done_tasks = await db.tasks.count_documents({"company_id": cid, "project_id": pid, "status": "DONE"})
    progress_pct = round((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    doc = serialize_doc(project)
    doc["members"] = members
    doc["total_tasks"] = total_tasks
    doc["done_tasks"] = done_tasks
    doc["progress_percentage"] = progress_pct
    return doc


@router.get("", response_model=List[ProjectResponse])
async def list_projects(company_id: ObjectId = Depends(get_current_company_id)):
    """
    Liste tous les projets de l'entreprise active avec progression et membres.
    """
    db = get_database()
    cursor = db.projects.find({"company_id": company_id}).sort("created_at", -1)
    projects = await cursor.to_list(length=200)

    enriched = [await enrich_project(p, db) for p in projects]
    return enriched


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_admin)])
async def create_project(
    project_in: ProjectCreate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Crée un projet rattaché à l'entreprise active.
    Valide que tous les membres spécifiés appartiennent à cette entreprise.
    """
    db = get_database()
    now = datetime.now(timezone.utc)

    # Conversion et validation des member_ids
    validated_member_ids: List[ObjectId] = []
    for mid_str in project_in.member_ids:
        mid = parse_object_id(mid_str, "member_id")
        user = await db.users.find_one({"_id": mid, "company_id": company_id})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Le membre {mid_str} n'appartient pas à l'entreprise active."
            )
        validated_member_ids.append(mid)

    project_doc = {
        "company_id": company_id,
        "name": project_in.name,
        "description": project_in.description,
        "status": project_in.status,
        "member_ids": validated_member_ids,
        "created_at": now,
        "updated_at": now
    }

    res = await db.projects.insert_one(project_doc)
    project_doc["_id"] = res.inserted_id

    return await enrich_project(project_doc, db)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Détail d'un projet de l'entreprise active.
    """
    db = get_database()
    pid = parse_object_id(project_id, "project_id")

    project = await db.projects.find_one({"_id": pid, "company_id": company_id})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable dans cette entreprise."
        )

    return await enrich_project(project, db)


@router.get("/{project_id}/stats")
async def get_project_stats(
    project_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Calcule des statistiques et métriques avancées sur un projet :
    - Tâches par statut
    - Tâches par priorité
    - Nombre de tâches en retard
    - Charge de travail par membre
    - Taux d'avancement
    """
    db = get_database()
    pid = parse_object_id(project_id, "project_id")

    project = await db.projects.find_one({"_id": pid, "company_id": company_id})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable.")

    tasks_cursor = db.tasks.find({"company_id": company_id, "project_id": pid})
    tasks = await tasks_cursor.to_list(length=500)

    total_tasks = len(tasks)
    status_counts = {"TODO": 0, "IN_PROGRESS": 0, "IN_REVIEW": 0, "DONE": 0}
    priority_counts = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    now = datetime.now(timezone.utc)
    overdue_count = 0
    workload_map = {}

    for t in tasks:
        st = t.get("status", "TODO")
        pr = t.get("priority", "MEDIUM")
        status_counts[st] = status_counts.get(st, 0) + 1
        priority_counts[pr] = priority_counts.get(pr, 0) + 1

        due = t.get("due_date")
        if due:
            if isinstance(due, datetime) and due.tzinfo is None:
                due = due.replace(tzinfo=timezone.utc)
            if due < now and st != "DONE":
                overdue_count += 1

        aid = str(t.get("assignee_id")) if t.get("assignee_id") else "unassigned"
        if aid not in workload_map:
            workload_map[aid] = {"total": 0, "done": 0}
        workload_map[aid]["total"] += 1
        if st == "DONE":
            workload_map[aid]["done"] += 1

    # Récupération des informations des utilisateurs pour le workload
    users_cursor = db.users.find({"company_id": company_id})
    users = await users_cursor.to_list(length=100)
    user_dict = {str(u["_id"]): u for u in users}

    workload_list = []
    for aid, counts in workload_map.items():
        if aid == "unassigned":
            name = "Non assigné"
            color = "#64748B"
        else:
            u = user_dict.get(aid, {})
            name = u.get("name", "Inconnu")
            color = u.get("avatar_color", "#4F46E5")

        workload_list.append({
            "user_id": aid,
            "name": name,
            "avatar_color": color,
            "total_tasks": counts["total"],
            "done_tasks": counts["done"]
        })

    done_tasks = status_counts.get("DONE", 0)
    completion_rate = round((done_tasks / total_tasks * 100)) if total_tasks > 0 else 0

    return {
        "project_id": str(pid),
        "project_name": project["name"],
        "total_tasks": total_tasks,
        "done_tasks": done_tasks,
        "completion_rate": completion_rate,
        "overdue_tasks": overdue_count,
        "status_counts": status_counts,
        "priority_counts": priority_counts,
        "workload": workload_list
    }


@router.get("/{project_id}/export")
async def export_project(
    project_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Exporte toutes les tâches d'un projet au format CSV ou JSON.
    """
    db = get_database()
    pid = parse_object_id(project_id, "project_id")

    project = await db.projects.find_one({"_id": pid, "company_id": company_id})
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Projet introuvable.")

    tasks_cursor = db.tasks.find({"company_id": company_id, "project_id": pid}).sort("position", 1)
    tasks = await tasks_cursor.to_list(length=1000)

    users_cursor = db.users.find({"company_id": company_id})
    users = await users_cursor.to_list(length=100)
    user_dict = {str(u["_id"]): u.get("name", "") for u in users}

    if format == "json":
        serialized = serialize_docs(tasks)
        for t in serialized:
            aid = t.get("assignee_id")
            t["assignee_name"] = user_dict.get(aid, "")
        json_content = json.dumps(serialized, indent=2, ensure_ascii=False)
        return Response(
            content=json_content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="export-{project["name"].replace(" ", "_")}.json"'}
        )

    # Format CSV
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(["ID", "Titre", "Description", "Statut", "Priorité", "Assigné", "Tags", "Date d'échéance", "Sous-tâches totales", "Sous-tâches faites", "Créé le"])

    for t in tasks:
        aid = str(t.get("assignee_id")) if t.get("assignee_id") else ""
        assignee_name = user_dict.get(aid, "")
        tags_str = ", ".join(t.get("tags", []))
        due_str = t["due_date"].isoformat() if t.get("due_date") else ""
        subtasks = t.get("subtasks", [])
        st_total = len(subtasks)
        st_done = len([s for s in subtasks if s.get("done")])
        created_str = t["created_at"].isoformat() if t.get("created_at") else ""

        writer.writerow([
            str(t["_id"]),
            t.get("title", ""),
            t.get("description", ""),
            t.get("status", ""),
            t.get("priority", ""),
            assignee_name,
            tags_str,
            due_str,
            st_total,
            st_done,
            created_str
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="export-{project["name"].replace(" ", "_")}.csv"'}
    )


@router.put("/{project_id}", response_model=ProjectResponse, dependencies=[Depends(require_admin)])
async def update_project(
    project_id: str,
    project_in: ProjectUpdate,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Met à jour les informations d'un projet de l'entreprise active.
    """
    db = get_database()
    pid = parse_object_id(project_id, "project_id")

    update_fields = {}
    if project_in.name is not None:
        update_fields["name"] = project_in.name
    if project_in.description is not None:
        update_fields["description"] = project_in.description
    if project_in.status is not None:
        update_fields["status"] = project_in.status
    if project_in.member_ids is not None:
        validated_mids = []
        for mid_str in project_in.member_ids:
            mid = parse_object_id(mid_str, "member_id")
            user = await db.users.find_one({"_id": mid, "company_id": company_id})
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Le membre {mid_str} n'appartient pas à l'entreprise active."
                )
            validated_mids.append(mid)
        update_fields["member_ids"] = validated_mids

    if not update_fields:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Aucun champ à modifier.")

    update_fields["updated_at"] = datetime.now(timezone.utc)

    updated = await db.projects.find_one_and_update(
        {"_id": pid, "company_id": company_id},
        {"$set": update_fields},
        return_document=True
    )

    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable dans cette entreprise."
        )

    return await enrich_project(updated, db)


@router.delete("/{project_id}", status_code=status.HTTP_200_OK, dependencies=[Depends(require_admin)])
async def delete_project(
    project_id: str,
    company_id: ObjectId = Depends(get_current_company_id)
):
    """
    Supprime un projet et toutes ses tâches en cascade (isolation stricte company_id).
    """
    db = get_database()
    pid = parse_object_id(project_id, "project_id")

    project = await db.projects.find_one({"_id": pid, "company_id": company_id})
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Projet introuvable dans cette entreprise."
        )

    # 1. Suppression en cascade des tâches associées au projet
    tasks_res = await db.tasks.delete_many({"company_id": company_id, "project_id": pid})

    # 2. Suppression du projet
    await db.projects.delete_one({"_id": pid, "company_id": company_id})

    return {
        "message": f"Projet '{project['name']}' et ses {tasks_res.deleted_count} tâches supprimés avec succès.",
        "deleted_tasks_count": tasks_res.deleted_count
    }
