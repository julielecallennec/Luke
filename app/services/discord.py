import logging
from typing import Optional, Dict, Any
import httpx
from app.config import settings

logger = logging.getLogger("luke.discord")


async def send_discord_notification(
    title: str,
    description: str,
    color: int = 0x4F46E5,
    fields: Optional[list] = None,
    webhook_url: Optional[str] = None
) -> bool:
    """
    Envoie une notification Discord via Webhook (pour les actions clés comme la complétion de tâche).
    Ne bloque jamais l'exécution normale si le webhook échoue ou si aucun réseau n'est disponible.
    """
    url = webhook_url or settings.DISCORD_WEBHOOK_URL
    if not url:
        return False

    payload: Dict[str, Any] = {
        "username": "Luke SaaS Bot",
        "avatar_url": "https://raw.githubusercontent.com/feathericons/feather/master/icons/trello.svg",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "footer": {"text": "Luke - SaaS Agile Multi-Tenant"},
                "fields": fields or []
            }
        ]
    }

    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code in (200, 204):
                logger.info(f"Notification Discord envoyée avec succès : {title}")
                return True
            else:
                logger.warning(f"Échec envoi Discord webhook (status {resp.status_code}): {resp.text}")
                return False
    except Exception as exc:
        logger.warning(f"Impossible d'envoyer la notification Discord : {exc}")
        return False
