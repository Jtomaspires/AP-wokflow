"""Postgres operators + operator_sessions."""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.adapters.db_models import OperatorSessionTable, OperatorTable
from app.auth.tokens import new_token, token_hash
from app.domain.models import Operator


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _to_operator(row: OperatorTable) -> Operator:
    return Operator(
        id=row.id,
        email=row.email,
        display_name=row.display_name,
        is_active=row.is_active,
        created_at=row.created_at,
    )


class AuthRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_operator(self, operator_id: str) -> Operator | None:
        row = self.session.get(OperatorTable, operator_id)
        return _to_operator(row) if row else None

    def get_credentials(self, email: str) -> tuple[Operator, str] | None:
        row = self.session.exec(
            select(OperatorTable).where(OperatorTable.email == _normalize_email(email))
        ).first()
        if row is None:
            return None
        return _to_operator(row), row.password_hash

    def upsert_operator(self, operator: Operator, password_hash: str) -> Operator:
        row = self.session.get(OperatorTable, operator.id)
        if row is None:
            row = OperatorTable(
                id=operator.id,
                email=_normalize_email(operator.email),
                display_name=operator.display_name,
                password_hash=password_hash,
                is_active=operator.is_active,
                created_at=operator.created_at,
            )
        else:
            row.email = _normalize_email(operator.email)
            row.display_name = operator.display_name
            row.password_hash = password_hash
            row.is_active = operator.is_active
        self.session.add(row)
        self.session.commit()
        return _to_operator(row)

    def update_password_hash(self, operator_id: str, password_hash: str) -> None:
        row = self.session.get(OperatorTable, operator_id)
        if row is None:
            return
        row.password_hash = password_hash
        self.session.add(row)
        self.session.commit()

    def create_session(self, operator_id: str, ttl_hours: int) -> str:
        token = new_token()
        now = datetime.now(UTC)
        self.session.add(
            OperatorSessionTable(
                token_hash=token_hash(token),
                operator_id=operator_id,
                created_at=now,
                expires_at=now + timedelta(hours=ttl_hours),
            )
        )
        self.session.commit()
        return token

    def get_session_operator(self, token: str) -> Operator | None:
        row = self.session.exec(
            select(OperatorSessionTable).where(OperatorSessionTable.token_hash == token_hash(token))
        ).first()
        if row is None or row.revoked_at is not None or row.expires_at <= datetime.now(UTC):
            return None
        operator = self.get_operator(row.operator_id)
        if operator is None or not operator.is_active:
            return None
        return operator

    def revoke_session(self, token: str) -> None:
        row = self.session.exec(
            select(OperatorSessionTable).where(OperatorSessionTable.token_hash == token_hash(token))
        ).first()
        if row is None or row.revoked_at is not None:
            return
        row.revoked_at = datetime.now(UTC)
        self.session.add(row)
        self.session.commit()
