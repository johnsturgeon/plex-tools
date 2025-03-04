from typing import Optional, List, Annotated, Dict

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Form
from pydantic import BaseModel
from sqlalchemy import func
from sqlmodel import Session, select
from starlette import status
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.db.database import create_db_and_tables, engine
from app.db.models import (
    PlexUser,
    PlexServer,
    PlexLibrary,
    query_user_by_uuid,
    PlexTrack,
)
from app.routers import auth
from app.config import Config

# Constants used for Plex API configuration and cookie settings.

config = Config.get_config()

# Initialize the FastAPI app and add session middleware.
app = FastAPI()
# noinspection PyTypeChecker
app.add_middleware(
    SessionMiddleware, secret_key=config.SESSION_SECRET_KEY, max_age=3600
)


create_db_and_tables()

app.include_router(auth.router)

# Initialize the Jinja2 templates directory.
templates = Jinja2Templates(directory="templates")


def get_session():
    with Session(engine) as session:
        yield session


async def verify_plex_user(request: Request) -> str:
    """
    Verify the Plex user from the current session or redirect to the login if not authenticated.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        str: The authenticated Plex user uuid.

    Raises:
        HTTPException: If the user is not authenticated, with a temporary redirect header to the login page.
    """

    user_uuid: Optional[str] = request.session.get("user_uuid")
    if user_uuid:
        return user_uuid

    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": "/auth/login"},
    )


async def verify_library_db_synced(request: Request):
    if not request.session.get("db_is_synced"):
        user_uuid: Optional[str] = request.session.get("user_uuid")
        if user_uuid:
            with Session(engine) as session:
                plex_user: PlexUser = query_user_by_uuid(session, user_uuid)
                plex_user.sync_libraries_with_db(session)
                request.session["db_is_synced"] = True


async def verify_tracks_db_synced(request: Request):
    if not request.session.get("tracks_are_synced"):
        user_uuid: Optional[str] = request.session.get("user_uuid")
        if user_uuid:
            with Session(engine) as session:
                plex_user: PlexUser = query_user_by_uuid(session, user_uuid)
                plex_user.sync_tracks_with_db(session)
                request.session["tracks_are_synced"] = True


@app.get("/")
async def root(
    request: Request,
    user_uuid: Optional[str] = Depends(verify_plex_user),
    session: Session = Depends(get_session),
):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.
        user_uuid (Optional[str]): The UUID of the authenticated user.
        session (Optional[Session]): The current session object.

    Returns:
        TemplateResponse: The rendered home page.
    """
    plex_user: PlexUser = query_user_by_uuid(session, user_uuid)
    return templates.TemplateResponse(
        "home.j2",
        {"request": request, "plex_user": plex_user, "config": config},
    )


# noinspection Pydantic,PyTypeChecker
@app.get("/duplicates", name="duplicates")
async def duplicates(
    request: Request,
    user_uuid: Optional[str] = Depends(verify_plex_user),
    session: Session = Depends(get_session),
    _=Depends(verify_library_db_synced),
    __=Depends(verify_tracks_db_synced),
):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.
        user_uuid (Optional[str]): The UUID of the authenticated user.
        session (Optional[Session]): The current session object.
        _: verify that the database has been synced with the Plex server.
        __: Verify that the library tracks have been synced to the DB.

    Returns:
        TemplateResponse: The rendered home page.
    """
    plex_user: PlexUser = query_user_by_uuid(session, user_uuid)
    statement = (
        select(PlexTrack)
        .group_by(PlexTrack.hash_value)
        .having(func.count(PlexTrack.hash_value) > 1)
    )
    dupe_set: Dict[str, List] = {}
    for track in session.exec(statement):
        dupe_query = select(PlexTrack).where(PlexTrack.hash_value == track.hash_value)
        for dupe in session.exec(dupe_query):
            if dupe.hash_value not in dupe_set:
                dupe_set[dupe.hash_value] = []
            dupe_set[dupe.hash_value].append(dupe)
    return templates.TemplateResponse(
        "duplicates.j2",
        {
            "request": request,
            "plex_user": plex_user,
            "config": config,
            "dupe_set": dupe_set,
        },
    )


@app.get("/preferences")
async def preferences(
    request: Request,
    user_uuid: Optional[str] = Depends(verify_plex_user),
    session: Session = Depends(get_session),
    _=Depends(verify_library_db_synced),
):
    """
    Renders the user's account page
    """
    plex_user: PlexUser = query_user_by_uuid(session, user_uuid)

    plex_servers: List[PlexServer] = plex_user.servers
    plex_music_libraries: Optional[List[PlexLibrary]] = None
    selected_server_id: Optional[str] = None
    selected_music_library_id: Optional[str] = None
    if plex_user.preferred_server:
        plex_music_libraries: List[PlexLibrary] = plex_user.preferred_server.libraries
        selected_server_id: Optional[str] = plex_user.preferred_server.uuid
        if plex_user.preferred_music_library:
            selected_music_library_id: Optional[str] = (
                plex_user.preferred_music_library.uuid
            )
    return templates.TemplateResponse(
        "preferences.j2",
        {
            "request": request,
            "plex_user": plex_user,
            "config": config,
            "plex_servers": plex_servers,
            "selected_server_id": selected_server_id,
            "plex_music_libraries": plex_music_libraries,
            "selected_music_library_id": selected_music_library_id,
        },
    )


class PreferenceFormData(BaseModel):
    server_id: Optional[str] = None
    music_library_id: Optional[str] = None


@app.post("/preferences/save")
async def save_preferences(
    request: Request,
    data: Annotated[PreferenceFormData, Form()],
    user_uuid: Optional[str] = Depends(verify_plex_user),
    session: Session = Depends(get_session),
    _=Depends(verify_library_db_synced),
):
    plex_user: PlexUser = query_user_by_uuid(session, user_uuid)
    if data.server_id:
        plex_user.set_server(session, data.server_id)
    if data.music_library_id:
        plex_user.set_music_library(session, data.music_library_id)
    redirect_url = request.url_for("preferences")
    response = RedirectResponse(url=redirect_url, status_code=status.HTTP_302_FOUND)
    return response


if __name__ == "__main__":
    """
    Entry point for running the application.

    This block checks the 'ENVIRONMENT' variable to determine whether to enable auto-reloading.
    It then runs the FastAPI application using uvicorn on host '0.0.0.0' and port 6701.
    """
    reload: bool = config.ENVIRONMENT != "production"
    uvicorn.run(
        "main:app", host="0.0.0.0", port=config.PORT, reload=reload, access_log=False
    )
