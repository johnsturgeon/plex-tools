from typing import Optional, List, Annotated

import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends, Form
from pydantic import BaseModel
from sqlalchemy import Engine
from starlette import status
from starlette.responses import RedirectResponse
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.db.database import (
    find_user_by_plex_uuid,
    get_engine,
    PlexUser,
    get_plex_user_from_auth_token,
    PlexServer,
    PlexLibrary,
)
from app.routers import auth
from app.config import Config

# Constants used for Plex API configuration and cookie settings.

config = Config.get_config()

# Initialize the FastAPI app and add session middleware.
app = FastAPI()
# noinspection PyTypeChecker
app.add_middleware(SessionMiddleware, secret_key=config.SESSION_SECRET_KEY)

engine: Engine = get_engine()

app.include_router(auth.router)


@app.middleware("http")
async def some_middleware(request: Request, call_next):
    """
    Middleware to preserve the session cookie across HTTP responses.

    This middleware intercepts incoming HTTP requests and ensures that if the session cookie is present,
    it is set as an HTTP-only cookie in the outgoing response.

    Args:
        request (Request): The incoming HTTP request.
        call_next (Callable): The next middleware or route handler in the chain.

    Returns:
        Response: The HTTP response with the session cookie set (if present).
    """
    response = await call_next(request)
    session = request.cookies.get("session")
    if session:
        response.set_cookie(
            key="session", value=request.cookies.get("session"), httponly=True
        )
    return response


# Initialize the Jinja2 templates directory.
templates = Jinja2Templates(directory="templates")

# A simple in-memory store for user tokens (if needed in the future).
user_tokens = {}


async def get_cookie_user_from_db(request: Request) -> Optional[PlexUser]:
    plex_uuid = request.cookies.get("plex_uuid")
    if plex_uuid:
        return find_user_by_plex_uuid(plex_uuid)


async def verify_plex_user(request: Request) -> PlexUser:
    """
    Verify the Plex user from the current session or redirect to the login if not authenticated.

    This function attempts to retrieve the Plex user information using the 'auth_token' stored in the cookies.
    If the token is valid, it returns a PlexUser object. Otherwise, it raises an HTTPException to trigger a
    redirection to the login route.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        PlexUser: The authenticated Plex user.

    Raises:
        HTTPException: If the user is not authenticated, with a temporary redirect header to the login page.
    """
    plex_user: Optional[PlexUser] = await get_cookie_user_from_db(request)
    if plex_user:
        if request.session.get("token_is_valid"):
            return plex_user
        else:
            # attempt to just re-authenticate the token and log them in
            if await get_plex_user_from_auth_token(plex_user.auth_token):
                request.session["token_is_valid"] = True
                return plex_user

    if request.cookies.get("plex_uuid"):
        request.cookies.pop("plex_uuid")
    raise HTTPException(
        status_code=status.HTTP_307_TEMPORARY_REDIRECT,
        headers={"Location": "/auth/login"},
    )


@app.get("/")
async def root(request: Request):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.

    Returns:
        TemplateResponse: The rendered home page.
    """
    user_name: Optional[str] = None
    plex_user: PlexUser = await get_cookie_user_from_db(request)
    if plex_user:
        user_name: str = plex_user.name
    return templates.TemplateResponse(
        "home.j2",
        {"request": request, "user_name": user_name, "config": config},
    )


@app.get("/duplicates", name="duplicates")
async def duplicates(
    request: Request,
    plex_user: PlexUser = Depends(verify_plex_user),
):
    """
    Render the home page for authenticated Plex users.

    This route handler renders the home page template with the authenticated user's information.

    Args:
        request (Request): The incoming HTTP request.
        plex_user (PlexUser): The authenticated Plex user, obtained via dependency injection.

    Returns:
        TemplateResponse: The rendered home page.
    """
    return templates.TemplateResponse(
        "duplicates.j2",
        {
            "request": request,
            "plex_user": plex_user,
            "config": config,
        },
    )


@app.get("/preferences")
async def preferences(
    request: Request,
    plex_user: PlexUser = Depends(verify_plex_user),
):
    """
    Renders the user's account page
    """
    plex_servers: List[PlexServer] = plex_user.server_list
    plex_music_libraries: List[PlexLibrary] = plex_user.music_library_list
    selected_server_id: Optional[str] = None
    selected_music_library_id: Optional[str] = None
    if plex_user.server:
        selected_server_id: Optional[str] = plex_user.server.client_id
    if plex_user.music_library:
        selected_music_library_id: Optional[str] = plex_user.music_library.uuid
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
    plex_user: PlexUser = Depends(verify_plex_user),
):
    if data.server_id:
        plex_user.set_server(data.server_id)
    if data.music_library_id:
        plex_user.set_music_library(data.music_library_id)
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
