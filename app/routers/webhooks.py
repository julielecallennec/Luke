from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.services.discord import send_discord_notification

router = APIRouter(prefix="/api/webhook", tags=["Webhooks & Intégrations"])


class WebhookTestRequest(BaseModel):
    message: str = Field(default="Test d'intégration Webhook Luke SaaS", examples=["Test réussi !"])


@router.post("/test")
async def trigger_webhook_test(req: WebhookTestRequest):
    """
    Déclenche l'envoi d'un webhook de test vers le serveur Discord Grande SAE.
    """
    ok = await send_discord_notification(
        title="Test d'intégration Webhook Luke SaaS 🚀",
        description=req.message,
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
