#!/usr/bin/env bash

echo "Setting up virtualenv..."
if [ -e venv ]; then
	echo "virtualenv already exists; skipping"
else
	virtualenv venv
fi

source ./venv/Scripts/activate || exit 1

echo "Installing requirements..."
pip install -r requirements.txt || exit 1

echo "Configuring pywikibot"
python ./venv/src/pywikibot/generate_user_files.py || exit 1
python ./venv/src/pywikibot/pwb.py login || exit 1
