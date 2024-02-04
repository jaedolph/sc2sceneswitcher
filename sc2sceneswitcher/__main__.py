import obsws_python as obs

from time import sleep
from datetime import datetime, timezone, timedelta
import requests

import asyncio
import argparse
import logging
import sys
import traceback

from sc2sceneswitcher.sc2replaystats import SC2ReplayStats
from sc2sceneswitcher.predictions import Predictions
from sc2sceneswitcher.config import Config, ConfigError, DEFAULT_CONFIG_FILE_PATH
from sc2sceneswitcher import setup_config

LOG = logging.getLogger("sc2sceneswitcher")


def is_in_game():
    """
    Check if the SC2 client is in game.

    :returns: True if in game, False if not in game
    """
    req = requests.get("http://127.0.0.1:6119/ui", timeout=5)
    ui = req.json()
    LOG.debug(ui)
    active_screens = ui["activeScreens"]
    if active_screens and "ScreenLoading/ScreenLoading" not in active_screens:
        return False
    return True


def get_game_details():
    req = requests.get("http://127.0.0.1:6119/game", timeout=5)
    req.raise_for_status()
    game = req.json()
    LOG.debug(game)
    return game


def connect_to_obs(config: Config):
    return obs.ReqClient(
        host="localhost",
        port=config.obs_websocket_port,
        password=config.obs_websocket_password,
        timeout=3,
    )


async def run(config: Config):
    LOG.info("connecting to OBS websocket...")
    try:
        obs_ws_client = connect_to_obs(config)
    except ConnectionRefusedError as exp:
        LOG.error("Could not connect to OBS websocket: %s", exp)
        sys.exit(1)

    LOG.info("configuring sc2replaystats api connection...")
    sc2rs = SC2ReplayStats(config.sc2rs_authkey, config.last_game_file_path)

    LOG.info("configuring twitch api connection...")
    predictions = Predictions(config)
    await predictions.setup()

    in_game_prev = False
    last_replay_found = True
    last_game_start = datetime.now(tz=timezone(offset=timedelta()))
    prediction = None

    LOG.info("started")
    while True:
        try:
            try:
                current_scene_output = obs_ws_client.get_current_program_scene()
                current_scene = current_scene_output.current_program_scene_name
            except BrokenPipeError as exp:
                LOG.info("attempting to reconnect to OBS")
                obs_ws_client = connect_to_obs(config)
                sleep(1)
                continue
            in_game = is_in_game()

            if not in_game_prev and in_game:
                if current_scene != config.in_game_scene:
                    LOG.info("switching to in game scene")
                    obs_ws_client.set_current_program_scene(config.in_game_scene)

                last_game_start = datetime.now(tz=timezone(offset=timedelta()))
                last_replay_found = True
                sc2rs.clear_last_replay_info()

            if in_game and prediction is None:
                game = get_game_details()
                if game["players"][0]["result"] == "Undecided" and not game["isReplay"]:
                    LOG.info("starting prediction")
                    prediction = await predictions.start_prediction()

            if in_game_prev and not in_game:
                obs_ws_client.set_current_program_scene(config.out_of_game_scene)
                LOG.info("switching to out of game scene")
                last_replay_found = False

            if not last_replay_found:
                last_replay = sc2rs.find_last_replay(last_game_start)
                if last_replay:
                    last_replay_found = True
                    streamer_won = sc2rs.process_last_replay(last_replay)
                    if streamer_won:
                        LOG.info("streamer won")
                    else:
                        LOG.info("streamer lost")
                    LOG.info("paying out prediction")
                    if prediction:
                        await predictions.payout_prediction(prediction, streamer_won)
                        prediction = None

            in_game_prev = in_game

        except Exception as exp:
            if LOG.level == logging.DEBUG:
                LOG.exception("Exception during poll loop: %s", exp)
            else:
                LOG.error("Exception during poll loop: %s", exp)

        sleep(1)


def load_config(config_file_path: str) -> Config:
    """Loads config file.

    :param config_file_path: path to the config file to read
    :return: Config object containing the configuration from the config file
    """

    try:
        LOG.info("parsing config file...")
        config = Config(config_file_path)
        config.load_config()
    except ConfigError as exp:
        LOG.error("invalid config: %s", exp)
        sys.exit(1)

    return config


def run_setup_config(config_file_path: str) -> None:
    """Run the configuration helper.

    :param config_file_path: path to the config file to write/edit
    """

    LOG.info("starting configuration helper")
    try:
        asyncio.run(setup_config.configure(config_file_path))
    except Exception as exp:  # pylint: disable=broad-exception-caught
        traceback.print_tb(exp.__traceback__)
        print(f"Fatal exception occurred: {exp}")
        sys.exit(1)
    sys.exit(0)


def main() -> None:
    """Main entrypoint to the program."""

    parser = argparse.ArgumentParser(
        prog="sc2sceneswitcher",
        description="Auto switch OBS scenes and create channel point predictions when joining a Starcraft II game.",
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
        LOG.info("setting log level to DEBUG")
        log_level = logging.DEBUG
        LOG.debug("test")

    if args.log_file:
        log_handlers.append(logging.FileHandler(args.log_file))

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
    asyncio.run(run(config), debug=False)


if __name__ == "__main__":
    asyncio.run(main())
