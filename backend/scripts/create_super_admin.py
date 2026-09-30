from __future__ import annotations

import sys
from pathlib import Path
from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database import SessionLocal
from app.core.security import MIN_PASSWORD_LENGTH, hash_password, normalize_email
from app.models.user import User


def main() -> int:
    try:
        email = normalize_email(str(TypeAdapter(EmailStr).validate_python(input("Super Admin email: "))))
    except ValidationError:
        print("Error: enter a valid email address.", file=sys.stderr)
        return 1

    password = getpass("Password: ")
    confirmation = getpass("Confirm password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(
            f"Error: password must be at least {MIN_PASSWORD_LENGTH} characters.",
            file=sys.stderr,
        )
        return 1
    if password != confirmation:
        print("Error: passwords do not match.", file=sys.stderr)
        return 1

    db = SessionLocal()
    try:
        existing_user_id = db.scalar(
            select(User.user_id).where(func.lower(User.email) == email)
        )
        if existing_user_id is not None:
            print(f"Error: an account already exists for {email}.", file=sys.stderr)
            return 1

        user = User(
            email=email,
            password_hash=hash_password(password),
            person_id=None,
            is_active=True,
            is_super_admin=True,
        )
        db.add(user)
        db.commit()
    except IntegrityError:
        db.rollback()
        existing_user_id = db.scalar(
            select(User.user_id).where(func.lower(User.email) == email)
        )
        if existing_user_id is not None:
            print(f"Error: an account already exists for {email}.", file=sys.stderr)
            return 1
        print("Error: the database rejected the account; no user was created.", file=sys.stderr)
        return 1
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    print(f"Platform Super Admin created for {email}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
