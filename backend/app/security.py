import os
from datetime import datetime, timedelta, timezone
import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from .database import DATABASE_URL, get_db
from .models import User

SECRET_KEY = os.getenv("FINPILOT_SECRET_KEY")
if not SECRET_KEY:
    if not DATABASE_URL.startswith("sqlite"):
        raise RuntimeError("Définissez FINPILOT_SECRET_KEY avant d'utiliser une base PostgreSQL.")
    SECRET_KEY = "dev-only-change-me-before-deploying"
elif not DATABASE_URL.startswith("sqlite") and len(SECRET_KEY) < 32:
    raise RuntimeError("FINPILOT_SECRET_KEY doit contenir au moins 32 caractères en production.")
ALGORITHM = "HS256"
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentification requise")
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Jeton invalide ou expiré")
    user = db.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Utilisateur introuvable")
    return user
