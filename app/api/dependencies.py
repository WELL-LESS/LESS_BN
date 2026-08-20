from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import ApiError
from app.services.demo_store import DemoSession
from app.services.store import store

bearer = HTTPBearer(auto_error=False)


def require_session(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> DemoSession:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "AUTHENTICATION_REQUIRED", "인증이 필요합니다.")
    session = store.get_session(credentials.credentials)
    if session is None:
        raise ApiError(401, "ACCESS_TOKEN_EXPIRED", "세션이 만료되었습니다.")
    return session


SessionDependency = Annotated[DemoSession, Depends(require_session)]
