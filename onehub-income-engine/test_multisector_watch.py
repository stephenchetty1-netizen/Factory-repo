import datetime as dt
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import multisector_watch as s

class MultisectorSafetyTests(unittest.TestCase):
    def test_kraken_bid_ask_extracted_without_profit_promise(self):
        data = {"error":[],"result":{"XXBTZUSD":{"a":["110"],"b":["109"]}}}
        val = s.extract("trading","Kraken BTC/USD public ticker",data)
        self.assertEqual(val["bid_usd"],109)
        self.assertEqual(val["executable_profit"],"UNVERIFIED")

    def test_mining_stats_not_personal_mining(self):
        val=s.extract("mining","Bitcoin mining pools / latest blocks",{"pools":[{},{}]})
        self.assertEqual(val["personally_mining"],"UNVERIFIED")

    def test_no_money_without_transaction_confirmation(self):
        row=s.scan(s.QUICK[0],getter=lambda url:'{"pools":[{}]}')
        self.assertIsNone(row["verified_income_btc"])
        self.assertIsNone(row["verified_income_zar"])

    def test_outages_are_visible(self):
        def bad(url): raise OSError("403")
        row=s.scan(s.QUICK[0],getter=bad)
        self.assertEqual(row["status"],"UNAVAILABLE")

    def test_cadence_quarter_hour(self):
        info=s.scan_all(dt.datetime(2026,9,23,12,7,tzinfo=dt.timezone.utc),
                        getter=lambda url: "{}")
        self.assertTrue(info["deep_sales_check_this_run"])
        self.assertFalse(info["trade_executed"])
        self.assertFalse(info["mining_started"])
        self.assertFalse(info["orders_placed"])
        self.assertFalse(info["payouts_sent"])
        self.assertEqual(info["sources_checked"],len(s.QUICK)+len(s.DEEP))
        x=s.scan_all(dt.datetime(2026,9,23,13,22,tzinfo=dt.timezone.utc),
                     getter=lambda url: "{}")
        self.assertFalse(x["deep_sales_check_this_run"])
        self.assertEqual(x["sources_checked"],len(s.QUICK))

    def test_luno_zar_market_price_is_not_profit(self):
        v=s.extract("trading","Luno BTC/ZAR public ticker",
                    {"bid":"100000","ask":"100050","pair":"XBTZAR"})
        self.assertEqual(v["bid_zar"],100000)
        self.assertEqual(v["executable_profit"],"UNVERIFIED")

    def test_forced_deep_scans_all_six_sectors_without_transactions(self):
        info=s.scan_all(dt.datetime(2026,9,23,13,22,tzinfo=dt.timezone.utc),
                        getter=lambda url: "<html><title>Public page</title></html>",
                        force_deep=True)
        self.assertEqual(info["sources_checked"],len(s.QUICK)+len(s.DEEP))
        self.assertEqual(set(info["sectors_attempted"]),{"crypto","mining","sales","trading","paid-work","global-prizes"})
        self.assertFalse(info["trade_executed"])
        self.assertFalse(info["payouts_sent"])

    def test_paid_work_research_never_marks_earnings(self):
        sources=[x for x in s.DEEP if x[0]=="paid-work"]
        self.assertGreaterEqual(len(sources),5)
        r=s.scan(sources[0],getter=lambda url: "<html><title>Paid studies</title></html>")
        self.assertEqual(r["status"],"REACHABLE")
        self.assertIsNone(r["verified_income_zar"])
        self.assertIsNone(r["verified_income_btc"])
        self.assertIn("enrollment",r["limitation"])

    def test_paid_work_page_does_not_invent_job(self):
        row = s.scan(("paid-work", "TesterWork live test projects",
                      "https://testerwork.com/current-projects/", "html"),
                     getter=lambda url: "<html><title>Countries South Africa</title></html>")
        self.assertEqual(row["status"], "REACHABLE")
        self.assertEqual(row["data"]["opportunity_status"], "NOT_VERIFIED")
        self.assertIn("worldwide", row["data"]["next_action"])
        self.assertEqual(row["data"]["automation_of_paid_tasks"],
                         "NOT_AUTHORISED_BY_THIS_SCAN")

    def test_access_denied_is_not_pass(self):
        def forbidden(url):
            raise s.urllib.error.HTTPError(url, 403, "Forbidden", {}, None)
        row = s.scan(s.DEEP[2], getter=forbidden)
        self.assertEqual(row["status"], "ACCESS_DENIED")
        self.assertIn("do not bypass", row["data"]["next_action"])

    def test_sales_page_not_verified_as_sale(self):
        row=s.scan(("sales", "OneHub published storefront reachable",
                    "https://onehub-ai-business.floot.app/", "html"),
                   getter=lambda url:"<html><title>Store</title></html>")
        self.assertEqual(row["data"]["sale_status"],"NOT_VERIFIED")

    def test_global_prize_sources_present_without_country_prefilter(self):
        sources=[x for x in s.DEEP if x[0]=="global-prizes"]
        self.assertGreaterEqual(len(sources),5)
        row=s.scan(sources[0],getter=lambda url:"<html><title>Global challenges</title></html>")
        self.assertEqual(row["data"]["eligible_country"],"CHECK_INDIVIDUAL_RULES")
        self.assertFalse(row["data"]["cash_award_verified"])
        self.assertIsNone(row["verified_income_btc"])

    def test_no_ministry_store_in_scanner(self):
        self.assertFalse(any("onemillionsouls" in x[2] for x in s.QUICK+s.DEEP))

    def test_global_scope_and_unverified_income_on_full_scan(self):
        info=s.scan_all(dt.datetime(2026,9,24,8,7,tzinfo=dt.timezone.utc),
                        getter=lambda url: "<html><title>Public</title></html>",
                        force_deep=True)
        self.assertEqual(info["scope"],"GLOBAL_ALL_REGIONS_NO_LOCATION_FILTER")
        self.assertIn("NOT CHECKED",info["new_verified_income"])
        self.assertTrue(all(row["verified_income_zar"] is None
                            and row["verified_income_btc"] is None
                            for row in info["results"]))

    def test_bad_prices_refused(self):
        with self.assertRaises(ValueError):
            s.num(float("nan"))
        with self.assertRaises(ValueError):
            s.num(-1)

if __name__=="__main__":
    unittest.main()
