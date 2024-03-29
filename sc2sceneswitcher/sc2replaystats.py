"""Functions used for generating post game info file that can be displayed on stream."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import requests
from tabulate import tabulate

from sc2sceneswitcher.config import Config
from sc2sceneswitcher.exceptions import SetupError

LOG = logging.getLogger("sc2sceneswitcher")

SC2RS_API = "https://api.sc2replaystats.com"
RACES = {
    "P": "Protoss",
    "T": "Terran",
    "Z": "Zerg",
}


class SC2ReplayStats:
    """Handles requests to the SC2ReplayStats API and writes post game stats to file.

    :param config: Config object containing application configuration
    """

    def __init__(self, config: Config) -> None:
        self.sc2rs_authkey = config.sc2rs_authkey
        self.last_game_file_path = config.last_game_file_path

        self.last_game_start = datetime.now(tz=timezone(offset=timedelta()))
        self.last_replay_found = True
        self.player_ids: list[int] = []

    def setup(self) -> None:
        """Perform initial setup."""
        LOG.info("Configuring sc2replaystats api connection...")
        # get player ids to check connection to the SC2ReplayStats API.
        try:
            self.player_ids = self.get_player_ids()
            if not self.player_ids:
                raise SetupError("Could not get list of player IDs from SC2ReplayStats")
        except requests.RequestException as exp:
            raise SetupError(f"failed to connect to SC2ReplayStats API: {exp}") from exp
        except (SetupError, ValueError) as exp:
            raise SetupError(exp) from exp

    def get_player_ids(self) -> list[int]:
        """Get list of player IDs from the sc2replaystats account.

        :returns: list of player ids
        """
        LOG.debug("Getting player ids associated with sc2replaystats account")
        players = requests.get(
            f"{SC2RS_API}/account/players",
            headers={"Authorization": self.sc2rs_authkey},
            timeout=5,
        )
        LOG.debug("Players: %s", players.text)
        players.raise_for_status()
        players_list = []
        # if account only has one player associated with it, put that in a list
        if not isinstance(players.json(), list):
            players_list = [players.json()]
        else:
            players_list = players.json()

        player_ids = []
        for player in players_list:
            LOG.debug("Player: %s", player["player"])
            player_id = int(player["player"]["players_id"])
            player_ids.append(player_id)

        LOG.debug("Player ids: %s", player_ids)

        return player_ids

    def find_last_replay(self) -> Optional[Any]:
        """Use the Sc2ReplayStats API to find details on the replay of the previous game.

        :returns: dictionary of replay details
        """

        try:
            req = requests.get(
                f"{SC2RS_API}/account/last-replay",
                headers={"Authorization": self.sc2rs_authkey},
                timeout=5,
            )
            req.raise_for_status()
            last_replay = req.json()
            LOG.debug("Last replay: %s", last_replay)
            last_replay_datetime = datetime.strptime(
                last_replay["replay_date"], "%Y-%m-%dT%H:%M:%S%z"
            )
            if last_replay_datetime > self.last_game_start:
                LOG.debug("Last replay was uploaded after the previous game started")
                return last_replay
            LOG.debug("Last replay was uploaded before the previous game started")
        except requests.RequestException as exp:
            LOG.error("failed to get replay from SC2ReplayStats: %s", exp)

        return None

    def process_last_replay(self, last_replay: dict[str, Any]) -> Optional[tuple[bool, str]]:
        """Prints last game details to a file that can be displayed in OBS.

        :param last_replay: dictionary of replay details from the Sc2ReplayStats API
        :return: tuple containing a boolean of if the streamer won and a replay info table e.g.
            ***** LAST GAME *****
            Alcyone LE | 0:00:01
            -  -------------  ------  -------  -----
            L  Jaedolph       Terran  4329MMR  700APM
            W  A.I. 1 (Easy)  Zerg    0MMR     83APM
            -  -------------  ------  -------  -----
        """
        message = ""
        message += "***** LAST GAME *****\n"
        players = []
        streamer_won = False

        try:
            game_length = int(last_replay["game_length"])
            map_name = last_replay["map_name"]
            # append game details
            message += f"{map_name} | {str(timedelta(seconds=game_length))}\n"

            for player in last_replay["players"]:
                is_streamer = False
                win_status = "L"
                if player["players_id"] in self.player_ids:
                    is_streamer = True
                if player["winner"] == 1:
                    win_status = "W"
                    if is_streamer:
                        streamer_won = True
                players.append(
                    [
                        win_status,
                        player["player"]["players_name"],
                        RACES[player["race"]],
                        f"{player['mmr']}MMR",
                        f"{player['apm']}APM",
                    ]
                )
            message += tabulate(players)
            LOG.debug("Replay info:\n%s", message)
            return streamer_won, message
        except (ValueError, KeyError) as exp:
            LOG.error("failed to parse replay from SC2ReplayStats: %s", exp)
            return None

    def search_for_last_replay(self) -> Optional[bool]:
        """Try to get the last replay.

        :return: True if the streamer won the game, False if they lost, None if the result is not
            known.
        """

        # get the last replay from the SC2ReplayStats API
        last_replay = self.find_last_replay()
        if last_replay is None:
            LOG.debug("Could not find last replay, it may still be uploading")
            return None

        # process the replay to check if the streamer won and get the "replay_info" text
        result = self.process_last_replay(last_replay)
        if result is None:
            return None

        streamer_won, replay_info = result

        # write replay info to file
        LOG.info("Writing replay info to %s", self.last_game_file_path)
        with open(self.last_game_file_path, "w", encoding="utf-8") as file:
            file.write(replay_info)

        # mark the last replay as "found" so we stop searching for it
        self.last_replay_found = True
        return streamer_won

    def clear_last_replay_info(self) -> None:
        """Reset the "last replay" file and last game start time."""

        self.last_game_start = datetime.now(tz=timezone(offset=timedelta()))
        with open(self.last_game_file_path, "w", encoding="utf-8") as file:
            file.write("")
