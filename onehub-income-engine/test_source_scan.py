import unittest
from source_scan import inspect_source, safe_bounty_links, SOURCES, report

class PublicWatchTests(unittest.TestCase):
    def test_only_official_bounty_links(self):
        html = '<a href="/issue/abc-123">A</a><a href="https://evil.test/issue/steal">bad</a><a href="/issue/abc-123?x=2">dup</a>'
        self.assertEqual(safe_bounty_links(html), ["https://app.lightningbounties.com/issue/abc-123"])

    def test_listing_is_never_a_payment(self):
        row = inspect_source(*SOURCES[0], fetch=lambda url: '<a href="/issue/abc">Sats 50000</a>')
        self.assertEqual(len(row["lead_urls"]), 1)
        self.assertFalse(row["payment_verified"])
        self.assertFalse(row["earnings_confirmed"])
        self.assertFalse(row["country_and_payout_verified"])
        self.assertFalse(row["ai_automation_approved"])

    def test_country_directory_is_not_job_confirmation(self):
        row = inspect_source(*SOURCES[3], fetch=lambda url: "<p>South Africa</p>")
        self.assertIn("individual country eligibility", row["finding"])

    def test_global_competition_sources_added(self):
        self.assertGreaterEqual(sum("Global" in source[0] for source in SOURCES),2)

    def test_global_competition_page_does_not_claim_prize(self):
        source=next(x for x in SOURCES if x[0]=="Kaggle Global Competitions")
        row=inspect_source(*source,fetch=lambda url:"<html><title>Worldwide competitions</title></html>")
        self.assertEqual(row["access"],"ACCESSIBLE")
        self.assertIn("payout remain unverified",row["finding"])
        self.assertFalse(row["earnings_confirmed"])
        self.assertFalse(row["payment_verified"])

    def test_source_failure_does_not_generate_fake_opportunities(self):
        def bad(url):
            raise OSError("offline")
        row = inspect_source(*SOURCES[0], fetch=bad)
        self.assertEqual(row["access"], "UNAVAILABLE")
        self.assertEqual(row["lead_urls"], [])

    def test_report_disclaims_wallet_balance(self):
        self.assertIn("not a wallet or bank balance", report([], "2026-09-23T00:00Z"))

if __name__ == "__main__":
    unittest.main()
