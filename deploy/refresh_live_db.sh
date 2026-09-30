#!/usr/bin/env bash
# Refresh the live dashboard database from real Manifold + Polymarket data (Phase LD).
#
# Runs the full enrichment pipeline: backfill curated markets' prices/features, retrain the
# calibration model and store honest predictions, and run the logical-constraint + cross-source
# divergence detectors — writing data/parallax-live.db, the DB the API serves in production.
#
# Cron example (refresh every 6 hours):
#   0 */6 * * * /path/to/Parallax/deploy/refresh_live_db.sh >> /path/to/Parallax/data/refresh.log 2>&1
set -euo pipefail
cd "$(dirname "$0")/../research"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) refreshing live DB"
uv run python scripts/build_live_db.py --db ../data/parallax-live.db "$@"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) refresh complete"
