set /p key_id="ACCESS_KEY_ID: "
set /p key_secret="ACCESS_KEY_SECRET: "
set /p app_id="APP_ID: "
poetry run python build.py --name bili_ncm --windowed main.py --access_key_id %key_id% --access_key_secret %key_secret% --app_id %app_id%