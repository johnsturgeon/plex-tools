""" Model class for GD Plex Track """
from typing import Optional

from plexapi.audio import Track


# pylint: disable=too-many-instance-attributes
class GDPlexTrack:
    """ Model class for wrapping Plex library track """
    def __init__(self, track: Track):
        self.track = track
        self.flagged_for_deletion: bool = False
        self.title = self.track.title
        self.artist = self.track.grandparentTitle
        self.album = self.track.parentTitle
        self.duration: int = self.track.duration
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

    def durations_are_close(self, duration, variance=5000):
        """ durations are in milliseconds """
        return self.duration - variance <= duration <= self.duration + variance

    @property
    def star_rating(self) -> str:
        """
        Returns:
            The string of 'stars'
            (from none to five stars) representing the user_rating // 2

        Examples:
            * One star (user_rating of 2.0) ⭑
            * Two stars (user_rating of 4.0) ⭑⭑

        NOTES:
            * Star rating of None will return empty string
            * 'between' ratings (1.0, 3.0, 5.0, 7.0) will round down to the nearest integer
        """
        stars: str = "Unrated"
        if self.user_rating is not None:
            stars: str = ""
            rating: int = int(self.user_rating // 2)
            for _ in range(rating):
                stars += "⭑"
        return stars

    @property
    def user_rating(self) -> float:
        """
        User Rating is an API call, so we need to lazily init it and cache the result
        Returns:
            float: for the rating the user chose for the track from 0.0 - 10.0
        """
        if self._user_rating:
            return self._user_rating
        if self.track.userRating is not None:
            self._user_rating = float(self.track.userRating)
        else:
            self._user_rating = 0.0
        return self._user_rating
