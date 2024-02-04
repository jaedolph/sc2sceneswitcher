from twitchAPI.twitch import Twitch
from twitchAPI.helper import first
from twitchAPI.type import AuthScope, PredictionStatus
import logging

PREDICTION_WINDOW = 10
LOG = logging.getLogger("sc2sceneswitcher")


class Predictions:
    def __init__(self, config):
        self.config = config
        self.broadcaster = None
        self.twitch = None

    async def setup(self):
        self.twitch = await Twitch(self.config.client_id, self.config.client_secret)

        await self.twitch.authenticate_app([])
        scope = [AuthScope.CHANNEL_READ_PREDICTIONS, AuthScope.CHANNEL_MANAGE_PREDICTIONS]
        await self.twitch.set_user_authentication(
            self.config.auth_token, scope, self.config.refresh_token
        )

        self.broadcaster = await first(self.twitch.get_users(logins=[self.config.broadcaster_name]))

    async def start_prediction(self):
        prediction = await self.twitch.create_prediction(
            self.broadcaster.id,
            self.config.prediction_title,
            [self.config.prediction_win_option, self.config.prediction_loss_option],
            PREDICTION_WINDOW,
        )

        return prediction

    async def payout_prediction(self, prediction, streamer_won):
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
