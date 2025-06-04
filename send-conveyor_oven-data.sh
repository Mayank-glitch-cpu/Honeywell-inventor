#!/bin/bash

# This script sends mock data to your conveyor_oven asset
source venv-sitewise/bin/activate
python senddata.py --alias "conveyoroven/conveyor-oven-2/oven_temp" --min 170 --max 190 --interval 1.0
