#!/usr/bin/env python3
"""OneHub read-only public opportunity watcher. Findings are NEVER earnings."""
import datetime as dt
import html
from html.parser import HTMLParser
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SOURCES = [
    ("Lightning Bounties", "BTC / Lightning bounties", "https://app.lightningbounties.com/"),
    ("HackerOne Opportunities", "Authorised security programs", "https://hackerone.com/opportunities/all"),
    ("HackerOne Payment Guide", "BTC payout policy", "https://docs.hackerone.com/en/articles/8395720-payment-preferences"),
    ("TesterWork Current Projects", "Phone testing", "https://testerwork.com/current-projects/"),
    ("Clickworker Eligibility", "Phone microtasks", "https://support-workplace.clickworker.com/support/solutions/articles/80000671469-is-it-possible-to-work-for-clickworker-from-many-countries-all-over-the-world-"),
    ("Bugcrowd Programs", "Authorised security programs", "https://bugcrowd.com/programs"),
]
USER_AGENT = "OneHub-Public-Income-Watcher/1.0 (read-only; no accounts)"
MAX_BYTES = 850_000
MAX_LISTINGS = 20


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            url = dict(attrs).get("href")
            if url:
                self.urls.append(html.unescape(url))


def safe_bounty_links(page, base="https://app.lightningbounties.com/"):
    parser = Links()
    parser.feed(page)
    selected = []
    for link in parser.urls:
        absolute = urllib.parse.urljoin(base, link)
        split = urllib.parse.urlsplit(absolute)
        if (split.scheme == "https" and
                split.netloc == "app.lightningbounties.com" and
                re.fullmatch(r"/issue/[a-zA-Z0-9-]+/?", split.path)):
            canonical = urllib.parse.urlunsplit(
                (split.scheme, split.netloc, split.path.rstrip("/"), "", ""))
            if canonical not in selected:
                selected.append(canonical)
        if len(selected) >= MAX_LISTINGS:
            break
    return selected


def fetch_public(url):
    if not url.startswith("https://"):
        raise ValueError("HTTPS sources only")
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html"})
    with urllib.request.urlopen(request, timeout=16) as response:
        data = response.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise ValueError("Source exceeds size limit")
        return data.decode("utf-8", errors="replace")


def inspect_source(name, category, url, fetch=fetch_public):
    row = {
        "source": name, "category": category, "url": url,
        "access": "UNTESTED", "lead_urls": [],
        "payment_verified": False, "sa_payout_verified": False,
        "ai_automation_approved": False, "earnings_confirmed": False,
        "finding": "Not checked",
    }
    try:
        page = fetch(url)
        row["access"] = "ACCESSIBLE"
        if name == "Lightning Bounties":
            row["lead_urls"] = safe_bounty_links(page)
            row["finding"] = (
                str(len(row["lead_urls"])) +
                " public listings; claim, funding, expiry, competing work and "
                "payment eligibility not independently verified"
                if row["lead_urls"] else
                "Feed accessible; no issue links extracted; website may be JavaScript-rendered"
            )
        elif name == "TesterWork Current Projects":
            country = bool(re.search(r"South\s+Africa", page, re.I))
            row["finding"] = (
                "South Africa mentioned on directory; no individual invitation or "
                "open SA project confirmed" if country else
                "No South African project verified in fetched listing"
            )
        elif name == "HackerOne Payment Guide":
            row["finding"] = (
                "BTC wallet method appears in policy; account eligibility, KYC "
                "and individual bounty payment remain unverified"
                if re.search(r"Bitcoin Wallet|BTC or USDC", page, re.I)
                else "Policy fetched; BTC payout option not parsed")
        elif name == "Clickworker Eligibility":
            row["finding"] = (
                "Country and payment availability depend on registration "
                "and account-specific payment details; no job confirmed"
            )
        else:
            row["finding"] = (
                "Program directory fetched; no authorised target, bounty amount "
                "or award eligibility independently established"
            )
    except (OSError, ValueError, UnicodeError) as exc:
        row["access"] = "UNAVAILABLE"
        row["finding"] = type(exc).__name__ + ": " + str(exc)[:170]
    return row


def report(rows, when):
    lines = [
        "# OneHub AI Income Engine — public-source read-only scan", "",
        "Checked UTC: " + when,
        "**Funds generated by this scan: none. Verified payouts: none.**",
        "**This is not a wallet or bank balance check.**",
        "No account creation, vulnerability probing, login, dark-web crawling, "
        "withdrawal, purchase, or social-media posting occurs.", "",
        "## Official sources", "",
        "| Source | Access | Verified opportunity or limitation |",
        "|---|---|---|",
    ]
    for row in rows:
        finding = row["finding"].replace("|", "/").replace("\n", " ")
        lines.append("| [%s](%s) | %s | %s |" % (
            row["source"], row["url"], row["access"], finding))
    lines.extend(["", "## Public Lightning bounty leads — not accepted jobs", ""])
    lightning = next((r for r in rows if r["source"] == "Lightning Bounties"), {})
    if lightning.get("lead_urls"):
        for u in lightning["lead_urls"]:
            lines.append("- " + u + " — REVIEW funding, issue/PR status, "
                         "South African payout accessibility and AI rules")
    else:
        lines.append("No independently verified paid BTC opportunity this cycle.")
    lines.extend(["", "## Other operational channels", "",
        "- Existing funded-issue lead scout: "
        "https://github.com/stephenchetty1-netizen/Factory-repo/actions/workflows/onehub-bounty-discovery-50.yml",
        "- OneHub digital storefront: account-authenticated Shopify review "
        "is required; this public scanner cannot infer sales.",
        "- If a valid income payout is received, any conversion to BTC needs "
        "the owner's explicit instruction, an eligible exchange and applicable "
        "fees/tax review. Never collect private keys or wallet seed phrases.",
        "- Never submit mass automated vulnerability scans; follow each "
        "program's written scope and authorisation.", ""])
    return "\n".join(lines)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("onehub-income-report.md"))
    ap.add_argument("--json-out", type=Path, default=Path("onehub-income-report.json"))
    args = ap.parse_args()
    when = dt.datetime.now(dt.timezone.utc).isoformat()
    rows = [inspect_source(*s) for s in SOURCES]
    data = {"checked_utc": when, "sources": rows,
            "payments_received_or_verified_by_scanner": 0,
            "independently_verified_paid_opportunities": 0}
    args.out.write_text(report(rows, when), encoding="utf-8")
    args.json_out.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print("Official sources: %d; reachable: %d; verified payments: 0; "
          "independently confirmed payable opportunities: 0" %
          (len(rows), sum(r["access"] == "ACCESSIBLE" for r in rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
