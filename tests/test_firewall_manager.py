import json
import unittest

from app.firewall_manager import (
    apply_firewall_rules,
    firewall_context,
    parse_addr_cidrs,
    parse_route_cidrs,
    preview_firewall_rules,
)
from app.system_actions import CommandResult


class FakeRunner:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def __call__(self, args, input_text=None, env=None):
        self.calls.append(list(args))
        response = self.responses.get(tuple(args))
        if response is None:
            return CommandResult(list(args), 0, "", "")
        return CommandResult(list(args), *response)


class FirewallManagerTests(unittest.TestCase):
    def test_parse_route_cidrs_dedupes_link_routes(self):
        payload = json.dumps(
            [
                {"dst": "default", "dev": "eth0"},
                {"dst": "192.168.1.0/24", "dev": "eth0"},
                {"dst": "192.168.1.0/24", "dev": "eth0"},
            ]
        )

        self.assertEqual(parse_route_cidrs(payload), ["192.168.1.0/24"])

    def test_parse_addr_cidrs_derives_networks(self):
        payload = json.dumps(
            [
                {
                    "ifname": "eth0",
                    "addr_info": [
                        {"family": "inet", "local": "192.168.1.50", "prefixlen": 24},
                        {"family": "inet6", "local": "fe80::1", "prefixlen": 64},
                    ],
                }
            ]
        )

        self.assertEqual(parse_addr_cidrs(payload), ["192.168.1.0/24"])

    def test_firewall_context_detects_lan_and_samba_app(self):
        runner = FakeRunner(
            {
                ("ufw", "status"): (0, "Status: inactive\n", ""),
                ("ufw", "app", "list"): (0, "Available applications:\n  OpenSSH\n  Samba\n", ""),
                ("ip", "-j", "-4", "route", "show", "scope", "link"): (
                    0,
                    '[{"dst":"192.168.1.0/24","dev":"eth0"}]',
                    "",
                ),
            }
        )

        context = firewall_context(runner)

        self.assertEqual(context["ufw_status"], "inactive")
        self.assertEqual(context["lan_cidrs"], ["192.168.1.0/24"])
        self.assertTrue(context["samba_app_available"])
        self.assertTrue(context["preview"]["can_apply"])

    def test_preview_blocks_when_lan_detection_fails(self):
        preview = preview_firewall_rules(lan_cidrs=[], ufw_active=False, samba_app_available=True)

        self.assertFalse(preview["can_apply"])
        self.assertIn("will not guess", preview["message"])

    def test_inactive_firewall_apply_enables_after_safe_rules(self):
        runner = FakeRunner()

        results = apply_firewall_rules(
            runner,
            lan_cidrs=["192.168.1.0/24"],
            ufw_active=False,
            samba_app_available=True,
            root_checker=lambda: True,
        )

        self.assertTrue(all(result["status"] == "passed" for result in results))
        self.assertEqual(runner.calls[0], ["ufw", "default", "deny", "incoming"])
        self.assertIn(["ufw", "allow", "from", "192.168.1.0/24", "to", "any", "app", "Samba"], runner.calls)
        self.assertIn(["ufw", "allow", "in", "on", "tailscale0", "to", "any", "app", "Samba"], runner.calls)
        self.assertEqual(runner.calls[-1], ["ufw", "--force", "enable"])

    def test_active_firewall_adds_rules_without_enabling(self):
        runner = FakeRunner()

        apply_firewall_rules(
            runner,
            lan_cidrs=["192.168.1.0/24"],
            ufw_active=True,
            samba_app_available=True,
            root_checker=lambda: True,
        )

        self.assertNotIn(["ufw", "--force", "enable"], runner.calls)
        self.assertFalse(any(call[:3] == ["ufw", "default", "deny"] for call in runner.calls))

    def test_samba_fallback_uses_ports_when_profile_missing(self):
        runner = FakeRunner()

        apply_firewall_rules(
            runner,
            lan_cidrs=["192.168.1.0/24"],
            ufw_active=True,
            samba_app_available=False,
            root_checker=lambda: True,
        )

        self.assertIn(
            ["ufw", "allow", "proto", "tcp", "from", "192.168.1.0/24", "to", "any", "port", "445"],
            runner.calls,
        )
        self.assertIn(
            ["ufw", "allow", "in", "on", "tailscale0", "to", "any", "port", "445", "proto", "tcp"],
            runner.calls,
        )


if __name__ == "__main__":
    unittest.main()
