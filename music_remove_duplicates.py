import os
import time
from typing import List, Dict, Optional

import inquirer
from dotenv import load_dotenv
from plexapi.audio import Track
from plexapi.library import Library, MusicSection
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized
from rich.panel import Panel
from rich.progress import Progress
from rich.console import Console, Group
from rich.prompt import Prompt, Confirm
from rich.table import Table
from rich.tree import Tree

console: Console = Console()
PLEX_SERVER: Optional[PlexServer] = None


class JHSTrack:

    def __init__(self, track: Track):
        self.track = track
        self.flagged_as_duplicate = False
        self.title = self.track.title
        self.artist = self.track.grandparentTitle
        self.album = self.track.parentTitle
        self.duration = self.track.duration
        self.key = self.track.key
        self.audio_codec = self.track.media[0].audioCodec
        self.added_at = str(self.track.addedAt)
        if self.track.media[0].parts[0].file is None:
            self.filepath = "TIDAL"
        else:
            self.filepath = self.track.media[0].parts[0].file.strip()
        self.play_count = str(self.track.viewCount)

        self.hash_val = str(f"{self.title}{self.artist}{self.album}{self.duration}")

    def is_duplicate(self, other):
        return self.hash_val == other.hash_val

    def is_identical(self, other):
        return self.track == other.track

    @property
    def song_len(self) -> str:
        m, s = divmod(self.duration / 1000, 60)
        m = int(m)
        s = int(s)
        return f"{m}m{s}s"

    @property
    def rating(self) -> str:
        stars: str = "Unrated"
        if self.track.userRating is not None:
            stars = ""
            rating = int(self.track.userRating / 2)
            for i in range(rating):
                stars += "⭑"
        return stars


def print_duplicate_information(tracks: List[JHSTrack], count, index) -> None:
    track_1: JHSTrack = tracks[0]
    tree = Tree(f"[red]{index}/{count}[/red]: [blue]Song Details[/blue]")
    tree.add(f"[green]Album:[/green] {track_1.album}")
    tree.add(f"[green]Artist:[/green] {track_1.artist}")
    tree.add(f"[green]Duration:[/green] {track_1.song_len}")
    tree.add(f"[green]Duplicates ([i]including original[/i]):[/green] {len(tracks)}")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Version", justify="center")
    table.add_column("Date Added")
    table.add_column("Plays", justify="center")
    table.add_column("Rating", justify="left")
    table.add_column("Codec", justify="left")
    table.add_column("Filepath", justify="left")
    track_version: int = 1
    for track in tracks:
        table.add_row(
            str(track_version),
            track.added_at,
            track.play_count,
            track.rating,
            track.audio_codec,
            track.filepath
        )
        track_version += 1
    panel_group = Group(tree, table)
    box_panel = Panel(
        panel_group,
        title=f"[u]{track_1.title}[/u] -- [i]{track_1.artist}[/i]"
    )
    console.print(box_panel)


def delete_duplicates(duplicate_sets):
    duplicates_to_delete: List[str] = []
    count: int = len(duplicate_sets)
    index: int = 1
    for tracks in duplicate_sets:
        print_duplicate_information(tracks, count, index)
        choices: List = []
        track_version: int = 1
        track: JHSTrack
        for track in tracks:
            choices.append(
                (f"Version: {track_version}",
                 track.key)
            )
            track_version += 1
        questions = [
            inquirer.Checkbox(
                "dupes_to_delete",
                message="Choose which version(s) to delete:",
                choices=choices,
            ),
        ]
        answers = inquirer.prompt(questions)
        if answers is None:
            if len(duplicates_to_delete) == 0:
                console.print("There were no duplicates chosen to delete... exiting")
                exit(0)
            else:
                console.print("Would you like to review the duplicates you've chosen to delete?")
        else:
            duplicates_to_delete += answers["dupes_to_delete"]
        index += 1
    print(duplicates_to_delete)


def setup() -> MusicSection:
    """
    Sets up the environment, logs in to the Plex server and returns the library.
    Returns:
        Library: Library object for the music library

    """
    global PLEX_SERVER
    found_env = load_dotenv()

    # if there is an existing .env, let's use it to try and log in
    if found_env:
        console.print("\n[green]Found an existing .env file, checking it for valid login info[/green]")
        PLEX_SERVER = connect_to_plexserver()
    else:
        #  write code to get ENV vars here
        pass

    library_name: str = os.getenv("MUSIC_LIBRARY_NAME")
    library: MusicSection = PLEX_SERVER.library.section(library_name)
    if not library_name:
        console.rule()
        console.print(
            "[red]No music library name was found in the .env![/red]\n"
            "[yellow]Please delete the .env file and re-run to recreate it.[/yellow]"
        )
        exit(1)

    return library


def connect_to_plexserver() -> PlexServer:
    token = os.getenv("PLEX_TOKEN")
    # if we're using token based auth, then all we need is the base url
    if token:
        console.print("")
        console.print("[blue]Found a Plex Token, trying to log in with that[/blue]\n")
        plex_url = os.getenv("PLEX_URL")
        try:
            plex = PlexServer(plex_url, token)
        except Unauthorized as e:
            console.print(
                "[red]Could not log into plex server with values in .env[/red]\n"
                "[yellow]Please delete the .env file and re-run to recreate it.[/yellow]"
                f"{e}"
            )
            exit(1)

    else:
        from plexapi.myplex import MyPlexAccount
        username = os.getenv("PLEX_USERNAME")
        password = os.getenv("PLEX_PASSWORD")
        servername = os.getenv("PLEX_SERVERNAME")
        account = MyPlexAccount(username, password)
        plex = account.resource(servername).connect()  # returns a PlexServer instance

    if not plex:
        console.print(
            "[red]Could not log into plex server with values in .env[/red]\n"
            "[yellow]Please delete the .env file and re-run to recreate it.[/yellow]"
        )
        exit(1)
    success_panel = Panel.fit("[green bold]Successfully connected to plex server[/green bold]")
    console.print(success_panel)
    console.print("")

    return plex


def duplicate_finder(music_library: MusicSection) -> (List[List[Track]], int):
    """
    Args:
        music_library:
    Returns:
        a list of sets of tracks that have duplicate tracks.
    """
    return_sets: List[List[JHSTrack]] = []
    all_tracks = music_library.searchTracks()
    count: int = len(all_tracks)
    unique_tracks: Dict[str, List[JHSTrack]] = {}
    with Progress() as progress:
        task1 = progress.add_task(f"Querying Plex Server", total=count)
        track: Track
        for track in all_tracks:
            progress.update(task1, advance=1)
            jhs_track: JHSTrack = JHSTrack(track)
            if jhs_track.hash_val not in unique_tracks:
                unique_tracks[jhs_track.hash_val] = []
            unique_tracks[jhs_track.hash_val].append(jhs_track)
        task2 = progress.add_task(f"Searching results for duplicates", total=len(unique_tracks))
        table = Table()
        table.add_column("Row ID")
        table.add_column("Description")
        table.add_column("Level")

        for key, tracks in unique_tracks.items():
            progress.update(task2, advance=1)
            if len(tracks) > 1:
                return_sets.append(tracks)
    return return_sets, count


if __name__ == '__main__':
    panel = Panel.fit(
        "\n[green]Welcome to the [b]Plex Music Duplicate Song Remover[/b][/green]\n"
        "[i]This app will scan your music library searching for duplicates.\n",
        title="Plex Duplicate Song Finder"
    )
    console.clear()
    console.print(panel)
    time.sleep(1)
    the_music_library: MusicSection = setup()
    console.print("")
    sets, num_tracks = duplicate_finder(the_music_library)
    time.sleep(1)
    if len(sets) == 0:
        console.print("Congratulations! You have no duplicates!")
        exit(0)
    else:
        console.print("")
        console.rule()
        console.print("[u]Finished Here's a report of our findings[/u]\n")
        console.print(f"[b]:heavy_check_mark: Total Tracks Searched:[/b] {num_tracks}")
        console.print(f"[b]:heavy_check_mark: Total Tracks with Duplicates:[/b] {len(sets)}")
        console.rule()

    console.print("\nDONE: Let's clean up the duplicates\n", style="bold green")
    should_continue: bool = Confirm.ask("Should we continue?", default="y")
    if not should_continue:
        exit(0)

    console.print("")
    console.print("\nOK, I'm going to go through each song and you need to "
                  "choose which song to delete by selecting the checkbox.")
    console.print("Hit Ctrl+C to stop selecting, and you can choose what to do after that.\n")
    time.sleep(2)
    console.rule()
    console.print("")
    delete_duplicates(sets)
