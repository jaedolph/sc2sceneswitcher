"""Handles starting and ending Twitch predictions."""

import logging

from twitchAPI.helper import first
from twitchAPI.twitch import Prediction, Twitch
from twitchAPI.type import AuthScope, PredictionStatus, TwitchAPIException

from sc2sceneswitcher.exceptions import SetupError
from sc2sceneswitcher.config import Config

PREDICTION_WINDOW = 120
LOG = logging.getLogger("sc2sceneswitcher")


class Predictions:
    """Manages starting and ending Twitch predictions.

    :param config: Config object containing application configuration
    """

    def __init__(self, config: Config):
        self.config = config
        self.broadcaster = None
        self.twitch = None

    async def setup(self) -> None:
        """Setup connection to the Twitch API.

        :raises SetupError: if setup fails
        """

        try:
            LOG.info("Configuring twitch api connection...")

            self.twitch = await Twitch(self.config.client_id, self.config.client_secret)

            assert self.twitch is not None

            await self.twitch.authenticate_app([])
            scope = [AuthScope.CHANNEL_READ_PREDICTIONS, AuthScope.CHANNEL_MANAGE_PREDICTIONS]
            await self.twitch.set_user_authentication(
                self.config.auth_token, scope, self.config.refresh_token
            )

            self.broadcaster = await first(
                self.twitch.get_users(logins=[self.config.broadcaster_name])
            )
        except (AssertionError, TwitchAPIException) as exp:
            raise SetupError(f"Failed to configure Twitch API connection: {exp}") from exp

    async def clear_current_predictions(self) -> None:
        """Cancels any existing predictions."""

        assert self.twitch is not None

        prediction = await first(self.twitch.get_predictions(str(self.broadcaster.id)))
        if prediction:
            LOG.debug("Found existing prediction: %s", prediction.to_dict())
            if prediction.status in [PredictionStatus.ACTIVE, PredictionStatus.LOCKED]:
                LOG.info("Cancelling existing prediction: %s", prediction.title)
                await self.twitch.end_prediction(
                    self.broadcaster.id, prediction.id, PredictionStatus.CANCELED
                )

    async def lock_prediction(self, prediction: Prediction) -> None:
        """Locks the prediction to not accept any additional bets.

        :param prediction: prediction to lock
        """
        assert self.twitch is not None
        await self.twitch.end_prediction(
            self.broadcaster.id, prediction.id, PredictionStatus.LOCKED
        )

    async def start_prediction(self) -> Prediction:
        """Starts a new prediction.

        :return: created Prediction object
        """

        assert self.twitch is not None

        # ensure we delete any existing predictions
        await self.clear_current_predictions()

        # create a new prediction
        prediction = await self.twitch.create_prediction(
            self.broadcaster.id,
            self.config.prediction_title,
            [self.config.prediction_win_option, self.config.prediction_loss_option],
            PREDICTION_WINDOW,
        )
        LOG.debug("Started prediction: %s", prediction.to_dict())

        return prediction

    async def end_prediction(self, prediction: Prediction, streamer_won: bool) -> None:
        """Ends a specified prediction.

        :param prediction: prediction to end
        :param streamer_won: True if the streamer won, False if they lost/tied
        """

        assert self.twitch is not None

        win_id = None
        lose_id = None

        for outcome in prediction.outcomes:
            if outcome.title == self.config.prediction_win_option:
                win_id = outcome.id
            if outcome.title == self.config.prediction_loss_option:
                lose_id = outcome.id

        if streamer_won:
            winning_outcome_id = win_id
        else:
            winning_outcome_id = lose_id

        await self.twitch.end_prediction(
            self.broadcaster.id, prediction.id, PredictionStatus.RESOLVED, winning_outcome_id
        )
