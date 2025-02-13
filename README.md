# AutoPlex

Utilities and scripts for plex using the Plex API to clean up and manage your Plex Music library.

<img width="300" src="https://github.com/johnsturgeon/plex-tools/assets/9746310/0c42ce63-983b-43a6-8f2e-77338e204cba" alt="GoshDarned Mascot">

---

## UPDATE 2025-01-29

I'm going to work on making a web server for interacting with the plex tools.  You can follow along the project here:
[Prioritized backlog · Create a website for the plex-tools](https://github.com/users/johnsturgeon/projects/8)

## Deployment instructions

### Linux Installation Notes

* I've installed this on a bare bones Debian 12 LXC (in ProxMox).  

You can review the script, each step is commented
```shell
bash -c "$(wget -qLO - https://github.com/johnsturgeon/autoplex/raw/main/scripts/deploy.sh)"
```

## Scripts
You can read about the CLI version of `deduplex.py` [here](docs/deduplex.md)
