#!/bin/sh
# wait for the first chain (zenith series, then frames) to finish, then refine and run aerosol cases
cd "$(dirname "$0")/.."
while pgrep -f "render_frames.py|zenith_series.py$" > /dev/null || ! [ -f logs/render_frames.log ]; do sleep 20; done
while pgrep -f render_frames.py > /dev/null; do sleep 20; done
PY=~/Developer/claudes-space/.venv/bin/python
$PY zenith_series.py --aerosol > logs/aerosol.log 2>&1
$PY zenith_series.py --refine > logs/refine.log 2>&1
