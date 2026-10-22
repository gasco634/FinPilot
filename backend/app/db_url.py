"""Normalisation des URL de base de données pour SQLAlchemy."""


def normalize_database_url(url: str) -> str:
    """Utilise le pilote psycopg v3 pour les URL PostgreSQL standards de Neon."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
