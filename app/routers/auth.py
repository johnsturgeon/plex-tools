from typing import Optional, Final

from fastapi import APIRouter
from sqlmodel import Session
from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse

from app.config import Config
from app.db.database import engine
from app.db.models import PlexUser, upsert_plex_user
from app.plex.api import (
    fetch_auth_token_from_plex,
    create_pin_from_plex,
    get_auth_url_from_pin_info,
)

config = Config.get_config()
SECONDS_IN_A_DAY: Final[int] = 60 * 60 * 24
COOKIE_TIME_OUT = config.COOKIE_RETENTION_DAYS * SECONDS_IN_A_DAY

router = APIRouter(prefix="/auth", tags=["auth"])


async def _get_auth_token_from_pin(pin_id: str, pin_code: str) -> Optional[str]:
    """
    Retrieve the authentication token from a previously generated PIN stored in session.

    This function checks if the session contains PIN information. If present, it uses that information
    to fetch the authentication token from the Plex API. Once the token is retrieved, it removes the
    PIN information from the session.

    Args:
        pin_id (str): The PIN ID of the PLEX user.
        pin_code (str): The PIN code of the PLEX user.

    Returns:
        Optional[str]: The retrieved authentication token if available; otherwise, None.
    """
    auth_token: Optional[str] = None
    pin_data = await fetch_auth_token_from_plex(pin_id, pin_code)
    if isinstance(pin_data, dict):
        auth_token = pin_data.get("authToken")
    return auth_token


@router.get("/login")
async def login(request: Request) -> JSONResponse:
    """
    Initiate the Plex login process by generating a PIN and redirecting to Plex's authentication page.

    This route handler calls the Plex PIN API to generate a new PIN, builds the authentication URL using the
    generated PIN, and stores the PIN information in the session. The user is then redirected to Plex to complete
    the authentication process.

    Returns:
        RedirectResponse: A redirection to the Plex authentication URL, or a JSONResponse with an error message
                          if the PIN generation fails.
    """
    if request.cookies.get("saved_user_uuid"):
        request.cookies.pop("saved_user_uuid")
    request_pin_info = await create_pin_from_plex()
    if request_pin_info:
        pin_code = request_pin_info.get("code")
        pin_id = request_pin_info.get("id")
        auth_url = get_auth_url_from_pin_info(pin_code=pin_code, pin_id=pin_id)
        # noinspection PyTypeChecker
        return RedirectResponse(auth_url)

    return JSONResponse(status_code=500, content={"error": "Invalid PIN response"})


@router.get("/callback")
async def callback(request: Request, pin_id: str, pin_code: str):
    """
    Handle the callback from Plex authentication.

    After Plex authentication, this route is called to retrieve the authentication token using the PIN
    information stored in the session. Depending on whether the token retrieval is successful, the user is
    redirected either to the home page or to the login page.

    Args:
        request (Request): The incoming HTTP request containing session data.
        pin_id (str): The ID of the generated PIN.
        pin_code (str): The code corresponding to the PIN.

    Returns:
        RedirectResponse: A redirection to the home page if authentication is successful,
                          or to the login page if not.
    """
    auth_token = await _get_auth_token_from_pin(pin_id, pin_code)
    if auth_token:
        with Session(engine) as db_session:
            plex_user: PlexUser = await upsert_plex_user(db_session, auth_token)
            request.session["user_uuid"] = plex_user.uuid
            redirect_url = request.url_for("root")
            response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
            response.set_cookie(
                key="saved_user_uuid",
                value=plex_user.uuid,
                max_age=COOKIE_TIME_OUT,
            )
    else:
        redirect_url = request.url_for("login")
        response = RedirectResponse(redirect_url, status_code=status.HTTP_302_FOUND)
    return response
