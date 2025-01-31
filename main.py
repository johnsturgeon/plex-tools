import os
import httpx
import urllib.parse

from starlette.responses import RedirectResponse, JSONResponse
import uvicorn
from fastapi import FastAPI, Request
from starlette.templating import Jinja2Templates

PLEX_CLIENT_ID = "dc0537e0-6755-44de-97ee-6edd7a51c9b4"  # Generate a UUID for this
PLEX_REDIRECT_URI = "http://localhost:6701/auth/callback"
PLEX_PRODUCT_NAME = "Gosh Darned Plex Tools"
PLEX_PIN_URL = "https://plex.tv/api/v2/pins"
PLEX_AUTH_URL = "https://app.plex.tv/auth#"
PLEX_FORWARD_URL = "http://localhost:6701/"
app = FastAPI()
templates = Jinja2Templates(directory="templates")

user_tokens = {}


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("home.j2", {"request": request})


@app.get("/auth/login")
async def login():
    """
    Step 1: Generate a PIN and redirect the user to Plex for authentication.
    """
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

    pin_data = response.json()
    pin_code = pin_data.get("code")
    pin_id = pin_data.get("id")

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
    user_tokens[pin_id] = {"pin": pin_code, "token": None}

    return RedirectResponse(auth_url)


if __name__ == "__main__":
    reload: bool = os.getenv("ENVIRONMENT") != "production"
    uvicorn.run("main:app", host="0.0.0.0", port=6701, reload=reload, access_log=False)
