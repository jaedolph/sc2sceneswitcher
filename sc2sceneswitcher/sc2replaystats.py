"""Functions used for generating post game info file that can be displayed on stream."""

import requests
from datetime import datetime
from tabulate import tabulate
from typing import Optional, Any
import logging

LOG = logging.getLogger("sc2sceneswitcher")

SC2RS_API = "https://api.sc2replaystats.com"
RACES = {
    "P": "Protoss",
    "T": "Terran",
    "Z": "Zerg",
}


class SC2ReplayStats:
    def __init__(self, authkey, last_replay_file):
        self.authkey = authkey
        self.last_replay_file = last_replay_file

        self.player_ids = self.get_player_ids()

    def get_player_ids(self):
        LOG.info("getting player ids associated with sc2replaystats account")
        players = requests.get(
            f"{SC2RS_API}/account/players", headers={"Authorization": self.authkey}
        )
        players.raise_for_status()

        player_ids = []
        for player in players.json():
            player_ids.append(player["player"]["players_id"])
        LOG.debug(f"player ids: {player_ids}")

        return player_ids

    def find_last_replay(self, last_game_start: datetime) -> Optional[dict[Any]]:
        """
        Use the Sc2ReplayStats API to find details on the replay of the previous game

        :returns: dictionary of replay details
        """
        last_replay = requests.get(
            f"{SC2RS_API}/account/last-replay", headers={"Authorization": self.authkey}
        ).json()
        last_replay_datetime = datetime.strptime(last_replay["replay_date"], "%Y-%m-%dT%H:%M:%S%z")
        if last_replay_datetime > last_game_start:
            LOG.debug(last_replay)
            return last_replay

        return None

    def process_last_replay(self, last_replay) -> None:
        """Prints last game details to a file that can be displayed in OBS.

        :param last_replay: dictionary of replay details from the Sc2ReplayStats API
        """
        message = ""
        message += "***** LAST GAME *****\n"
        players = []
        streamer_won = False

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
                    f"{is_streamer}",
                ]
            )
        message += tabulate(players)
        with open(self.last_replay_file, "w") as file:
            file.write(message)

        return streamer_won

    def clear_last_replay_info(self):
        with open(self.last_replay_file, "w") as file:
            file.write("")
