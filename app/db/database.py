from typing import Optional, List

from pydantic import computed_field
from sqlalchemy import create_engine, UniqueConstraint
from sqlmodel import SQLModel, Field, Session, select

from app.plex.api import get_plex_user_data_from_plex, get_server_list_from_plex


class Preference(SQLModel, table=True):
    """Class representing a preference"""

    id: int | None = Field(default=None, primary_key=True)
    user_id: str = Field(index=True, foreign_key="plexuser.id")
    key: str
    value: str


class PlexServer(SQLModel, table=False):
    """Class representing a Plex Server - no persistence"""

    client_id: str
    name: str


class PlexUser(SQLModel, table=True):
    """Model representing a Plex user."""

    __table_args__ = (UniqueConstraint("plex_uuid"),)
    id: int | None = Field(default=None, primary_key=True)
    plex_uuid: str = Field(index=True)
    auth_token: str
    name: str

    # -- private methods --
    def _set_preference(self, key, value):
        with Session(get_engine()) as session:
            # Check if the preference already exists
            # noinspection Pydantic

            statement = select(Preference).where(
                Preference.user_id == self.plex_uuid
                and Preference.key == key
                and Preference.value == value
            )
            # noinspection PyTypeChecker
            existing_preference = session.exec(statement).first()

            if existing_preference:
                # Update existing preference
                existing_preference.value = value
            else:
                # Insert new preference
                session.add(Preference(user_id=self.plex_uuid, key=key, value=value))

            session.commit()  # Commit changes

    # -- properties --
    @computed_field
    @property
    def server_list(self) -> List[PlexServer]:
        server_list: List[PlexServer] = []
        for server in get_server_list_from_plex(self.auth_token):
            plex_server: PlexServer = PlexServer(
                client_id=server.clientIdentifier, name=server.name
            )
            server_list.append(plex_server)
        return server_list

    @computed_field
    @property
    def preferences(self) -> List[Preference]:
        preferences: List[Preference] = []
        with Session(get_engine()) as session:
            # Check if the user already exists
            # noinspection Pydantic
            statement = select(Preference).where(Preference.user_id == self.plex_uuid)
            # noinspection PyTypeChecker
            db_prefs = session.exec(statement)
            for preference in db_prefs:
                preferences.append(preference)
        return preferences

    @computed_field
    @property
    def server(self) -> Optional[PlexServer]:
        for preference in self.preferences:
            if preference.key == "server":
                server_pref = preference
                for server in self.server_list:
                    if server.client_id == server_pref.value:
                        return server
                assert False, "The server preference did not match the list of servers"
        return None

    # -- public methods --
    def set_server(self, value):
        self._set_preference("server", value)


async def upsert_plex_user(auth_token: str):
    """Updates the user, or inserts if none exists"""
    plex_user: PlexUser = await get_plex_user_from_auth_token(auth_token)
    plex_uuid: str = plex_user.plex_uuid
    with Session(get_engine()) as session:
        # Check if the user already exists
        # noinspection Pydantic
        statement = select(PlexUser).where(PlexUser.plex_uuid == plex_uuid)
        # noinspection PyTypeChecker
        existing_user = session.exec(statement).first()
        if existing_user:
            # Update existing user
            existing_user.auth_token = plex_user.auth_token
            existing_user.name = plex_user.name
        else:
            # Insert new user
            session.add(plex_user)
        session.commit()  # Commit changes
    return plex_user


async def get_plex_user_from_auth_token(auth_token) -> Optional[PlexUser]:
    """
    Retrieve Plex user information using an authentication token.

    This function sends a GET request to the Plex user API endpoint with the
    provided authentication token. If the response is successful, it returns a
    PlexUser object containing the user's details; otherwise, it returns None.

    Args:
        auth_token (str): The authentication token for the Plex user.

    Returns:
        Optional[PlexUser]: A PlexUser object if successful; otherwise, None.
    """
    response_json = await get_plex_user_data_from_plex(auth_token)
    user = PlexUser(
        name=response_json["username"],
        auth_token=auth_token,
        plex_uuid=response_json["uuid"],
    )
    return user


def find_user_by_plex_uuid(plex_uuid: str) -> Optional[PlexUser]:
    with Session(get_engine()) as session:
        # noinspection Pydantic
        statement = select(PlexUser).where(PlexUser.plex_uuid == plex_uuid)
        # noinspection PyTypeChecker
        result = session.exec(statement)
        return result.first()


def get_engine():
    sqlite_file_name = "db/database.db"
    sqlite_url = f"sqlite:///{sqlite_file_name}"
    connect_args = {"check_same_thread": False}
    return create_engine(sqlite_url, connect_args=connect_args)


if __name__ == "__main__":
    # Run this manually once to create the database
    SQLModel.metadata.create_all(get_engine())
