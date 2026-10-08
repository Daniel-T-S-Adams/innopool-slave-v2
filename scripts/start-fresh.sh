#!/usr/bin/env bash
# Start only an explicitly installed v2 release. No Git, Compose or service changes.
set -euo pipefail
if [[ $# -lt 1 ]]; then
  printf '%s\n' 'Usage: scripts/start-fresh.sh /absolute/v2-installation-directory [--drain]' >&2
  exit 2
fi
worker_directory="$1"
shift
if [[ ! -f "$worker_directory/installation-v2.json" || ! -x "$worker_directory/run" ]]; then
  printf '%s\n' 'This is not an installed v2 worker. Use tools/install_worker_v2.py first.' >&2
  exit 2
fi
exec "$worker_directory/run" "$@"
