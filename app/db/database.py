from sqlalchemy import create_engine, UniqueConstraint
from sqlmodel import SQLModel, Field


class PlexUser(SQLModel, table=True):
    """
    Model representing a Plex user.
    """

    __table_args__ = (UniqueConstraint("plex_uuid"),)
    id: int | None = Field(default=None, primary_key=True)
    plex_uuid: str = Field(index=True)
    auth_token: str
    name: str


def get_engine():
    sqlite_file_name = "db/database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    connect_args = {"check_same_thread": False}
    return create_engine(sqlite_url, connect_args=connect_args)


if __name__ == "__main__":
    # Run this manually once to create the database
    SQLModel.metadata.create_all(get_engine())
