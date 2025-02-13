#!/usr/bin/env bash
##
# This script will deploy autoplex into a linux server, or update it if it's already installed
# run as root
#

# CHANGE THIS if you want to install in a different directory
INSTALL_DIR=/opt/autoplex
DB_FILE="${INSTALL_DIR}/app/db/database.db"
DB_FILE_EXISTS=n
# CHANGE THIS to anything other than 'y'
#   if you do not want to use infisical for your secret manangement
USE_INFISICAL=y

if [ ! -d "${INSTALL_DIR}" ]
then
  mkdir -p "${INSTALL_DIR}"
fi

cd $INSTALL_DIR || exit

# Stop the running service
if systemctl is-active --quiet autoplex
then
  systemctl stop autoplex.service
fi

# Install or update dependencies
echo "Updating installed packages"
apt update && apt upgrade -y

# install python if it's not installed
if ! dpkg -s python3.11 python3.11-venv python3-pip python-is-python3 > /dev/null 2>&1
then
  echo "Installing Python"
  apt install python3.11 python3.11-venv python3-pip python-is-python3 -y
fi

if ! which uv
then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source "$HOME/.profile"
else
  uv self update
fi

echo "Fetching / installing web site from github"
# fetch the tgfp code
wget https://github.com/johnsturgeon/autoplex/archive/main.zip
unzip main.zip
rm main.zip

# check to see if there is a database
if [ -f "${DB_FILE}" ]
then
  cp "${DB_FILE}.bak" autoplex-main/app/db
  mv "${DB_FILE}" autoplex-main/app/db
fi
rm -rf ${INSTALL_DIR}/app

# grab the important bits
mv autoplex-main/app ${INSTALL_DIR}/app
mv autoplex-main/pyproject.toml ${INSTALL_DIR}/app
mv autoplex-main/.infisical.json ${INSTALL_DIR}/app
mv autoplex-main/uv.lock ${INSTALL_DIR}/app
mv autoplex-main/helpers/autoplex.service /etc/systemd/system
rm -rf autoplex-main

cd "${INSTALL_DIR}/app" || exit

if [ "${USE_INFISICAL}" == "y" ]
then
  if ! which infisical
  then
    curl -1sLf 'https://dl.cloudsmith.io/public/infisical/infisical-cli/setup.deb.sh' | bash
    apt-get update && apt-get install -y infisical
  fi
  if ! infisical run echo "hi"
  then
    echo "Logging you into infisical"
    infisical login
  fi
  # Create the .env file
  infisical export --format=dotenv-export --env prod > .env
fi

# now use `uv` to create the environment
uv sync

if [ ! -f "${DB_FILE}" ]
then
  cd db || exit
  .venv/bin/python database.py
fi

systemctl daemon-reload
systemctl enable autoplex.service
systemctl start autoplex.service

