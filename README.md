# srs.ly

Requires Python >= 3.10 due to `match` statements being used.

## Setup

1. Create a virtual environment, and install the requirements:
```
python3 -m venv .venv
pip install -r requirements.txt
```
2. If you want to use the search feature, follow the directions to create a Google Cloud Platform (GCP) Vision API key. Export the `json`, and store it somewhere safe on your device you're hosting this app on. Then, set the Google credentials environment variable:
```
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/secret.json
```
3. If you want the Discord bot, set your bot token as an environment variable (see [Discord Bot](#discord-bot) below).

4. Start the app (optionally append a custom port):
```
python main.py [PORT]
```

The Discord bot starts automatically alongside the web UI if `DISCORD_BOT_TOKEN` is set. If the token is not found, the app runs as web-only.

## Configurations
Configurations are stored in the `config.toml` file, and all the variables should be self explanatory along with the comments provided. The `[discord]` section controls the bot token environment variable name and command prefix.

## How is the data stored?
Data is stored in `./db`, and `KanjiDatabase.sqlite` contains a static copy of dictionary information. `SrsDatabase.sqlite` is the dynamic, user data that will change on updates. Lastly, `empty_test.db` is a very small database that contains a few rows for testing and implementation purposes.

The database file names and naming schemes are directly from Houhou SRS. In the future, I might choose to restructure the datasets to suit my needs better.

## Discord Bot

The Discord bot runs in the same process as the web UI and shares the same database connection, so changes made via the web UI are immediately visible in Discord without restarting.

### Environment variable

Set `DISCORD_BOT_TOKEN` before launching:
```
export DISCORD_BOT_TOKEN="your token"
```

### Running as a systemd service

Create an environment file at `/etc/systemd/system/srsly.env`:
```
PATH={path_to_python_venv}/bin
DISCORD_BOT_TOKEN="{your token}"
```

Create a service file at `/etc/systemd/system/srsly.service`:
```
[Unit]
Description=srsly
After=network.target

[Service]
Type=simple
User={your user}
WorkingDirectory={path_to_this_repo}
EnvironmentFile=/etc/systemd/system/srsly.env
ExecStart={path_to_python_venv}/bin/python main.py
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```
