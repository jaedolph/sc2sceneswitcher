# sc2sceneswitcher

Auto switch scenes in your stream and create channel point predictions when joining a StarCraft II game.

Features:
* Auto switch scene in OBS or Streamlabs Desktop (SLOBS) when entering and exiting a game.
* Auto start and payout channel point predictions (must be an Affiliate or Partner to use this feature).
* Look up and display SC2ReplayStats info after a game (must have a SC2ReplayStats account and have the auto uploader
  running to use this feature). The replay info can be displayed by adding a "Text" source with "Read from file" and
  setting the path to "~/last_game.txt" (or whatever path you set in the configuration).

To use the predictions feature you must also use the SC2ReplayStats feature. The internal SC2 client API gives very
limited information that can be unreliable for determining the result of a game. SC2ReplayStats gives much more
detailed information on the result of a game once the replay is parsed and uploaded. For best results I recommend
using a "Premium" (paid) account for SC2ReplayStats as the replays will upload much faster (1-3 seconds rather than
1-2 minutes) which will allow the predictions to be paid out faster.

# Installation

## Install using pip

Installation has been tested on Fedora 38 using python 3.11 but should work on other Linux distributions.
```bash
# install using pip
python3 -m pip install . --user
# run configuration utility
sc2sceneswitcher --configure
# run the program
sc2sceneswitcher
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
sc2sceneswitcher --configure
```

## Configuration example

```ini
[TWITCH]
enabled = yes # enable twitch integration for creating and paying out predictions for each game
# oauth configuration (it is recommended to run `sc2sceneswitcher --configure` to create these)
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
enabled = yes # enable sc2replaystats features
auth_key = qwertyuiopasdfghjkl1234567890asdfghjkllk;a539704bcdfaca203df520c98e74c4c721c47f50;1670112810 # sc2replaystats api token
last_game_file_path = C:\Users\jaedolph\last_game.txt # path that last replay info will be saved

[SCENE_SWITCHER]
enabled = yes # enable scene switching
websocket_type = OBS # set the type of websocket for your streaming program. Can be "OBS" or "STREAMLABS".
websocket_server_port = 4455 # port for the OBS websocket connection
websocket_server_password = 1234567890abcdef # password for the OBS websocket connection
in_game_scene = starcraft2 # name of in game scene in OBS
out_of_game_scene = just-chatting # name of out of game scene in OBS
show_load_screen = yes # set to "yes" to show the loading screen in your in game scene
```

# Running with Podman

Install using pip to get the configuration utility
```
python3 -m pip install . --user
sc2sceneswitcher --configure
```
Ensure you use `/tmp/last_game.txt` as the value for `Where would you like the post game stats to be saved?`


To run using podman you need to use `podman unshare` to set the correct permissions on the `last_game.txt` file:
```bash
# create last_game.txt with correct permissions for rootless podman
export LAST_GAME_FILE=~/Documents/twitch/obs/last_game.txt
touch $LAST_GAME_FILE
podman unshare chown 1001:1001 $LAST_GAME_FILE
# run container (need to use --net=host to access the SC2 client API and OBS websocket on 127.0.0.1)
podman run \
  -d \
  --name sc2sceneswitcher \
  --net=host \
  -v ~/sc2sceneswitcher.ini:/usr/src/app/sc2sceneswitcher.ini:z \
  -v $LAST_GAME_FILE:/tmp/last_game.txt:z \
  docker.io/jaedolph/sc2sceneswitcher:latest
```
