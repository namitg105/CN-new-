#!/bin/bash
# Stop the running live NetTwin-SDN demo
set -euo pipefail
cd "$(dirname "$0")/.."

echo "[*] Stopping live NetTwin-SDN environment..."

if [ -f /tmp/netwin_demo.pid ]; then
    while read -r pid; do
        if [ -n "$pid" ]; then
            kill "$pid" 2>/dev/null || true
        fi
    done < /tmp/netwin_demo.pid
    sudo rm -f /tmp/netwin_demo.pid
fi

python3 -m nettwin.terminals --kill > /dev/null 2>&1 || true
pkill -9 -f ryu-manager 2>/dev/null || true
pkill -9 -f run_live_demo.py 2>/dev/null || true
echo 123456 | sudo -S mn -c > /dev/null 2>&1 || sudo mn -c > /dev/null 2>&1
echo "[+] NetTwin-SDN stopped cleanly."
