#!/bin/bash
# Terminal 2: start the virtual network and open the mininet> prompt.
# Extra arguments are passed on, e.g.  scripts/run_network.sh --terminals
set -euo pipefail
cd "$(dirname "$0")/.."

# Always the system Python (Mininet lives there), never the Ryu virtualenv.
# sudo -E preserves environment (like DISPLAY for xterm terminals)
# and Mininet hosts inherit the repo root.
exec sudo -E /usr/bin/python3 -m nettwin.network "$@"
