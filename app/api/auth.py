"""HTTP adapter: operator login, logout, me."""

from fastapi import APIRouter, HTTPException, Request, Response
from sqlmodel import Session

from app.auth.dependencies import CurrentOperator
from app.auth.passwords import hash_password, needs_rehash, verify_password
from app.auth.repo import AuthRepo
from app.auth.schemas import LoginBody, OperatorOut
from app.domain.models import Operator
from app.worker.tasks import engine
from settings import settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Verified against when the email is unknown, so both failures take the same time.
_DUMMY_HASH = hash_password("not-a-real-password")


def _out(operator: Operator) -> OperatorOut:
    return OperatorOut(id=operator.id, email=operator.email, display_name=operator.display_name)


@router.post("/login")
def login(body: LoginBody, response: Response) -> OperatorOut:
    with Session(engine) as session:
        repo = AuthRepo(session)
        credentials = repo.get_credentials(body.email)
        if credentials is None:
            verify_password(_DUMMY_HASH, body.password)
            raise HTTPException(status_code=401, detail="invalid credentials")
        operator, password_hash = credentials
        if not verify_password(password_hash, body.password) or not operator.is_active:
            raise HTTPException(status_code=401, detail="invalid credentials")
        if needs_rehash(password_hash):
            repo.update_password_hash(operator.id, hash_password(body.password))
        token = repo.create_session(operator.id, settings.SESSION_TTL_HOURS)

    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
        max_age=settings.SESSION_TTL_HOURS * 3600,
        path="/",
    )
    return _out(operator)


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response) -> None:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if token:
        with Session(engine) as session:
            AuthRepo(session).revoke_session(token)
    response.delete_cookie(settings.SESSION_COOKIE_NAME, path="/")


@router.get("/me")
def me(operator: CurrentOperator) -> OperatorOut:
    return _out(operator)
