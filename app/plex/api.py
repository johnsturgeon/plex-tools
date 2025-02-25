import urllib.parse
from typing import Optional, List, Dict
import httpx
from plexapi.myplex import MyPlexAccount, MyPlexResource
from starlette.responses import JSONResponse

from app.config import Config

config = Config.get_config()


async def get_plex_user_data_from_plex(auth_token) -> Optional[Dict]:
    """
    Retrieve Plex user information using an authentication token.

    This function sends a GET request to the Plex user API endpoint with the
     provided authentication token. If the response is successful, it returns the plex user data
     dictionary containing the user's details; otherwise, it returns None.

    Args:
        auth_token (str): The authentication token for the Plex user.

    Returns:
        Optional[dict]: A dictionary of the plex user data if successful; otherwise, None.
    """
    url = f"{config.PLEX_USER_URL}"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            headers={
                "accept": "application/json",
                "X-Plex-Product": config.APP_PRODUCT_NAME,
                "X-Plex-Client-Identifier": config.APP_CLIENT_ID,
                "X-Plex-Token": auth_token,
            },
        )
    if response.status_code != 200:
        return None
    return response.json()


async def fetch_auth_token_from_plex(pin_id, pin_code):
    """
    Fetch the authentication token using a given PIN ID and code.

    This function queries the Plex PIN API with the provided PIN ID and PIN code to retrieve
    the associated authentication token.

    Args:
        pin_id (str): The ID of the generated PIN.
        pin_code (str): The code corresponding to the PIN.

    Returns:
        dict or JSONResponse: The JSON response containing the authentication token if successful,
                              or a JSONResponse with an error message if the token cannot be fetched.
    """
    url = f"{config.PLEX_PIN_URL}/{pin_id}"
    async with httpx.AsyncClient() as client:
        response = await client.get(
            url,
            params={"code": pin_code},
            headers={
                "accept": "application/json",
                "X-Plex-Client-Identifier": config.APP_CLIENT_ID,
            },
        )

    if response.status_code != 200:
        return JSONResponse(status_code=500, content={"error": "Failed to fetch token"})
    response_json = response.json()
    return response_json


async def create_pin_from_plex() -> dict | None:
    """
    Generate a PIN for Plex authentication.

    This function calls the Plex PIN API to generate a new PIN for user authentication. It sends a POST request
    with the required headers and returns the JSON response containing the PIN details.

    Returns:
        dict or JSONResponse: The JSON response with PIN information if successful,
                              or a JSONResponse with an error message if PIN generation fails.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            config.PLEX_PIN_URL,
            json={"strong": True},
            headers={
                "accept": "application/json",
                "X-Plex-Product": config.APP_PRODUCT_NAME,
                "X-Plex-Client-Identifier": config.APP_CLIENT_ID,
            },
        )
    if response.status_code == 201:
        response_json = response.json()
        return response_json

    return None


def get_auth_url_from_pin_info(pin_code: str, pin_id: str) -> str:
    forward_url = f"{config.APP_CALLBACK_URL}?pin_id={pin_id}&pin_code={pin_code}"
    return (
        f"{config.PLEX_AUTH_URL}?clientID={config.APP_CLIENT_ID}&code={pin_code}"
        f"&context%5Bdevice%5D%5Bproduct%5D="
        + urllib.parse.quote(config.APP_PRODUCT_NAME)
        + "&forwardUrl="
        + urllib.parse.quote(forward_url)
    )


def get_server_list_from_plex(auth_token) -> List[MyPlexResource]:
    account = MyPlexAccount(token=auth_token)
    resources = account.resources()
    servers: List[MyPlexResource] = []
    for resource in resources:
        if resource.provides == "server" and resource.owned:
            servers.append(resource)
    return servers


def main():
    account = MyPlexAccount(token=config.DEV_AUTH_TOKEN)
    server = account.resource(config.DEV_RESOURCE_ID)
    print(server)
    resources = account.resources()
    servers: List[str] = []
    for resource in resources:
        if resource.provides == "server" and resource.owned:
            plex = resource.connect()
            for section in plex.library.sections():
                print(section.title)
            servers.append(resource.name)

    for server in servers:
        plex = account.resource(server).connect()
        for section in plex.library.sections():
            print(section.title)


if __name__ == "__main__":
    main()
