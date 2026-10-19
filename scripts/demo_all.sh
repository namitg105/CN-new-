#!/bin/bash
# NetTwin-SDN: Complete All-in-One Demo Launcher
# Starts Ryu controller, Mininet network, Flask server, and spawns all 7 terminals.
set -euo pipefail
cd "$(dirname "$0")/.."
xhost +local: >/dev/null 2>&1 || true

echo -e "\033[1;36m====================================================================\033[0m"
echo -e "\033[1;32m  Starting NetTwin-SDN Self-Healing Network Demonstration\033[0m"
echo -e "\033[1;36m====================================================================\033[0m"

# 1. Clean previous state
echo "[*] Step 1/4: Cleaning up any previous Mininet or Ryu processes..."
echo 123456 | sudo -S -v > /dev/null 2>&1 || true
sudo mn -c > /dev/null 2>&1 || true
pkill -9 -f ryu-manager 2>/dev/null || true
pkill -9 -f "RouterCLI" 2>/dev/null || true
pkill -9 -f "system_env.sh" 2>/dev/null || true
pkill -9 -f "server_env.sh" 2>/dev/null || true
rm -f /tmp/netwin_*.json /tmp/netwin_*.pids /tmp/c*.log /tmp/server.log /tmp/ryu.log 2>/dev/null || true

# 2. Start Ryu Controller
echo "[*] Step 2/4: Starting Ryu Controller with OpenFlow 1.3 in background..."
source .ryu-env/bin/activate
PYTHONPATH="$PWD" ryu-manager nettwin.controller.app > /tmp/ryu.log 2>&1 &
RYU_PID=$!
sleep 2

if ! kill -0 $RYU_PID 2>/dev/null; then
    echo -e "\033[1;31m[-] Error: Ryu failed to start. Check /tmp/ryu.log\033[0m"
    cat /tmp/ryu.log
    exit 1
fi
echo "[+] Ryu controller running (PID $RYU_PID). Telemetry at /tmp/ryu.log"

# Cleanup trap on exit
cleanup() {
    echo -e "\n[*] Shutting down NetTwin-SDN..."
    python3 -m nettwin.terminals --kill > /dev/null 2>&1 || true
    kill -9 $RYU_PID 2>/dev/null || true
    echo 123456 | sudo -S mn -c > /dev/null 2>&1 || sudo mn -c > /dev/null 2>&1
    rm -f /tmp/netwin_*.json /tmp/netwin_*.pids 2>/dev/null || true
    echo "[+] Clean shutdown complete."
}
trap cleanup EXIT INT TERM

# 3. Start Mininet and spawn terminals
echo "[*] Step 3/4: Initializing virtual topology and spawning terminals..."
echo "[*] Spawning 3 System Terminals, 4 Router Terminals, 1 Main Server Terminal, and 1 Controller Monitor..."

sudo /usr/bin/python3 -m nettwin.network --terminals "$@"
