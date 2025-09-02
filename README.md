# SRS Web Tool

Requires Python < 3.10 due to `match` statements being used.

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
3. Start the app:
```
python main.py
```

## Configurations
Configurations are stored in the `config.toml` file, and all the variables should be self explanatory along with the comments provided.

## How is the data stored?
Data is stored in `./db`, and `KanjiDatabase.sqlite` contains a static copy of dictionary information. `SrsDatabase.sqlite` is the dynamic, user data that will change on updates. Lastly, `empty_test.db` is a very small database that contains a few rows for testing and implementation purposes.
