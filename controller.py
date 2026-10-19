from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.ofproto import ofproto_v1_3

SERVER = "10.0.0.100"
C1, C2, C3 = "10.0.0.1", "10.0.0.2", "10.0.0.3"

# Switches that choose between the two core paths (A = via s2, B = via s3).
# value = (port towards path A, port towards path B)
UPLINKS = {1: (4, 5), 4: (1, 2)}

# Destinations each switch can reach directly: {dpid: {ip: output port}}
DIRECT = {
    1: {C1: 1, C2: 2, C3: 3},
    2: {C1: 1, C2: 1, C3: 1, SERVER: 2},
    3: {C1: 1, C2: 1, C3: 1, SERVER: 2},
    4: {SERVER: 3},
}

# Destinations that s1 and s4 send into the failover group
VIA_GROUP = {1: [SERVER], 4: [C1, C2, C3]}

# Every (switch, port) that belongs to each path, used to judge path health
PATH_A = {(1, 4), (2, 1), (2, 2), (4, 1)}
PATH_B = {(1, 5), (3, 1), (3, 2), (4, 2)}

GROUP_ID = 1


class NetTwin(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dps = {}      # dpid -> datapath
        self.down = set()  # (dpid, port) pairs whose link is down

    # ---------- when a switch connects ----------
    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def on_connect(self, ev):
        dp = ev.msg.datapath
        self.dps[dp.id] = dp
        # forget any link state left over from a previous Mininet run
        self.down = {k for k in self.down if k[0] != dp.id}
        self.logger.info("switch s%d connected", dp.id)
        self.wipe(dp)
        if dp.id in UPLINKS:
            self.send_group(dp, dp.ofproto.OFPGC_ADD)
        self.install_flows(dp)

    def wipe(self, dp):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        dp.send_msg(parser.OFPFlowMod(
            dp, table_id=ofp.OFPTT_ALL, command=ofp.OFPFC_DELETE,
            out_port=ofp.OFPP_ANY, out_group=ofp.OFPG_ANY,
            match=parser.OFPMatch()))
        dp.send_msg(parser.OFPGroupMod(
            dp, ofp.OFPGC_DELETE, ofp.OFPGT_ALL, ofp.OFPG_ALL))

    # ---------- failover group (s1 and s4 only) ----------
    def port_order(self, dpid):
        a, b = UPLINKS[dpid]
        a_bad = bool(self.down & PATH_A)
        b_bad = bool(self.down & PATH_B)
        return [b, a] if (a_bad and not b_bad) else [a, b]

    def send_group(self, dp, command):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        buckets = [
            parser.OFPBucket(watch_port=p, watch_group=ofp.OFPG_ANY,
                             actions=[parser.OFPActionOutput(p)])
            for p in self.port_order(dp.id)
        ]
        dp.send_msg(parser.OFPGroupMod(
            dp, command, ofp.OFPGT_FF, GROUP_ID, buckets))

    # ---------- forwarding rules ----------
    def install_flows(self, dp):
        parser = dp.ofproto_parser
        for ip, port in DIRECT[dp.id].items():
            self.add_flow(dp, ip, [parser.OFPActionOutput(port)])
        for ip in VIA_GROUP.get(dp.id, []):
            self.add_flow(dp, ip, [parser.OFPActionGroup(GROUP_ID)])

    def add_flow(self, dp, dst_ip, actions, priority=10):
        ofp, parser = dp.ofproto, dp.ofproto_parser
        match = parser.OFPMatch(eth_type=0x0800, ipv4_dst=dst_ip)
        inst = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        dp.send_msg(parser.OFPFlowMod(
            dp, priority=priority, match=match, instructions=inst))

    # ---------- link up/down events ----------
    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def on_port_status(self, ev):
        msg = ev.msg
        dp = msg.datapath
        key = (dp.id, msg.desc.port_no)
        if msg.desc.state & dp.ofproto.OFPPS_LINK_DOWN:
            self.down.add(key)
            self.logger.info("LINK DOWN  s%d port %d", *key)
        else:
            self.down.discard(key)
            self.logger.info("LINK UP    s%d port %d", *key)
        # keep both ends of the core in agreement about the best path
        for dpid in UPLINKS:
            if dpid in self.dps:
                self.send_group(self.dps[dpid], self.dps[dpid].ofproto.OFPGC_MODIFY)
        self.logger.info("preferred path: %s",
                         "B (via s3)" if self.port_order(1)[0] == UPLINKS[1][1] else "A (via s2)")
