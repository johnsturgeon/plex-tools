cd "$(dirname "$0")" || exit
cd ..
infisical export --format=dotenv-export --env dev > .env
