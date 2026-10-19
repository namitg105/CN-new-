#!/usr/bin/env python3
"""Terminal launcher for NetTwin-SDN:
Spawns 3 Systems (c1, c2, c3), 3 Routers (s1, s2, s3), and 1 Main Server (srv).

Supports both X11 (xterm) GUI mode and tmux terminal multiplexer mode.
"""
import argparse
import json
import os
import subprocess
import sys
import time

PROJECT_DIR = "/home/kalis/nettwin"
NODES_FILE = "/tmp/netwin_nodes.json"
PID_TRACKER = "/tmp/netwin_terminals.pids"


def save_node_pids(net):
    """Save mininet host PIDs to /tmp/netwin_nodes.json for external launchers."""
    data = {}
    for name in ["c1", "c2", "c3", "srv"]:
        try:
            h = net.get(name)
            data[name] = {"pid": h.pid, "ip": h.IP()}
        except Exception:
            pass
    with open(NODES_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_node_pid(node_name):
    """Get PID of a mininet host node."""
    if os.path.exists(NODES_FILE):
        try:
            with open(NODES_FILE) as f:
                data = json.load(f)
                if node_name in data and "pid" in data[node_name]:
                    pid = data[node_name]["pid"]
                    # verify process still exists
                    if os.path.exists(f"/proc/{pid}"):
                        return pid
        except Exception:
            pass
    # Fallback to pgrep
    res = subprocess.run(["pgrep", "-f", f"mininet:{node_name}"], stdout=subprocess.PIPE, text=True)
    pids = res.stdout.strip().split()
    if pids:
        return int(pids[0])
    return None


def launch_xterms(include_router4=True, include_controller=True):
    """Launch 7 (or more) dedicated xterm windows arranged across screen."""
    display = os.environ.get("DISPLAY", ":0.0")
    os.environ["DISPLAY"] = display

    pids_spawned = []

    # Verify nodes
    for node in ["c1", "c2", "c3", "srv"]:
        pid = get_node_pid(node)
        if not pid:
            print(f"[!] Warning: Mininet host '{node}' process not found. Is Mininet running?")

    # Definition of the 7+ terminals:
    # (Category, Title, Geometry, BG, FG, Command)
    terminals = [
        # --- 3 SYSTEMS ---
        (
            "system",
            "System 1 (c1 - 10.0.0.1)",
            "74x17+10+10",
            "#0d1f18", "#70e000",
            f"sudo mnexec -a {get_node_pid('c1') or '$$'} env SYS_NAME=c1 SYS_IP=10.0.0.1 bash --rcfile {PROJECT_DIR}/nettwin/system_env.sh -i"
        ),
        (
            "system",
            "System 2 (c2 - 10.0.0.2)",
            "74x17+10+325",
            "#0d1f18", "#70e000",
            f"sudo mnexec -a {get_node_pid('c2') or '$$'} env SYS_NAME=c2 SYS_IP=10.0.0.2 bash --rcfile {PROJECT_DIR}/nettwin/system_env.sh -i"
        ),
        (
            "system",
            "System 3 (c3 - 10.0.0.3)",
            "74x17+10+640",
            "#0d1f18", "#70e000",
            f"sudo mnexec -a {get_node_pid('c3') or '$$'} env SYS_NAME=c3 SYS_IP=10.0.0.3 bash --rcfile {PROJECT_DIR}/nettwin/system_env.sh -i"
        ),

        # --- 3 ROUTERS ---
        (
            "router",
            "Router 1 (s1 - Ingress Router)",
            "74x17+650+10",
            "#221608", "#ffb703",
            f"python3 -m nettwin.router_cli s1"
        ),
        (
            "router",
            "Router 2 (s2 - Path A Core)",
            "74x17+650+325",
            "#221608", "#ffb703",
            f"python3 -m nettwin.router_cli s2"
        ),
        (
            "router",
            "Router 3 (s3 - Path B Core)",
            "74x17+650+640",
            "#221608", "#ffb703",
            f"python3 -m nettwin.router_cli s3"
        ),

        # --- 1 MAIN SERVER ---
        (
            "server",
            "Main Server (srv - 10.0.0.100)",
            "74x17+1290+10",
            "#0b1d28", "#38b000",
            f"sudo mnexec -a {get_node_pid('srv') or '$$'} bash --rcfile {PROJECT_DIR}/nettwin/server_env.sh -i"
        ),
    ]

    if include_controller:
        terminals.append((
            "controller",
            "Ryu Controller Live Telemetry Monitor",
            "74x17+1290+325",
            "#1c1124", "#e0aaff",
            "bash -c 'echo \"=== RYU CONTROLLER LOG MONITOR ===\"; tail -f -n 50 /tmp/ryu.log 2>/dev/null || (sleep 2 && tail -f /tmp/ryu.log)'"
        ))

    if include_router4:
        terminals.append((
            "router",
            "Router 4 (s4 - Egress Router)",
            "74x17+1290+640",
            "#221608", "#ffb703",
            f"python3 -m nettwin.router_cli s4"
        ))

    print(f"[*] Spawning {len(terminals)} dedicated terminal windows on display {display}...")

    for category, title, geom, bg, fg, cmd_str in terminals:
        full_cmd = [
            "xterm",
            "-title", title,
            "-geometry", geom,
            "-bg", bg,
            "-fg", fg,
            "-fa", "Monospace",
            "-fs", "10",
            "-e", "bash", "-c", cmd_str
        ]
        proc = subprocess.Popen(full_cmd)
        pids_spawned.append(proc.pid)
        time.sleep(0.12)

    try:
        with open(PID_TRACKER, "w") as f:
            f.write("\n".join(str(p) for p in pids_spawned))
        os.chmod(PID_TRACKER, 0o666)
    except Exception:
        try:
            pid_content = "\n".join(str(p) for p in pids_spawned)
            subprocess.run(["sudo", "rm", "-f", PID_TRACKER], check=False)
            subprocess.run(["sudo", "bash", "-c", f"cat << 'EOF' > {PID_TRACKER}\n{pid_content}\nEOF\nchmod 666 {PID_TRACKER}"], check=False)
        except Exception:
            pass

    print("[+] All terminals launched successfully!")
    print("    - 3 System Terminals (c1, c2, c3)")
    print("    - 3 Router Terminals (Router-1 [s1], Router-2 [s2], Router-3 [s3])")
    print("    - 1 Main Server Terminal (srv)")
    if include_controller:
        print("    - 1 Ryu Controller Monitor Terminal")
    if include_router4:
        print("    - 1 Router-4 Egress Terminal")


def launch_tmux():
    """Launch terminals inside a structured tmux session."""
    session = "netwin-sdn"
    subprocess.run(["tmux", "kill-session", "-t", session], stderr=subprocess.DEVNULL)

    c1_pid = get_node_pid("c1") or "$$"
    c2_pid = get_node_pid("c2") or "$$"
    c3_pid = get_node_pid("c3") or "$$"
    srv_pid = get_node_pid("srv") or "$$"

    # 1. Window: Systems (3 vertical panes)
    subprocess.run([
        "tmux", "new-session", "-d", "-s", session, "-n", "systems",
        f"sudo mnexec -a {c1_pid} env SYS_NAME=c1 SYS_IP=10.0.0.1 bash --rcfile {PROJECT_DIR}/nettwin/system_env.sh -i"
    ])
    subprocess.run([
        "tmux", "split-window", "-h", "-t", f"{session}:systems",
        f"sudo mnexec -a {c2_pid} env SYS_NAME=c2 SYS_IP=10.0.0.2 bash --rcfile {PROJECT_DIR}/nettwin/system_env.sh -i"
    ])
    subprocess.run([
        "tmux", "split-window", "-h", "-t", f"{session}:systems",
        f"sudo mnexec -a {c3_pid} env SYS_NAME=c3 SYS_IP=10.0.0.3 bash --rcfile {PROJECT_DIR}/nettwin/system_env.sh -i"
    ])
    subprocess.run(["tmux", "select-layout", "-t", f"{session}:systems", "even-horizontal"])

    # 2. Window: Routers (3 vertical panes)
    subprocess.run([
        "tmux", "new-window", "-t", session, "-n", "routers",
        f"python3 -m nettwin.router_cli s1"
    ])
    subprocess.run([
        "tmux", "split-window", "-h", "-t", f"{session}:routers",
        f"python3 -m nettwin.router_cli s2"
    ])
    subprocess.run([
        "tmux", "split-window", "-h", "-t", f"{session}:routers",
        f"python3 -m nettwin.router_cli s3"
    ])
    subprocess.run(["tmux", "select-layout", "-t", f"{session}:routers", "even-horizontal"])

    # 3. Window: Server
    subprocess.run([
        "tmux", "new-window", "-t", session, "-n", "server",
        f"sudo mnexec -a {srv_pid} bash --rcfile {PROJECT_DIR}/nettwin/server_env.sh -i"
    ])

    # 4. Window: Controller Monitor
    subprocess.run([
        "tmux", "new-window", "-t", session, "-n", "controller",
        "tail -f /tmp/ryu.log"
    ])

    print(f"[+] Created tmux session '{session}' with 4 windows:")
    print("    1. 'systems'    : 3 panes (System 1, System 2, System 3)")
    print("    2. 'routers'    : 3 panes (Router 1, Router 2, Router 3)")
    print("    3. 'server'     : Main Server terminal")
    print("    4. 'controller' : Ryu Controller log monitor")
    print(f"\nAttach anytime using:  tmux attach -t {session}")


def kill_terminals():
    """Kill previously spawned xterm windows."""
    if os.path.exists(PID_TRACKER):
        try:
            with open(PID_TRACKER) as f:
                for line in f:
                    p = line.strip()
                    if p:
                        os.system(f"kill -9 {p} 2>/dev/null")
            os.remove(PID_TRACKER)
        except Exception:
            pass
    os.system("pkill -f 'RouterCLI' 2>/dev/null")
    os.system("pkill -f 'system_env.sh' 2>/dev/null")
    os.system("pkill -f 'server_env.sh' 2>/dev/null")
    print("[+] Terminals stopped.")


def main():
    parser = argparse.ArgumentParser(description="NetTwin-SDN Terminals Manager")
    parser.add_argument("--tmux", action="store_true", help="Launch in tmux session instead of X11 xterm")
    parser.add_argument("--kill", action="store_true", help="Kill all active terminal windows")
    parser.add_argument("--with-r4", action="store_true", help="Also include Router 4 (s4) window")
    args = parser.parse_args()

    if args.kill:
        kill_terminals()
        return

    if args.tmux:
        launch_tmux()
    else:
        launch_xterms(include_router4=args.with_r4)


if __name__ == "__main__":
    main()
