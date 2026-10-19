"""Start the network and open the Mininet CLI:  sudo python3 -m nettwin.network"""
import argparse
import subprocess
import time

from mininet.cli import CLI
from mininet.log import setLogLevel

from nettwin import policy
from nettwin.network.builder import build
from nettwin.terminals import save_node_pids, launch_xterms, launch_tmux, kill_terminals



class NetTwinCLI(CLI):
    prompt = "netwin> "

    def __init__(self, mininet, *args, **kwargs):
        save_node_pids(mininet)
        print("\n\033[1;36m" + "=" * 68 + "\033[0m")
        print("\033[1;32m  NetTwin-SDN Interactive Controller & Network CLI\033[0m")
        print("\033[1;36m" + "=" * 68 + "\033[0m")
        print("  \033[1;33mTerminal Commands:\033[0m")
        print("    \033[1;37mterminals\033[0m      - Spawn 7 dedicated terminals (3 systems, 3 routers, 1 server)")
        print("    \033[1;37mtmux\033[0m           - Create a 4-window tmux dashboard for all nodes")
        print("    \033[1;37mkillterminals\033[0m  - Close all opened terminal windows")
        print("  \033[1;33mQuick Server & Traffic Commands:\033[0m")
        print("    \033[1;37mstartserver\033[0m    - Start Flask web server on srv (10.0.0.100:5000)")
        print("    \033[1;37mstopserver\033[0m     - Stop Flask server on srv (simulate server crash)")
        print("    \033[1;37mstarttraffic\033[0m   - Start recurring background HTTP traffic from c1, c2, c3")
        print("    \033[1;37mcutlink\033[0m        - Cut primary link s1 <-> s2 (trigger failover to Path B)")
        print("    \033[1;37mrestorelink\033[0m    - Restore primary link s1 <-> s2 (return to Path A)")
        print("  \033[1;33mPolicy & Re-routing Commands:\033[0m")
        print("    \033[1;37mblock <r> <ip>\033[0m - Block IP on router (e.g. block s2 10.0.0.2)")
        print("    \033[1;37mallow <r> <ip>\033[0m - Unblock IP on router (e.g. allow s2 10.0.0.2)")
        print("    \033[1;37mreroutes\033[0m       - View active controller re-routes and bypass paths")
        print("    \033[1;37missues\033[0m         - View risk analysis & operational issues of re-routing")
        print("\033[1;36m" + "=" * 68 + "\033[0m\n")
        super().__init__(mininet, *args, **kwargs)

    def do_terminals(self, line):
        """Spawn all 7 dedicated terminals: 3 systems, 3 routers, 1 main server."""
        save_node_pids(self.mn)
        with_r4 = "--with-r4" in line
        launch_xterms(include_router4=with_r4)

    def do_xterms(self, line):
        """Alias for terminals: xterms"""
        self.do_terminals(line)

    def do_tmux(self, line):
        """Spawn all nodes inside a tiled tmux session: tmux"""
        save_node_pids(self.mn)
        launch_tmux()

    def do_killterminals(self, line):
        """Close opened terminal windows: killterminals"""
        kill_terminals()

    def do_startserver(self, line):
        """Start Flask application server on srv: startserver"""
        srv = self.mn.get("srv")
        srv.cmd("python3 -m nettwin.server.app > /tmp/server.log 2>&1 &")
        time.sleep(1)
        res = srv.cmd("curl -s http://127.0.0.1:5000/health")
        print(f"[+] Server started: {res.strip()}")

    def do_stopserver(self, line):
        """Stop Flask application server on srv: stopserver"""
        srv = self.mn.get("srv")
        srv.cmd("pkill -f nettwin.server.app")
        print("[-] Flask server stopped (Application crash simulated)")

    def do_starttraffic(self, line):
        """Start client background HTTP traffic from c1, c2, c3: starttraffic"""
        for c in ["c1", "c2", "c3"]:
            host = self.mn.get(c)
            host.cmd(f"bash /home/kalis/nettwin/scripts/client.sh {c} > /tmp/{c}.log 2>&1 &")
        print("[+] Background traffic started on c1, c2, c3. Logs at /tmp/c*.log")

    def do_cutlink(self, line):
        """Cut the primary path link s1 <-> s2: cutlink"""
        print("[*] Cutting primary link s1 <-> s2...")
        self.mn.configLinkStatus("s1", "s2", "down")
        print("[+] Link s1 <-> s2 is DOWN. Watch traffic failover to Path B!")

    def do_restorelink(self, line):
        """Restore the primary path link s1 <-> s2: restorelink"""
        print("[*] Restoring primary link s1 <-> s2...")
        self.mn.configLinkStatus("s1", "s2", "up")
        print("[+] Link s1 <-> s2 is UP. Watch traffic return to Path A!")

    def do_block(self, line):
        """Block a client IP on a router: block [router] <ip> (e.g. block s2 10.0.0.2)"""
        parts = line.strip().split()
        if not parts:
            print("Usage: block [router] <ip>  (e.g. block s2 10.0.0.2  or  block 10.0.0.2)")
            return
        if len(parts) == 1:
            router = "s2"
            ip = parts[0]
        else:
            router = parts[0]
            ip = parts[1]
        cmd = f"ovs-ofctl -O OpenFlow13 add-flow {router} 'priority=100,ip,nw_src={ip},nw_dst=10.0.0.100,actions=drop'"
        subprocess.run(["sudo", "bash", "-c", cmd])
        policy.add_block(router, ip, "10.0.0.100")
        print(f"\033[1;32m[+] Traffic from {ip} blocked on {router}.\033[0m")
        print(f"\033[1;33m[*] Controller notified. Check controller window or type 'reroutes' / 'issues'.\033[0m")

    def do_allow(self, line):
        """Unblock a client IP on a router: allow [router] <ip> (e.g. allow s2 10.0.0.2)"""
        parts = line.strip().split()
        if not parts:
            print("Usage: allow [router] <ip>  (e.g. allow s2 10.0.0.2  or  allow 10.0.0.2)")
            return
        if len(parts) == 1:
            router = "s2"
            ip = parts[0]
        else:
            router = parts[0]
            ip = parts[1]
        cmd = f"ovs-ofctl -O OpenFlow13 --strict del-flows {router} 'priority=100,ip,nw_src={ip},nw_dst=10.0.0.100'"
        subprocess.run(["sudo", "bash", "-c", cmd])
        policy.remove_block(router, ip, "10.0.0.100")
        print(f"\033[1;32m[+] Block removed for {ip} on {router}. Default routing restored.\033[0m")

    def do_reroutes(self, line):
        """Display controller active re-routes and bypass paths: reroutes"""
        data = policy.load_reroutes()
        print(policy.format_reroutes_table(data))

    def do_issues(self, line):
        """Display risk and operational impact analysis of re-routing: issues"""
        data = policy.load_reroutes()
        print(policy.format_issues_table(data))



def main():
    parser = argparse.ArgumentParser(description="Start the NetTwin-SDN virtual network.")
    parser.add_argument("--datapath", choices=("kernel", "user"), default="kernel",
                        help="Open vSwitch datapath; use 'user' if the kernel lacks "
                             "the openvswitch module (default: kernel)")
    parser.add_argument("--terminals", "-t", action="store_true",
                        help="Automatically spawn the 7 terminals (3 systems, 3 routers, 1 server)")
    parser.add_argument("--tmux", action="store_true",
                        help="Automatically spawn all terminals in a tmux dashboard")
    args = parser.parse_args()

    setLogLevel("info")
    net = build(datapath=args.datapath)
    net.start()
    save_node_pids(net)

    if args.terminals:
        time.sleep(1)
        # Start Flask server and client background traffic automatically
        srv = net.get("srv")
        srv.cmd("python3 -m nettwin.server.app > /tmp/server.log 2>&1 &")
        time.sleep(0.5)
        for c in ["c1", "c2", "c3"]:
            host = net.get(c)
            host.cmd(f"bash /home/kalis/nettwin/scripts/client.sh {c} > /tmp/{c}.log 2>&1 &")
        launch_xterms(include_router4=True)
    elif args.tmux:
        time.sleep(1)
        srv = net.get("srv")
        srv.cmd("python3 -m nettwin.server.app > /tmp/server.log 2>&1 &")
        for c in ["c1", "c2", "c3"]:
            host = net.get(c)
            host.cmd(f"bash /home/kalis/nettwin/scripts/client.sh {c} > /tmp/{c}.log 2>&1 &")
        launch_tmux()

    try:
        NetTwinCLI(net)
    finally:
        kill_terminals()
        net.stop()


if __name__ == "__main__":
    main()
