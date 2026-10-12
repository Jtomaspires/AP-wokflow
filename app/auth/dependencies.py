"""FastAPI dependency: the operator who owns the session cookie."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from sqlmodel import Session

from app.auth.repo import AuthRepo
from app.domain.models import Operator
from app.worker.tasks import engine
from settings import settings


def get_current_operator(request: Request) -> Operator:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="not authenticated")
    with Session(engine) as session:
        operator = AuthRepo(session).get_session_operator(token)
    if operator is None:
        raise HTTPException(status_code=401, detail="not authenticated")
    return operator


CurrentOperator = Annotated[Operator, Depends(get_current_operator)]
