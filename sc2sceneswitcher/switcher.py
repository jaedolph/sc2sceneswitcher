"""Handles switching OBS scenes."""

import logging
import json
from time import sleep
from typing import Any, Optional
import websocket

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
        self.obs_ws_client: Optional[obs.ReqClient] = None
        self.streamlabs_ws_client: Optional[websocket.WebSocket] = None

        # for streamlabs, the unique id of the scene must be used (not just the namef)
        self.streamlabs_in_game_scene_id: Optional[str] = None
        self.streamlabs_out_of_game_scene_id: Optional[str] = None

    def setup(self) -> None:
        """Setup connection to OBS websocket."""

        if self.config.switcher_websocket_type == "OBS":
            LOG.info("Configuring OBS connection...")
            try:
                self.connect_to_obs()
            except (ConnectionError, BrokenPipeError) as exp:
                raise SetupError(f"Could not connect to OBS websocket: {exp}") from exp
        if self.config.switcher_websocket_type == "STREAMLABS":
            LOG.info("Configuring Streamlabs Desktop websocket connection...")
            try:
                self.connect_to_streamlabs()
                LOG.info("Getting scene IDs from streamlabs...")
                self.streamlabs_in_game_scene_id = self._get_streamlabs_in_game_scene_id()
                LOG.debug("Streamlabs in game scene id: %s", self.streamlabs_in_game_scene_id)
                self.streamlabs_out_of_game_scene_id = self._get_streamlabs_out_of_game_scene_id()
                LOG.debug(
                    "Streamlabs out of game scene id: %s", self.streamlabs_out_of_game_scene_id
                )
            except ConnectionError as exp:
                raise SetupError(f"Could not connect to Streamlabs websocket: {exp}") from exp

    def connect_to_streamlabs(self) -> None:
        """Attempt to connect to Streamlabs websocket."""

        LOG.info("Connecting to Streamlabs API...")
        self.streamlabs_ws_client = websocket.WebSocket()
        self.streamlabs_ws_client.connect(
            f"ws://127.0.0.1:{self.config.switcher_websocket_port}/api/websocket", timeout=5
        )
        payload = {
            "jsonrpc": "2.0",
            "id": 8,
            "method": "auth",
            "params": {
                "resource": "TcpServerService",
                "args": [self.config.switcher_websocket_password],
            },
        }
        self.streamlabs_ws_client.send(json.dumps(payload))
        response = json.loads(self.streamlabs_ws_client.recv())

        LOG.debug("response: %s", response)

        LOG.info("Connected to Streamlabs API successfully")

    def reconnect_to_streamlabs(self) -> None:
        """Attempt to connect to Streamlabs websocket."""
        try:
            self.connect_to_streamlabs()
            sleep(1)
        except (ConnectionError, websocket.WebSocketException) as exp:
            LOG.error("Failed to reconnect to Streamlabs: %s", exp)

    def connect_to_obs(self) -> None:
        """Attempt to connect to OBS websocket."""

        LOG.info("Connecting to OBS websocket...")
        self.obs_ws_client = obs.ReqClient(
            host="localhost",
            port=self.config.switcher_websocket_port,
            password=self.config.switcher_websocket_password,
            timeout=3,
        )
        LOG.info("Connected to OBS websocket successfully")

    def reconnect_to_obs(self) -> None:
        """Attempt to reconnect to OBS websocket."""

        LOG.info("Attempting to reconnect to OBS...")
        try:
            self.connect_to_obs()
            sleep(1)
        except ConnectionError as exp:
            LOG.error("Failed to reconnect to OBS: %s", exp)

    def _get_streamlabs_scenes(self) -> list[dict[str, Any]]:
        """Get list of scenes from Streamlabs.

        :return: list of dictionaries containing scene information
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getScenes",
            "params": {"resource": "ScenesService"},
        }
        LOG.debug("Getting list of scenes from Streamlabs")
        assert self.streamlabs_ws_client is not None
        self.streamlabs_ws_client.send(json.dumps(payload))
        response = json.loads(self.streamlabs_ws_client.recv())
        LOG.debug("Response: %s", response)
        scenes = response["result"]

        return scenes

    def _get_streamlabs_in_game_scene_id(self) -> Optional[str]:
        """Get the unique ID of in-game scene from Streamlabs."""

        LOG.debug('Finding ID of in game scene "%s"', self.config.in_game_scene)
        scenes = self._get_streamlabs_scenes()
        for scene in scenes:
            if scene["name"] == self.config.in_game_scene:
                scene_id = scene["id"]
                LOG.debug("Found in game scene id: %s", scene_id)
                return scene_id
        LOG.error('Could not find id for in game scene "%s"', self.config.in_game_scene)
        return None

    def _get_streamlabs_out_of_game_scene_id(self) -> Optional[str]:
        """Get the unique ID of out-of-game scene from Streamlabs."""

        LOG.debug('Finding ID of out of game scene "%s"', self.config.in_game_scene)
        scenes = self._get_streamlabs_scenes()
        for scene in scenes:
            if scene["name"] == self.config.out_of_game_scene:
                scene_id = scene["id"]
                LOG.debug("Found out of game scene id: %s", scene_id)
                return scene_id
        LOG.error('Could not find id for out of game scene "%s"', self.config.out_of_game_scene)
        return None

    def _switch_streamlabs_scene(self, scene_id: str) -> None:
        """Switch to a specific scene in Streamlabs.

        :param scene_id: ID of the scene to switch to.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "makeSceneActive",
            "params": {
                "resource": "ScenesService",
                "args": [scene_id],
            },
        }
        LOG.debug("Switching to Streamlabs scene: %s", scene_id)
        assert self.streamlabs_ws_client is not None
        self.streamlabs_ws_client.send(json.dumps(payload))
        response = json.loads(self.streamlabs_ws_client.recv())
        LOG.debug("Response: %s", response)

    def switch_to_out_of_game_scene(self) -> None:
        """Switches to the configured out-of-game scene."""
        LOG.info("Switching to out of game scene")
        LOG.debug("Websocket type: %s", self.config.switcher_websocket_type)
        if self.config.switcher_websocket_type == "OBS":
            self._switch_to_out_of_game_scene_obs()
        if self.config.switcher_websocket_type == "STREAMLABS":
            self._switch_to_out_of_game_scene_streamlabs()

    def switch_to_in_game_scene(self) -> None:
        """Switches to the configured in-game scene."""
        LOG.info("Switching to in game scene")
        LOG.debug("Websocket type: %s", self.config.switcher_websocket_type)
        if self.config.switcher_websocket_type == "OBS":
            self._switch_to_in_game_scene_obs()
        if self.config.switcher_websocket_type == "STREAMLABS":
            self._switch_to_in_game_scene_streamlabs()

    def _switch_to_out_of_game_scene_streamlabs(self) -> None:
        """Switches to the configured out-of-game scene in Streamlabs."""
        retries = 0
        while retries <= RETRY_LIMIT:
            try:
                self._switch_streamlabs_scene(self.streamlabs_out_of_game_scene_id)
                LOG.info('Switched to scene "%s"', self.config.out_of_game_scene)
                break
            except (ConnectionError, websocket.WebSocketException) as exp:
                LOG.info("Failed to switch scene: %s", exp)
                if retries >= RETRY_LIMIT:
                    LOG.info("Reached retry limit")
                    break
                self.reconnect_to_streamlabs()
                retries += 1

    def _switch_to_in_game_scene_streamlabs(self) -> None:
        """Switches to the configured in-game scene in Streamlabs."""
        retries = 0
        while retries <= RETRY_LIMIT:
            try:
                self._switch_streamlabs_scene(self.streamlabs_in_game_scene_id)
                LOG.info('Switched to scene "%s"', self.config.in_game_scene)
                break
            except (ConnectionError, websocket.WebSocketException) as exp:
                LOG.info("Failed to switch scene: %s", exp)
                if retries >= RETRY_LIMIT:
                    LOG.info("Reached retry limit")
                    break
                self.reconnect_to_streamlabs()
                retries += 1

    def _switch_to_out_of_game_scene_obs(self) -> None:
        """Switches to the configured out-of-game scene in OBS."""
        retries = 0
        while retries <= RETRY_LIMIT:
            try:
                assert self.obs_ws_client is not None
                self.obs_ws_client.set_current_program_scene(self.config.out_of_game_scene)
                LOG.info('Switched to scene "%s"', self.config.out_of_game_scene)
                break
            except obs.error.OBSSDKError as exp:
                LOG.error("Failed to switch scene: %s", exp)
                break
            except (BrokenPipeError, AssertionError) as exp:
                LOG.info("Failed to switch scene: %s", exp)
                if retries >= RETRY_LIMIT:
                    LOG.info("Reached retry limit")
                    break
                self.reconnect_to_obs()
                retries += 1

    def _switch_to_in_game_scene_obs(self) -> None:
        """Switches to the configured in-game scene in OBS."""
        retries = 0
        while retries <= RETRY_LIMIT:
            try:
                assert self.obs_ws_client is not None
                self.obs_ws_client.set_current_program_scene(self.config.in_game_scene)
                LOG.info('Switched to scene "%s"', self.config.in_game_scene)
                break
            except obs.error.OBSSDKError as exp:
                LOG.error("Failed to switch scene: %s", exp)
                break
            except (BrokenPipeError, AssertionError) as exp:
                LOG.info("Failed to switch scene: %s", exp)
                if retries >= RETRY_LIMIT:
                    LOG.info("Reached retry limit")
                    break
                self.reconnect_to_obs()
                retries += 1
