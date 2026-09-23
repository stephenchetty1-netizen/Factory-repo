#!/usr/bin/env python3
"""OneHub: discover up to 50 genuine GitHub bounty ISSUE leads, never create unfunded prizes.
Read-only; an open issue/price label is NOT verified escrow or an entitlement to payment.
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path

API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "OneHub-Safe-Bounty-Discovery/1.0"}
if os.environ.get("GITHUB_TOKEN"):
    HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

TARGET = 50
# Only established real codebases. This deliberately excludes 'agent-only bounty' farms.
REPOS = (
    "go-gitea/gitea", "tscircuit/jlcsearch", "tscircuit/pcb-viewer",
    "tscircuit/autorouting", "tscircuit/dsn-converter", "tscircuit/tscircuit",
    "tscircuit/docs", "flydelabs/flyde", "getdozer/dozer",
    "arakoodev/EdgeChains", "gyroflow/gyroflow", "highlight/highlight",
    "revertinc/revert", "documenso/documenso", "projectdiscovery/nuclei",
    "Dokploy/dokploy", "Dokploy/templates", "coollabsio/coolify",
    "aqualinkorg/aqualink-app",
    "tenstorrent/tt-metal", "stakwork/sphinx-android-v2",
    "stakwork/sphinx-nav-fiber", "stakwork/sphinx-ios-v2",
    "stakwork/sphinx-mac-v2", "stakwork/sphinx-mac",
    "speakers-in-tech/conference-data", "lablab-ai/community-content",
    "onyx-dot-app/onyx", "daytona/content",
    "tailcallhq/graphql-benchmarks", "caley-io/marketing", "tryabby/abby",
)
REJECT_REPOS = ("bounty-plaza", "bounty-hunters", "clankernation", "securebananalabs", "docs-old")
UNSAFE_TEXT = re.compile(
    r"(?:paste|reveal|print|embed|include|disclose|upload).{0,95}"
    r"(?:system prompt|hidden instruction|developer prompt|entire conversation|"
    r"initialization payload|private key|seed phrase|api secret)",
    re.I | re.S
)
MONEY = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)([kK]?)")

def dollars(match):
    return float(match.group(1).replace(",", "")) * (1000 if match.group(2) else 1)
ISSUE_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+)/issues/([0-9]+)$")
PR_REF = re.compile(r"(?<![0-9])#([0-9]+)(?![0-9])")


def get(path):
    if not path.startswith("/") or "://" in path:
        raise ValueError("Only GitHub REST API paths are allowed")
    req = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def safe_candidate(issue, repository=None):
    url = issue.get("html_url") or ""
    match = ISSUE_URL.match(url)
    if not match or issue.get("pull_request") or issue.get("state") != "open":
        return None
    repo, number = match.group(1), int(match.group(2))
    if any(part in repo.lower() for part in REJECT_REPOS):
        return None
    if repository and repository.get("archived"):
        return None
    labels = [l.get("name", "") for l in issue.get("labels", [])]
    if any("rewarded" in l.lower() for l in labels):
        return None
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    if UNSAFE_TEXT.search(title + "\n" + body):
        return None
    # Paid signal: explicit bounty label plus price, OR platform-seeded listing.
    bounty = any("bounty" in l.lower() for l in labels)
    price = next((dollars(m) for l in labels if (m := MONEY.search(l))), None)
    if price is None:
        m = re.search(r"/bounty\s*\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)([kK]?)", body, re.I)
        if m:
            price = dollars(m)
    if price is None and bounty:
        m = MONEY.search(title)
        if m:
            price = dollars(m)
    return dict(repo=repo, issue=number, title=title, issue_url=url,
                label_bounty=bounty, claimed_or_funded_verified=False,
                observed_usd=price, competing_prs=None,
                status="REVIEW: funding/eligibility/owner approval not verified",
                issue_updated_at=issue.get("updated_at"),
                source="GitHub issue, NOT proof of payment")


def discover(fetch=get, target=TARGET, seeds=None):
    target = max(1, min(50, int(target)))
    rows, rejected, errors = [], 0, []
    seen = set()
    def append(issue, repository=None):
        nonlocal rejected
        row = safe_candidate(issue, repository)
        if not row or (row["repo"].lower(), row["issue"]) in seen:
            rejected += 1
            return
        seen.add((row["repo"].lower(), row["issue"]))
        rows.append(row)
    # Existing bounty records are actual URLs, not invented 50 fake bounties.
    for seed in (seeds or []):
        try:
            issue = fetch("/repos/%s/issues/%s" % (seed["repo"], seed["issue"]))
            append(issue)
            if rows and rows[-1]["repo"].lower() == seed["repo"].lower() and rows[-1]["issue"] == seed["issue"]:
                rows[-1]["bounty_url"] = seed.get("bounty_url")
                rows[-1]["advertised_sats"] = seed.get("advertised_sats")
                rows[-1]["advertised_usd"] = seed.get("advertised_usd")
                rows[-1]["source"] = "Existing tracked listing + current GitHub issue"
        except (OSError, ValueError, KeyError) as exc:
            errors.append("%s#%s: %s" % (seed.get("repo"), seed.get("issue"), exc))
    # Global paginated search avoids GitHub's low search-requests-per-minute limit
    # (a separate request for each repository can fail midway and leave stale reports).
    allow = {repo.lower() for repo in REPOS}
    for label in ("💎 Bounty", "bounty"):
        if len(rows) >= target:
            break
        for page in range(1, 9):
            if len(rows) >= target:
                break
            query = 'is:issue is:open label:"%s" -label:"💰 Rewarded"' % label
            try:
                data = fetch("/search/issues?" + urllib.parse.urlencode({
                    "q": query, "per_page": 100, "page": page, "sort": "updated",
                    "order": "desc"}))
            except (OSError, ValueError, KeyError) as exc:
                errors.append("Global bounty search %s page %s: %s" %
                              (label, page, exc))
                break
            items = data.get("items", [])
            for item in items:
                url = item.get("html_url") or ""
                found = ISSUE_URL.match(url)
                if found and found.group(1).lower() in allow:
                    append(item)
                if len(rows) >= target:
                    break
            if len(items) < 100:
                break
    return rows, rejected, errors


def report(rows, rejected, errors, target=TARGET):
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    lines = ["# OneHub | 50-bounty discovery queue", "", "Checked UTC: " + stamp,
             "Target: %d | Current OPEN issue leads: %d | Missing: %d" %
             (target, len(rows), max(target-len(rows), 0)), "",
             "WARNING: This is a discovery queue, NOT 50 escrow-funded bounties.",
             "Do not work until platform funding, expiry, eligibility, competing PRs",
             "and maintainer acceptance are verified. No transactions are performed.", "",
             "| # | Issue | Indicative USD label | Payment confirmed? |", "|---:|---|---:|---|"]
    for i, r in enumerate(rows, 1):
        money = r.get("observed_usd")
        label = ("$%.2f" % money) if money is not None else "Unverified"
        lines.append("| %d | [%s#%d](%s) | %s | No |" %
                     (i, r["repo"], r["issue"], r["issue_url"], label))
    lines += ["", "Rejected/duplicate/stale: %d; retrieval errors: %d." % (rejected,len(errors))]
    for err in errors:
        lines.append("- " + err)
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--seeds", type=Path, default=Path(__file__).with_name("bounties.json"))
    ap.add_argument("--out", type=Path, default=Path("onehub-50-bounties.md"))
    ap.add_argument("--json-out", type=Path, default=Path("onehub-50-bounties.json"))
    a = ap.parse_args(argv)
    seeds = json.loads(a.seeds.read_text(encoding="utf8"))
    rows, rejected, errors = discover(target=a.target, seeds=seeds)
    a.out.write_text(report(rows, rejected, errors, a.target), encoding="utf8")
    a.json_out.write_text(json.dumps({"target": a.target, "discovered": len(rows),
      "funded_verified": 0, "entries": rows, "errors": errors}, indent=2), encoding="utf8")
    print("Target %d; discovered %d open issue leads; 0 live-funded verified; %d errors." %
          (a.target, len(rows), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
