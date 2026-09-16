#!/usr/bin/env bash
# Simplest possible always-on option: no systemd/launchd required. Restarts the collector
# whenever it exits (crash, network drop the reconnect logic couldn't recover from, etc.).
# Run this under `nohup` or inside a `screen`/`tmux` session so it survives a logout:
#   nohup ./deploy/run_collector.sh &
set -euo pipefail
cd "$(dirname "$0")/.."

BIN=./target/release/collector
LOG=./data/collector.log
mkdir -p ./data

while true; do
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) starting collector" >> "$LOG"
    RUST_LOG=info "$BIN" --db-path ./data/parallax.db --archive-dir ./data/archive >> "$LOG" 2>&1 || true
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) collector exited, restarting in 5s" >> "$LOG"
    sleep 5
done
