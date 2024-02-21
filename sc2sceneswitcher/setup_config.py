"""Helper program to write config file."""

from pwinput import pwinput
from twitchAPI.oauth import UserAuthenticator
from twitchAPI.twitch import Twitch
from twitchAPI.type import AuthScope, TwitchAPIException

from sc2sceneswitcher.config import DEFAULT_LAST_GAME_FILE_PATH, Config
from sc2sceneswitcher.exceptions import ConfigError

TARGET_SCOPE = [AuthScope.CHANNEL_READ_PREDICTIONS, AuthScope.CHANNEL_MANAGE_PREDICTIONS]


def input_bool(prompt: str) -> bool:
    """Wrapper around the input function that can be used for boolean values. Repeats the prompt
    until a valid yes/no answer is added.

    :param prompt: input prompt to show the user
    :return: true if the user enters yes, false if they enter no
    """
    return_val = None
    while return_val is None:
        input_string = input(prompt)
        if input_string.lower().startswith("y"):
            return_val = True
        elif input_string.lower().startswith("n"):
            return_val = False
        else:
            print("Please enter 'yes' or 'no'")
            return_val = None

    return return_val


def configure_twitch(config: Config) -> Config:
    """Configure twitch application settings.

    :param config: Config object to update
    :return: updated Config object
    """

    print(
        "1. Create a new application at: https://dev.twitch.tv/console/apps/create\n"
        '2. Set "Name" to whatever you want e.g. "sc2sceneswitcher"\n'
        '3. Add an "OAuth Redirect URL" to http://localhost:17563\n'
        '4. Set "Category" to "Application Integration"\n'
        '5. Set "Client" to "Confidential"\n'
        '6. Click the "I\'m not a robot" verification and click "Create"\n'
        '7. Click "manage" on the application you have created'
    )
    input("\nPress `ENTER` when complete.")
    print("\n" * 5)
    config.client_id = input("Copy and paste the 'Client ID' here: ")
    config.client_secret = pwinput("Click 'New Secret' and paste the secret here: ")
    print("\n" * 5)
    config.broadcaster_name = input("\nWhat is the name of your twitch channel? e.g. 'jaedolph': ")
    print("\n" * 5)

    return config


def configure_sc2rs(config: Config) -> Config:
    """Configure SC2ReplayStats settings.

    :param config: Config object to update
    :return: updated Config object
    """

    print(
        "1. Sign in to https://sc2replaystats.com\n"
        '2. Navigate to "My Account" -> "Settings" -> "API Access"\n'
        '3. Copy your "Authorization Key"\n'
    )
    input("\nPress `ENTER` when complete.")
    print("\n" * 5)
    config.sc2rs_authkey = pwinput('Copy and paste the "Authorization Key" here: ')
    last_game_file_path = input(
        "\nWhere would you like the post game stats to be saved? "
        f"(leave blank to use '{DEFAULT_LAST_GAME_FILE_PATH}'): "
    )
    if not last_game_file_path:
        last_game_file_path = DEFAULT_LAST_GAME_FILE_PATH
    config.last_game_file_path = last_game_file_path
    print("\n" * 5)

    return config


def configure_obs(config: Config) -> Config:
    """Configure OBS settings.

    :param config: Config object to update
    :return: updated Config object
    """

    print(
        '1. Open OBS and go to "Tools" -> "WebSocket Server Settings"\n'
        '2. Change "Server Port" and "Server Password" if required\n'
        '3. Click "Show Connect Info"'
    )
    input("\nPress `ENTER` when complete.")
    print("\n" * 5)
    obs_websocket_port = None
    while obs_websocket_port is None:
        obs_websocket_port = input('\nCopy and paste the "Server Port" here: ')
        try:
            config.obs_websocket_port = int(obs_websocket_port)
        except ValueError:
            print("ERROR: please enter a valid port number")
            obs_websocket_port = None
    config.obs_websocket_password = pwinput('Copy and paste the "Server Password" here')
    print("\n" * 5)
    config.in_game_scene = input(
        'What is the name of your "in game" OBS scene? e.g. "starcraft2": '
    )
    config.out_of_game_scene = input(
        'What is the name of your "out of game" OBS scene? e.g. "camera": '
    )
    print("\n" * 5)
    return config


async def authorize_twitch(config: Config) -> tuple[Twitch, Config]:
    """Configure twitch API authorization.

    :param config: Config object to update
    :return: initialized Twitch object and updated Config object
    """

    print("\nYou must authorize the application to manage predictions.")
    input("\nPress `ENTER` to open a new window to authorize the application.")

    # create TwitchAPI object
    twitch = await Twitch(config.client_id, config.client_secret)
    await twitch.authenticate_app([])
    auth = UserAuthenticator(twitch, TARGET_SCOPE, force_verify=True)
    auth.document = """<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>sc2sceneswitcher authorization</title>
        </head>
        <body>
            <h1>Successfully authorized application</h1>
        Please close this page and return to the setup utility.
        </body>
    </html>"""
    config.auth_token, config.refresh_token = await auth.authenticate()

    await twitch.set_user_authentication(config.auth_token, TARGET_SCOPE, config.refresh_token)

    return twitch, config


async def configure_predictions(config: Config) -> Config:
    """Configure channel point predictions.

    :param config: Config object to update
    :return: updated Config object
    """

    prediction_title = input(
        "\nWhat would you like the title of predictions to be? "
        "(leave blank to use 'Streamer win?'): "
    )
    if not prediction_title:
        prediction_title = "Streamer win?"
    prediction_win_option = input(
        "\nWhat would call the option for a win? (leave blank to use 'YES'): "
    )
    if not prediction_win_option:
        prediction_win_option = "YES"

    prediction_loss_option = input(
        "\nWhat would call the option for a loss? (leave blank to use 'NO'): "
    )
    if not prediction_loss_option:
        prediction_loss_option = "NO"

    config.prediction_title = prediction_title
    config.prediction_win_option = prediction_win_option
    config.prediction_loss_option = prediction_loss_option

    return config


# pylint: disable=too-many-statements,too-many-branches
async def configure(config_file_path: str) -> None:
    """Utility that prompts user for settings to configure the scene switcher."""

    config = Config(config_file_path)
    config.new_config()

    print("\n⚠⚠⚠⚠⚠ WARNING: DO NOT SHOW THE FOLLOWING ON STREAM. ⚠⚠⚠⚠⚠" * 10)
    input("\nPress `ENTER` if this is not showing on stream.")

    print("checking current config...")
    config_valid = False
    try:
        config.load_config()
        config_valid = True
    except ConfigError:
        print("config is currently not valid")
        config_valid = False

    print("\n" * 5)
    print("OBS SETUP")
    print("\n--------------------------")
    obs_config_valid = False
    if config_valid:
        obs_config_valid = not input_bool(
            "OBS configuration is valid, would you like to update it? (yes/no): "
        )
    while not obs_config_valid:
        config = configure_obs(config)
        try:
            config.validate_obs_section()
            obs_config_valid = True
        except ConfigError as exception:
            print(f"\nERROR: invalid config {exception}\n")
            obs_config_valid = False

    print("\n" * 5)
    print("SC2REPLAYSTATS SETUP")
    print("\n--------------------------")
    sc2rs_config_valid = False
    if config_valid:
        sc2rs_config_valid = not input_bool(
            "Sc2ReplayStats configuration is valid, would you like to update it? (yes/no): "
        )
    while not sc2rs_config_valid:
        config = configure_sc2rs(config)
        try:
            config.validate_sc2rs_section()
            sc2rs_config_valid = True
        except ConfigError as exception:
            print(f"\nERROR: invalid config {exception}\n")
            sc2rs_config_valid = False

    print("\n" * 5)
    print("TWITCH INTEGRATION SETUP")
    print("\n--------------------------")

    twitch_config_valid = False
    if config_valid:
        twitch_config_valid = not input_bool(
            "Twitch configuration is valid, would you like to update it? (yes/no): "
        )
    while not twitch_config_valid:
        config = configure_twitch(config)
        try:
            _, config = await authorize_twitch(config)
        except TwitchAPIException as exception:
            print(f"\nERROR: could not configure Twitch API authorization: {exception}\n")
            continue

        print("\n" * 5)
        print("PREDICTIONS SETUP")
        print("\n--------------------------")
        config = await configure_predictions(config)
        try:
            config.validate_twitch_section()
            twitch_config_valid = True
        except ConfigError as exception:
            print(f"\nERROR: invalid config {exception}\n")
            twitch_config_valid = False

    print("\n" * 5)
    print(f"Writing config file to {config.config_file_path}...")
    config.write_config()
    print("CONFIGURATION COMPLETE")


# pylint: disable=
