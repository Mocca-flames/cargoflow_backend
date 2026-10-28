import os

from sqlalchemy import select

from app.core.database import SessionLocal   # change if yours is named differently
from app.core.security import hash_password
from app.features.users.model import User


def main() -> None:
    email = os.environ['SEED_DIRECTOR_EMAIL'].lower().strip()
    password = os.environ['SEED_DIRECTOR_PASSWORD']

    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email == email)):
            print('Director already exists, nothing to do.')
            return

        db.add(User(
            email=email,
            password_hash=hash_password(password),
            full_name='Director',
            staff_role='director',
            must_change_password=True,
        ))
        db.commit()
        print(f'Created director: {email}')


if __name__ == '__main__':
    main()