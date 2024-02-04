"""Config class used for storing/validating configuration."""

import configparser
import re
import os
import pathlib

DEFAULT_CONFIG_FILE_NAME = "sc2sceneswitcher.ini"
DEFAULT_CONFIG_FILE_PATH = str(pathlib.Path.home() / DEFAULT_CONFIG_FILE_NAME)

DEFAULT_LAST_GAME_FILE_NAME = "last_game.txt"
DEFAULT_LAST_GAME_FILE_PATH = str(pathlib.Path.home() / DEFAULT_LAST_GAME_FILE_NAME)


class ConfigError(Exception):
    """Custom exception thrown when the configuration is invalid."""


# pylint: disable=too-many-public-methods
class Config:
    """Stores and manages config.

    :param config_file_path: path to the config file to read/write
    """

    def __init__(self, config_file_path: str) -> None:
        """Initialize the Config."""
        self.config_file_path = config_file_path
        self.config = configparser.ConfigParser()

    def new_config(self) -> None:
        """Creates sections so new config can be created."""
        self.config.add_section("TWITCH")
        self.config.add_section("SC2_REPLAY_STATS")
        self.config.add_section("OBS")

    def load_config(self) -> None:
        """Creates sections so new config can be created."""
        if not os.path.isfile(self.config_file_path):
            raise ConfigError(f'could not open config file "{self.config_file_path}"')

        self.config.read(self.config_file_path)
        self.validate_config()

    def validate_sc2rs_section(self) -> None:
        """Validates the [SC2_REPLAY_STATS] section of the config."""
        try:
            assert self.config.has_section("SC2_REPLAY_STATS")
            assert self.is_non_empty_string(self.sc2rs_authkey)
            assert self.is_non_empty_string(self.last_game_file_path)
        except (configparser.Error, AssertionError, ValueError, KeyError) as exp:
            raise ConfigError(exp) from exp

    def validate_obs_section(self) -> None:
        """Validates the [OBS] section of the config."""
        try:
            assert self.config.has_section("OBS")
            assert isinstance(self.obs_websocket_port, int)
            assert self.is_non_empty_string(self.obs_websocket_password)
            assert self.is_non_empty_string(self.in_game_scene)
            assert self.is_non_empty_string(self.out_of_game_scene)
        except (configparser.Error, AssertionError, ValueError, KeyError) as exp:
            raise ConfigError(exp) from exp

    def is_non_empty_string(self, value):
        if not isinstance(value, str):
            return False
        if not value:
            return False
        if value.isspace():
            return False
        return True

    def validate_twitch_section(self) -> None:
        """Validates the [TWITCH] section of the config."""

        try:
            assert self.config.has_section("TWITCH")
            assert self.is_non_empty_string(self.client_id)
            assert self.is_non_empty_string(self.client_secret)
            assert self.is_non_empty_string(self.broadcaster_name)
            assert self.is_non_empty_string(self.auth_token)
            assert self.is_non_empty_string(self.refresh_token)
            assert self.is_non_empty_string(self.prediction_title)
            assert self.is_non_empty_string(self.prediction_win_option)
            assert self.is_non_empty_string(self.prediction_loss_option)
        except (configparser.Error, AssertionError, ValueError, KeyError) as exp:
            raise ConfigError(exp) from exp

    def validate_config(self) -> None:
        """Validates that the current config."""
        self.validate_obs_section()
        self.validate_sc2rs_section()
        self.validate_twitch_section()

    def write_config(self) -> None:
        """Writes current config to file."""
        self.validate_config()
        with open(self.config_file_path, "w", encoding="utf-8") as config_file:
            self.config.write(config_file)

    # pylint: disable=missing-function-docstring
    @property
    def sc2rs_authkey(self) -> str:
        return self.config["SC2_REPLAY_STATS"]["AUTH_KEY"]

    @sc2rs_authkey.setter
    def sc2rs_authkey(self, value: str) -> None:
        self.config["SC2_REPLAY_STATS"]["AUTH_KEY"] = value

    @property
    def last_game_file_path(self) -> str:
        return self.config["SC2_REPLAY_STATS"]["LAST_GAME_FILE_PATH"]

    @last_game_file_path.setter
    def last_game_file_path(self, value: str) -> None:
        self.config["SC2_REPLAY_STATS"]["LAST_GAME_FILE_PATH"] = value

    @property
    def auth_token(self) -> str:
        return self.config["TWITCH"]["AUTH_TOKEN"]

    @auth_token.setter
    def auth_token(self, value: str) -> None:
        self.config["TWITCH"]["AUTH_TOKEN"] = value

    @property
    def refresh_token(self) -> str:
        return self.config["TWITCH"]["REFRESH_TOKEN"]

    @refresh_token.setter
    def refresh_token(self, value: str) -> None:
        self.config["TWITCH"]["REFRESH_TOKEN"] = value

    @property
    def client_id(self) -> str:
        return self.config["TWITCH"]["CLIENT_ID"]

    @client_id.setter
    def client_id(self, value: str) -> None:
        self.config["TWITCH"]["CLIENT_ID"] = value

    @property
    def client_secret(self) -> str:
        return self.config["TWITCH"]["CLIENT_SECRET"]

    @client_secret.setter
    def client_secret(self, value: str) -> None:
        self.config["TWITCH"]["CLIENT_SECRET"] = value

    @property
    def broadcaster_name(self) -> str:
        return self.config["TWITCH"]["BROADCASTER_NAME"]

    @broadcaster_name.setter
    def broadcaster_name(self, value: str) -> None:
        self.config["TWITCH"]["BROADCASTER_NAME"] = value

    @property
    def prediction_title(self) -> str:
        return self.config["TWITCH"]["PREDICTION_TITLE"]

    @prediction_title.setter
    def prediction_title(self, value: str) -> None:
        self.config["TWITCH"]["PREDICTION_TITLE"] = value

    @property
    def prediction_win_option(self) -> str:
        return self.config["TWITCH"]["PREDICTION_WIN_OPTION"]

    @prediction_win_option.setter
    def prediction_win_option(self, value: str) -> None:
        self.config["TWITCH"]["PREDICTION_WIN_OPTION"] = value

    @property
    def prediction_loss_option(self) -> str:
        return self.config["TWITCH"]["PREDICTION_LOSS_OPTION"]

    @prediction_loss_option.setter
    def prediction_loss_option(self, value: str) -> None:
        self.config["TWITCH"]["PREDICTION_LOSS_OPTION"] = value

    @property
    def obs_websocket_port(self) -> int:
        return self.config.getint("OBS", "WEBSOCKET_SERVER_PORT")

    @obs_websocket_port.setter
    def obs_websocket_port(self, value: int) -> None:
        assert isinstance(value, int)
        self.config["OBS"]["WEBSOCKET_SERVER_PORT"] = str(value)

    @property
    def obs_websocket_password(self) -> str:
        return self.config["OBS"]["WEBSOCKET_SERVER_PASSWORD"]

    @obs_websocket_password.setter
    def obs_websocket_password(self, value: str) -> None:
        self.config["OBS"]["WEBSOCKET_SERVER_PASSWORD"] = value

    @property
    def in_game_scene(self) -> str:
        return self.config["OBS"]["IN_GAME_SCENE"]

    @in_game_scene.setter
    def in_game_scene(self, value: str) -> None:
        self.config["OBS"]["IN_GAME_SCENE"] = value

    @property
    def out_of_game_scene(self) -> str:
        return self.config["OBS"]["OUT_OF_GAME_SCENE"]

    @out_of_game_scene.setter
    def out_of_game_scene(self, value: str) -> None:
        self.config["OBS"]["OUT_OF_GAME_SCENE"] = value

    # pylint: disable=
