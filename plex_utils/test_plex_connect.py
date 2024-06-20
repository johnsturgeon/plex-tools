from unittest.mock import patch, Mock, call, MagicMock, PropertyMock

import pytest
from callee import InstanceOf, StartsWith, String, ShorterThan, EndsWith
from plexapi.exceptions import Unauthorized, NotFound
from rich.panel import Panel

from .plex_connect import load_or_create_dotenv, connect_to_plexserver, GDException, setup


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
        call(''),
        call(StartsWith(":information: Found a Plex Token"))
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


@patch('plex_utils.plex_connect.os.getenv')
@patch('plex_utils.plex_connect.Panel.fit')
@patch('plex_utils.plex_connect.connect_to_plexserver')
@patch('plex_utils.plex_connect.load_or_create_dotenv')
def test_setup(
        mock_load_or_create_dotenv,
        mock_connect_to_plexserver,
        mock_panel_fit,
        mock_os_getenv
):
    # first case under test is if the library is not loaded into the env
    mock_console = Mock()
    console_calls = [
        call(mock_panel_fit()),
        call(''),
        call('Log in [green]Successful[/green]')
    ]

    mock_os_getenv.return_value = "Music"
    setup(console=mock_console)
    mock_console.print.assert_has_calls(console_calls)
    mock_console.reset_mock()
    mock_os_getenv.return_value = None

    # remove the last element from the list
    console_calls.pop()
    with pytest.raises(GDException):
        setup(console=mock_console)
    mock_console.print.assert_has_calls(console_calls)


    # """
    # Returns:  The MusicSection specific plex library
    #           or throws GDException if it couldn't get it
    # """
    # load_or_create_dotenv(console)
    # plex = connect_to_plexserver(console)
    # success_panel = Panel.fit(
    #     f"[green bold]Successfully connected to plex server library"
    #     f" \"{os.getenv('MUSIC_LIBRARY_NAME')}\"[/green bold]"
    # )
    # console.print(success_panel)
    # console.print("")
    #
    # library_name: str = os.getenv("MUSIC_LIBRARY_NAME")
    # if not library_name:
    #     raise GDException("Could not find a library name in the .env file")
    # try:
    #     library: MusicSection = plex.library.section(library_name)
    # except NotFound:
    #     raise GDException(f"Could not find library \"{library_name}\" on your plexserver")
    # console.print("Log in [green]Successful[/green]")
    # return library
