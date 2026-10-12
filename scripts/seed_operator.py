"""Create or reset an operator login. The password is prompted, never passed as an argument."""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlmodel import Session

from app.auth.passwords import hash_password
from app.auth.repo import AuthRepo
from app.domain.models import Operator
from app.worker.tasks import engine


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="operator id, e.g. op_joao")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True, help="display name")
    parser.add_argument("--inactive", action="store_true", help="store the operator as inactive")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if not password:
        print("Password cannot be empty.", file=sys.stderr)
        return 1
    if getpass.getpass("Repeat password: ") != password:
        print("Passwords do not match.", file=sys.stderr)
        return 1

    operator = Operator(
        id=args.id, email=args.email, display_name=args.name, is_active=not args.inactive
    )
    with Session(engine) as session:
        saved = AuthRepo(session).upsert_operator(operator, hash_password(password))
    print(f"Saved operator {saved.id} <{saved.email}>")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
