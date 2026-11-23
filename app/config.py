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
    
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
