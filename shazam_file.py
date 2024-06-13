import asyncio

import requests
from typing import Optional, Dict

from plexapi.audio import Track
from plexapi.exceptions import NotFound
from plexapi.library import MusicSection
from plexapi.playlist import Playlist
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.table import Table
from shazamio import Shazam, Serialize
from plex_utils import setup, GDPlexTrack, GDShazamTrack

console = Console()
MAX_PLAYLIST_SIZE = 100


def get_root_folder_map(library: MusicSection) -> Dict[str, str]:
    folder_map: Dict[str, str] = {}
    for remote_location in library.locations:
        local_location = Prompt.ask(f"Enter your local folder that maps to {remote_location}")
        folder_map[remote_location] = local_location
    return folder_map


def instructions_panel() -> Panel:
    t1 = "[u]Pre-requisites[/u]"
    m1 = Markdown(
        "* Filesystem access to your plex library files to "
        "scan the audio signature of the file.  \nTo do this you must do one of the following:\n"
        "   1. Mount your Plex Media folder --or--\n"
        "   2. Run the script directly on your Plex server.\n"
        "* Optional: Write access to the Plex Media files (if you want to 'move' the files with new metadata)"
    )
    content = Group(t1, m1)
    padded_content: Padding = Padding(content, (1, 3))
    return Panel.fit(padded_content, title="Instructions")

def track_details_table(gd_plex_track: GDPlexTrack, gd_shazam_track: GDShazamTrack) -> Table:
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Source", justify="left")
    table.add_column("Artist", justify="left")
    table.add_column("Title", justify="left")
    table.add_column("Album", justify="left")
    table.add_row(
        "Plex",
        gd_plex_track.artist,
        gd_plex_track.title,
        gd_plex_track.album,
    )
    table.add_row(
        "Shazam",
        gd_shazam_track.artist,
        gd_shazam_track.title,
        gd_shazam_track.album,
    )
    return table


def get_playlist(library: MusicSection) -> Optional[Playlist]:
    not_found: bool = True
    playlist: Optional[Playlist] = None
    while not_found:
        answer: str = Prompt.ask("Please enter a playlist name")
        try:
            playlist = library.playlist(answer)
        except NotFound:
            console.print(f"Playlist [blue]{answer} [red]not found[/red]")
            continue
        if len(playlist.items()) > MAX_PLAYLIST_SIZE:
            console.print(
                f"Playlist [blue]{answer} [red]too large[/red]\n"
                f"Please limit the query to 100 tracks at a time."
            )
            done: bool = Confirm.ask("Quit, or retry?", choices=["q", "r"])
            if done:
                return None
            else:
                continue
        not_found = False
    return playlist


async def main():
    shazam = Shazam()
    library: MusicSection = setup(console)
    playlist = get_playlist(library)
    if playlist is None:
        console.print("No playlist chosen... Exiting")
        return
    instructions = instructions_panel()
    console.print(instructions)
    location: str = Confirm.ask(
        "Where are you running this script?", choices=["Remote", "Direct"], default="Remote"
    )
    root_folder_map: Dict[str, str] = {}
    if location == "Remote":
        root_folder_map = get_root_folder_map(library)
    track: Track
    for track in playlist.items():
        console.print("First let's try a quick Shazam search")
        gd_plex_track: GDPlexTrack = GDPlexTrack(track)
        out = await shazam.recognize(gd_plex_track.mapped_filepath(root_folder_map))
        gd_shazam_track: GDShazamTrack = GDShazamTrack(Serialize.track(out['track']))
        if gd_shazam_track.match_confidence(gd_plex_track) >= 95:
            console.print(f"Matched! {gd_shazam_track}\n")
            continue
        console.print("Quick search didn't match")
        console.print(track_details_table(gd_plex_track, gd_shazam_track))
        console.rule(title="Begin Deep Match")
        console.print("Trying to match based on streaming.  Patience,")
        url = track.getStreamURL()
        r = requests.get(url)
        out = await shazam.recognize(data=r.content)
        serialized = Serialize.track(out['track'])
        gd_shazam_track = GDShazamTrack(serialized)
        console.rule(characters=" -")
        console.print("\nResults after deep match:")
        console.print(track_details_table(gd_plex_track, gd_shazam_track))
        if gd_shazam_track.match_confidence(gd_plex_track) >= 95:
            console.print(f"Matched! {gd_shazam_track}\n")
        else:
            console.print("NO MATCH (GO DEEPER)")
            console.print("This time let's advance to halfway through the song")
            half_way: int = (gd_plex_track.duration // 1000) // 2
            url = url + "&offset=" + str(half_way)
            console.print(url)
            r = requests.get(url)
            out = await shazam.recognize(data=r.content)
            serialized = Serialize.track(out['track'])
            gd_shazam_track = GDShazamTrack(serialized)
            console.print("\nResults after DEEPER match:")
            console.print(track_details_table(gd_plex_track, gd_shazam_track))
            if gd_shazam_track.match_confidence(gd_plex_track) >= 95:
                console.print(f"FINALLY!!!!Matched! {gd_shazam_track}\n")
            else:
                console.print("NO MATCH (GIVE UP)")

        console.rule(title="End Find Match")
    return


if __name__ == '__main__':
    asyncio.run(main())
