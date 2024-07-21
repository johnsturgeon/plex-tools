"""
    Deduplex: De duplicate your plex library!  This script will scan your plex
    library for song duplicates and allow you to fix them.
"""
import sys
import time
from typing import List, Dict, Optional

from plexapi.audio import Track
from plexapi.library import MusicSection
from rich.padding import Padding
from rich.panel import Panel
from rich.progress import Progress
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.prompt import Prompt, Confirm
from rich.style import Style
from rich.table import Table
from rich.tree import Tree

from models import GDPlexTrack, GDDuplicateSet
from plex_utils import setup, GDException

console: Console = Console()
DEFAULT_DUPLICATE_PLAYLIST_NAME = "GoshDarned Duplicates"


def print_intro() -> None:
    """ Prints a brief introductory message """
    console.clear()
    panel = Panel.fit(
        "\n[green]Welcome to the [b]Plex Music Duplicate Song Remover[/b][/green]\n"
        "[i]This app will scan your music library searching for duplicates.\n",
        title="Plex Duplicate Song Finder"
    )
    console.print(panel)


# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
def main(  # noqa: C901
) -> None:
    """ Main entry point for the program """
    print_intro()
    # set up the environment / and get the music library
    try:
        the_music_library: MusicSection = setup(console)
    except GDException as gd_exception:
        console.rule()
        console.print("\n" + str(gd_exception))
        console.print("\nPlease delete the .env file and re-run to recreate it.\nExiting...")
        return
    console.print("")
    songs_with_duplicates, num_tracks = duplicate_finder(the_music_library)
    time.sleep(1)
    if len(songs_with_duplicates) == 0:
        console.print("Congratulations! You have no duplicates!")
        sys.exit(0)
    else:
        console.print("")
        panel = findings_panel(songs_with_duplicates, num_tracks)
        console.print(panel)

    console.print("\n[green]READY:[/green] Let's clean up the duplicates\n"
                  "But first, a couple of questions.\n")
    padded_content: Padding = Padding(
        "[u]Q: What is \"Safe Delete Mode\"?[/u]\n\n"
        "[i]Enabling Safe Mode Delete will add your duplicate tracks"
        f" to a playlist called \"{DEFAULT_DUPLICATE_PLAYLIST_NAME}\" [u]without deleting them[/u]."
        " After the script is complete, you can review them in plex for manual removal", (1, 3)
    )
    panel = Panel.fit(padded_content, title="[green]Safe Delete Mode[/green]")
    console.print(panel)
    console.print("")
    enable_safe_mode: bool = Confirm.ask(
        "Would you like to enable [green]Safe Mode Delete[/green]?",
        default="y"
    )
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
        sys.exit(0)
    choose_duplicates_to_delete(songs_with_duplicates)
    answer = Confirm.ask(
        "Would you like to review the list of duplicates you've flagged for removal?",
        default="y"
    )
    if answer:
        review_tracks: str = ""
        for duplicate_set in songs_with_duplicates:
            duplicate: GDPlexTrack
            for duplicate in duplicate_set.flagged_delete_gd_plex_tracks:
                review_tracks += f"*  \"{duplicate.title}\" - {duplicate.filepath}\n"
        console.print(Markdown(review_tracks))
    if enable_safe_mode:
        console.print(f"[green]Finished selecting songs, safe mode enabled,"
                      f" creating playlist: \"{DEFAULT_DUPLICATE_PLAYLIST_NAME}\"")
        add_duplicates_to_playlist(songs_with_duplicates, the_music_library)
        console.print("[green]Playlist created[/green]\nExiting...")
    else:
        console.print("Finished selecting songs, safe mode [red]disabled[/red]")
        answer = Confirm.ask("Continue with delete?", default="y")
        if not answer:
            console.print("Exiting...")
            sys.exit(0)
        delete_duplicates(songs_with_duplicates)


def duplicate_finder(music_library: MusicSection) -> (List[GDDuplicateSet], int):
    """
    Args:
        music_library:
    Returns:
        a list of sets of tracks that have duplicate tracks.
    """
    return_sets: List[GDDuplicateSet] = []
    all_tracks = music_library.searchTracks()
    count: int = len(all_tracks)
    unique_tracks: Dict[str, List[GDPlexTrack]] = {}
    with Progress() as progress:
        task1 = progress.add_task("Querying Plex Server", total=count)
        track: Track
        for track in all_tracks:
            progress.update(task1, advance=1)
            gd_track: GDPlexTrack = GDPlexTrack(track)
            if gd_track.hash_val not in unique_tracks:
                unique_tracks[gd_track.hash_val] = []
            unique_tracks[gd_track.hash_val].append(gd_track)
        task2 = progress.add_task("Searching results for duplicates", total=len(unique_tracks))
        tracks: List[GDPlexTrack]
        for _, tracks in unique_tracks.items():
            progress.update(task2, advance=1)
            if len(tracks) > 1:
                duplicate_set: GDDuplicateSet = GDDuplicateSet(tracks)
                return_sets.append(duplicate_set)
    return return_sets, count


def choose_duplicates_to_delete(duplicate_sets: List[GDDuplicateSet]) -> None:
    """
    Prompt the user for each duplicate set,
       getting input for which duplicates to select for deletion
    Args:
        duplicate_sets:
    """
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
        control_prompt: str = ("[magenta](n)[/magenta]ext, "
                               "[magenta](p)[/magenta]revious, "
                               "[magenta](d)[/magenta]one")
        panel = duplicate_panel(track_set, count, track_set_index)
        console.print(panel)
        if track_set.all_tracks_selected:
            warn = Panel("WARNING: You have chosen every track to be deleted", style="yellow")
            console.print(warn)
        answer = Prompt.ask("[blue]Choose a track number to toggle selection:[/blue]\n" +
                            f"Tracks: [magenta]{track_num_prompt}[/magenta] {control_prompt}",
                            choices=choices, default="n", show_choices=False)
        if answer == 'd':
            break
        if answer == 'p':
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


def delete_duplicates(duplicate_sets: List[GDDuplicateSet]) -> None:
    """
    Delete duplicate tracks from a list
    Args:
        duplicate_sets:
    """
    delete_tracks: List[GDPlexTrack] = []
    for duplicate_set in duplicate_sets:
        delete_tracks += duplicate_set.flagged_delete_gd_plex_tracks
    for gd_track in delete_tracks:
        console.print(f"Removing \"{gd_track.title}\" - {gd_track.filepath}\n")
        gd_track.track.delete()


def add_duplicates_to_playlist(
        duplicate_sets: List[GDDuplicateSet],
        music_library: MusicSection
) -> None:
    """
    Copies the tracks that are flagged to delete to a playlist
    Args:
        duplicate_sets:
        music_library:
    """
    delete_tracks: List[Track] = []
    for duplicate_set in duplicate_sets:
        delete_tracks += duplicate_set.flagged_delete_plex_tracks
    music_library.createPlaylist(title=DEFAULT_DUPLICATE_PLAYLIST_NAME, items=delete_tracks)


# =======  View methods  ========
def instructions_panel() -> Panel:
    """
    Instructions for the script
    Returns:
        rich.panel.Panel
    """
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
    """
    Findings for duplicate tracks detected
    Args:
        songs_with_duplicates:
        num_tracks:
    Returns:
        rich.panel.Pane
    """
    padded_content: Padding = Padding(
        f":heavy_check_mark: [b]Total Tracks Searched: "
        f"[green]{num_tracks}[/green][/b]\n"
        f":heavy_check_mark: [b]Total Tracks with Duplicates: "
        f"[green]{len(songs_with_duplicates)}[/green][/b]", (1, 3)
    )
    return Panel.fit(
        padded_content,
        title="[u][b]Finished![/b] Here's a report of our findings[/u]"
    )


def duplicate_panel(track_set: GDDuplicateSet, count, index) -> Panel:
    """ Panel for one song and all it's duplicate tracks"""
    tree = Tree(f"[black on white] {index}/{count} [/black on white]: [blue]Song Details[/blue]")
    tree.add(f"[green]Album:[/green] {track_set.album}")
    tree.add(f"[green]Artist:[/green] {track_set.artist}")
    tree.add(f"[green]Duration:[/green] {track_set.duration_str}")
    tree.add(f"[green]Duplicates ([i]including original[/i]):[/green] {track_set.duplicate_count}")
    if track_set.has_conflicting_metadata:
        tree.add("[yellow]Metadata: Tracks have some conflicting metadata[/yellow]")
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
