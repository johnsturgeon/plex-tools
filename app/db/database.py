from sqlalchemy import create_engine, Engine
from sqlmodel import SQLModel


def get_engine() -> Engine:
    sqlite_file_name = "db/database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    connect_args = {"check_same_thread": False}
    return create_engine(sqlite_url, connect_args=connect_args)


engine: Engine = get_engine()


def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
