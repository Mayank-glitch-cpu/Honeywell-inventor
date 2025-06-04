#!/bin/bash

# This script sends mock data to your cookie_cutter asset
source venv-sitewise/bin/activate
python senddata.py --alias "cookies_per_min" --min 100 --max 150 --interval 1.0
