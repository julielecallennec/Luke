import hashlib
import re
import secrets
import unicodedata

SALT = "luke_salt_secure_2026"


def hash_password(password: str) -> str:
    """
    Hash sécurisé salé pour les mots de passe Luke.
    """
    return hashlib.sha256((SALT + password).encode("utf-8")).hexdigest()


def verify_password(password: str, hashed: str) -> bool:
    """
    Vérifie la correspondance d'un mot de passe en temps constant.
    """
    candidate = hash_password(password)
    return secrets.compare_digest(candidate, hashed)


def generate_token(nbytes: int = 32) -> str:
    """
    Génère un jeton cryptographique aléatoire pour les sessions SaaS.
    """
    return secrets.token_urlsafe(nbytes)


def generate_reset_code() -> str:
    """
    Génère un code de réinitialisation lisible et sécurisé (ex: RSET-78A9C2).
    """
    return f"RSET-{secrets.token_hex(4).upper()}"


def slugify(text: str) -> str:
    """
    Transforme un nom d'entreprise en slug URL friendly (ex: 'Agence Web & Co' -> 'agence-web-co').
    """
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[-\s]+", "-", text) or "workspace"
