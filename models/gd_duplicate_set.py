""" Model class for duplicate sets"""
from typing import List

from plexapi.audio import Track

from .gd_plex_track import  GDPlexTrack


class GDDuplicateSet:
    """ Represents a set of tracks that are considered duplicates """
    def __init__(self, duplicate_tracks: List[GDPlexTrack]):
        self.duplicate_tracks: List[GDPlexTrack] = duplicate_tracks
        self.title: str = self.duplicate_tracks[0].title
        self.artist: str = self.duplicate_tracks[0].artist
        self.album: str = self.duplicate_tracks[0].album
        self.duration: int = self.duplicate_tracks[0].duration
        self.duplicate_count: int = len(self.duplicate_tracks)

    @property
    def duration_str(self) -> str:
        """
        String representation of duration of the track
        Returns:
            formatted string in mm:ss
        Notes:
            track duration is 320000 (milliseconds)
            we / 1000 to get seconds
            and divmod the result by 60
        """
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
        return self._play_counts_conflict() or self._ratings_conflict()

    def _ratings_conflict(self) -> bool:
        """
        Compare the ratings of our tracks
        Returns:
            True if ratings are different, False otherwise
        """
        conflicting_rating = False
        base_rating = self.duplicate_tracks[0].user_rating
        for track in self.duplicate_tracks:
            if base_rating != track.user_rating:
                conflicting_rating = True
        return conflicting_rating

    def _play_counts_conflict(self) -> bool:
        """
        Compare the playCount of our tracks
        Returns:
            True if playCount is different, False otherwise
        """
        conflicting_play_count = False
        base_play_count = self.duplicate_tracks[0].play_count
        for track in self.duplicate_tracks:
            if base_play_count != track.play_count:
                conflicting_play_count = True
        return conflicting_play_count

    def toggle_delete(self, index):
        """ Toggles the deletion flag of a specific track """
        self.duplicate_tracks[index].flagged_for_deletion = \
            not self.duplicate_tracks[index].flagged_for_deletion


    @property
    def has_track_to_delete(self) -> bool:
        """
        Checks all tracks to determine if any are flagged for deletion
        Returns:
            True if there are tracks are flagged for deletion, False otherwise

        """
        for track in self.duplicate_tracks:
            if track.flagged_for_deletion:
                return True
        return False

    @property
    def all_tracks_selected(self):
        """
        Checks to determine if every track has been selected for deletion
        Returns:
            True if all tracks are flagged for deletion, False otherwise
        """
        for track in self.duplicate_tracks:
            if not track.flagged_for_deletion:
                return False
        return True

    def flagged_delete_plex_tracks(self) -> List[Track]:
        """
        Returns List[Track] where `Track` is a  plexapi.audio.Track object
        Returns:
            A list of all Plex tracks that are currently flagged for deletion
        """
        flagged_tracks: List[Track] = []
        for track in self.duplicate_tracks:
            if track.flagged_for_deletion:
                flagged_tracks.append(track.track)
        return flagged_tracks

    @property
    def flagged_delete_gd_plex_tracks(self) -> List[GDPlexTrack]:
        """
        Returns List[GDPlexTrack]
        Returns:
            A list of all GDPlexTrack tracks that are currently flagged for deletion
        """
        flagged_tracks: List[GDPlexTrack] = []
        for track in self.duplicate_tracks:
            if track.flagged_for_deletion:
                flagged_tracks.append(track)
        return flagged_tracks
