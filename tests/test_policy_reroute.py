import unittest
from nettwin import netmodel
from nettwin.controller.failover import LinkHealth, PolicyReRouteManager
from nettwin import policy


def make_health():
    return LinkHealth({name: netmodel.path_ports(name) for name in netmodel.PATHS})


class PolicyReRouteTest(unittest.TestCase):
    def setUp(self):
        self.mgr = PolicyReRouteManager(target_ip="10.0.0.100")
        self.health = make_health()

    def test_no_blocks_returns_none(self):
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNone(dec)

    def test_s2_block_reroutes_to_path_b(self):
        self.mgr.set_block("s2", "10.0.0.2")
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNotNone(dec)
        self.assertEqual(dec.active_path, "B")
        self.assertIn("RE-ROUTED VIA PATH B", dec.status)
        self.assertIn("s1", dec.reroute_rules)
        self.assertIn("s4", dec.reroute_rules)
        self.assertEqual(dec.reroute_rules["s1"]["out_port"], 5)  # Port 5 -> s3
        self.assertEqual(dec.reroute_rules["s4"]["out_port"], 2)  # Port 2 -> s3

        # Check that risk issues are generated
        categories = {issue["category"] for issue in dec.issues}
        self.assertIn("SECURITY_BYPASS", categories)
        self.assertIn("ASYMMETRIC_ROUTING", categories)
        self.assertIn("PATH_CONGESTION", categories)
        self.assertIn("TCAM_OVERHEAD", categories)
        self.assertIn("LOSS_OF_REDUNDANCY", categories)

    def test_s3_block_keeps_on_path_a_with_warning(self):
        self.mgr.set_block("s3", "10.0.0.2")
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNotNone(dec)
        self.assertEqual(dec.active_path, "A")
        self.assertIn("HELD ON PRIMARY PATH A", dec.status)
        categories = {issue["category"] for issue in dec.issues}
        self.assertIn("LOSS_OF_REDUNDANCY", categories)

    def test_s1_ingress_block_impossible(self):
        self.mgr.set_block("s1", "10.0.0.2")
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNotNone(dec)
        self.assertEqual(dec.active_path, "NONE")
        self.assertIn("INGRESS EDGE ISOLATION", dec.status)
        self.assertEqual(dec.reroute_rules, {})

    def test_s4_egress_block_impossible(self):
        self.mgr.set_block("s4", "10.0.0.2")
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNotNone(dec)
        self.assertEqual(dec.active_path, "NONE")
        self.assertIn("EGRESS EDGE CHOKEPOINT", dec.status)
        self.assertEqual(dec.reroute_rules, {})

    def test_both_core_paths_blocked_impossible(self):
        self.mgr.set_block("s2", "10.0.0.2")
        self.mgr.set_block("s3", "10.0.0.2")
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNotNone(dec)
        self.assertEqual(dec.active_path, "NONE")
        self.assertIn("ALL CORE PATHS BLOCKED", dec.status)

    def test_s2_blocked_and_path_b_link_down(self):
        self.mgr.set_block("s2", "10.0.0.2")
        # Cut link on Path B (s1 port 5)
        self.health.set_link_down(1, 5, True)
        dec = self.mgr.evaluate("10.0.0.2", self.health)
        self.assertIsNotNone(dec)
        self.assertEqual(dec.active_path, "NONE")
        self.assertIn("PATH B DOWN", dec.status)

    def test_policy_storage_and_formatting(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_pol = f.name
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_reroutes = f.name

        try:
            policy.add_block("s2", "10.0.0.3", path=tmp_pol)
            blocks = policy.load_policy(tmp_pol)
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0]["switch"], "s2")
            self.assertEqual(blocks[0]["src_ip"], "10.0.0.3")

            policy.remove_block("s2", "10.0.0.3", path=tmp_pol)
            blocks_after = policy.load_policy(tmp_pol)
            self.assertEqual(len(blocks_after), 0)

            # Test formatting
            self.mgr.set_block("s2", "10.0.0.2")
            dec = self.mgr.evaluate("10.0.0.2", self.health)
            data = {"reroutes": {"10.0.0.2": dec.to_dict()}}
            policy.save_reroutes(data, path=tmp_reroutes)
            loaded = policy.load_reroutes(path=tmp_reroutes)
            self.assertIn("10.0.0.2", loaded["reroutes"])

            table_str = policy.format_reroutes_table(loaded)
            self.assertIn("10.0.0.2", table_str)
            self.assertIn("Path B", table_str)

            issues_str = policy.format_issues_table(loaded)
            self.assertIn("SECURITY_BYPASS", issues_str)
        finally:
            if os.path.exists(tmp_pol):
                os.remove(tmp_pol)
            if os.path.exists(tmp_reroutes):
                os.remove(tmp_reroutes)


if __name__ == "__main__":
    unittest.main()
