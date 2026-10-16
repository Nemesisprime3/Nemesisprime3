"""Smoke tests for the lightweight agent runtime. Run: python -m unittest -v"""
import os
import unittest
import agent_runtime as ar

class AgentRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.old_rpc = os.environ.pop("MONEY_AGENT_TESTNET_RPC_URL", None)

    def tearDown(self):
        if self.old_rpc is not None:
            os.environ["MONEY_AGENT_TESTNET_RPC_URL"] = self.old_rpc
        else:
            os.environ.pop("MONEY_AGENT_TESTNET_RPC_URL", None)

    def test_opportunity_score_never_claims_verification(self):
        result = ar.score_opportunity({
            "source_url": "https://example.org/task",
            "reward_amount": "20",
            "payment_terms": "after acceptance",
            "eligibility": "open",
            "deadline": "Friday",
            "acceptance_criteria": "tests pass",
        })
        self.assertEqual(result["score"], 100)
        self.assertEqual(result["decision"], "manual_review_required")
        self.assertIn("not independently verified", result["evidence"][1])

    def test_wallet_requires_valid_address(self):
        with self.assertRaises(ValueError):
            ar.wallet_status("not-an-address")

    def test_wallet_without_rpc_is_safe_and_does_not_claim_balance(self):
        result = ar.wallet_status("0x" + "a" * 40)
        self.assertFalse(result["configured"])
        self.assertIsNone(result["balance_wei"])
        self.assertIn("No network request was made", result["message"])

    def test_idle_worker_can_be_retired(self):
        agent = ar.spawn_agent("test", "smoke test worker")
        retired = ar.retire_agent(agent["id"])
        self.assertEqual(retired["status"], "retired")

    def test_action_allowlist_rejects_unapproved_action_types(self):
        with self.assertRaises(ValueError):
            ar.request_action("send_transaction", {"to": "0x" + "a" * 40})

    def test_action_request_starts_pending(self):
        action = ar.request_action("pause_workers", {})
        self.assertEqual(action["status"], "pending_approval")
        ar.finish_action(action["id"], "test_complete", "test cleanup")

if __name__ == "__main__":
    unittest.main()
