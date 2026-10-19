#!/usr/bin/env python3
"""Interactive router console for NetTwin-SDN OpenFlow routers/switches.

Usage:
    python3 -m nettwin.router_cli s1
    python3 -m nettwin.router_cli r1
"""
import cmd
import os
import readline
import subprocess
import sys
import time

from nettwin import policy

ROUTER_INFO = {
    "s1": {
        "num": 1,
        "name": "Router-1",
        "dpid": "0000000000000001",
        "role": "Ingress / Access Router (Client Gateway)",
        "ports": {
            1: "Connected to System 1 (c1 - 10.0.0.1)",
            2: "Connected to System 2 (c2 - 10.0.0.2)",
            3: "Connected to System 3 (c3 - 10.0.0.3)",
            4: "Uplink to Router-2 (s2) [Primary Path A]",
            5: "Uplink to Router-3 (s3) [Backup Path B]",
        },
    },
    "s2": {
        "num": 2,
        "name": "Router-2",
        "dpid": "0000000000000002",
        "role": "Core Router - Path A (Primary Transmission Path)",
        "ports": {
            1: "Link to Router-1 (s1)",
            2: "Link to Router-4 / Server Egress (s4)",
        },
    },
    "s3": {
        "num": 3,
        "name": "Router-3",
        "dpid": "0000000000000003",
        "role": "Core Router - Path B (Standby Failover Path)",
        "ports": {
            1: "Link to Router-1 (s1)",
            2: "Link to Router-4 / Server Egress (s4)",
        },
    },
    "s4": {
        "num": 4,
        "name": "Router-4",
        "dpid": "0000000000000004",
        "role": "Egress / Server Gateway Router",
        "ports": {
            1: "Link to Router-2 (s2) [Path A]",
            2: "Link to Router-3 (s3) [Path B]",
            3: "Connected to Main Server (srv - 10.0.0.100:5000)",
        },
    },
}

# Alias r1 -> s1, etc.
ALIAS_MAP = {
    "r1": "s1", "router1": "s1", "router-1": "s1",
    "r2": "s2", "router2": "s2", "router-2": "s2",
    "r3": "s3", "router3": "s3", "router-3": "s3",
    "r4": "s4", "router4": "s4", "router-4": "s4",
}


def run_cmd(cmd_list):
    try:
        if os.geteuid() != 0 and cmd_list[0] in ("ovs-ofctl", "ip"):
            cmd_list = ["sudo"] + cmd_list
        res = subprocess.run(cmd_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return res.returncode, res.stdout, res.stderr
    except Exception as e:
        return 1, "", str(e)


class RouterCLI(cmd.Cmd):
    def __init__(self, sw_id):
        super().__init__()
        self.sw_id = sw_id
        self.info = ROUTER_INFO[sw_id]
        self.r_name = self.info["name"]
        self.prompt = f"\033[1;33m{self.r_name}({self.sw_id})# \033[0m"

    def onecmd(self, line):
        line_strip = line.strip()
        if not line_strip:
            return self.emptyline()
        if line_strip == "EOF":
            return self.do_EOF("")
        parts = line_strip.split(None, 1)
        cmd_name = parts[0].replace("-", "_").lower()
        arg = parts[1] if len(parts) > 1 else ""
        func = getattr(self, "do_" + cmd_name, None)
        if func:
            return func(arg)
        return self.default(line)

    def banner(self):
        print("\033[1;36m" + "=" * 66 + "\033[0m")
        print(f"\033[1;32m  {self.r_name.upper()} CONSOLE -- {self.info['role']}\033[0m")
        print(f"  Switch ID: \033[1;37m{self.sw_id}\033[0m  |  DPID: \033[1;37m{self.info['dpid']}\033[0m")
        print("\033[1;36m" + "-" * 66 + "\033[0m")
        print("  \033[1;34mConfigured Interfaces & Links:\033[0m")
        for p, desc in self.info["ports"].items():
            iface = f"{self.sw_id}-eth{p}"
            print(f"    * Port {p} ({iface}): {desc}")
        print("\033[1;36m" + "-" * 66 + "\033[0m")
        print("  \033[1;37mCommands:\033[0m")
        print("    \033[1;32mflows\033[0m        - View active OpenFlow forwarding table")
        print("    \033[1;32mgroups\033[0m       - View Fast-Failover group configuration")
        print("    \033[1;32mstats\033[0m        - View group and packet forwarding statistics")
        print("    \033[1;32mports\033[0m        - View interface status (UP/DOWN) and counters")
        print("    \033[1;32mblock <ip>\033[0m   - Block a client IP via OpenFlow rule (e.g. block 10.0.0.2)")
        print("    \033[1;32mallow <ip>\033[0m   - Unblock a client IP")
        print("    \033[1;32mreroutes\033[0m     - View active controller re-routes and bypass paths")
        print("    \033[1;32missues\033[0m        - View risk analysis & operational issues of re-routing")
        print("    \033[1;32mcut-link <p>\033[0m - Simulate link cut on port (e.g. cut-link 4)")
        print("    \033[1;32mup-link <p>\033[0m  - Restore cut link on port (e.g. up-link 4)")
        print("    \033[1;32mmonitor\033[0m      - Real-time live monitoring dashboard")
        print("    \033[1;32mbash\033[0m         - Drop into a standard Linux shell")
        print("    \033[1;32mexit\033[0m         - Exit router console")
        print("\033[1;36m" + "=" * 66 + "\033[0m\n")

    def do_flows(self, arg):
        """Display active OpenFlow forwarding rules."""
        code, out, err = run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", self.sw_id])
        if code != 0:
            print(f"\033[1;31mError querying switch {self.sw_id}: {err.strip()}\033[0m")
            return
        lines = out.strip().splitlines()
        print(f"\033[1;34m--- OpenFlow 1.3 Flow Table on {self.r_name} ({self.sw_id}) ---\033[0m")
        header = lines[0] if lines else ""
        flow_lines = lines[1:] if len(lines) > 1 else []
        print(f"\033[0;37m{header}\033[0m")
        if not flow_lines:
            print("  (No flow rules currently installed)")
            return
        for line in flow_lines:
            line_str = line.strip()
            if "actions=drop" in line_str:
                print(f"  \033[1;31m[DROP RULE] {line_str}\033[0m")
            elif "actions=group" in line_str:
                print(f"  \033[1;32m[FAILOVER]  {line_str}\033[0m")
            elif "actions=output" in line_str:
                print(f"  \033[1;36m[DIRECT]    {line_str}\033[0m")
            else:
                print(f"  {line_str}")

    def do_groups(self, arg):
        """Display Fast Failover groups."""
        code, out, err = run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-groups", self.sw_id])
        if code != 0:
            print(f"\033[1;31mError querying switch {self.sw_id}: {err.strip()}\033[0m")
            return
        print(f"\033[1;34m--- Fast-Failover Groups on {self.r_name} ({self.sw_id}) ---\033[0m")
        lines = out.strip().splitlines()
        group_lines = lines[1:] if len(lines) > 1 else []
        if not group_lines:
            print("  (No groups installed on this switch)")
        else:
            for g in group_lines:
                print(f"  \033[1;33m{g.strip()}\033[0m")

    def do_stats(self, arg):
        """Display packet counters for groups and flow rules."""
        code, out, err = run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-group-stats", self.sw_id])
        print(f"\033[1;34m--- Group Usage Stats on {self.r_name} ({self.sw_id}) ---\033[0m")
        if code == 0 and out.strip():
            for line in out.strip().splitlines():
                print(f"  {line.strip()}")
        else:
            print("  (No group statistics available)")

    def do_ports(self, arg):
        """Display port link status and traffic counters."""
        code, out, err = run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-ports-desc", self.sw_id])
        if code != 0:
            print(f"\033[1;31mError querying ports: {err.strip()}\033[0m")
            return
        print(f"\033[1;34m--- Interface Port Status on {self.r_name} ({self.sw_id}) ---\033[0m")
        for line in out.strip().splitlines()[1:]:
            line_str = line.strip()
            if "state:      LINK_DOWN" in line_str or "state: LINK_DOWN" in line_str:
                print(f"  \033[1;31m{line_str} [DOWN]\033[0m")
            elif "state:      0" in line_str or "state: 0" in line_str or "UP" in line_str:
                print(f"  \033[1;32m{line_str} [UP / ACTIVE]\033[0m")
            else:
                print(f"  {line_str}")

    def do_block(self, arg):
        """Block traffic from a client IP: block <ip>"""
        ip = arg.strip()
        if not ip:
            print("Usage: block <ip>  (e.g. block 10.0.0.2)")
            return
        cmd_call = [
            "ovs-ofctl", "-O", "OpenFlow13", "add-flow", self.sw_id,
            f"priority=100,ip,nw_src={ip},nw_dst=10.0.0.100,actions=drop"
        ]
        code, out, err = run_cmd(cmd_call)
        if code == 0:
            policy.add_block(self.sw_id, ip, "10.0.0.100")
            print(f"\033[1;32m[POLICY APPLIED] Traffic from {ip} to 10.0.0.100 is now BLOCKED on {self.r_name}.\033[0m")
            print(f"\033[1;33m[CONTROLLER TELEMETRY] Controller notified. Dynamic re-routing analysis active.\033[0m")
            print("  * Type \033[1;32mreroutes\033[0m to view how the controller is steering traffic.")
            print("  * Type \033[1;31missues\033[0m to inspect the operational & security risks.")
        else:
            print(f"\033[1;31mFailed to add block rule: {err}\033[0m")

    def do_allow(self, arg):
        """Unblock traffic from a client IP: allow <ip>"""
        ip = arg.strip()
        if not ip:
            print("Usage: allow <ip>  (e.g. allow 10.0.0.2)")
            return
        cmd_call = [
            "ovs-ofctl", "-O", "OpenFlow13", "--strict", "del-flows", self.sw_id,
            f"priority=100,ip,nw_src={ip},nw_dst=10.0.0.100"
        ]
        code, out, err = run_cmd(cmd_call)
        if code == 0:
            policy.remove_block(self.sw_id, ip, "10.0.0.100")
            print(f"\033[1;32m[POLICY REMOVED] Traffic from {ip} to 10.0.0.100 is now ALLOWED on {self.r_name}.\033[0m")
            print(f"\033[1;33m[CONTROLLER TELEMETRY] Controller notified. Bypasses cleared, normal routing restored.\033[0m")
        else:
            print(f"\033[1;31mFailed to remove block rule: {err}\033[0m")

    def do_reroutes(self, arg):
        """View controller dynamic re-routes and active bypass flows."""
        data = policy.load_reroutes()
        print(policy.format_reroutes_table(data))

    def do_issues(self, arg):
        """View risk analysis and operational issues caused by router blocks."""
        data = policy.load_reroutes()
        print(policy.format_issues_table(data))


    def do_cut_link(self, arg):
        """Simulate link down: cut-link <port_num> (e.g. cut-link 4)"""
        port = arg.strip()
        if not port:
            print("Usage: cut-link <port_number> (e.g. cut-link 4)")
            return
        iface = f"{self.sw_id}-eth{port}"
        code, out, err = run_cmd(["ip", "link", "set", iface, "down"])
        if code == 0:
            print(f"\033[1;31m[LINK CUT] Interface {iface} (Port {port}) set to DOWN. Fast-failover triggered!\033[0m")
        else:
            print(f"\033[1;31mFailed to bring down {iface}: {err}\033[0m")

    def do_up_link(self, arg):
        """Restore link: up-link <port_num> (e.g. up-link 4)"""
        port = arg.strip()
        if not port:
            print("Usage: up-link <port_number> (e.g. up-link 4)")
            return
        iface = f"{self.sw_id}-eth{port}"
        code, out, err = run_cmd(["ip", "link", "set", iface, "up"])
        if code == 0:
            print(f"\033[1;32m[LINK RESTORED] Interface {iface} (Port {port}) set to UP. Path restored!\033[0m")
        else:
            print(f"\033[1;31mFailed to bring up {iface}: {err}\033[0m")

    def do_monitor(self, arg):
        """Continuously monitor flows, groups, and ports (Ctrl+C to stop)."""
        print("\033[1;33mStarting live monitor (Press Ctrl+C to exit monitor)...\033[0m")
        try:
            while True:
                os.system("clear")
                print(f"\033[1;36m=== LIVE MONITOR: {self.r_name} ({self.sw_id}) === {time.strftime('%H:%M:%S')} ===\033[0m")
                self.do_ports("")
                print()
                self.do_groups("")
                print()
                self.do_flows("")
                time.sleep(1.5)
        except KeyboardInterrupt:
            print("\n\033[1;32mMonitor stopped.\033[0m\n")

    def do_bash(self, arg):
        """Drop into a bash subshell."""
        print(f"\033[1;33mEntering bash shell for {self.r_name}. Type 'exit' to return to router console.\033[0m")
        subprocess.run(["bash"])

    def default(self, line):
        # Allow running normal Linux shell commands directly
        res = os.system(line)
        if res != 0:
            pass

    def do_exit(self, arg):
        """Exit router console."""
        print(f"Exiting {self.r_name} console.")
        return True

    def do_quit(self, arg):
        """Exit router console."""
        return self.do_exit(arg)

    def do_EOF(self, arg):
        print()
        return True

    # Aliases
    do_routes = do_flows
    do_show = do_flows
    do_block_ip = do_block
    do_allow_ip = do_allow


def main():
    target = sys.argv[1].lower() if len(sys.argv) > 1 else "s1"
    target = ALIAS_MAP.get(target, target)
    if target not in ROUTER_INFO:
        print(f"Unknown router '{target}'. Available: s1 (r1), s2 (r2), s3 (r3), s4 (r4)")
        sys.exit(1)
    cli = RouterCLI(target)
    cli.banner()
    cli.cmdloop()


if __name__ == "__main__":
    main()
