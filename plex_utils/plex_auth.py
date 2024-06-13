import os

from dotenv import load_dotenv, set_key
from plexapi.exceptions import Unauthorized, NotFound
from plexapi.library import MusicSection
from plexapi.server import PlexServer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from pathlib import Path


class GDException(Exception):
    pass


def _connect_to_plexserver(console: Console) -> PlexServer:
    token = os.getenv("PLEX_TOKEN")
    # if we're using token based auth, then all we need is the base url
    if token:
        console.print("")
        console.print(":information: Found a Plex Token, trying to log in with that\n")
        plex_url = os.getenv("PLEX_URL")
        try:
            plex = PlexServer(plex_url, token)
        except Unauthorized:
            raise GDException("Could not log into plex server with values in .env")
    else:
        from plexapi.myplex import MyPlexAccount
        username = os.getenv("PLEX_USERNAME")
        password = os.getenv("PLEX_PASSWORD")
        servername = os.getenv("PLEX_SERVERNAME")
        account = MyPlexAccount(username, password)
        try:
            plex = account.resource(servername).connect()  # returns a PlexServer instance
        except Unauthorized:
            raise GDException("Could not log into plex server with values in .env")

    if not plex:
        raise GDException("Could not log into plex server with values in .env")
    return plex


def setup(console: Console) -> MusicSection:
    """
    Sets up the environment, logs in to the Plex server and returns the library.
    Returns:
        Library: Library object for the music library
    Throws:
        Unauthorized

    """
    found_env = load_dotenv()

    # if there is an existing .env, let's use it to try and log in
    if found_env:
        console.print("\n:information: Found an existing .env file, checking it for valid login info")
    else:
        #  write code to get ENV vars here
        console.print("\n:information: No .env file found, let's create one and save it in the current directory.")
        choices = ["u", "t"]
        panel = Panel(
            "Information about how to log in to your Plex Server for API access can be found "
            "here: https://python-plexapi.readthedocs.io/en/stable/introduction.html#getting-a-plexserver-instance",
            style="blue"
        )
        console.print(panel)
        answer = Prompt.ask("How would you like to access your server?\n"
                            "[magenta](u):[/magenta] Username/Password, or [magenta](t):[/magenta] Token?",
                            choices=choices)
        env_file_path = Path(".env")
        # Create the file if it does not exist.
        env_file_path.touch(mode=0o600, exist_ok=True)
        if answer == "u":
            username = Prompt.ask("What is your username?")
            password = Prompt.ask("What is your password?", password=True)
            servername = Prompt.ask("What is your server?")
            set_key(dotenv_path=env_file_path, key_to_set="PLEX_USERNAME", value_to_set=username)
            set_key(dotenv_path=env_file_path, key_to_set="PLEX_PASSWORD", value_to_set=password)
            set_key(dotenv_path=env_file_path, key_to_set="PLEX_SERVERNAME", value_to_set=servername)
        else:
            token = Prompt.ask("What is your token?")
            url = Prompt.ask("What is your Plex Server URL [i](ex: http://192.168.1.44:32400)[/i]?")
            set_key(dotenv_path=env_file_path, key_to_set="PLEX_TOKEN", value_to_set=token)
            set_key(dotenv_path=env_file_path, key_to_set="PLEX_URL", value_to_set=url)
        console.print("\n:information: Login information saved values to .env file\n")
        music_library = Prompt.ask("What is the name of your Music library?")
        set_key(dotenv_path=env_file_path, key_to_set="MUSIC_LIBRARY_NAME", value_to_set=music_library)
        load_dotenv()
    try:
        plex = _connect_to_plexserver(console)
    except GDException as jhs_exception:
        console.rule()
        console.print(f"\n[red]{jhs_exception}[/red]")
        console.print("\n[yellow]Please delete the .env file and re-run to recreate it.[/yellow]\n")
        exit(1)
    success_panel = Panel.fit(
        f"[green bold]Successfully connected to plex server library"
        f" \"{os.getenv('MUSIC_LIBRARY_NAME')}\"[/green bold]"
    )
    console.print(success_panel)
    console.print("")

    library_name: str = os.getenv("MUSIC_LIBRARY_NAME")
    if not library_name:
        console.rule()
        console.print(f"\n[red]MUSIC_LIBRARY_NAME not found in .env file![/red]")
        console.print("\n[yellow]Please delete the .env file and re-run to recreate it, or manually add it.[/yellow]\n")
        exit(1)
    try:
        library: MusicSection = plex.library.section(library_name)
    except NotFound:
        console.rule()
        console.print(f"\n[red]Plex Library \"{library_name}\" could not be found![/red]")
        console.print("\n[yellow]Please correct MUSIC_LIBRARY_NAME in the .env file.\n"
                      "Optionally, you can delete the .env file and re-run to recreate it[/yellow]\n")
        exit(1)
    if library:
        console.print("Log in [green]Successful[/green]")
    return library
