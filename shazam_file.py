import asyncio
import sys
from typing import Optional

from plexapi.audio import Track
from plexapi.exceptions import NotFound
from plexapi.library import Library
from plexapi.playlist import Playlist
from rich.console import Console
from rich.prompt import Prompt, Confirm
from shazamio import Shazam, Serialize
from plex_utils import JHSException, setup, JHSTrack

console = Console()
MAX_PLAYLIST_SIZE = 100


def get_playlist(library: Library) -> Optional[Playlist]:
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
    library = setup(console)
    playlist = get_playlist(library)
    if playlist is None:
        console.print("No playlist chosen... Exiting")
        return
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
