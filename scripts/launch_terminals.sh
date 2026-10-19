#!/bin/bash
# Launch the 7 terminals (3 systems, 3 routers, 1 main server)
set -euo pipefail
cd "$(dirname "$0")/.."
exec python3 -m nettwin.terminals "$@"
