import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration de l'application Luke.
    Aucune adresse IP, nom d'hôte ou port MongoDB n'est codé en dur dans l'application.
    Toute la connectivité s'appuie sur la variable d'environnement MONGO_URI,
    ce qui permettra une transition transparente vers un cluster Sharded avec mongos en Partie II.
    """
    APP_NAME: str = "Luke - SaaS Agile Kanban"
    DEBUG: bool = False
    
    # Variable d'environnement prioritaire pour la connexion MongoDB
    MONGO_URI: str = "mongodb://mongodb:27017/luke_db"
    
    # URL du Webhook Discord (pour notifications en temps réel)
    DISCORD_WEBHOOK_URL: Optional[str] = "https://discord.com/api/webhooks/1560190079031574609/jY71YASDqgPionK1V26R1cgT8HR6JBvqFIxHkLPj6QN3HTdhGkJk6me0WPMVaGI8divn"
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
