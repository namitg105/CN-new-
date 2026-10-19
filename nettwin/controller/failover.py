"""Link-health bookkeeping, path ranking, and policy-based re-routing logic.

Pure logic with no OpenFlow or Ryu imports, so it can be unit tested anywhere.
"""
from nettwin import netmodel


class LinkHealth:
    """Remembers which (dpid, port) links are down and ranks the core paths.

    A path is unhealthy as soon as any one of its ports is down. Healthy paths
    are ranked ahead of unhealthy ones; ties keep the declared order, so the
    primary path wins whenever it is usable.
    """

    def __init__(self, path_ports):
        """`path_ports` maps a path name to the (dpid, port) pairs on it."""
        self._path_ports = dict(path_ports)
        self._down = set()

    def set_link_down(self, dpid, port, down):
        if down:
            self._down.add((dpid, port))
        else:
            self._down.discard((dpid, port))

    def forget_switch(self, dpid):
        """Drop stale state for a switch that has just (re)connected."""
        self._down = {link for link in self._down if link[0] != dpid}

    def is_path_healthy(self, path_name):
        return not (self._down & self._path_ports[path_name])

    def ranked_paths(self):
        """Path names, best first (healthy before unhealthy, declared order)."""
        return sorted(self._path_ports, key=lambda name: not self.is_path_healthy(name))


class PolicyDecision:
    """Encapsulates a controller re-routing decision and its risk analysis."""

    def __init__(self, src_ip, dst_ip, blocked_on, status, active_path,
                 flow_path, reroute_rules, issues):
        self.src_ip = src_ip
        self.dst_ip = dst_ip
        self.blocked_on = list(blocked_on)
        self.status = status
        self.active_path = active_path
        self.flow_path = flow_path
        self.reroute_rules = dict(reroute_rules)  # switch -> {"out_port": int}
        self.issues = list(issues)

    def to_dict(self):
        return {
            "src_ip": self.src_ip,
            "target": self.dst_ip,
            "blocked_on": self.blocked_on,
            "status": self.status,
            "active_path": self.active_path,
            "flow_path": self.flow_path,
            "reroute_rules": self.reroute_rules,
            "issues": self.issues,
        }


class PolicyReRouteManager:
    """Evaluates router IP blocking policies and calculates dynamic re-routes.

    When one router (e.g. s2 / Path A core) blocks an IP, this manager:
    1. Checks if alternate transit paths (e.g. s3 / Path B) are healthy and unblocked.
    2. Determines the exact forwarding ports to steer traffic around the blocking switch.
    3. Identifies edge chokepoints (s1 ingress or s4 egress blocks) where bypass is physically impossible.
    4. Compiles a comprehensive risk and impact analysis detailing:
       - Security policy circumvention (ACL evasion)
       - Flow asymmetry and stateful middlebox disruption
       - Standby path bandwidth contention / QoS degradation
       - Hardware TCAM / flow table consumption
       - High-availability redundancy loss
    """

    def __init__(self, target_ip="10.0.0.100"):
        self.target_ip = target_ip
        # map (switch, src_ip) -> dict of metadata
        self._blocks = {}

    def set_block(self, switch, src_ip, dst_ip=None):
        dst = dst_ip or self.target_ip
        self._blocks[(switch, src_ip)] = {"switch": switch, "src_ip": src_ip, "dst_ip": dst}

    def remove_block(self, switch, src_ip):
        self._blocks.pop((switch, src_ip), None)

    def clear(self):
        self._blocks.clear()

    def sync_blocks(self, block_entries):
        """Sync internal block table from external list of dicts."""
        self._blocks.clear()
        for b in block_entries:
            sw = b.get("switch")
            ip = b.get("src_ip")
            dst = b.get("dst_ip", self.target_ip)
            if sw and ip:
                self._blocks[(sw, ip)] = {"switch": sw, "src_ip": ip, "dst_ip": dst}

    def get_blocked_ips(self):
        return sorted(list({src_ip for (_, src_ip) in self._blocks}))

    def get_switches_blocking_ip(self, src_ip):
        return sorted([sw for (sw, ip) in self._blocks if ip == src_ip])

    def evaluate(self, src_ip, link_health):
        """Evaluate re-routing for a specific client IP given current link health."""
        blocking_switches = self.get_switches_blocking_ip(src_ip)
        if not blocking_switches:
            return None

        # Check for host name
        host_name = "client"
        for name, ip in netmodel.HOSTS.items():
            if ip == src_ip:
                host_name = name
                break

        # 1. Edge switch blocks: s1 (Ingress)
        if "s1" in blocking_switches:
            flow_path = f"{host_name} ({src_ip}) -> [X Port 1/2/3 DROP at s1] -> NO TRAFFIC LEAVES INGRESS"
            issues = [
                {
                    "category": "INGRESS_EDGE_ISOLATION",
                    "title": "Complete First-Hop Client Isolation",
                    "desc": f"Router-1 (s1) is the physical edge access gateway for {src_ip}. "
                            "Packets are dropped at the ingress port before entering the switching fabric.",
                },
                {
                    "category": "FAILOVER_INEFFECTIVE",
                    "title": "Multi-Path SDN Core Redundancy Ineffective",
                    "desc": "SDN dynamic core failover cannot bypass an ingress edge drop policy; "
                            "no alternate physical link exists from the host.",
                },
            ]
            return PolicyDecision(
                src_ip=src_ip,
                dst_ip=self.target_ip,
                blocked_on=blocking_switches,
                status="IMPOSSIBLE: INGRESS EDGE ISOLATION",
                active_path="NONE",
                flow_path=flow_path,
                reroute_rules={},
                issues=issues,
            )

        # 2. Edge switch blocks: s4 (Egress)
        if "s4" in blocking_switches:
            flow_path = f"{host_name} ({src_ip}) -> s1 -> [s2/s3] -> [X Port 3 DROP at s4] -> srv unreachable"
            issues = [
                {
                    "category": "EGRESS_EDGE_CHOKEPOINT",
                    "title": "Egress Destination Access Chokepoint",
                    "desc": "Router-4 (s4) is the sole gateway to the destination server (10.0.0.100). "
                            "All core paths converge on s4, so traffic is dropped regardless of core transit path.",
                },
                {
                    "category": "DESTINATION_UNREACHABLE",
                    "title": "Total Server Denial",
                    "desc": "Both Path A and Path B terminate at s4; egress blocking completely denies communication.",
                },
            ]
            return PolicyDecision(
                src_ip=src_ip,
                dst_ip=self.target_ip,
                blocked_on=blocking_switches,
                status="IMPOSSIBLE: EGRESS EDGE CHOKEPOINT",
                active_path="NONE",
                flow_path=flow_path,
                reroute_rules={},
                issues=issues,
            )

        # 3. Both core transit routers block: s2 and s3
        if "s2" in blocking_switches and "s3" in blocking_switches:
            flow_path = f"{host_name} ({src_ip}) -> s1 -> [X BLOCKED on s2 (Path A) & s3 (Path B)] -> s4"
            issues = [
                {
                    "category": "ALL_TRANSIT_PATHS_BLOCKED",
                    "title": "Complete Core Transit Denial",
                    "desc": "Both Core Router-2 (Path A) and Core Router-3 (Path B) have active drop policies. "
                            "No healthy transit path remains between Ingress (s1) and Egress (s4).",
                },
                {
                    "category": "TOTAL_BLACKOUT",
                    "title": "Traffic Blackholed",
                    "desc": "Traffic from this client is completely dropped in the core network.",
                },
            ]
            return PolicyDecision(
                src_ip=src_ip,
                dst_ip=self.target_ip,
                blocked_on=blocking_switches,
                status="IMPOSSIBLE: ALL CORE PATHS BLOCKED",
                active_path="NONE",
                flow_path=flow_path,
                reroute_rules={},
                issues=issues,
            )

        # 4. Router-2 (Path A) blocks: Can we re-route to Path B (s3)?
        if "s2" in blocking_switches:
            path_b_healthy = link_health.is_path_healthy("B")
            if path_b_healthy:
                port_s1 = netmodel.uplink_port("s1", "B")  # Port 5 -> s3
                port_s4 = netmodel.uplink_port("s4", "B")  # Port 2 -> s3
                flow_path = (
                    f"{host_name} ({src_ip}) -> [Port 1/2/3] s1 [BYPASS Port {port_s1}] "
                    f"-> [Port 1] s3 [Port 2] -> [Port {port_s4}] s4 [Port 3] -> srv (10.0.0.100)"
                )
                issues = [
                    {
                        "category": "SECURITY_BYPASS",
                        "title": "Security Policy Circumvention (ACL Evasion)",
                        "desc": "Router-2 applied a drop rule for this IP, but the SDN controller dynamically "
                                "diverted traffic around it via Router-3 (Path B). If Router-2 blocked this IP for "
                                "security reasons, the security policy is bypassed unless synchronized globally.",
                    },
                    {
                        "category": "ASYMMETRIC_ROUTING",
                        "title": "Asymmetric Routing & Stateful Inspection Disruption",
                        "desc": "Traffic for this client traverses Path B while other clients use Path A. "
                                "Flow asymmetry can break stateful firewalls, connection trackers, and NAT on Router-2.",
                    },
                    {
                        "category": "PATH_CONGESTION",
                        "title": "Standby Path B Contention (QoS Degradation)",
                        "desc": "Diverting blocked client flows onto backup Path B increases link utilization on s3, "
                                "risking contention and jitter for normal failover traffic.",
                    },
                    {
                        "category": "TCAM_OVERHEAD",
                        "title": "Switch Hardware TCAM / Flow Table Overhead",
                        "desc": "Requires fine-grained per-IP microflow override rules (priority 60) on edge switches "
                                "s1 & s4, consuming hardware TCAM instead of aggregated group tables.",
                    },
                    {
                        "category": "LOSS_OF_REDUNDANCY",
                        "title": "Zero High-Availability Redundancy Remaining",
                        "desc": "This client is now utilizing its secondary path with no fallback. If a link on Path B fails, "
                                "traffic cannot failover to Path A because Router-2 drops it, causing total outage.",
                    },
                ]
                return PolicyDecision(
                    src_ip=src_ip,
                    dst_ip=self.target_ip,
                    blocked_on=blocking_switches,
                    status="RE-ROUTED VIA PATH B (ROUTER-3)",
                    active_path="B",
                    flow_path=flow_path,
                    reroute_rules={
                        "s1": {"out_port": port_s1, "src_match": True},
                        "s4": {"out_port": port_s4, "dst_match": True},
                    },
                    issues=issues,
                )
            else:
                flow_path = f"{host_name} ({src_ip}) -> s1 -> [s2 BLOCKS, s3 LINK DOWN] -> NO PATH"
                issues = [
                    {
                        "category": "DOUBLE_FAULT_BLACKOUT",
                        "title": "Secondary Path Down During Primary Core Block",
                        "desc": "Router-2 has an active block on this IP, and Path B has a down link. "
                                "No healthy transit path exists.",
                    }
                ]
                return PolicyDecision(
                    src_ip=src_ip,
                    dst_ip=self.target_ip,
                    blocked_on=blocking_switches,
                    status="BLACKHOLED: PATH A BLOCKED & PATH B DOWN",
                    active_path="NONE",
                    flow_path=flow_path,
                    reroute_rules={},
                    issues=issues,
                )

        # 5. Router-3 (Path B) blocks: Primary Path A is available
        if "s3" in blocking_switches:
            path_a_healthy = link_health.is_path_healthy("A")
            port_s1 = netmodel.uplink_port("s1", "A")  # Port 4 -> s2
            port_s4 = netmodel.uplink_port("s4", "A")  # Port 1 -> s2
            if path_a_healthy:
                flow_path = (
                    f"{host_name} ({src_ip}) -> s1 [Port {port_s1}] "
                    f"-> [Port 1] s2 [Port 2] -> [Port {port_s4}] s4 [Port 3] -> srv (10.0.0.100)"
                )
                issues = [
                    {
                        "category": "LOSS_OF_REDUNDANCY",
                        "title": "Standby Failover Path Invalidated",
                        "desc": "Traffic currently runs on Primary Path A, but Router-3 (Path B) has blocked this IP. "
                                "If Path A experiences a link failure, this client CANNOT failover to Path B and will fail.",
                    },
                    {
                        "category": "SECURITY_CONSISTENCY",
                        "title": "Inconsistent Core Router Policy Enforcement",
                        "desc": "Router-3 is dropping traffic for this IP, but Router-2 is permitting it. "
                                "Security policy is inconsistent across the core fabric.",
                    },
                ]
                return PolicyDecision(
                    src_ip=src_ip,
                    dst_ip=self.target_ip,
                    blocked_on=blocking_switches,
                    status="HELD ON PRIMARY PATH A (BACKUP PATH B BLOCKED)",
                    active_path="A",
                    flow_path=flow_path,
                    reroute_rules={
                        "s1": {"out_port": port_s1, "src_match": True},
                        "s4": {"out_port": port_s4, "dst_match": True},
                    },
                    issues=issues,
                )
            else:
                flow_path = f"{host_name} ({src_ip}) -> s1 -> [s2 LINK DOWN, s3 BLOCKS] -> NO PATH"
                issues = [
                    {
                        "category": "FAILOVER_BLOCKED",
                        "title": "Failover Path Blocked During Link Cut",
                        "desc": "Path A link is down, and backup Router-3 is actively blocking this IP. "
                                "Failover is prevented by the router policy block.",
                    }
                ]
                return PolicyDecision(
                    src_ip=src_ip,
                    dst_ip=self.target_ip,
                    blocked_on=blocking_switches,
                    status="BLACKHOLED: PATH A DOWN & PATH B BLOCKED",
                    active_path="NONE",
                    flow_path=flow_path,
                    reroute_rules={},
                    issues=issues,
                )

        return None

    def evaluate_all(self, link_health):
        """Evaluate all currently known blocked IPs."""
        results = {}
        for ip in self.get_blocked_ips():
            dec = self.evaluate(ip, link_health)
            if dec:
                results[ip] = dec
        return results
