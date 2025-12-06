from collections.abc import Generator
from typing import Annotated
import os

from fastapi import Depends
from sqlmodel import SQLModel, Session, create_engine

# Connect to the dev_pg Postgres service
# (user=app, password=app, db=db, host=dev_pg, port=5432)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://app:app@dev_pg:5432/db",
)

engine = create_engine(
    DATABASE_URL,
    echo=True,  # set to False later if logs are too noisy
)


def create_db_and_tables() -> None:
    """Create all tables in the database if they don't exist."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Yield a database session for dependency injection."""
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]
