cd "$(dirname "$0")" || exit
cd ../app || exit
infisical export --format=dotenv-export --env dev > .env
