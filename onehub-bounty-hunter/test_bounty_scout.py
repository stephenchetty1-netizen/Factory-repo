import unittest

from bounty_scout import relevant_pr, verify, render


class ScoutTests(unittest.TestCase):
    def setUp(self):
        self.entry = {
            "repo": "PrimalHQ/primal-android-app", "issue": 1055,
            "advertised_sats": 50000,
            "bounty_url": "https://app.lightningbounties.com/"
        }

    @staticmethod
    def fake(issue_state="open", prs=None):
        prs = prs or []
        def fetch(path):
            if "/issues/" in path:
                return {"title": "Translate notes", "state": issue_state,
                        "html_url": "https://github.com/PrimalHQ/primal-android-app/issues/1055"}
            if "/pulls?" in path:
                return prs
            raise AssertionError("Unexpected API path " + path)
        return fetch

    def test_matches_exact_issue_only(self):
        self.assertTrue(relevant_pr(
            {"title": "Translate notes", "body": "Closes #1055"}, 1055))
        self.assertFalse(relevant_pr(
            {"title": "Other change", "body": "Fixes #10550"}, 1055))
        self.assertFalse(relevant_pr(
            {"title": "Other change", "body": "Fixes #11055"}, 1055))

    def test_competing_pr_detected(self):
        pr = {"number": 1102, "title": "Translation",
              "body": "Closes #1055",
              "html_url": "https://github.com/example/pull/1102"}
        result = verify(self.entry, self.fake(prs=[pr]))
        self.assertEqual(len(result["open_competing_prs"]), 1)
        self.assertIn("COMPETING", result["verdict"])
        self.assertFalse(result["funding_verified_live"])

    def test_closed_issue_rejected_even_with_reward(self):
        result = verify(self.entry, self.fake(issue_state="closed"))
        self.assertIn("CLOSED", result["verdict"])

    def test_no_pr_not_a_guarantee(self):
        result = verify(self.entry, self.fake())
        self.assertIn("require verification", result["verdict"])
        self.assertFalse(result["funding_verified_live"])

    def test_report_is_explicit_about_unconfirmed_funds(self):
        report = render([verify(self.entry, self.fake())], [])
        self.assertIn("NOT payment or confirmed escrow", report)
        self.assertIn("50", report)


if __name__ == "__main__":
    unittest.main()
