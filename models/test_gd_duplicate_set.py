"""Test for GD Duplicate Set"""
from unittest.mock import Mock, MagicMock, PropertyMock, call, create_autospec

from plexapi.audio import Track

from models import GDDuplicateSet, GDPlexTrack


# pylint: disable=missing-function-docstring)
# pylint: disable=relative-beyond-top-level
def test_duration_str():
    mock_track = MagicMock(duration=320000)
    duplicate_set = GDDuplicateSet([mock_track, Mock()])
    assert duplicate_set.duration_str == "5m20s"


def test_has_conflicting_metadata():
    mock_track1 = MagicMock(user_rating=2.0, play_count=4)
    mock_track2 = MagicMock(user_rating=2.0, play_count=4)
    duplicate_set = GDDuplicateSet([mock_track1, mock_track2])
    assert duplicate_set.has_conflicting_metadata is False

    mock_track1 = MagicMock(user_rating=1.0, play_count=4)
    mock_track2 = MagicMock(user_rating=2.0, play_count=4)
    duplicate_set = GDDuplicateSet([mock_track1, mock_track2])
    assert duplicate_set.has_conflicting_metadata is True

    mock_track1 = MagicMock(user_rating=2.0, play_count=3)
    mock_track2 = MagicMock(user_rating=2.0, play_count=4)
    duplicate_set = GDDuplicateSet([mock_track1, mock_track2])
    assert duplicate_set.has_conflicting_metadata is True

    mock_track1 = MagicMock(user_rating=1.0, play_count=3)
    mock_track2 = MagicMock(user_rating=2.0, play_count=4)
    duplicate_set = GDDuplicateSet([mock_track1, mock_track2])
    assert duplicate_set.has_conflicting_metadata is True


def test_toggle_delete():
    mock_track0 = MagicMock()
    gd_plex_track0 = GDPlexTrack(mock_track0)
    mock_track1 = MagicMock()
    gd_plex_track1 = GDPlexTrack(mock_track1)
    duplicate_set = GDDuplicateSet([gd_plex_track0, gd_plex_track1])
    duplicate_set.toggle_delete(0)
    flagged_tracks = duplicate_set.flagged_delete_gd_plex_tracks
    assert flagged_tracks[0] == gd_plex_track0
    assert len(duplicate_set.flagged_delete_gd_plex_tracks) == 1
    duplicate_set.toggle_delete(0)
    assert len(duplicate_set.flagged_delete_gd_plex_tracks) == 0


def test_has_track_to_delete():
    mock_track0 = MagicMock()
    gd_plex_track0 = GDPlexTrack(mock_track0)
    mock_track1 = MagicMock()
    gd_plex_track1 = GDPlexTrack(mock_track1)
    duplicate_set = GDDuplicateSet([gd_plex_track0, gd_plex_track1])
    assert duplicate_set.has_track_to_delete is False
    duplicate_set.toggle_delete(0)
    assert duplicate_set.has_track_to_delete is True


def test_all_tracks_selected():
    mock_track0 = MagicMock()
    gd_plex_track0 = GDPlexTrack(mock_track0)
    mock_track1 = MagicMock()
    gd_plex_track1 = GDPlexTrack(mock_track1)
    duplicate_set = GDDuplicateSet([gd_plex_track0, gd_plex_track1])
    assert duplicate_set.all_tracks_selected is False
    duplicate_set.toggle_delete(0)
    assert duplicate_set.all_tracks_selected is False
    duplicate_set.toggle_delete(1)
    assert duplicate_set.all_tracks_selected is True


def test_flagged_delete_plex_tracks():
    mock_child_track1 = Mock(spec=Track)
    mock_track1 = Mock(flagged_for_deletion=False, track=mock_child_track1)
    mock_child_track2 = Mock(spec=Track)
    mock_track2 = Mock(flagged_for_deletion=False, track=mock_child_track2)
    mock_child_track3 = Mock(spec=Track)
    mock_track3 = Mock(flagged_for_deletion=True, track=mock_child_track3)
    mock_child_track4 = Mock(spec=Track)
    mock_track4 = Mock(flagged_for_deletion=True, track=mock_child_track4)
    track_list = [mock_child_track3, mock_child_track4]
    parent_list = [mock_track3, mock_track4]
    duplicate_set = GDDuplicateSet([mock_track1, mock_track2, mock_track3, mock_track4])

    # first we check the tracks
    flagged_track_list = duplicate_set.flagged_delete_plex_tracks
    assert track_list == flagged_track_list

    # now we check the plex tracks
    flagged_gd_tracks = duplicate_set.flagged_delete_gd_plex_tracks
    assert parent_list == flagged_gd_tracks

