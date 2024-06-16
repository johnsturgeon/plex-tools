import os
import time
import logging
from pathlib import Path
from typing import List, Dict, Optional

from dotenv import load_dotenv, set_key
from plexapi.audio import Track
from plexapi.library import Library, MusicSection
from plexapi.server import PlexServer
from plexapi.exceptions import Unauthorized, NotFound
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.table import Table
from rich.tree import Tree

from plex_utils import setup

console: Console = Console()
DEFAULT_DUPLICATE_PLAYLIST_NAME = "GoshDarned Duplicates"


class JHSException(Exception):
    pass


class JHSTrack:
    def __init__(self, track: Track):
        self.track = track
        self.flagged_for_deletion: bool = False
        self.title = self.track.title
        self.artist = self.track.grandparentTitle
        self.album = self.track.parentTitle
        self.duration = self.track.duration
        self.key = self.track.key
        self.audio_codec = self.track.media[0].audioCodec
        self.added_at = str(self.track.addedAt)
        self._user_rating: Optional[float] = None
        self.play_count = str(self.track.viewCount)
        if self.track.media[0].parts[0].file is None:
            self.filepath = "TIDAL"
        else:
            self.filepath = self.track.media[0].parts[0].file.strip()

        self.hash_val = str(f"{self.title}{self.artist}{self.album}{self.duration}")

    def is_duplicate(self, other):
        return self.hash_val == other.hash_val

    def is_identical(self, other):
        return self.track == other.track

    @property
    def star_rating(self) -> str:
        stars: str = "Unrated"
        if self.user_rating is not None:
            stars = ""
            rating = int(self.user_rating / 2)
            for i in range(rating):
                stars += "⭑"
        return stars

    @property
    def user_rating(self):
        if self._user_rating:
            return self._user_rating
        elif self.track.userRating is not None:
            self._user_rating = float(self.track.userRating)
        return self._user_rating


class JHSDuplicateSet:
    def __init__(self, duplicate_tracks: List[JHSTrack]):
        self.duplicate_tracks: List[JHSTrack] = duplicate_tracks
        self.title: str = self.duplicate_tracks[0].title
        self.artist: str = self.duplicate_tracks[0].artist
        self.album: str = self.duplicate_tracks[0].album
        self.duration: int = self.duplicate_tracks[0].duration
        self.duplicate_count: int = len(self.duplicate_tracks)

    @property
    def duration_str(self) -> str:
        m, s = divmod(self.duration / 1000, 60)
        m = int(m)
        s = int(s)
        return f"{m}m{s}s"

    @property
    def has_conflicting_metadata(self) -> bool:
        """
        Compare the following metadata to see if there are conflicts:
          * Rating (userRating)
          * playCount (viewCount)
        Returns:

        """
        return self.play_counts_conflict or self.ratings_conflict

    @property
    def ratings_conflict(self) -> bool:
        conflicting_rating = False
        base_rating = self.duplicate_tracks[0].user_rating
        for track in self.duplicate_tracks:
            if base_rating != track.user_rating:
                conflicting_rating = True
        return conflicting_rating

    @property
    def play_counts_conflict(self) -> bool:
        conflicting_play_count = False
        base_play_count = self.duplicate_tracks[0].play_count
        for track in self.duplicate_tracks:
            if base_play_count != track.play_count:
                conflicting_play_count = True
        return conflicting_play_count

    def toggle_delete(self, index):
        self.duplicate_tracks[index].flagged_for_deletion = not self.duplicate_tracks[index].flagged_for_deletion

    def clear_deletes(self):
        for track in self.duplicate_tracks:
            track.flagged_for_deletion = False

    @property
    def has_track_to_delete(self) -> bool:
        for track in self.duplicate_tracks:
            if track.flagged_for_deletion:
                return True
        return False

    @property
    def all_tracks_selected(self):
        for track in self.duplicate_tracks:
            if not track.flagged_for_deletion:
                return False
        return True

    def flagged_delete_plex_tracks(self) -> List[Track]:
        flagged_tracks: List[Track] = []
        for track in self.duplicate_tracks:
            if track.flagged_for_deletion:
                flagged_tracks.append(track.track)
        return flagged_tracks

    @property
    def flagged_delete_jhs_tracks(self) -> List[JHSTrack]:
        flagged_tracks: List[JHSTrack] = []
        for track in self.duplicate_tracks:
            if track.flagged_for_deletion:
                flagged_tracks.append(track)
        return flagged_tracks


def console_log(message: str, level=logging.NOTSET):
    style: Optional[str] = None
    match level:
        case logging.INFO:
            style = "blue"
        case logging.WARN:
            style = "yellow"
        case logging.ERROR:
            style = "red"
    console.print(message, style=style)


def main():
    # Welcome message and info
    console.clear()
    panel = Panel.fit(
        "\n[green]Welcome to the [b]Plex Music Duplicate Song Remover[/b][/green]\n"
        "[i]This app will scan your music library searching for duplicates.\n",
        title="Plex Duplicate Song Finder"
    )
    console.print(panel)
    time.sleep(1)

    # set up the environment / and get the music library
    try:
        the_music_library: MusicSection = setup(console)
    except JHSException as jhs_exception:
        console.rule()
        console_log("\n" + str(jhs_exception), logging.ERROR)
        console_log("\nPlease delete the .env file and re-run to recreate it.\n", logging.INFO)
        exit(1)
    success_panel = Panel.fit(
        f"[green bold]Successfully connected to plex server library"
        f" \"{os.getenv('MUSIC_LIBRARY_NAME')}\"[/green bold]"
    )
    console.print(success_panel)
    console.print("")
    console.print("")
    songs_with_duplicates, num_tracks = duplicate_finder(the_music_library)
    time.sleep(1)
    if len(songs_with_duplicates) == 0:
        console.print("Congratulations! You have no duplicates!")
        exit(0)
    else:
        console.print("")
        panel = findings_panel(songs_with_duplicates, num_tracks)
        console.print(panel)

    console.print("\n[green]READY:[/green] Let's clean up the duplicates\nBut first, a couple of questions.\n")
    padded_content: Padding = Padding(
        "[u]Q: What is \"Safe Delete Mode\"?[/u]\n\n"
        "[i]Enabling Safe Mode Delete will add your duplicate tracks"
        f" to a playlist called \"{DEFAULT_DUPLICATE_PLAYLIST_NAME}\" [u]without deleting them[/u]."
        " After the script is complete, you can review them in plex for manual removal", (1, 3)
    )
    panel = Panel.fit(padded_content, title="[green]Safe Delete Mode[/green]")
    console.print(panel)
    console.print("")
    enable_safe_mode: bool = Confirm.ask("Would you like to enable [green]Safe Mode Delete[/green]?", default="y")
    if enable_safe_mode:
        console.print("\nExcellent, [b]Safe Mode Delete[/b] is now [green]ENABLED[/green]")
    else:
        console.print("\nOK, [b]Safe Mode Delete[/b] is [red]OFF[/red]")
    view_instructions: bool = Confirm.ask("\nView instructions?", default="y")
    console.print("")
    if view_instructions:
        panel = instructions_panel()
        console.print(panel)
    answer = Confirm.ask("Ready to continue?", default="y")
    if not answer:
        console.print("Exiting...")
        exit(0)
    choose_duplicates_to_delete(songs_with_duplicates)
    answer = Confirm.ask("Would you like to review the list of duplicates you've flagged for removal?", default="y")
    if answer:
        review_tracks: str = ""
        for duplicate_set in songs_with_duplicates:
            duplicate: JHSTrack
            for duplicate in duplicate_set.flagged_delete_jhs_tracks:
                review_tracks += f"*  \"{duplicate.title}\" - {duplicate.filepath}\n"
        console.print(Markdown(review_tracks))
    if enable_safe_mode:
        console.print(f"[green]Finished selecting songs, safe mode enabled,"
                      f" creating playlist: \"{DEFAULT_DUPLICATE_PLAYLIST_NAME}\"")
        add_duplicates_to_playlist(songs_with_duplicates, the_music_library)
        console.print(f"[green]Playlist created[/green]\nExiting...")
    else:
        console.print(f"Finished selecting songs, safe mode [red]disabled[/red]")
        answer = Confirm.ask("Continue with delete?", default="y")
        if not answer:
            console.print("Exiting...")
            exit(0)
        delete_duplicates(songs_with_duplicates)


def connect_to_plexserver() -> PlexServer:
    token = os.getenv("PLEX_TOKEN")
    # if we're using token based auth, then all we need is the base url
    if token:
        console.print("")
        console_log(":information: Found a Plex Token, trying to log in with that\n")
        plex_url = os.getenv("PLEX_URL")
        try:
            plex = PlexServer(plex_url, token)
        except Unauthorized:
            raise JHSException("Could not log into plex server with values in .env")
    else:
        from plexapi.myplex import MyPlexAccount
        username = os.getenv("PLEX_USERNAME")
        password = os.getenv("PLEX_PASSWORD")
        servername = os.getenv("PLEX_SERVERNAME")
        account = MyPlexAccount(username, password)
        try:
            plex = account.resource(servername).connect()  # returns a PlexServer instance
        except Unauthorized:
            raise JHSException("Could not log into plex server with values in .env")

    if not plex:
        raise JHSException("Could not log into plex server with values in .env")
    return plex


def duplicate_finder(music_library: MusicSection) -> (List[JHSDuplicateSet], int):
    """
    Args:
        music_library:
    Returns:
        a list of sets of tracks that have duplicate tracks.
    """
    return_sets: List[JHSDuplicateSet] = []
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
        tracks: List[JHSTrack]
        for key, tracks in unique_tracks.items():
            progress.update(task2, advance=1)
            if len(tracks) > 1:
                duplicate_set: JHSDuplicateSet = JHSDuplicateSet(tracks)
                return_sets.append(duplicate_set)
    return return_sets, count


def choose_duplicates_to_delete(duplicate_sets: List[JHSDuplicateSet]):
    count: int = len(duplicate_sets)
    track_set_index: int = 1
    while True:
        console.clear()
        track_set = duplicate_sets[track_set_index-1]
        choices: List[str] = []
        for i in range(1, len(track_set.duplicate_tracks) + 1):
            choices.append(str(i))
        track_num_prompt: str = "[" + ", ".join(choices) + "] "
        choices.append("n")
        choices.append("p")
        choices.append("d")
        control_prompt: str = "[magenta](n)[/magenta]ext, [magenta](p)[/magenta]revious, [magenta](d)[/magenta]one"
        panel = duplicate_panel(track_set, count, track_set_index)
        console.print(panel)
        if track_set.all_tracks_selected:
            warn = Panel("WARNING: You have chosen every track to be deleted", style="yellow")
            console.print(warn)
        track: JHSTrack
        answer = Prompt.ask(f"[blue]Choose a track number to toggle selection:[/blue]\n" +
                            f"Tracks: [magenta]{track_num_prompt}[/magenta] {control_prompt}",
                            choices=choices, default="n", show_choices=False)
        if answer == 'd':
            break
        elif answer == 'p':
            if track_set_index > 1:
                track_set_index -= 1
                continue
        elif answer == 'n':
            track_set_index += 1
            continue
        else:
            del_index: int = int(answer) - 1
            track_set.toggle_delete(del_index)
            continue


def delete_duplicates(duplicate_sets: List[JHSDuplicateSet]) -> None:
    delete_tracks: List[JHSTrack] = []
    for duplicate_set in duplicate_sets:
        delete_tracks += duplicate_set.flagged_delete_jhs_tracks
    for jhs_track in delete_tracks:
        console.print(f"Removing \"{jhs_track.title}\" - {jhs_track.filepath}\n")
        jhs_track.track.delete()


def add_duplicates_to_playlist(duplicate_sets: List[JHSDuplicateSet], music_library: MusicSection) -> None:
    delete_tracks: List[Track] = []
    for duplicate_set in duplicate_sets:
        delete_tracks += duplicate_set.flagged_delete_plex_tracks()
    music_library.createPlaylist(title=DEFAULT_DUPLICATE_PLAYLIST_NAME, items=delete_tracks)


# =======  View methods  ========
def instructions_panel() -> Panel:
    t1 = "[u]First the review process[/u]"
    m1 = Markdown(
        "*  Review the song details for each duplicate found\n"
        "*  Enter the version number(s) of the song you want to delete\n"
        "*  Enter (n)ext, (p)revious, (d)one"
    )
    t2 = "\n[u]Metadata cleanup[/u] - coming SOON!"
    m2 = Markdown(
        "* If there are metadata [star rating / play count]"
        " inconsistencies between the tracks, this will be your chance"
        " to correct them\n"
        "* Enter a 'star' rating [0-5]\n"
        "* Choose to combine the play count (y/n)\n\n"
    )
    t3 = "\n[u]Additional info[/u]"
    m3 = Markdown(
        "* Choosing 'd' to stop selecting, and you can choose what to do after that."
    )
    t4 = (
        "\n[yellow][b]NOTE:[/b] Songs will not be deleted until "
        "you confirm after all selections have been made."
    )
    content = Group(t1, m1, t2, m2, t3, m3, t4)
    padded_content: Padding = Padding(content, (1, 3))
    return Panel.fit(padded_content, title="Instructions")


def findings_panel(songs_with_duplicates, num_tracks) -> Panel:
    padded_content: Padding = Padding(
        f":heavy_check_mark: [b]Total Tracks Searched: [green]{num_tracks}[/green][/b]\n"
        f":heavy_check_mark: [b]Total Tracks with Duplicates: [green]{len(songs_with_duplicates)}[/green][/b]", (1, 3)
    )
    return Panel.fit(
        padded_content,
        title="[u][b]Finished![/b] Here's a report of our findings[/u]"
    )


def duplicate_panel(track_set: JHSDuplicateSet, count, index) -> Panel:
    tree = Tree(f"[black on white] {index}/{count} [/black on white]: [blue]Song Details[/blue]")
    tree.add(f"[green]Album:[/green] {track_set.album}")
    tree.add(f"[green]Artist:[/green] {track_set.artist}")
    tree.add(f"[green]Duration:[/green] {track_set.duration_str}")
    tree.add(f"[green]Duplicates ([i]including original[/i]):[/green] {track_set.duplicate_count}")
    if track_set.has_conflicting_metadata:
        tree.add(f"[yellow]Metadata: Tracks have some conflicting metadata[/yellow]")
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Ver", justify="center")
    table.add_column("Date Added")
    table.add_column("Plays", justify="center")
    table.add_column("Rating", justify="left")
    table.add_column("Codec", justify="left")
    table.add_column("Filepath", justify="left")
    track_version: int = 1
    for track in track_set.duplicate_tracks:
        style: Optional[Style] = None
        if track_set.has_track_to_delete:
            if track.flagged_for_deletion:
                style = Style(
                    strike=True,
                    dim=True)
            else:
                style = Style(
                    bold=True
                )
        table.add_row(
            str(track_version),
            track.added_at,
            track.play_count,
            track.star_rating,
            track.audio_codec,
            track.filepath,
            style=style
        )
        track_version += 1
    panel_group = Group(tree, table)
    box_panel = Panel(
        panel_group,
        title=f"[u]{track_set.title}[/u] -- [i]{track_set.artist}[/i]"
    )
    return box_panel


if __name__ == '__main__':
    main()
