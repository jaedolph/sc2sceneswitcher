# sc2sceneswitcher

Auto switch OBS scenes and create channel point predictions when joining a StarCraft II game.

Features:
* Auto switch scene in OBS when entering and exiting a game (currently does not support StreamlabsOBS).
* Auto start and payout channel point predictions (must be an Affiliate or Partner to use this feature).
* Look up and display SC2ReplayStats info after a game (must have a Sc2ReplayStats account and have the auto uploader
  running to use this feature). The replay info can be displayed by adding a "Text" source with "Read from file" and
  setting the path to "C:/Users/your-username/last_game.txt" (or whatever path you set in the configuration).


# Installation

## Install using pip

Installation has been tested on Fedora 38 using python 3.11 but should work on other Linux distributions.
```bash
# install using pip
python3 -m pip install . --user
# run configuration utility
sc2replaystats --configure
# run the program
sc2replaystats
```

## Install on Windows

Installation has been tested on Windows 11.

1. Download the latest release zip file
2. Copy the zip to a location such as "Documents"
3. Right click and select "Extract here"
4. Follow [README.txt](windows/README.txt) instructions in the extracted folder

# Configuration

## Configuration helper utility
The application can be configured using a configuration helper utility by adding the `--configure`
flag to the program.
```
sc2replaystats --configure
```

## Configuration example

```ini
[TWITCH]
# oauth configuration (it is recommended to run `sc2replaystats --configure` to create these)
client_id = 1234567890abcdefghijklmnopqrst # client id of custom twitch application
client_secret = abcdefghijklmnopqrst1234567890 # client secret of twitch application
broadcaster_name = jaedolph # username (not display name) of your channel
auth_token = poiuytrewqlkjhgfdsamnbvcxz1234 # user auth token
refresh_token = qwertyuiopasdfghjkl1234567890asdfghjkllkjhgfdsa123 # user refresh token

# prediction settings
prediction_title = Jaedolph win? # title of the predictions that will be auto created
prediction_win_option = YES # prediction option that will get payed out after a win
prediction_loss_option = NO # prediction option that will get payed out after a loss

[SC2_REPLAY_STATS]
auth_key = qwertyuiopasdfghjkl1234567890asdfghjkllk;a539704bcdfaca203df520c98e74c4c721c47f50;1670112810 # sc2replaystats api token
last_game_file_path = C:\Users\jaedolph\last_game.txt # path that last replay info will be saved

[OBS]
websocket_server_port = 4455 # port for the OBS websocket connection
websocket_server_password = 1234567890abcdef # password for the OBS websocket connection
in_game_scene = starcraft2 # name of in game scene in OBS
out_of_game_scene = just-chatting # name of out of game scene in OBS
```
