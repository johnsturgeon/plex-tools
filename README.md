# GoshDarned Plex Tools
Utilities and scripts for plex using the Plex API

---

## `music_remove_duplicates.py`

At the moment, this script will search your Music Library for duplicates.  It will provide information for you to decide which ones you want to clean.

## Prerequisites
* Plex Login credentials (either `token` or `username/password`)  
  _see [Plex API Login](https://python-plexapi.readthedocs.io/en/stable/introduction.html) documentation for more details._
* Your Plex server URL

```bash
pip install rich inquire python-dotenv plexapi
```

## Usage
```bash
python music_remove_duplicates.py
```

Fire up the app, it will walk you through an initial configuration, Optionally offer to save the config in a `.env` file, and begin the search

### Setup


### Safe Clean

Safe clean will move duplicate tracks to a playlist for you to review and delete in Plex yourself.

### Delete Clean

Delete clean will remove the duplicate 
