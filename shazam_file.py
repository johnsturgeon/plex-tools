"""
This script will use various methods for making sure that Plex has accurately
  identified the song.

If it is a mismatch, the user can then choose to update Plex's metadata
"""
import asyncio
import os

import requests
from typing import Optional, Dict, List, Set
import acoustid
import musicbrainzngs

from plexapi.audio import Track as PlexTrack
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
    """
    Returns: Returns a Rich Panel containing the instructions.
    """
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
    """
    Prompts the user to enter a playlist, and validates the playlist's existence
    Returns:
        Optional[Playlist]: Plex Playlist object, or None if none found
    """
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





def acoustid_match(apikey, gd_plex_track: GDPlexTrack, filepath) -> bool:
    """
    Plex gets its info from MusicBrainz, here we can use AcoustID to fingerprint the song,
      find the match in MusicBrainz and compare to Plex's metadata

    If there is a mismatch, then we have a problem.
    """
    title_match: bool = False
    artist_match: bool = False
    album_match: bool = False
    duration_match: bool = False
    results = acoustid.match(apikey, filepath, parse=False)
    for result in results['results']:
        score = result['score']
        recordings = result['recordings']
        for recording in recordings:
            rid = recording['id']
            title_match = title_match or recording['title'] == gd_plex_track.title
            duration_match  = duration_match or \
                gd_plex_track.durations_are_close(int(recording['duration']*1000))
            # We have a bit of information to see if we have enough of a match to continue
            #
            for artist_detail in recording['artists']:
                artist_match = artist_match or artist_detail['name'] == gd_plex_track.artist
                mb_result = musicbrainzngs.get_recording_by_id(rid, includes=['releases'])
                for album in mb_result['recording']['release-list']:
                    album_match = album_match or album['title'] == gd_plex_track.album
        return title_match and artist_match and album_match and duration_match


async def get_better_match(track: PlexTrack, root_folder_map) -> List:
    """
    Figures out if the plex metadata matches the actual song using several services for comparison
      1. Check the file against Shazam (quick)
      2. Check the 'stream' from Plex against Shazam
      3. Check AcoustID fingerprint / MusicBrainz song lookup

    Returns: Empty list if the song matched, otherwise a dictionary containing the song metadata
        Dict keys:
            'title', 'artists', 'album', 'source'
    """
    shazam = Shazam()
    different_metadata: List = []

    # First step would be the fastest, and that is if we have local access
    #    to the file, we can just send that to Shazam for quick recognition
    console.print("First let's try a quick Shazam search")
    gd_plex_track: GDPlexTrack = GDPlexTrack(track)
    filepath = gd_plex_track.mapped_filepath(root_folder_map)
    out = await shazam.recognize(filepath)
    gd_shazam_track: GDShazamTrack = GDShazamTrack(Serialize.track(out['track']))

    #  If we have a match, then we're done, otherwise we need to move to slower
    #    methods to make sure that it is indeed not a match.
    if gd_shazam_track.match_confidence(gd_plex_track) >= 95:
        console.print(f"Matched {gd_shazam_track}\n")
        return []

    different_metadata.append({
        'title': gd_shazam_track.title,
        'artist': gd_shazam_track.artist,
        'album': gd_shazam_track.album,
        'source': 'shazam_quick'
    })
    console.print("Quick search didn't match")
    console.print(track_details_table(gd_plex_track, gd_shazam_track))
    console.rule(title="Begin Deep Match")
    console.print("Trying to match based on streaming.  Patience,")
    #  Grab the Streaming URL from Plex and send that to Shazam for matching
    r = requests.get(track.getStreamURL())
    out = await shazam.recognize(data=r.content)
    serialized = Serialize.track(out['track'])
    gd_shazam_track = GDShazamTrack(serialized)
    console.rule(characters=" -")
    console.print("\nResults after deep match:")
    console.print(track_details_table(gd_plex_track, gd_shazam_track))

    #  If we have a match, then we're done
    if gd_shazam_track.match_confidence(gd_plex_track) >= 95:
        console.print(f"Matched! {gd_shazam_track}\n")
        return []

    different_metadata.append({
        'title': gd_shazam_track.title,
        'artist': gd_shazam_track.artist,
        'album': gd_shazam_track.album,
        'source': 'shazam_stream'
    })



    return different_metadata


async def main():
    library: MusicSection = setup(console)
    # At the moment, the matching is quite slow, so this gives the user a chance
    #   to specify exactly which songs they want to match
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
    track: PlexTrack
    for track in playlist.items():
        gd_plex_track: GDPlexTrack = GDPlexTrack(track)
        filepath = gd_plex_track.mapped_filepath(root_folder_map)
        apikey = os.getenv("ACOUSTID_API_KEY")
        mb_user = os.getenv("MB_USERNAME")
        mb_pass = os.getenv("MB_PASSWORD")
        musicbrainzngs.auth(mb_user, mb_pass)
        musicbrainzngs.set_useragent("GoshDarned Plex Tools", "0.1", "https://github.com/johnsturgeon/plex-tools")
        console.print("Checking Song:")
        console.print(gd_plex_track)
        if not acoustid_match(apikey, gd_plex_track, filepath):
            console.print("NO MATCH")
        else:
            console.print("MATCH")

        # better_metadata: List[Dict] = await get_better_match(track, root_folder_map)
        # if not better_metadata:
        #     console.print("Matched!\n")
        # else:
        #     for metadata in better_metadata:
        #         print(metadata)



if __name__ == '__main__':
    asyncio.run(main())
