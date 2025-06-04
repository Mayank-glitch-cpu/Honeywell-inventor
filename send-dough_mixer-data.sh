#!/bin/bash

# This script sends mock data to your dough_mixer asset
source venv-sitewise/bin/activate
python senddata.py --alias "mixer_speed" --min 80 --max 120 --interval 1.0
