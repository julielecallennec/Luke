"""Luke API and web application."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path as FilePath
from bson import ObjectId
from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app import database
from app.models import CompanyCreate, CompanyUpdate, UserCreate, UserUpdate, ProjectCreate, ProjectUpdate, TaskCreate, TaskUpdate, TaskMove
from app.seed import seed_demo

ROOT = FilePath(__file__).resolve().parent

@asynccontextmanager
async def lifespan(app: FastAPI):
    database.connect()
    await database.ensure_indexes()
    await seed_demo()
    yield
    database.close()

app = FastAPI(title="Luke", description="Gestion de projets et tableau Kanban multi-entreprise", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def collection(name: str):
    if database.db is None:
        raise HTTPException(503, "Base de donnees indisponible")
    return database.db[name]


def oid(value: str, label: str = "identifiant") -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(404, f"{label.capitalize()} introuvable")
    return ObjectId(value)


def serialize(doc):
    if doc is None:
        return None
    result = {k: (str(v) if isinstance(v, ObjectId) else v) for k, v in doc.items() if k != "password_hash"}
    for key in ("company_id", "project_id", "assignee_id"):
        if isinstance(result.get(key), ObjectId): result[key] = str(result[key])
    for key in ("member_ids",):
        if key in result: result[key] = [str(x) for x in result[key]]
    return result

async def company_or_404(company_id: str):
    company = await collection("companies").find_one({"_id": oid(company_id, "entreprise")})
    if not company: raise HTTPException(404, "Entreprise introuvable")
    return company

async def project_filter(company_id: str, project_id: str):
    cid, pid = oid(company_id, "entreprise"), oid(project_id, "projet")
    project = await collection("projects").find_one({"_id": pid, "company_id": cid})
    if not project: raise HTTPException(404, "Projet introuvable dans cette entreprise")
    return cid, pid, project

@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(ROOT / "templates" / "index.html")

@app.get("/api/health")
async def health(): return {"status": "ok"}

@app.get("/api/companies")
async def list_companies():
    return [serialize(x) async for x in collection("companies").find().sort("name", 1)]

@app.post("/api/companies", status_code=201)
async def create_company(payload: CompanyCreate):
    now = datetime.now(timezone.utc); doc = payload.model_dump() | {"created_at": now, "updated_at": now}
    try: result = await collection("companies").insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409, "Ce slug existe deja")
    doc["_id"] = result.inserted_id; return serialize(doc)

@app.patch("/api/companies/{company_id}")
async def update_company(company_id: str, payload: CompanyUpdate):
    fields = payload.model_dump(exclude_unset=True)
    if not fields: raise HTTPException(400, "Aucune modification fournie")
    fields["updated_at"] = datetime.now(timezone.utc)
    try: doc = await collection("companies").find_one_and_update({"_id": oid(company_id, "entreprise")}, {"$set": fields}, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError: raise HTTPException(409, "Ce slug existe deja")
    if not doc: raise HTTPException(404, "Entreprise introuvable")
    return serialize(doc)

@app.delete("/api/companies/{company_id}", status_code=204)
async def delete_company(company_id: str):
    cid = oid(company_id, "entreprise")
    result = await collection("companies").delete_one({"_id": cid})
    if not result.deleted_count: raise HTTPException(404, "Entreprise introuvable")
    await collection("users").delete_many({"company_id": cid})
    await collection("projects").delete_many({"company_id": cid})
    await collection("tasks").delete_many({"company_id": cid})
    return Response(status_code=204)

@app.get("/api/companies/{company_id}/users")
async def list_users(company_id: str):
    await company_or_404(company_id)
    return [serialize(x) async for x in collection("users").find({"company_id": oid(company_id)}).sort("name", 1)]

@app.post("/api/companies/{company_id}/users", status_code=201)
async def create_user(company_id: str, payload: UserCreate):
    await company_or_404(company_id); cid = oid(company_id)
    doc = payload.model_dump() | {"email": str(payload.email).lower(), "company_id": cid, "created_at": datetime.now(timezone.utc)}
    try: result = await collection("users").insert_one(doc)
    except DuplicateKeyError: raise HTTPException(409, "Cet e-mail est deja utilise dans cette entreprise")
    doc["_id"] = result.inserted_id; return serialize(doc)

@app.patch("/api/companies/{company_id}/users/{user_id}")
async def update_user(company_id: str, user_id: str, payload: UserUpdate):
    await company_or_404(company_id); fields = payload.model_dump(exclude_unset=True)
    if "email" in fields and fields["email"]: fields["email"] = str(fields["email"]).lower()
    if not fields: raise HTTPException(400, "Aucune modification fournie")
    try: doc = await collection("users").find_one_and_update({"_id": oid(user_id, "utilisateur"), "company_id": oid(company_id)}, {"$set": fields}, return_document=ReturnDocument.AFTER)
    except DuplicateKeyError: raise HTTPException(409, "Cet e-mail est deja utilise dans cette entreprise")
    if not doc: raise HTTPException(404, "Utilisateur introuvable dans cette entreprise")
    return serialize(doc)

@app.delete("/api/companies/{company_id}/users/{user_id}", status_code=204)
async def delete_user(company_id: str, user_id: str):
    cid, uid = oid(company_id), oid(user_id, "utilisateur")
    result = await collection("users").delete_one({"_id": uid, "company_id": cid})
    if not result.deleted_count: raise HTTPException(404, "Utilisateur introuvable dans cette entreprise")
    await collection("projects").update_many({"company_id": cid}, {"$pull": {"member_ids": uid}})
    await collection("tasks").update_many({"company_id": cid, "assignee_id": uid}, {"$set": {"assignee_id": None}})
    return Response(status_code=204)

@app.get("/api/companies/{company_id}/projects")
async def list_projects(company_id: str):
    await company_or_404(company_id)
    return [serialize(x) async for x in collection("projects").find({"company_id": oid(company_id)}).sort("updated_at", -1)]

@app.post("/api/companies/{company_id}/projects", status_code=201)
async def create_project(company_id: str, payload: ProjectCreate):
    await company_or_404(company_id); cid = oid(company_id)
    members = [oid(x, "utilisateur") for x in payload.member_ids]
    if members and await collection("users").count_documents({"_id": {"$in": members}, "company_id": cid}) != len(set(members)):
        raise HTTPException(400, "Tous les membres doivent appartenir a cette entreprise")
    now = datetime.now(timezone.utc)
    doc = payload.model_dump(exclude={"member_ids"}) | {"company_id": cid, "member_ids": members, "status": "ACTIVE", "created_at": now, "updated_at": now}
    result = await collection("projects").insert_one(doc); doc["_id"] = result.inserted_id; return serialize(doc)

@app.patch("/api/companies/{company_id}/projects/{project_id}")
async def update_project(company_id: str, project_id: str, payload: ProjectUpdate):
    cid, pid, _ = await project_filter(company_id, project_id); fields = payload.model_dump(exclude_unset=True)
    if "member_ids" in fields and fields["member_ids"] is not None:
        members = [oid(x, "utilisateur") for x in fields["member_ids"]]
        if members and await collection("users").count_documents({"_id": {"$in": members}, "company_id": cid}) != len(set(members)):
            raise HTTPException(400, "Tous les membres doivent appartenir a cette entreprise")
        fields["member_ids"] = members
    if not fields: raise HTTPException(400, "Aucune modification fournie")
    fields["updated_at"] = datetime.now(timezone.utc)
    doc = await collection("projects").find_one_and_update({"_id": pid, "company_id": cid}, {"$set": fields}, return_document=ReturnDocument.AFTER)
    return serialize(doc)

@app.delete("/api/companies/{company_id}/projects/{project_id}", status_code=204)
async def delete_project(company_id: str, project_id: str):
    cid, pid, _ = await project_filter(company_id, project_id)
    await collection("projects").delete_one({"_id": pid, "company_id": cid})
    await collection("tasks").delete_many({"project_id": pid, "company_id": cid})
    return Response(status_code=204)

@app.get("/api/companies/{company_id}/projects/{project_id}/tasks")
async def list_tasks(company_id: str, project_id: str, assignee_id: str | None = None, priority: str | None = Query(default=None, pattern="^(LOW|MEDIUM|HIGH)$")):
    cid, pid, _ = await project_filter(company_id, project_id)
    query = {"company_id": cid, "project_id": pid}
    if assignee_id: query["assignee_id"] = oid(assignee_id, "utilisateur")
    if priority: query["priority"] = priority
    return [serialize(x) async for x in collection("tasks").find(query).sort([("status", 1), ("position", 1)])]

@app.post("/api/companies/{company_id}/projects/{project_id}/tasks", status_code=201)
async def create_task(company_id: str, project_id: str, payload: TaskCreate):
    cid, pid, project = await project_filter(company_id, project_id)
    assignee = oid(payload.assignee_id, "utilisateur") if payload.assignee_id else None
    if assignee and (assignee not in project["member_ids"] or not await collection("users").find_one({"_id": assignee, "company_id": cid})):
        raise HTTPException(400, "La personne doit etre membre du projet")
    position = await collection("tasks").count_documents({"company_id": cid, "project_id": pid, "status": payload.status})
    now = datetime.now(timezone.utc)
    doc = payload.model_dump(exclude={"assignee_id"}) | {"company_id": cid, "project_id": pid, "assignee_id": assignee, "position": position, "created_at": now, "updated_at": now}
    result = await collection("tasks").insert_one(doc); doc["_id"] = result.inserted_id; return serialize(doc)

@app.patch("/api/companies/{company_id}/projects/{project_id}/tasks/{task_id}")
async def update_task(company_id: str, project_id: str, task_id: str, payload: TaskUpdate):
    cid, pid, project = await project_filter(company_id, project_id); tid = oid(task_id, "tache")
    fields = payload.model_dump(exclude_unset=True)
    if "assignee_id" in fields:
        aid = oid(fields["assignee_id"], "utilisateur") if fields["assignee_id"] else None
        if aid and (aid not in project["member_ids"] or not await collection("users").find_one({"_id": aid, "company_id": cid})):
            raise HTTPException(400, "La personne doit etre membre du projet")
        fields["assignee_id"] = aid
    if not fields: raise HTTPException(400, "Aucune modification fournie")
    fields["updated_at"] = datetime.now(timezone.utc)
    doc = await collection("tasks").find_one_and_update({"_id": tid, "company_id": cid, "project_id": pid}, {"$set": fields}, return_document=ReturnDocument.AFTER)
    if not doc: raise HTTPException(404, "Tache introuvable dans ce projet")
    return serialize(doc)

@app.patch("/api/companies/{company_id}/projects/{project_id}/tasks/{task_id}/move")
async def move_task(company_id: str, project_id: str, task_id: str, payload: TaskMove):
    cid, pid, _ = await project_filter(company_id, project_id); tid = oid(task_id, "tache")
    task = await collection("tasks").find_one({"_id": tid, "company_id": cid, "project_id": pid})
    if not task: raise HTTPException(404, "Tache introuvable dans ce projet")
    target = await collection("tasks").find({"company_id": cid, "project_id": pid, "status": payload.status, "_id": {"$ne": tid}}).sort("position", 1).to_list(length=None)
    insert_at = min(payload.position, len(target)); target.insert(insert_at, task); now = datetime.now(timezone.utc)
    for pos, item in enumerate(target):
        await collection("tasks").update_one({"_id": item["_id"], "company_id": cid, "project_id": pid}, {"$set": {"status": payload.status, "position": pos, "updated_at": now}})
    return serialize(await collection("tasks").find_one({"_id": tid, "company_id": cid, "project_id": pid}))

@app.delete("/api/companies/{company_id}/projects/{project_id}/tasks/{task_id}", status_code=204)
async def delete_task(company_id: str, project_id: str, task_id: str):
    cid, pid, _ = await project_filter(company_id, project_id)
    result = await collection("tasks").delete_one({"_id": oid(task_id, "tache"), "company_id": cid, "project_id": pid})
    if not result.deleted_count: raise HTTPException(404, "Tache introuvable dans ce projet")
    return Response(status_code=204)
