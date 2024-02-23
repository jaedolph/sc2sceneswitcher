"""Main program."""

import argparse
import asyncio
import logging
import re
import signal
import sys
import os
import traceback
from time import sleep
from types import FrameType
from typing import Optional

from twitchAPI.twitch import Prediction
from twitchAPI.type import TwitchAPIException

from sc2sceneswitcher import setup_config
from sc2sceneswitcher.config import DEFAULT_CONFIG_FILE_PATH, Config
from sc2sceneswitcher.exceptions import ConfigError, SetupError
from sc2sceneswitcher.predictions import Predictions
from sc2sceneswitcher.sc2 import GameResult, get_game_details, is_in_game
from sc2sceneswitcher.sc2replaystats import SC2ReplayStats
from sc2sceneswitcher.switcher import Switcher

LOG = logging.getLogger(__name__)

POLL_INTERVAL = 1
RETRY_INTERVAL = 5

def custom_exit(return_code: int) -> None:
    """Custom exit routine that ensures the console window doesn't close immediately on Windows.

    :param return_code: the return code to set on exit
    """
    if os.name == "nt":
        input("Press `ENTER` to exit")
    sys.exit(return_code)

class Runner:
    """Class that runs the scene switcher bot.

    :param config: Config object containing application configuration
    """

    def __init__(self, config: Config):
        self.in_game: Optional[bool] = False
        self.in_game_prev = False
        self.prediction: Optional[Prediction] = None
        self.switcher = Switcher(config)
        self.sc2rs = SC2ReplayStats(config)
        self.predictions = Predictions(config)
        # ensure graceful shutdown is handled on SIGINT and SIGTERM signals (only works for linux)
        try:
            signal.signal(signal.SIGINT, self.exit_gracefully)
            signal.signal(signal.SIGTERM, self.exit_gracefully)
        except NotImplementedError as exp:
            LOG.warning("Could not set up signal handlers: %s", exp)

    def exit_gracefully(self, signum: int, frame: Optional[FrameType]) -> None:
        """Ensure the program exits gracefully."""

        del signum, frame
        if self.switcher.obs_ws_client:
            LOG.debug("Disconnecting OBS websocket")
            self.switcher.obs_ws_client.disconnect()
        LOG.info("Exiting")
        custom_exit(0)

    async def start_prediction(self) -> None:
        """Start a new prediction for the outcome of the SC2 game."""
        game = get_game_details()
        if game is None:
            LOG.debug("Could not get game details, not starting prediction")
            return

        if game.is_replay:
            LOG.debug("Game is a replay, not starting prediction")
            return

        if game.result != GameResult.UNDECIDED:
            LOG.debug("Game is not in-progress, not starting prediction")
            return

        try:
            LOG.info("Starting prediction")
            self.prediction = await self.predictions.start_prediction()
        except TwitchAPIException as exp:
            LOG.error("Failed to start prediction: %s", exp)

    async def end_prediction(self) -> None:
        """End the current prediction."""

        if self.prediction is None:
            LOG.error("Can't end prediction because no prediction exists.")
            return

        game = get_game_details()
        if not game:
            LOG.error("Could not get game details, not ending prediction")
            return

        if game.result == GameResult.UNDECIDED:
            LOG.debug("Game is in progress, not ending prediction")
            return

        try:
            LOG.info("Ending prediction result=%s", game.result.name)
            await self.predictions.end_prediction(self.prediction, game.result)
            self.prediction = None
        except TwitchAPIException as exp:
            LOG.error("Failed to end prediction: %s", exp)

    async def poll(self) -> None:
        """Poll SC2 game status and run any required tasks."""

        # check if in game
        self.in_game = is_in_game()
        if self.in_game is None:
            # exit poll loop if we can't get the game state
            return

        # if we have entered a game
        if not self.in_game_prev and self.in_game:
            # switch to in game scene
            self.switcher.switch_to_in_game_scene()

            # ensure we don't display old game info when the game is finished
            self.sc2rs.clear_last_replay_info()

        # if we are in a game but a prediction is not started
        if self.in_game and self.prediction is None:
            await self.start_prediction()

        # if we have exited a game
        if self.in_game_prev and not self.in_game:
            # switch to out of game scene
            self.switcher.switch_to_out_of_game_scene()

            # need to check if a game has been played to avoid an edge case that happens when the
            # sc2 client is first started
            game = get_game_details()
            if game is not None:
                # toggle searching for the replay in Sc2ReplayStats
                self.sc2rs.last_replay_found = False
            else:
                LOG.debug("Skipping searching for sc2replaystats replay")

        # if we are out of game and there is an active prediction that hasn't been paid out
        if not self.in_game and self.prediction:
            # end the prediction
            await self.end_prediction()

        # if the last replay is not found from sc2replaystats, search for it
        if not self.sc2rs.last_replay_found:
            self.sc2rs.search_for_last_replay()

        self.in_game_prev = self.in_game

    async def run(self) -> None:
        """Main run loop for the program."""

        # setup each component of the scene switcher
        setup_complete = False
        while not setup_complete:
            try:
                self.switcher.setup()
                self.sc2rs.setup()
                await self.predictions.setup()
                setup_complete = True
            except SetupError as exp:
                LOG.error("Setup failed: %s", exp)
                LOG.error("Retrying in %ss", RETRY_INTERVAL)
                sleep(RETRY_INTERVAL)

        LOG.info("Setup complete, starting poll loop")
        while True:
            try:
                await self.poll()
            except Exception as exp:  # pylint: disable=broad-exception-caught
                if LOG.level == logging.DEBUG:
                    LOG.exception("Exception during poll loop: %s %s",type(exp).__name__, exp)
                else:
                    LOG.error("Exception during poll loop: %s %s",type(exp).__name__, exp)
            sleep(POLL_INTERVAL)


def load_config(config_file_path: str) -> Config:
    """Loads config file.

    :param config_file_path: path to the config file to read
    :return: Config object containing the configuration from the config file
    """

    try:
        LOG.info("Parsing config file...")
        config = Config(config_file_path)
        config.load_config()
    except ConfigError as exp:
        LOG.error("Invalid config: %s", exp)
        custom_exit(1)

    return config


def run_setup_config(config_file_path: str) -> None:
    """Run the configuration helper.

    :param config_file_path: path to the config file to write/edit
    """

    LOG.info("Starting configuration helper")
    try:
        asyncio.run(setup_config.configure(config_file_path))
    except KeyboardInterrupt:
        LOG.info("Exiting")
        custom_exit(0)
    except Exception as exp:  # pylint: disable=broad-exception-caught
        traceback.print_tb(exp.__traceback__)
        print(f"Fatal exception occurred: {exp}")
        custom_exit(1)
    custom_exit(0)


class NoPasswordFilter(logging.Filter):  # pylint: disable=too-few-public-methods
    """The obsws-python library logs the password in cleartext at "INFO" level.

    Add a filter to remove these logs.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter function to apply to each log message.

        :param record: log record
        :return: False if the log has a "password" field, False otherwise
        """
        if re.match(r".*password=.*", record.getMessage()):
            return False
        return True


def main() -> None:
    """Main entrypoint to the program."""

    parser = argparse.ArgumentParser(
        prog="sc2sceneswitcher",
        description="Auto switch OBS scenes and create channel point predictions when joining a "
        "StarCraft II game.",
    )
    parser.add_argument("--configure", action="store_true", help="run the configuration utility")
    parser.add_argument(
        "--config-file", default=DEFAULT_CONFIG_FILE_PATH, help="path to config file"
    )
    parser.add_argument("--debug", action="store_true", help="turn on debug logging")
    parser.add_argument("--log-file", help="path to log file")

    args = parser.parse_args()

    # configure logging
    log_level = logging.INFO
    log_handlers: list[logging.Handler] = [logging.StreamHandler()]
    if args.debug:
        LOG.info("Setting log level to DEBUG")
        log_level = logging.DEBUG

    if args.log_file:
        log_handlers.append(logging.FileHandler(args.log_file))

    # add a filter to not log the OBS websocket password if we are not debug logging.
    if not args.debug:
        for handler in log_handlers:
            handler.addFilter(NoPasswordFilter())

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(message)s",
        level=log_level,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=log_handlers,
    )

    # run config helper utility if required
    if args.configure:
        run_setup_config(args.config_file)
        return

    # load config file
    config = load_config(args.config_file)

    # run the scene switcher
    runner = Runner(config)

    asyncio.run(runner.run(), debug=False)


if __name__ == "__main__":
    asyncio.run(main())  # type: ignore
