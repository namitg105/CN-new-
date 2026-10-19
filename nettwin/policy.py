"""Policy management and telemetry state for NetTwin-SDN.

Tracks blocked IPs across routers, shares state between router CLIs and the
Ryu controller, and formats diagnostic tables for the interactive consoles.

Compatible with Python 3.9+ (Ryu virtualenv and system Python).
"""
import json
import os
import time

POLICY_FILE = "/tmp/netwin_policy.json"
REROUTES_FILE = "/tmp/netwin_reroutes.json"


def _safe_write_json(file_path, data):
    tmp_path = file_path + ".tmp"
    try:
        with open(tmp_path, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, file_path)
        try:
            os.chmod(file_path, 0o666)
        except OSError:
            pass
    except Exception as e:
        pass


def load_policy(path=POLICY_FILE):
    """Load list of blocked rules: [{'switch': 's2', 'src_ip': '10.0.0.2', ...}]."""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r") as f:
            content = json.load(f)
            if isinstance(content, list):
                return content
            elif isinstance(content, dict) and "blocks" in content:
                return content["blocks"]
            return []
    except Exception:
        return []


def save_policy(blocks, path=POLICY_FILE):
    """Save list of blocked rules to JSON file."""
    _safe_write_json(path, blocks)


def add_block(switch, src_ip, dst_ip="10.0.0.100", path=POLICY_FILE):
    """Register an IP block rule."""
    blocks = load_policy(path)
    # Check if already present
    for entry in blocks:
        if entry.get("switch") == switch and entry.get("src_ip") == src_ip and entry.get("dst_ip") == dst_ip:
            return blocks
    blocks.append({
        "switch": switch,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "timestamp": time.time(),
        "time_str": time.strftime("%H:%M:%S")
    })
    save_policy(blocks, path)
    return blocks


def remove_block(switch, src_ip, dst_ip="10.0.0.100", path=POLICY_FILE):
    """Unregister an IP block rule."""
    blocks = load_policy(path)
    new_blocks = [
        entry for entry in blocks
        if not (entry.get("switch") == switch and entry.get("src_ip") == src_ip and entry.get("dst_ip") == dst_ip)
    ]
    save_policy(new_blocks, path)
    return new_blocks


def load_reroutes(path=REROUTES_FILE):
    """Load controller active reroutes and issues analysis."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_reroutes(data, path=REROUTES_FILE):
    """Save controller active reroutes and issues analysis."""
    _safe_write_json(path, data)


def format_reroutes_table(data):
    """Format active re-routes for CLI display."""
    if not data or not data.get("reroutes"):
        return "\033[1;32m[+] All traffic running on normal Fast-Failover paths. No per-IP blocks or overrides.\033[0m"

    reroutes = data.get("reroutes", {})
    lines = []
    lines.append("\033[1;36m" + "=" * 74 + "\033[0m")
    lines.append("\033[1;33m       SDN CONTROLLER ACTIVE RE-ROUTING STATUS & PATH OVERRIDES\033[0m")
    lines.append("\033[1;36m" + "=" * 74 + "\033[0m")

    for ip, info in reroutes.items():
        status = info.get("status", "UNKNOWN")
        target = info.get("target", "10.0.0.100")
        blocked_on = ", ".join(info.get("blocked_on", []))
        active_path = info.get("active_path", "NONE")
        flow_path = info.get("flow_path", "")

        status_color = "\033[1;32m" if "REROUTED" in status else "\033[1;31m"
        lines.append(f"  \033[1;37mClient IP      :\033[0m \033[1;33m{ip}\033[0m -> Destination: {target}")
        lines.append(f"  \033[1;37mBlocked On     :\033[0m \033[1;31m{blocked_on}\033[0m")
        lines.append(f"  \033[1;37mStatus         :\033[0m {status_color}{status}\033[0m")
        lines.append(f"  \033[1;37mCore Path      :\033[0m Path {active_path}")
        if flow_path:
            lines.append(f"  \033[1;37mForwarding Path:\033[0m \033[1;34m{flow_path}\033[0m")
        lines.append("\033[1;36m" + "-" * 74 + "\033[0m")

    lines.append("  \033[0;37mType \033[1;32missues\033[0;37m to inspect detailed risk and operational analysis.\033[0m")
    lines.append("\033[1;36m" + "=" * 74 + "\033[0m")
    return "\n".join(lines)


def format_issues_table(data):
    """Format detailed possible issues and operational risks for CLI display."""
    if not data or not data.get("reroutes"):
        return "\033[1;32m[+] Network healthy. No active router blocks or re-routing risks detected.\033[0m"

    reroutes = data.get("reroutes", {})
    lines = []
    lines.append("\033[1;31m" + "=" * 74 + "\033[0m")
    lines.append("\033[1;31m  [!] SDN CONTROLLER TELEMETRY: RE-ROUTING RISK & IMPACT ANALYSIS\033[0m")
    lines.append("\033[1;31m" + "=" * 74 + "\033[0m")

    for ip, info in reroutes.items():
        lines.append(f"  \033[1;33mTarget IP: {ip} | Blocked on: {', '.join(info.get('blocked_on', []))}\033[0m")
        issues = info.get("issues", [])
        if not issues:
            lines.append("    (No specific operational issues recorded)")
        for idx, issue in enumerate(issues, 1):
            category = issue.get("category", "")
            title = issue.get("title", "")
            desc = issue.get("desc", "")
            lines.append(f"  \033[1;31m{idx}. {title}\033[0m \033[0;37m[{category}]\033[0m")
            lines.append(f"     \033[0;37m{desc}\033[0m")
        lines.append("\033[1;31m" + "-" * 74 + "\033[0m")

    lines.append("\033[1;31m" + "=" * 74 + "\033[0m")
    return "\n".join(lines)
