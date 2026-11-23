from typing import Optional
from fastapi import APIRouter, Body, HTTPException, status
from pydantic import BaseModel, Field
from app.services.discord import send_discord_notification

router = APIRouter(tags=["Webhooks & Intégrations"])


class WebhookTestRequest(BaseModel):
    message: str = Field(default="Test d'intégration Webhook Luke SaaS", examples=["Test réussi !"])


@router.post("/api/webhook/test")
@router.post("/api/webhooks/test")
async def trigger_webhook_test(req: Optional[WebhookTestRequest] = None):
    """
    Déclenche l'envoi d'un webhook de test vers le serveur Discord Grande SAE.
    Compatible avec /api/webhook/test et /api/webhooks/test.
    """
    msg = req.message if req else "Test d'intégration Webhook Luke SaaS 🚀"
    ok = await send_discord_notification(
        title="Test d'intégration Webhook Luke SaaS 🚀",
        description=msg,
        color=0x4F46E5,
        fields=[
            {"name": "Application", "value": "Luke - SaaS Agile Kanban", "inline": True},
            {"name": "Statut", "value": "Opérationnel", "inline": True}
        ]
    )
    if not ok:
        return {
            "status": "warning",
            "message": "Notification non émise (vérifier la connectivité Internet ou l'URL du webhook)."
        }
    return {
        "status": "success",
        "message": "Message envoyé avec succès sur le serveur Discord !"
    }
