#!/usr/bin/env bash
# Serve the public read-only API against the live data DB (Phase LD).
#
# Defaults to the curated real-data DB built by refresh_live_db.sh and the real correlated-groups
# config. Override PARALLAX_DB / PARALLAX_GROUPS_CONFIG / PORT via the environment as needed.
set -euo pipefail
cd "$(dirname "$0")/.."

export PARALLAX_DB="${PARALLAX_DB:-data/parallax-live.db}"
export PARALLAX_GROUPS_CONFIG="${PARALLAX_GROUPS_CONFIG:-research/config/correlated_market_groups.yaml}"

exec uv run --project research python -m uvicorn api.main:app \
    --host "${HOST:-0.0.0.0}" --port "${PORT:-8000}"
