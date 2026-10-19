#!/usr/bin/env python3
"""Run the complete live NetTwin-SDN environment with 7 terminals in background."""
import os
import signal
import subprocess
import sys
import time

sys.path.insert(0, "/home/kalis/nettwin")

from nettwin.network.builder import build
from nettwin.terminals import save_node_pids, launch_xterms

DEMO_PID_FILE = "/tmp/netwin_demo.pid"


def cleanup_previous():
    os.system("echo 123456 | sudo -S mn -c > /dev/null 2>&1 || true")
    os.system("pkill -9 -f ryu-manager 2>/dev/null || true")
    os.system("pkill -9 -f RouterCLI 2>/dev/null || true")
    os.system("pkill -9 -f system_env.sh 2>/dev/null || true")
    os.system("pkill -9 -f server_env.sh 2>/dev/null || true")


def main():
    cleanup_previous()

    # 1. Start Ryu Controller
    print("[*] 1/4 Starting Ryu SDN Controller in background...")
    ryu_env_bin = "/home/kalis/nettwin/.ryu-env/bin/ryu-manager"
    ryu_proc = subprocess.Popen(
        [ryu_env_bin, "nettwin.controller.app"],
        cwd="/home/kalis/nettwin",
        env=dict(os.environ, PYTHONPATH="/home/kalis/nettwin"),
        stdout=open("/tmp/ryu.log", "w"),
        stderr=subprocess.STDOUT
    )
    time.sleep(2)

    # 2. Start Mininet Network
    print("[*] 2/4 Initializing Mininet Virtual Diamond Topology...")
    net = build()
    net.start()
    save_node_pids(net)
    time.sleep(2)

    # 3. Start Flask Web Server on srv
    print("[*] 3/4 Starting Flask Application Server on srv (10.0.0.100:5000)...")
    srv = net.get("srv")
    srv.cmd("python3 -m nettwin.server.app > /tmp/server.log 2>&1 &")
    time.sleep(1)

    # 4. Launch the 7 Terminals (+ controller monitor)
    print("[*] 4/4 Launching 7 Dedicated Terminal Windows on DISPLAY=:0.0...")
    launch_xterms(include_router4=False, include_controller=True)

    # Save PID file
    with open(DEMO_PID_FILE, "w") as f:
        f.write(f"{os.getpid()}\n{ryu_proc.pid}\n")

    print("\n" + "=" * 68)
    print("  [+] NetTwin-SDN IS LIVE AND RUNNING!")
    print("=" * 68)
    print("  Active Terminals on your screen:")
    print("    * Column 1 (Left)   : Systems 1, 2, 3 (c1, c2, c3)")
    print("    * Column 2 (Center) : Routers 1, 2, 3 (s1, s2, s3)")
    print("    * Column 3 (Right)  : Main Server (srv) + Ryu Controller Monitor")
    print("=" * 68 + "\n")
    sys.stdout.flush()

    def handle_exit(signum, frame):
        print("\n[*] Stopping NetTwin-SDN...")
        try:
            net.stop()
        except Exception:
            pass
        try:
            ryu_proc.terminate()
        except Exception:
            pass
        os.system("python3 -m nettwin.terminals --kill > /dev/null 2>&1 || true")
        cleanup_previous()
        if os.path.exists(DEMO_PID_FILE):
            os.remove(DEMO_PID_FILE)
        print("[+] Stopped successfully.")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    while True:
        time.sleep(1)


if __name__ == "__main__":
    main()
