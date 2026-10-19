import unittest
from nettwin import netmodel
from nettwin.router_cli import ROUTER_INFO, ALIAS_MAP


class RouterCLITest(unittest.TestCase):
    def test_routers_exist(self):
        for sw in ("s1", "s2", "s3", "s4"):
            self.assertIn(sw, ROUTER_INFO)
            self.assertIn("name", ROUTER_INFO[sw])
            self.assertIn("ports", ROUTER_INFO[sw])

    def test_alias_map(self):
        self.assertEqual(ALIAS_MAP["r1"], "s1")
        self.assertEqual(ALIAS_MAP["r2"], "s2")
        self.assertEqual(ALIAS_MAP["r3"], "s3")
        self.assertEqual(ALIAS_MAP["r4"], "s4")

    def test_s1_ports_match_netmodel(self):
        s1_ports = set(ROUTER_INFO["s1"]["ports"].keys())
        expected_s1_ports = {1, 2, 3, 4, 5}
        self.assertEqual(s1_ports, expected_s1_ports)


if __name__ == "__main__":
    unittest.main()
