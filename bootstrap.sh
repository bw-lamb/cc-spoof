#!/usr/bin/env bash

python3 -m venv .venv
. ./.venv/bin/activate
pip install -r ./requirements.txt
deactivate
echo "python3 virtualenv created in .venv/"
