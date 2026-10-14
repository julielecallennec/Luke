FROM python:3.11-slim

WORKDIR /app

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copie et installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copie du code source de l'application
COPY . .

# Exposition du port de l'application FastAPI
EXPOSE 8000

# Commande de lancement (le rechargement à chaud est activé pour le dev)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
