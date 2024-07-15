""" Unit tests for GD Plex Track"""
from unittest.mock import MagicMock

# pylint: disable=missing-function-docstring
# pylint: disable=relative-beyond-top-level
from .gd_plex_track import GDPlexTrack


def test_durations_are_close():

    compare_duration = 320000
    mock_track = MagicMock(duration=320000)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.duration == 320000

    # test using default variance of 5000 ms
    assert gd_plex_track.durations_are_close(compare_duration)

    # check lower bounds
    mock_track = MagicMock(duration=315000)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.durations_are_close(compare_duration)
    # check upper bounds
    mock_track = MagicMock(duration=325000)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.durations_are_close(compare_duration)
    # check BELOW lower bounds
    mock_track = MagicMock(duration=314999)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.durations_are_close(compare_duration) is False
    # check upper bounds
    mock_track = MagicMock(duration=325001)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.durations_are_close(compare_duration) is False

    # check to make sure the 'variance' works
    mock_track = MagicMock(duration=320000)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.durations_are_close(322000, variance=1000) is False
    assert gd_plex_track.durations_are_close(322000, variance=1999) is False
    assert gd_plex_track.durations_are_close(322000, variance=2000) is True

def test_star_rating():
    mock_track = MagicMock(userRating=None)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == ''
    mock_track = MagicMock(userRating=2.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == '⭑'
    mock_track = MagicMock(userRating=4.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == '⭑⭑'
    mock_track = MagicMock(userRating=6.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == '⭑⭑⭑'
    mock_track = MagicMock(userRating=8.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == '⭑⭑⭑⭑'
    mock_track = MagicMock(userRating=10.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == '⭑⭑⭑⭑⭑'
    mock_track = MagicMock(userRating=0.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == ''

    # let's check some edge cases
    mock_track = MagicMock(userRating=1.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == ''
    mock_track = MagicMock(userRating=3.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.star_rating == '⭑'



def test_user_rating():
    mock_track = MagicMock(userRating=1.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.user_rating == 1.0

    mock_track = MagicMock(userRating=9.0)
    gd_plex_track = GDPlexTrack(mock_track)
    assert gd_plex_track.user_rating == 9.0
