"""Handles requests to the StarCraft II Client API."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import requests

LOG = logging.getLogger(__name__)


class GameResult(Enum):
    """Enum to store result of the SC2 game."""

    UNDECIDED = 0
    VICTORY = 1
    DEFEAT = 2
    TIE = 3


@dataclass
class Game:
    """Dataclass to store last game info."""

    # these are the only values relevant to the scene switcher bot
    result: GameResult
    is_replay: bool


def is_in_game() -> Optional[bool]:
    """Check if the SC2 client is in game.

    :returns: True if in game, False if not in game, None if unknown
    """

    try:
        req = requests.get("http://127.0.0.1:6119/ui", timeout=5)
        ui = req.json()
        LOG.debug(ui)
        active_screens = ui["activeScreens"]
        if active_screens and "ScreenLoading/ScreenLoading" not in active_screens:
            return False
        return True
    except requests.exceptions.RequestException as exp:
        LOG.error("Failed to check if in SC2 game, SC2 may not be running: %s", exp)
        return None


def get_game_details() -> Optional[Game]:
    """Get the details from the current or previous SC2 game.

    :return: info from the current SC2 game (if game is in progress) or last SC2 game (if game has
        completed). None if game info was not found.
    """
    try:
        req = requests.get("http://127.0.0.1:6119/game", timeout=5)
        req.raise_for_status()
        game_json = req.json()
        LOG.debug("game info: %s", game_json)

        # check if this is a replay
        is_replay = bool(game_json["isReplay"])

        # make sure there are players in the game
        # (there will be none if the user has just logged in to SC2)
        assert len(game_json["players"]) > 0

        # seems like the player is always the first result in the players list
        result_string = game_json["players"][0]["result"]

        # ensure game result is valid
        result = None
        if result_string == "Undecided":
            result = GameResult.UNDECIDED
        if result_string == "Victory":
            result = GameResult.VICTORY
        if result_string == "Defeat":
            result = GameResult.DEFEAT
        if result_string == "Tie":
            result = GameResult.TIE

        assert result is not None

        return Game(result=result, is_replay=is_replay)

    except (requests.exceptions.RequestException, KeyError, AssertionError) as exp:
        LOG.error("Could not check SC2 game details: %s", exp)
        return None
