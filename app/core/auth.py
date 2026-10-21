from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user_model import UserModel

bearer = HTTPBearer()
optional_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> UserModel:
    try:
        payload = decode_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer),
    token: Optional[str] = Query(
        None,
        description="JWT, for clients that cannot send headers (e.g. <video src>)",
    ),
    db: Session = Depends(get_db),
) -> Optional[UserModel]:
    """Logged in user if a valid token is sent (header or ?token=), otherwise None."""
    raw_token = credentials.credentials if credentials else token
    if not raw_token:
        return None
    try:
        payload = decode_token(raw_token)
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        # Token caducado o inválido: se trata como anónimo
        return None
    return db.query(UserModel).filter(UserModel.id == user_id).first()


def get_current_admin(user: UserModel = Depends(get_current_user)) -> UserModel:
    if user.role.name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
        )
    return user
