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
from sc2sceneswitcher.sc2 import get_game_details, is_in_game
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
        self.config = config
        self.in_game: Optional[bool] = False
        self.in_game_prev = False
        self.prediction: Optional[Prediction] = None
        self.switcher: Optional[Switcher] = None
        self.sc2rs: Optional[SC2ReplayStats] = None
        self.predictions: Optional[Predictions] = None
        self.streamer_won: Optional[bool] = None
        self.game_is_replay: Optional[bool] = None

        # ensure graceful shutdown is handled on SIGINT and SIGTERM signals (only works for linux)
        try:
            signal.signal(signal.SIGINT, self.exit_gracefully)
            signal.signal(signal.SIGTERM, self.exit_gracefully)
        except NotImplementedError as exp:
            LOG.warning("Could not set up signal handlers: %s", exp)

    def exit_gracefully(self, signum: int, frame: Optional[FrameType]) -> None:
        """Ensure the program exits gracefully."""

        del signum, frame
        if self.switcher is not None:
            if self.switcher.obs_ws_client:
                LOG.debug("Disconnecting OBS websocket")
                self.switcher.obs_ws_client.disconnect()
            if self.switcher.streamlabs_ws_client:
                LOG.debug("Disconnecting Streamlabs websocket")
                self.switcher.streamlabs_ws_client.close()
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

        if game.decided:
            LOG.debug("Game is not in-progress, not starting prediction")
            return

        try:
            LOG.info("Starting prediction")
            assert self.predictions is not None
            self.prediction = await self.predictions.start_prediction()
            # clear the last replay info so we get the right replay from sc2replaystats
            # for this prediction
            assert self.sc2rs is not None
            self.sc2rs.clear_last_replay_info()
        except TwitchAPIException as exp:
            LOG.error("Failed to start prediction: %s", exp)

    async def end_prediction(self) -> None:
        """End the current prediction."""

        if self.prediction is None:
            LOG.error("Can't end prediction because no prediction exists.")
            return

        if self.streamer_won is None:
            LOG.error("Can't end prediction because result is not known yet.")
            return

        try:
            result = "WIN" if self.streamer_won else "LOSS"
            LOG.info("Ending prediction, result=%s", result)
            assert self.predictions is not None
            await self.predictions.end_prediction(self.prediction, self.streamer_won)
            self.prediction = None
            # Set streamer_won to None to show the game has not been decided yet
            self.streamer_won = None
        except TwitchAPIException as exp:
            LOG.error("Failed to end prediction: %s", exp)

    async def on_game_enter(self) -> None:
        """Run tasks when the user has just entered a game."""
        # switch to in game scene
        if self.switcher:
            self.switcher.switch_to_in_game_scene()
        if not self.predictions and self.sc2rs:
            # if predictions are not enabled, we need to clear the last replay info when
            # the game starts rather than when the prediction starts.
            self.sc2rs.clear_last_replay_info()

        # on first entering a game, it will be unknown if this is a replay or not
        self.game_is_replay = None

    async def on_game_exit(self) -> None:
        """Run tasks when the user has just exited a game."""
        # switch to out of game scene
        if self.switcher:
            self.switcher.switch_to_out_of_game_scene()

        if self.sc2rs:
            if self.game_is_replay is None:
                # need to check if a game has been played to avoid an edge case that happens
                # when the sc2 client is first started
                LOG.debug(
                    "Skipping searching for sc2replaystats replay. "
                    "Cannot determine if last game was a replay or not."
                )
            if self.game_is_replay is False:
                # toggle searching for the replay in Sc2ReplayStats
                self.sc2rs.last_replay_found = False
            if self.game_is_replay is True:
                LOG.debug(
                    "Skipping searching for sc2replaystats replay. "
                    "Previous game was a replay so will not be re-uploaded."
                )

        if self.predictions and self.prediction:
            # lock the prediction on game exit so we can wait for a result from sc2replaystats
            # This will be required for games that are shorter than the prediction window.
            LOG.info("Locking prediction to wait for result from sc2replaystats.")
            await self.predictions.lock_prediction(self.prediction)

    async def on_in_game(self) -> None:
        """Run tasks when the user is in game."""

        # Check if in a replay
        if self.game_is_replay is None:
            LOG.debug("Checking if game is a replay...")
            game = get_game_details()
            if game:
                # If the game is showing as "decided", then the API is showing the previous game
                # not the current game. This will happen if the player hit "quit and rewind" or
                # watched a replay before this game.
                if not game.decided:
                    self.game_is_replay = game.is_replay
                    LOG.debug("Game is replay: %s", self.game_is_replay)
                else:
                    LOG.debug("Game is 'decided'. Data received is not for the current game.")
            else:
                LOG.debug("Could not get game details yet.")

        # if we are in a game, this is not a replay, and a prediction is not started, start one
        if self.predictions and self.prediction is None and self.game_is_replay is False:
            await self.start_prediction()

    async def on_out_of_game(self) -> None:
        """Run tasks when the user is out of game."""
        # currently not required

    async def on_every_loop(self) -> None:
        """Run tasks every poll loop."""

        if self.sc2rs:
            # if required, check if the replay of the previous game is available
            if not self.sc2rs.last_replay_found:
                self.streamer_won = self.sc2rs.search_for_last_replay()
                # once the result of the game is known, pay out the prediction
                if self.prediction and self.predictions and self.streamer_won is not None:
                    await self.end_prediction()

    async def poll(self) -> None:
        """Poll SC2 game status and run any required tasks."""

        # check if in game
        self.in_game = is_in_game(self.config.show_load_screen)
        if self.in_game is None:
            # exit poll loop if we can't get the game state
            return

        # tasks that must be run every loop
        await self.on_every_loop()

        # if we are currently in a game
        if self.in_game:
            await self.on_in_game()
        else:
            await self.on_out_of_game()

        # if we have entered a game
        if not self.in_game_prev and self.in_game:
            await self.on_game_enter()

        # if we have exited a game
        if self.in_game_prev and not self.in_game:
            await self.on_game_exit()

        self.in_game_prev = self.in_game

    async def run(self) -> None:
        """Main run loop for the program."""

        # setup each component of the scene switcher
        setup_complete = False
        while not setup_complete:
            try:
                # make sure SC2 has been started
                if is_in_game(self.config.show_load_screen) is None:
                    raise SetupError("SC2 client is not responding yet, it may not be running")

                # set up scene switcher
                if self.config.switcher_enabled:
                    self.switcher = Switcher(self.config)
                    self.switcher.setup()

                # set up SC2ReplayStats connection
                if self.config.sc2rs_enabled:
                    self.sc2rs = SC2ReplayStats(self.config)
                    self.sc2rs.setup()

                # set up Twitch API connection for predictions
                if self.config.twitch_enabled:
                    self.predictions = Predictions(self.config)
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
                    LOG.exception("Exception during poll loop: %s %s", type(exp).__name__, exp)
                else:
                    LOG.error("Exception during poll loop: %s %s", type(exp).__name__, exp)
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
        print(f"Fatal exception occurred: {type(exp).__name__} {exp}")
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


def run() -> None:
    """Run the program."""

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
        log_handlers.append(logging.FileHandler(args.log_file, encoding="utf8"))

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


def main() -> None:
    """Main entrypoint to the program."""

    try:
        run()
    except Exception as exp:  # pylint: disable=broad-exception-caught
        traceback.print_tb(exp.__traceback__)
        print(f"Fatal exception occurred: {type(exp).__name__} - {exp}")
        custom_exit(1)


if __name__ == "__main__":
    asyncio.run(main())  # type: ignore
