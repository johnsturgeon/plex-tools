import os
import urllib.parse

import httpx
import uvicorn
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

PLEX_CLIENT_ID = "dc0537e0-6755-44de-97ee-6edd7a51c9b4"  # Generate a UUID for this
PLEX_REDIRECT_URI = "http://localhost:6701/auth/callback"
PLEX_PRODUCT_NAME = "Gosh Darned Plex Tools"
PLEX_PIN_URL = "https://plex.tv/api/v2/pins"
PLEX_AUTH_URL = "https://app.plex.tv/auth#"
PLEX_FORWARD_URL = "http://localhost:6701/"
app = FastAPI()
# noinspection PyTypeChecker
app.add_middleware(SessionMiddleware, secret_key="some-random-string")

@app.middleware("http")
async def some_middleware(request: Request, call_next):
    response = await call_next(request)
    session = request.cookies.get("session")
    if session:
        response.set_cookie(
            key="session", value=request.cookies.get("session"), httponly=True
        )
    return response


templates = Jinja2Templates(directory="templates")

user_tokens = {}

async def generate_pin():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            PLEX_PIN_URL,
            json={"strong": True},
            headers={
                "accept": "application/json",
                "X-Plex-Product": PLEX_PRODUCT_NAME,
                "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
            },
        )

    if response.status_code != 201:
        return JSONResponse(
            status_code=500, content={"error": "Failed to generate PIN"}
        )
    response_json = response.json()
    return response_json

async def fetch_auth_token(pin_id):
    # $ curl -X GET 'https://plex.tv/api/v2/pins/<pinID>' \
    #   -H 'accept: application/json' \
    #   -d 'code=<pinCode>' \
    #   -d 'X-Plex-Client-Identifier=<clientIdentifier>'
    async with httpx.AsyncClient() as client:
        response = await client.post(
            PLEX_PIN_URL,
            json={"code": pin_id},
            headers={
                "accept": "application/json",
                "X-Plex-Client-Identifier": PLEX_CLIENT_ID,
            },
        )

    if response.status_code != 201:
        return JSONResponse(
            status_code=500, content={"error": "Failed to fetch token"}
        )
    response_json = response.json()
    print(response_json.get("authToken"))
    return response_json

@app.get("/")
async def root(request: Request):
    pin_info = request.session.get("pin_info")
    pin_data = await fetch_auth_token(pin_info.get("pin_id"))
    print(pin_data)
    return templates.TemplateResponse(
        "home.j2", {
            "request": request,
            "pin_id": pin_info.get("pin_id"),
            "token": pin_info.get("token"),
        }
    )


@app.get("/auth/login")
async def login(request: Request):
    """
    Step 1: Generate a PIN and redirect the user to Plex for authentication.
    """
    request_pin_info = await generate_pin()
    pin_code = request_pin_info.get("code")
    pin_id = request_pin_info.get("id")

    if not pin_code or not pin_id:
        return JSONResponse(status_code=500, content={"error": "Invalid PIN response"})

    auth_url = (
        f"{PLEX_AUTH_URL}?clientID={PLEX_CLIENT_ID}&code={pin_code}"
        f"&context%5Bdevice%5D%5Bproduct%5D="
        + urllib.parse.quote(PLEX_PRODUCT_NAME)
        + "&forwardUrl="
        + urllib.parse.quote(PLEX_FORWARD_URL)
    )
    # Store the pin_id temporarily
    request.session["pin_info"] = {"pin_id": pin_id, "token": None}

    return RedirectResponse(auth_url)


if __name__ == "__main__":
    reload: bool = os.getenv("ENVIRONMENT") != "production"
    uvicorn.run("main:app", host="0.0.0.0", port=6701, reload=reload, access_log=False)
