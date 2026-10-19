#!/usr/bin/env python3
from functools import partial

from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.net import Mininet
from mininet.node import OVSKernelSwitch, RemoteController


def build():
    net = Mininet(
        controller=None,
        switch=partial(OVSKernelSwitch, protocols="OpenFlow13"),
        autoSetMacs=True,
        autoStaticArp=True,
    )
    net.addController("c0", controller=RemoteController, ip="127.0.0.1", port=6653)

    s1 = net.addSwitch("s1", dpid="1")
    s2 = net.addSwitch("s2", dpid="2")
    s3 = net.addSwitch("s3", dpid="3")
    s4 = net.addSwitch("s4", dpid="4")

    c1 = net.addHost("c1", ip="10.0.0.1/24")
    c2 = net.addHost("c2", ip="10.0.0.2/24")
    c3 = net.addHost("c3", ip="10.0.0.3/24")
    srv = net.addHost("srv", ip="10.0.0.100/24")

    # clients on s1 (ports 1, 2, 3)
    net.addLink(c1, s1, port2=1)
    net.addLink(c2, s1, port2=2)
    net.addLink(c3, s1, port2=3)
    # path A: s1 to s2 to s4
    net.addLink(s1, s2, port1=4, port2=1)
    net.addLink(s2, s4, port1=2, port2=1)
    # path B: s1 to s3 to s4
    net.addLink(s1, s3, port1=5, port2=1)
    net.addLink(s3, s4, port1=2, port2=2)
    # server on s4 (port 3)
    net.addLink(srv, s4, port2=3)
    return net


if __name__ == "__main__":
    setLogLevel("info")
    net = build()
    net.start()
    CLI(net)
    net.stop()
