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

### Known Issues:
If you run into `OSError: no library called "cairo-2" was found`: Install `libcairo2`.

## Voice Input

On the review tab, press `` ` `` (or click the mic button) to start recording your answer, and press it again to stop. The recording is transcribed on the machine hosting the app with [faster-whisper](https://github.com/SYSTRAN/faster-whisper), in Japanese for reading cards and English for meaning cards. The transcription is put in the answer field without submitting it, so you can check it, fix it by typing, and press Enter as usual.

The `[voice]` section of `config.toml` sets the Whisper model (`small` by default; `base` is faster but worse at Japanese) and the maximum recording length. The model is downloaded on the first startup. Set `enabled = false` to turn voice input off.

### HTTPS

Browsers only allow the microphone on `https://` or `localhost` pages. To use voice input from another device, put HTTPS in front of the app. With [Tailscale](https://tailscale.com/kb/1242/tailscale-serve) (HTTPS certificates enabled for your tailnet), this serves the app on its own port:
```
tailscale serve --bg --https=8443 localhost:8080
```
Then open `https://<machine>.<tailnet>.ts.net:8443`.

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
