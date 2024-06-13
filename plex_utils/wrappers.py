from typing import Optional, Dict
import re

from shazamio.schemas.models import TrackInfo
from thefuzz import fuzz
from plexapi.audio import Track


class GDPlexTrack:
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
            self.filepath: str = "TIDAL"
        else:
            self.filepath: str = self.track.media[0].parts[0].file.strip()

        self.hash_val = str(f"{self.title}{self.artist}{self.album}{self.duration}")

    def __str__(self):
        return f"Title: {self.title}, Artist: {self.artist}, Album: {self.album}"

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

    def mapped_filepath(self, path_map: Dict[str, str]) -> str:
        """
        Replaces the remote root of the file with the local root given
        Args:
            path_map: Dictionary in the form of
               {
                  remote_root1: local_root1,
                  remote_root2: local_root2,
                  ...
               }

        Returns:
            the full local path the current track
        """
        new_path: str = self.filepath
        for key, value in path_map.items():
            if key in self.filepath:
                new_path = self.filepath.replace(key, value)
        return new_path

    @property
    def user_rating(self):
        if self._user_rating:
            return self._user_rating
        elif self.track.userRating is not None:
            self._user_rating = float(self.track.userRating)
        return self._user_rating


class GDShazamTrack:
    def __init__(self, track: TrackInfo):
        self.track = track
        self.album: str = self.track.sections[0].metadata[0].text
        self.artist: str = self.track.subtitle
        self.title: str = self.track.title

    def __str__(self):
        return f"Title: {self.title}, Artist: {self.artist}, Album: {self.album}"

    def title_match_confidence(self, gd_plex_track: GDPlexTrack, strip_feat: bool = True) -> float:
        shazam_title = self.title
        plex_title = gd_plex_track.title
        if strip_feat:
            shazam_title = re.sub(' \(feat.*\)', "", shazam_title)
            plex_title = re.sub(' \(feat.*\)', "", plex_title)
        return fuzz.ratio(shazam_title, plex_title)

    def album_match_confidence(self, gd_plex_track: GDPlexTrack) -> float:
        return fuzz.ratio(gd_plex_track.album, self.album)

    def artist_match_confidence(self, gd_plex_track: GDPlexTrack) -> float:
        return fuzz.ratio(gd_plex_track.artist, self.artist)

    def match_confidence(self, gd_plex_track: GDPlexTrack, ignore_album: bool = False) -> float:
        if ignore_album:
            return (
                    self.title_match_confidence(gd_plex_track) +
                    self.artist_match_confidence(gd_plex_track)
            ) / 2
        else:
            return (
                self.title_match_confidence(gd_plex_track) +
                self.artist_match_confidence(gd_plex_track) +
                self.album_match_confidence(gd_plex_track)
            ) / 3
