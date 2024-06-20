""" Plex Connect will use (or create) a .env file to connect to your Plex server. """
import os
from pathlib import Path

from dotenv import load_dotenv, set_key
from plexapi.exceptions import Unauthorized, NotFound
from plexapi.library import MusicSection
from plexapi.server import PlexServer
from plexapi.myplex import MyPlexAccount
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt


class GDException(Exception):
    """ Generic exception class"""


def connect_to_plexserver(console: Console) -> PlexServer:
    """
    Connects to a PlexServer and returns the PlexServer object.
    Args:
        console (Console): Console object to connect to.
    Returns: PlexServer
    """
    token = os.getenv("PLEX_TOKEN")
    # if we're using token based auth, then all we need is the base url
    if token:
        console.print("")
        console.print(":information: Found a Plex Token, trying to log in with that\n")
        plex_url = os.getenv("PLEX_URL")
        try:
            plex_server: PlexServer = PlexServer(plex_url, token)
        except Unauthorized as exc:
            raise GDException("Could not log into plex server with values in .env") from exc
    else:
        username = os.getenv("PLEX_USERNAME")
        password = os.getenv("PLEX_PASSWORD")
        servername = os.getenv("PLEX_SERVERNAME")
        try:
            plex_server: PlexServer = MyPlexAccount(
                username,
                password
            ).resource(servername).connect()
        except (AttributeError, Unauthorized) as e:
            raise GDException("Could not log into plex server with values in .env") from e

    return plex_server


def _add_username_to_env_file(env_file_path):
    username = Prompt.ask("What is your username?")
    password = Prompt.ask("What is your password?", password=True)
    servername = Prompt.ask("What is your server?")
    set_key(dotenv_path=env_file_path, key_to_set="PLEX_USERNAME", value_to_set=username)
    set_key(dotenv_path=env_file_path, key_to_set="PLEX_PASSWORD", value_to_set=password)
    set_key(dotenv_path=env_file_path, key_to_set="PLEX_SERVERNAME", value_to_set=servername)

def _add_token_to_env_file(env_file_path):
    token = Prompt.ask("What is your token?")
    url = Prompt.ask("What is your Plex Server URL [i](ex: http://192.168.1.44:32400)[/i]?")
    set_key(dotenv_path=env_file_path, key_to_set="PLEX_TOKEN", value_to_set=token)
    set_key(dotenv_path=env_file_path, key_to_set="PLEX_URL", value_to_set=url)

def _add_music_library_to_env_file(env_file_path):
    music_library = Prompt.ask("What is the name of your Music library?")
    set_key(dotenv_path=env_file_path, key_to_set="MUSIC_LIBRARY_NAME", value_to_set=music_library)

def _get_plex_login_method(console) -> str:
    choices = ["u", "t"]
    # pylint: disable=line-too-long
    panel = Panel(
        "Information about how to log in to your "
        "Plex Server for API access can be found "
        "here: https://python-plexapi.readthedocs.io/en/stable/introduction.html#getting-a-plexserver-instance",
        style="blue"
    )
    # pylint: enable=line-too-long
    console.print(panel)
    answer = Prompt.ask("How would you like to access your server?\n"
                        "[magenta](u):[/magenta] "
                        "Username/Password, or [magenta](t):[/magenta] Token?",
                        choices=choices)
    return answer

def _get_plex_library_section(plex, library_name) -> MusicSection:
    section: MusicSection
    try:
        section = plex.library.section(library_name)
    except NotFound as exc:
        raise GDException(f"Could not find library \"{library_name}\" on your plexserver") from exc
    return section


def load_or_create_dotenv(console):

    """
    Sets up the environment, logs in to the Plex server and returns the library.
    Returns:
        Library: Library object for the music library
    Throws:
        Unauthorized

    """
    found_env = load_dotenv()
    if found_env:
        console.print("\n:information: Found an existing .env file, "
                      "checking it for valid login info")
    else:
        console.print("\n:information: No .env file found, "
                      "let's create one and save it in the current directory.")
        env_file_path = Path(".env")
        env_file_path.touch(mode=0o600, exist_ok=True)
        answer = _get_plex_login_method(console)
        if answer == "u":
            _add_username_to_env_file(env_file_path)
        else:
            _add_token_to_env_file(env_file_path)
        console.print("\n:information: Login information saved values to .env file\n")

        _add_music_library_to_env_file(env_file_path)

        load_dotenv()

def setup(console: Console) -> MusicSection:
    """
    Returns:  The MusicSection specific plex library
              or throws GDException if it couldn't get it
    """
    load_or_create_dotenv(console)
    plex = connect_to_plexserver(console)
    success_panel = Panel.fit(
        f"[green bold]Successfully connected to plex server library"
        f" \"{os.getenv('MUSIC_LIBRARY_NAME')}\"[/green bold]"
    )
    console.print(success_panel)
    console.print("")

    library_name: str = os.getenv("MUSIC_LIBRARY_NAME")
    if not library_name:
        raise GDException("Could not find a library name in the .env file")
    library: MusicSection = _get_plex_library_section(plex, library_name)
    console.print("Log in [green]Successful[/green]")
    return library
