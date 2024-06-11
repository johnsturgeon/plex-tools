import asyncio

from rich.console import Console
from shazamio import Shazam, Serialize
from plex_utils import JHSException, setup
console = Console()


async def main():
    library = setup(console)
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
