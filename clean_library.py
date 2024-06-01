import os
from typing import List, Optional, Dict

import inquirer
from dotenv import load_dotenv
from inquirer.themes import Default
from plexapi.audio import Track
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from rich.panel import Panel
from rich.progress import Progress
from rich.console import Console, Group
from rich.table import Table
from rich.tree import Tree

load_dotenv()

console = Console()

baseurl = os.getenv("PLEX_URL")
token = os.getenv("PLEX_TOKEN")
plex = PlexServer(baseurl, token)


class JHSTheme(Default):
    def __init__(self):
        super().__init__()
        self.Checkbox.selection_icon = "❯"
        self.Checkbox.selected_icon = "◉"
        self.Checkbox.unselected_icon = "◯"
        self.List.selection_cursor = "❯"


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


def is_song_in_playlist(song: Track, playlist: Playlist) -> bool:
    track: Track
    for track in playlist.items():
        if song == track:
            return True
        else:
            return False


def duplicate_finder(music_library_name: str) -> List[List[Track]]:
    """
    Args:
        music_library_name:
    Returns:
        a list of sets of tracks that have duplicate tracks.
    """
    return_sets: List[List[JHSTrack]] = []
    all_tracks = plex.library.section(music_library_name).searchTracks()
    count: int = len(all_tracks)
    unique_tracks: Dict[str, List[JHSTrack]] = {}
    with Progress() as progress:
        task1 = progress.add_task(f"Querying Plex Server", total=count)
        track: JHSTrack
        for track in all_tracks:
            progress.update(task1, advance=1)
            jhs_track: JHSTrack = JHSTrack(track)
            if jhs_track.hash_val not in unique_tracks:
                unique_tracks[jhs_track.hash_val] = []
            unique_tracks[jhs_track.hash_val].append(jhs_track)
        task2 = progress.add_task(f"Searching results for duplicates", total=len(unique_tracks))
        for key, tracks in unique_tracks.items():
            progress.update(task2, advance=1)
            if len(tracks) > 1:
                track_name: str = tracks[0].title
                progress.console.print(
                    f"\"{track_name}\" has {len(tracks) - 1} duplicate track{'s' if len(tracks) > 2 else ''}!")
                return_sets.append(tracks)
    return return_sets


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
    panel = Panel(
        panel_group,
        title=f"[u]{track_1.title}[/u] -- [i]{track_1.artist}[/i]"
    )
    console.print(panel)


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
                (f"Version {track_version}: {track.filepath}",
                 track.key)
            )
            track_version += 1
        questions = [
            inquirer.Checkbox(
                "dupes_to_delete",
                message="Choose duplicates to delete:",
                choices=choices,
            ),
        ]
        answers = inquirer.prompt(questions, theme=JHSTheme())
        if answers is None:
            exit(0)
        duplicates_to_delete += answers["dupes_to_delete"]
        index += 1
    print(duplicates_to_delete)


if __name__ == '__main__':
    sets = duplicate_finder('Old Music')
    console.print("DONE: Let's clean up the duplicates", style="bold green")
    delete_duplicates(sets)
