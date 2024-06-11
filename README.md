# GoshDarned Plex Tools
<img width="300" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/0c42ce63-983b-43a6-8f2e-77338e204cba">

Utilities and scripts for plex using the Plex API

---

## `music_remove_duplicates.py`

This script will search your Plex Music Library for duplicates.  It will provide information for you to decide which ones you want to clean.  You can choose to "Safe Clean" (place all duplicates in a playlist) or delete.

## Prerequisites
* Plex Login credentials (either `token` or `username/password`)  
  _see [Plex API Login](https://python-plexapi.readthedocs.io/en/stable/introduction.html#getting-a-plexserver-instance) documentation for more details._
* Your Plex server URL
* Python 3.11

## Quick Start

*  Install dependencies

```bash
mkdir plex-tools
cd plex-tools
# Recommended: Use a virtual env
pip install rich python-dotenv plexapi
```
* Download python script [music_remove_duplicates.py](music_remove_duplicates.py)
* Run the script `python music_remove_duplicates.py`
* The script will walk you through the entire process

# Detailed walk-through

## Usage

```bash
python music_remove_duplicates.py
```

The script will walk you through an initial configuration, Optionally offer to save the config in a `.env` file, and begin the search

## .env

If the .env file does not exist, you can opt to create it

<img width="690" alt="image" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/8b2a6b9a-78d4-4067-acf9-1f15bf001094">

## Setup

The setup process will attempt to connect to your plex server using credentials supplied in the .env file.  If successful, it will search for duplicates.

<img width="623" alt="image" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/b8462a9f-9292-46f2-b97f-5fa2f11a9e25">

## Safe Mode

Safe mode will move duplicate tracks to a playlist for you to review and delete in Plex yourself.

<img width="726" alt="image" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/7dfcaf44-330a-4c8f-9d1b-02994e41c3c3">

If you choose not to enable safe mode, then your duplicates will be deleted directly

## Instructions

You will (optionally) be shown some brief instructions for how to choose your duplicates, it will be more obvious once you begin.

<img width="730" alt="image" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/ddc04e84-12c8-4c3c-b851-40e96dd74573">

## Duplicate chooser

Each song that has duplicate(s) files will present you with a choice for choosing which songs to delete

<img width="728" alt="image" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/95d1a049-618c-488d-b80b-79a00f346b53">

## Final review

You will be asked if you'd like to review the actual files that you've chosen for clean-up then, either the files will be placed into a playlist (safe delete) or deleted

