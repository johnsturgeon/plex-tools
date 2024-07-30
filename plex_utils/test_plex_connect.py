""" Unit tests for plex_connect"""
from unittest.mock import patch, Mock, call, PropertyMock

# pylint: disable=missing-function-docstring
import pytest
from callee import StartsWith
from plexapi.exceptions import Unauthorized
# pylint: disable=relative-beyond-top-level
from .plex_connect import load_or_create_dotenv, connect_to_plexserver, GDException


@patch('plex_utils.plex_connect.load_dotenv')
def test_create_dotenv_existing_env(mock_load_dotenv):
    mock_load_dotenv.return_value = True
    mock_console = Mock()
    load_or_create_dotenv(console=mock_console)
    mock_console.print.assert_called_once_with(
        "\n:information: Found an existing .env file, checking it for valid login info"
    )


@patch('plex_utils.plex_connect._add_token_to_env_file')
@patch('plex_utils.plex_connect._add_music_library_to_env_file')
@patch('plex_utils.plex_connect._add_username_to_env_file')
@patch('plex_utils.plex_connect._get_plex_login_method')
@patch('plex_utils.plex_connect.load_dotenv')
def test_create_dotenv_no_env(
        mock_load_dotenv,
        mock_plex_login_method,
        mock_add_username_to_env_file,
        mock_add_music_library_to_env_file,
        mock_add_token_to_env_file,
):
    mock_load_dotenv.return_value = False
    mock_plex_login_method.return_value = "u"
    mock_console = Mock()
    calls = [
        call(StartsWith("\n:information: No .env")),
        call(StartsWith("\n:information: Login information saved"))
    ]
    load_or_create_dotenv(console=mock_console)
    mock_console.print.assert_has_calls(calls)
    mock_add_username_to_env_file.assert_called()
    mock_add_music_library_to_env_file.assert_called()
    mock_add_token_to_env_file.assert_not_called()
    # Test by token
    mock_plex_login_method.return_value = "t"

    mock_console.reset_mock()
    mock_add_username_to_env_file.reset_mock()
    mock_add_token_to_env_file.reset_mock()
    mock_add_music_library_to_env_file.reset_mock()

    load_or_create_dotenv(console=mock_console)
    mock_console.print.assert_has_calls(calls)
    mock_add_username_to_env_file.assert_not_called()
    mock_add_token_to_env_file.assert_called()
    mock_add_music_library_to_env_file.assert_called()


@patch('plex_utils.plex_connect.PlexServer')
@patch('plex_utils.plex_connect.os.getenv')
def test_connect_to_plex_server_with_token_1(
        mock_getenv,
        plex_server
):
    # First let's check with a valid URL
    env_return_vals = [
        "valid_token",
        "valid_url"
    ]
    mock_getenv.side_effect = env_return_vals
    mock_console = Mock()
    calls = [
        call(StartsWith("\n:information: Found a Plex Token"))
    ]
    connect_to_plexserver(console=mock_console)
    plex_server.assert_called_once_with("valid_url", "valid_token")
    mock_console.print.assert_has_calls(calls)


@patch('plex_utils.plex_connect.PlexServer')
@patch('plex_utils.plex_connect.os.getenv')
def test_connect_to_plex_server_with_token_2(
        mock_getenv,
        mock_plex_server
):
    # First let's check with a valid URL
    env_return_vals = [
        "valid_token",
        "valid_url"
    ]
    mock_getenv.side_effect = env_return_vals
    mock_console = Mock()
    # Now let's try when PlexServer throws an exception
    mock_plex_server.side_effect = Unauthorized
    with pytest.raises(GDException):
        connect_to_plexserver(console=mock_console)


@patch('plex_utils.plex_connect.MyPlexAccount')
@patch('plex_utils.plex_connect.os.getenv')
def test_connect_to_plex_server_with_passwd_1(
        mock_getenv,
        mock_plex_account
):
    env_return_vals = [
        None,
        "username",
        "password",
        "servername"
    ]
    mock_getenv.side_effect = env_return_vals
    mock_console = Mock()

    connect_to_plexserver(console=mock_console)
    mock_plex_account.assert_called_once_with("username", "password")


@patch('plex_utils.plex_connect.PlexServer')
@patch('plex_utils.plex_connect.os.getenv')
def test_connect_to_plex_server_with_passwd_2(
        mock_getenv,
        mock_plex_server
):
    env_return_vals = [
        None,
        "username",
        "password",
        "servername"
    ]
    mock_getenv.side_effect = env_return_vals
    mock_console = Mock()

    mock_plex_server.side_effect = Unauthorized
    with pytest.raises(GDException):
        connect_to_plexserver(console=mock_console)


@patch('plex_utils.plex_connect.MyPlexAccount', new_callable=PropertyMock)
@patch('plex_utils.plex_connect.os.getenv')
def test_connect_to_plex_server_with_passwd_3(
        mock_getenv,
        mock_plex_account
):
    env_return_vals = [
        None,
        "username",
        "password",
        "servername"
    ]
    mock_getenv.side_effect = env_return_vals
    mock_console = Mock()

    mock_plex_account.return_value = None
    with pytest.raises(GDException):
        connect_to_plexserver(console=mock_console)
