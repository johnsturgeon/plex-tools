import asyncio
import sys
from typing import Optional, Dict

from plexapi.audio import Track
from plexapi.exceptions import NotFound
from plexapi.library import Library, MusicSection
from plexapi.myplex import Section
from plexapi.playlist import Playlist
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.padding import Padding
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from shazamio import Shazam, Serialize
from plex_utils import JHSException, setup, JHSTrack

console = Console()
MAX_PLAYLIST_SIZE = 100


def get_root_folder_map(library: MusicSection) -> {}:
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


def get_playlist(library: MusicSection) -> Optional[Playlist]:
    not_found: bool = True
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
            done: bool = Confirm.ask("Quit, or retry?", choices=("q", "r"))
            if done:
                return None
            else:
                continue
        not_found = False
    return playlist


async def main():
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
    map_folders: bool = False
    if location == "Remote":
        map_folders = True
        root_folder_map: dict = get_root_folder_map(library)
    track: Track
    for track in playlist.items():
        a_track: JHSTrack = JHSTrack(track)
        print(f"{a_track.title}")
    shazam = Shazam()
    local_dir = '/Volumes/Media/'
    server_dir = '/media/'
    out = await shazam.recognize('/Volumes/Media/PlexMedia/Music/Stellar Exodus/Ephemeral/01 Ephemeral.flac')
    serialized = Serialize.track(data=out['track'])
    album: str = serialized.sections[0].metadata[0].text
    artist: str = serialized.subtitle
    title: str = serialized.title

    print(serialized)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
