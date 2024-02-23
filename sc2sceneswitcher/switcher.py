"""Handles switching OBS scenes."""

import logging
from time import sleep

import obsws_python as obs

from sc2sceneswitcher.config import Config
from sc2sceneswitcher.exceptions import SetupError

LOG = logging.getLogger(__name__)
RETRY_LIMIT = 1


class Switcher:
    """Handles switching OBS scenes.

    :param config: Config object containing application configuration
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self.obs_ws_client = None
        self.current_scene = None

    def setup(self) -> None:
        """Setup connection to OBS websocket."""

        LOG.info("Configuring OBS connection...")
        try:
            self.connect_to_obs()
        except (ConnectionRefusedError, BrokenPipeError) as exp:
            raise SetupError(f"Could not connect to OBS websocket: {exp}") from exp

    def connect_to_obs(self) -> None:
        """Attempt to connect to OBS websocket."""

        LOG.info("Connecting to OBS websocket...")
        self.obs_ws_client = obs.ReqClient(
            host="localhost",
            port=self.config.obs_websocket_port,
            password=self.config.obs_websocket_password,
            timeout=3,
        )
        LOG.info("Connected to OBS websocket successfully")

    def reconnect(self) -> None:
        """Attempt to reconnect to OBS websocket."""

        LOG.info("Attempting to reconnect to OBS...")
        try:
            self.connect_to_obs()
            sleep(1)
        except ConnectionRefusedError as exp:
            LOG.error("Failed to reconnect to OBS: %s", exp)

    def switch_to_out_of_game_scene(self) -> None:
        """Switches to the configured out-of-game scene in OBS."""
        retries = 0
        while retries < RETRY_LIMIT:
            LOG.info("Switching to out of game scene")
            try:
                assert self.obs_ws_client is not None
                self.obs_ws_client.set_current_program_scene(self.config.out_of_game_scene)
                break
            except obs.error.OBSSDKError as exp:
                LOG.error("Failed to switch scene: %s", exp)
                break
            except (BrokenPipeError, AssertionError) as exp:
                LOG.info("Failed to switch scene: %s", exp)
                self.reconnect()
                retries += 1

    def switch_to_in_game_scene(self) -> None:
        """Switches to the configured in-game scene in OBS."""
        retries = 0
        while retries < RETRY_LIMIT:
            LOG.info("Switching to in game scene")
            try:
                assert self.obs_ws_client is not None
                self.obs_ws_client.set_current_program_scene(self.config.in_game_scene)
                break
            except obs.error.OBSSDKError as exp:
                LOG.error("Failed to switch scene: %s", exp)
                break
            except (BrokenPipeError, AssertionError) as exp:
                LOG.info("Failed to switch scene: %s", exp)
                self.reconnect()
                retries += 1
