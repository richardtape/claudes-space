#!/bin/sh
# after queue.sh (aerosol + refine) finishes, run the ozone-hole experiment
cd "$(dirname "$0")/.."
sleep 30
while pgrep -f "queue.sh" > /dev/null; do sleep 20; done
~/Developer/claudes-space/.venv/bin/python hole_experiment.py > logs/hole.log 2>&1
