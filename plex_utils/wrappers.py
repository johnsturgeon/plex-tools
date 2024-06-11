from typing import Optional
from plexapi.audio import Track


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
