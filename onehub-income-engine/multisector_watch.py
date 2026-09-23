#!/usr/bin/env python3
"""24/7 schedule-compatible, read-only OneHub multi-sector public-signal monitor.

No exchange/wallet credentials, trades, mining, account creation, payouts, posting,
shopping, purchases, security scans or paid API calls. All results = observations.
"""
import argparse
import datetime as dt
import html
import json
import math
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

AGENT = "OneHub-ReadOnly-MultiSector/1.0"
BYTE_LIMIT = 900_000
UA = {"User-Agent": AGENT, "Accept": "application/json,text/html;q=0.8"}
QUICK = (
    ("mining", "Bitcoin mining pools / latest blocks", "https://mempool.space/api/v1/mining/pools/24h", "json"),
    ("mining", "Bitcoin difficulty adjustment", "https://mempool.space/api/v1/difficulty-adjustment", "json"),
    ("trading", "Kraken BTC/USD public ticker", "https://api.kraken.com/0/public/Ticker?pair=xbtusd", "json"),
    ("trading", "Bitstamp BTC/USD public ticker", "https://www.bitstamp.net/api/v2/ticker/btcusd/", "json"),
    ("trading", "Luno BTC/ZAR public ticker", "https://api.luno.com/api/1/ticker?pair=XBTZAR", "json"),
    ("crypto", "CoinGecko BTC and ETH public reference", "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin%2Cethereum&vs_currencies=usd%2Czar", "json"),
)
DEEP = (
    ("sales", "Shopify public product-trend research", "https://www.shopify.com/blog/trending-products", "html"),
    ("sales", "eBay Seller Center public research guidance", "https://www.ebay.com/sellercenter/growth/ebay-research-tools", "html"),
    ("sales", "Etsy Seller Handbook public guidance", "https://www.etsy.com/seller-handbook", "html"),
    ("sales", "Gumroad public website", "https://gumroad.com/", "html"),
    ("sales", "Payhip public website", "https://payhip.com/", "html"),
    ("sales", "OneHub published storefront reachable", "https://onehub-ai-business.floot.app/", "html"),
    ("crypto", "HackerOne public BTC payout policy", "https://docs.hackerone.com/en/articles/8395720-payment-preferences", "html"),
    ("paid-work", "Prolific global participation policy", "https://participant-help.prolific.com/en/articles/445007-who-can-participate-in-studies-on-prolific", "html"),
    ("paid-work", "Prolific participant study marketplace", "https://www.prolific.com/participants-how-it-works", "html"),
    ("paid-work", "TesterWork live test projects", "https://testerwork.com/current-projects/", "html"),
    ("paid-work", "uTest paid testing project board", "https://www.utest.com/projects", "html"),
    ("paid-work", "UserTesting participant application", "https://www.usertesting.com/get-paid-to-test/make-money-online", "html"),
    ("paid-work", "Clickworker official smartphone work", "https://www.clickworker.com/clickworker-app/", "html"),
    ("global-prizes", "Topcoder international challenge directory", "https://www.topcoder.com/challenges", "html"),
    ("global-prizes", "Kaggle international competitions", "https://www.kaggle.com/competitions", "html"),
    ("global-prizes", "Zindi competitions", "https://zindi.africa/competitions", "html"),
    ("global-prizes", "Devpost international hackathons", "https://devpost.com/hackathons", "html"),
    ("global-prizes", "Algora funded issue marketplace", "https://algora.io/bounties", "html"),
)
# Explicitly label navigation/policy pages; reachable does not mean work is available.
WORK_ACTIONS = {
    "Prolific global participation policy":
        "Check country-specific account admission, waitlist and identity rules. Do not assume any country can join.",
    "Prolific participant study marketplace":
        "Check participant invitation and account dashboard; no individual paid study verified.",
    "TesterWork live test projects":
        "Inspect every project worldwide; confirm its own device, country and payout restrictions before applying.",
    "uTest paid testing project board":
        "Inspect worldwide projects for account-specific invitations and accepted devices.",
    "UserTesting participant application":
        "Check country acceptance, available tests and withdrawal methods on the actual account.",
    "Clickworker official smartphone work":
        "Inspect global availability; eligibility, assigned jobs and withdrawals differ by country.",
}
GLOBAL_PRIZE_ACTION = (
    "Inspect live challenge rules, deadline, cash-versus-credit award, entry fee, "
    "country restrictions, mobile feasibility, AI assistance rules, payout route "
    "and competing participants. Landing page is not a prize claim."
)

BLOCKED_RETRY_NOTE = ("Access denied by site; do not bypass access controls. "
                      "Use an authorised connector or the site manually.")
EXPECTED = {
    "mining": "Network/pool aggregate only; never personal miner allocation or revenue",
    "trading": "Indicative public bid/ask only; no executable cross-exchange arbitrage verified",
    "crypto": "Reference price only; no rewards or trading profit verified",
    "sales": "Public research or storefront availability only; no verified orders or revenue",
    "paid-work": "Public application/policy page only; personal enrollment, tasks and payout unverified",
    "global-prizes": "Public worldwide listing only; cash prize, country access and winning unverified",
}

def fetch(url):
    if not url.startswith("https://"):
        raise ValueError("HTTPS required")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=12) as response:
        data = response.read(BYTE_LIMIT + 1)
        if len(data) > BYTE_LIMIT:
            raise ValueError("response above safe size bound")
        return data.decode("utf-8", errors="replace")

def num(value):
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError("invalid numeric quote")
    return value

def extract(category, name, obj):
    """Never interpret a price difference as a realizable return."""
    if name.startswith("Bitcoin mining pools"):
        if not isinstance(obj, dict):
            raise ValueError("Unexpected mining pools payload")
        pools = obj.get("pools")
        if not isinstance(pools, list):
            raise ValueError("No mining pools list")
        return {"reported_pools": len(pools), "personally_mining": "UNVERIFIED"}
    if name.startswith("Bitcoin difficulty"):
        if not isinstance(obj, dict):
            raise ValueError("Unexpected difficulty payload")
        return {"estimated_adjustment_percent": obj.get("difficultyChange"),
                "personal_rewards": "UNVERIFIED"}
    if name.startswith("Kraken"):
        rows = obj.get("result", {})
        if obj.get("error") or not isinstance(rows, dict) or not rows:
            raise ValueError("No Kraken ticker")
        row = list(rows.values())[0]
        return {"bid_usd": num(row["b"][0]), "ask_usd": num(row["a"][0]),
                "executable_profit": "UNVERIFIED"}
    if name.startswith("Bitstamp"):
        return {"bid_usd": num(obj["bid"]), "ask_usd": num(obj["ask"]),
                "executable_profit": "UNVERIFIED"}
    if name.startswith("Luno"):
        return {"bid_zar": num(obj["bid"]), "ask_zar": num(obj["ask"]),
                "pair": obj.get("pair"), "executable_profit": "UNVERIFIED"}
    if name.startswith("CoinGecko"):
        return {"btc_usd": num(obj["bitcoin"]["usd"]),
                "eth_usd": num(obj["ethereum"]["usd"]),
                "btc_zar": num(obj["bitcoin"]["zar"]),
                "executable_profit": "UNVERIFIED"}
    raise ValueError("No JSON parser configured")

def scan(source, getter=fetch):
    cat, name, url, kind = source
    row = {"sector": cat, "source": name, "url": url,
           "status": "UNAVAILABLE", "data": {},
           "verified_income_zar": None,
           "verified_income_btc": None,
           "limitation": EXPECTED[cat]}
    try:
        raw = getter(url)
        if kind == "json":
            row["data"] = extract(cat, name, json.loads(raw))
        else:
            # Status check only: no cookies, form submits, personal accounts or robots bypass.
            if not raw.strip() or raw.lstrip().lower().startswith('{"error"'):
                raise ValueError("Empty or inaccessible source")
            title = re.search(r"<title[^>]*>(.*?)</title\s*>", raw, re.I | re.S)
            row["data"] = {"public_page_title": html.unescape(re.sub(
                r"<[^>]+>", "", title.group(1))).strip()[:140] if title else
                "Page responded; contents not independently validated"}
        row["status"] = "REACHABLE"
        if cat == "paid-work":
            row["data"]["opportunity_status"] = "NOT_VERIFIED"
            row["data"]["next_action"] = WORK_ACTIONS.get(name, "Check platform eligibility and open jobs.")
            row["data"]["automation_of_paid_tasks"] = "NOT_AUTHORISED_BY_THIS_SCAN"
        elif cat == "sales":
            row["data"]["sale_status"] = "NOT_VERIFIED"
            row["data"]["next_action"] = "Public market research only; exclude unrelated owned ministries and their Shopify orders."
        elif cat == "global-prizes":
            row["data"]["opportunity_status"] = "NOT_VERIFIED"
            row["data"]["next_action"] = GLOBAL_PRIZE_ACTION
            row["data"]["eligible_country"] = "CHECK_INDIVIDUAL_RULES"
            row["data"]["cash_award_verified"] = False
    except (OSError, ValueError, TypeError, KeyError, IndexError) as exc:
        row["data"] = {"error": type(exc).__name__ + ": " + str(exc)[:180]}
        if isinstance(exc, urllib.error.HTTPError) and exc.code in (401, 403):
            row["status"] = "ACCESS_DENIED"
            row["data"]["next_action"] = BLOCKED_RETRY_NOTE
    return row

def scan_all(now=None, getter=fetch, force_deep=False):
    now = now or dt.datetime.now(dt.timezone.utc)
    # Every 4 hours at minute 7. Fast signals still run at each 15-minute pass.
    deep = force_deep or (now.hour % 4 == 0 and 7 <= now.minute < 22)
    sources = list(QUICK) + (list(DEEP) if deep else [])
    rows = [scan(s, getter) for s in sources]
    return {"timestamp_utc": now.isoformat(), "scope": "GLOBAL_ALL_REGIONS_NO_LOCATION_FILTER",
            "cadence_minutes": 15,
            "deep_sales_check_this_run": deep,
            "sources_checked": len(rows),
            "reachable_sources": sum(x["status"] == "REACHABLE" for x in rows),
            "sectors_attempted": sorted(set(x["sector"] for x in rows)),
            "results": rows,
            "new_verified_income": "NOT CHECKED: no bank, store or wallet credentials",
            "trade_executed": False, "mining_started": False,
            "orders_placed": False, "payouts_sent": False,
            "warning": ("Market quotes are asynchronous and omit fees, depth, "
                        "tax, market access, slippage and capital. Differences "
                        "are not assured profits. Public pages are not revenue.")}

def report(info):
    lines = ["# OneHub multi-sector 24/7 scheduled watch", "",
             "Observed UTC: " + info["timestamp_utc"],
             "GitHub cron: every 15 minutes, subject to GitHub delays or cancellation.",
             "Deep global paid-work, challenge and sales scan: every four hours.",
             "Scope: opportunities worldwide; no region prefilter. Check individual "
             "country, identity and payout restrictions before applying.",
             "**No trading, mining, sales or transfers executed by this bot.**",
             "**Income not verified: no bank, store-order or wallet verification.**",
             "Data sources reached: %d / %d." %
             (info["reachable_sources"], info["sources_checked"]), "",
             "| Sector | Source | Status | Observation / error |",
             "|---|---|---|---|"]
    for r in info["results"]:
        d = json.dumps(r["data"], ensure_ascii=False).replace("|", "/")
        lines.append("| %s | [%s](%s) | %s | %s |" %
                     (r["sector"], r["source"], r["url"], r["status"], d))
    lines.extend(["", "## Operating restrictions", "",
        "- No deposits, purchases, paid mining, unauthorised scans or exploitation.",
        "- No auto-orders or trades. No crypto conversion without explicit user approval.",
        "- Never treat dashboard returns, order estimates or quotes as actual income.",
        "- This monitors selected worldwide sites, not literally every platform.",
        "- No VPN or identity workaround to evade country or payout restrictions.",
        "- Unrelated ministry projects and their Shopify order data are excluded.",
        "- A 15-minute scheduled task is not a continuously running worker.",
        "- Respect all provider rate limits and terms; failed sources remain FAILED.", ""])
    return "\n".join(lines)

def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("onehub-24-7.md"))
    ap.add_argument("--json-out", type=Path, default=Path("onehub-24-7.json"))
    ap.add_argument("--deep", action="store_true", help="Include all public sales and payout sources now")
    opts = ap.parse_args(argv)
    result = scan_all(force_deep=opts.deep)
    opts.out.write_text(report(result), encoding="utf8")
    opts.json_out.write_text(json.dumps(result, indent=2), encoding="utf8")
    print("Sector scan %s: %d/%d sources reachable; sectors %s; "
          "payments unverified; no financial actions" %
          (result["timestamp_utc"], result["reachable_sources"],
           result["sources_checked"], ",".join(result["sectors_attempted"])))
    for row in result["results"]:
        print("%s | %s | %s | %s" % (
            row["sector"], row["source"], row["status"],
            json.dumps(row["data"], ensure_ascii=False)))
    # An all-outage scan is a failed attempt, not a successful monitoring check.
    # Partial outages remain visible in the saved report.
    if result["reachable_sources"] == 0:
        print("ERROR: zero public sources reachable; scanner unavailable", file=sys.stderr)
        return 2
    return 0

if __name__ == "__main__":
    sys.exit(main())
