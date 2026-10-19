#!/usr/bin/env python3
import os
import signal
import subprocess
import time
import sys

from topo import build

def log_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def main():
    log_header("1. Initializing Diamond SDN Topology in Mininet")
    net = build()
    net.start()

    c1 = net.get('c1')
    c2 = net.get('c2')
    c3 = net.get('c3')
    srv = net.get('srv')

    try:
        print("Waiting 3 seconds for OpenFlow 1.3 switches to register with Ryu...")
        time.sleep(3)

        log_header("2. Controller Telemetry & Initial Connection")
        if os.path.exists("/tmp/ryu.log"):
            with open("/tmp/ryu.log") as f:
                print(f.read().strip())

        log_header("3. Network Connectivity Check (pingAll)")
        drop = net.pingAll()
        print(f"pingAll packet drop: {drop}%")

        log_header("4. Inspecting Switch s1 OpenFlow 1.3 Groups & Flows")
        groups = subprocess.check_output(["ovs-ofctl", "-O", "OpenFlow13", "dump-groups", "s1"]).decode()
        print("[Fast Failover Group on s1]")
        print(groups.strip())

        flows = subprocess.check_output(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"]).decode()
        print("\n[Flow Rules on s1]")
        for line in flows.strip().splitlines():
            if "10.0.0.100" in line or "actions=" in line:
                print(" ", line)

        log_header("5. Starting Flask Server on 'srv' (10.0.0.100:5000)")
        srv.cmd("python3 server.py > /tmp/server.log 2>&1 &")
        time.sleep(2)

        health_resp = c1.cmd("curl -s http://10.0.0.100:5000/health")
        print(f"Verification request: c1 -> srv /health: {health_resp.strip()}")

        log_header("6. Starting Background Traffic from Clients (c1, c2, c3)")
        c1.cmd("./client.sh c1 > /tmp/c1.log 2>&1 &")
        c2.cmd("./client.sh c2 > /tmp/c2.log 2>&1 &")
        c3.cmd("./client.sh c3 > /tmp/c3.log 2>&1 &")
        time.sleep(2.5)

        print("[c1 Traffic via Path A (s1 -> s2 -> s4)]")
        c1_pre = subprocess.check_output(["tail", "-n", "3", "/tmp/c1.log"]).decode()
        print(c1_pre.strip())

        log_header("7. Simulating Failure: Cutting Primary Link (s1 <-> s2)")
        print("Executing: link s1 s2 down")
        net.configLinkStatus('s1', 's2', 'down')
        time.sleep(2)

        print("\n[Ryu Controller Telemetry on Link Failure]")
        if os.path.exists("/tmp/ryu.log"):
            with open("/tmp/ryu.log") as f:
                lines = f.readlines()
                for line in lines[-8:]:
                    print(" ", line.strip())

        print("\n[Client c1 Status AFTER Primary Link Failure]")
        c1_post = subprocess.check_output(["tail", "-n", "4", "/tmp/c1.log"]).decode()
        print(c1_post.strip())

        log_header("8. Fast Failover Latency & Packet Loss Measurement")
        print("Sending 100 fast pings (10ms interval) from c1 to srv over Backup Path B...")
        ping_res = c1.cmd("ping -i 0.01 -c 100 10.0.0.100")
        for line in ping_res.splitlines():
            if "packets transmitted" in line or "rtt min/avg/max" in line:
                print(" ", line)

        log_header("9. Restoring Primary Link (s1 <-> s2)")
        print("Executing: link s1 s2 up")
        net.configLinkStatus('s1', 's2', 'up')
        time.sleep(2)

        print("\n[Ryu Controller Telemetry on Link Recovery]")
        if os.path.exists("/tmp/ryu.log"):
            with open("/tmp/ryu.log") as f:
                lines = f.readlines()
                for line in lines[-6:]:
                    print(" ", line.strip())

        print("\n[Client c1 Status AFTER Primary Link Restored]")
        c1_restored = subprocess.check_output(["tail", "-n", "3", "/tmp/c1.log"]).decode()
        print(c1_restored.strip())

        log_header("10. Testing Security Policy: Drop Rule for c2")
        print("Adding drop rule: Drop all IP traffic from c2 (10.0.0.2) to srv (10.0.0.100)")
        subprocess.check_call([
            "ovs-ofctl", "-O", "OpenFlow13", "add-flow", "s1",
            "priority=100,ip,nw_src=10.0.0.2,nw_dst=10.0.0.100,actions=drop"
        ])
        time.sleep(2)

        print("\n[Client Logs During Policy Enforcement]")
        c2_blocked = subprocess.check_output(["tail", "-n", "3", "/tmp/c2.log"]).decode()
        c1_ok = subprocess.check_output(["tail", "-n", "2", "/tmp/c1.log"]).decode()
        print("c2 (blocked):")
        print(c2_blocked.strip())
        print("c1 (unaffected):")
        print(c1_ok.strip())

        print("\nRemoving drop rule (allow c2 again)...")
        subprocess.check_call([
            "ovs-ofctl", "-O", "OpenFlow13", "--strict", "del-flows", "s1",
            "priority=100,ip,nw_src=10.0.0.2,nw_dst=10.0.0.100"
        ])
        time.sleep(2)

        c2_recovered = subprocess.check_output(["tail", "-n", "3", "/tmp/c2.log"]).decode()
        print("c2 (recovered):")
        print(c2_recovered.strip())

    finally:
        log_header("11. Tearing Down Emulation & Stopping Processes")
        for h in [c1, c2, c3, srv]:
            try:
                h.cmd("pkill -9 -f client.sh; pkill -9 -f server.py; pkill -9 -f curl; pkill -9 -f ping")
            except Exception:
                pass
        net.stop()
        print("Mininet stopped.")

if __name__ == "__main__":
    main()
