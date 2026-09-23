#!/usr/bin/env python3
"""OneHub read-only 50-slot bounty lead discovery, NOT proof of funded prizes."""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json",
           "User-Agent": "OneHub-Safe-Bounty-Discovery/1.2"}
if os.environ.get("GITHUB_TOKEN"):
    HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]

TARGET = 50
REPOS = (
    "go-gitea/gitea", "tscircuit/jlcsearch", "tscircuit/pcb-viewer",
    "tscircuit/autorouting", "tscircuit/dsn-converter", "tscircuit/tscircuit",
    "tscircuit/docs", "flydelabs/flyde", "getdozer/dozer",
    "arakoodev/EdgeChains", "gyroflow/gyroflow", "highlight/highlight",
    "revertinc/revert", "documenso/documenso", "projectdiscovery/nuclei",
    "Dokploy/dokploy", "Dokploy/templates", "coollabsio/coolify",
    "aqualinkorg/aqualink-app", "tenstorrent/tt-metal",
    "stakwork/sphinx-android-v2", "stakwork/sphinx-nav-fiber",
    "stakwork/sphinx-ios-v2", "stakwork/sphinx-mac-v2",
    "stakwork/sphinx-mac", "speakers-in-tech/conference-data",
    "lablab-ai/community-content", "onyx-dot-app/onyx",
    "daytona/content", "tailcallhq/graphql-benchmarks",
    "caley-io/marketing", "tryabby/abby",
)
REJECT_REPOS = ("bounty-plaza", "bounty-hunters", "clankernation",
                "securebananalabs", "docs-old")
UNSAFE_TEXT = re.compile(
    r"(?:paste|reveal|print|embed|include|disclose|upload).{0,95}"
    r"(?:system prompt|hidden instruction|developer prompt|entire conversation|"
    r"initialization payload|private key|seed phrase|api secret)", re.I | re.S)
MONEY = re.compile(r"\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)([kK]?)")
ISSUE_URL = re.compile(r"^https://github\.com/([^/]+/[^/]+)/issues/([0-9]+)$")


def dollars(match):
    return float(match.group(1).replace(",", "")) * (1000 if match.group(2) else 1)


def get(path):
    if not path.startswith("/") or "://" in path:
        raise ValueError("Only GitHub REST API paths are allowed")
    req = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def safe_candidate(issue, repository=None, external_bounty=False):
    url = issue.get("html_url") or ""
    match = ISSUE_URL.match(url)
    if not match or issue.get("pull_request") or issue.get("state") != "open":
        return None
    repo, number = match.group(1), int(match.group(2))
    if any(word in repo.lower() for word in REJECT_REPOS):
        return None
    if repository and (repository.get("archived") or repository.get("disabled")
                       or repository.get("private")):
        return None
    labels = [l.get("name", "") for l in issue.get("labels", [])]
    if any("rewarded" in label.lower() for label in labels):
        return None
    title = issue.get("title") or ""
    body = issue.get("body") or ""
    if UNSAFE_TEXT.search(title + "\n" + body):
        return None
    has_bounty_label = any("bounty" in label.lower() for label in labels)
    price = next((dollars(m) for label in labels
                  if (m := MONEY.search(label))), None)
    if price is None:
        m = re.search(r"/bounty\s*\$\s*([0-9][0-9,]*(?:\.[0-9]+)?)([kK]?)",
                      body, re.I)
        if m:
            price = dollars(m)
    if price is None and has_bounty_label:
        m = MONEY.search(title)
        if m:
            price = dollars(m)
    if not has_bounty_label and price is None and not external_bounty:
        return None
    age_days = None
    try:
        updated = dt.datetime.fromisoformat(
            (issue.get("updated_at") or "").replace("Z", "+00:00"))
        age_days = (dt.datetime.now(dt.timezone.utc) - updated).days
    except ValueError:
        pass
    return {
        "repo": repo, "issue": number, "title": title, "issue_url": url,
        "label_bounty": has_bounty_label, "observed_usd": price,
        "advertised_usd": None, "advertised_sats": None,
        "funding_verified_live": False, "claimed_or_funded_verified": False,
        "competing_prs": None, "issue_updated_at": issue.get("updated_at"),
        "stale_over_180_days": age_days is not None and age_days > 180,
        "assignees": [x.get("login") for x in issue.get("assignees", [])],
        "status": "REVIEW: sponsor funds, expiry and payment terms not verified",
        "source": "GitHub issue is only a lead, not an escrow confirmation",
    }


def discover(fetch=get, target=TARGET, seeds=None):
    target = max(1, min(50, int(target)))
    rows, rejected, errors = [], 0, []
    seen, meta_cache = set(), {}
    allow = {name.lower() for name in REPOS}

    def metadata(repo):
        if repo.lower() not in meta_cache:
            meta_cache[repo.lower()] = fetch("/repos/" + repo)
        return meta_cache[repo.lower()]

    def append(issue, meta=None, external=False):
        nonlocal rejected
        row = safe_candidate(issue, meta, external)
        if not row or (row["repo"].lower(), row["issue"]) in seen:
            rejected += 1
            return None
        seen.add((row["repo"].lower(), row["issue"]))
        rows.append(row)
        return row

    for seed in seeds or []:
        try:
            repo, number = seed["repo"], seed["issue"]
            meta = metadata(repo)
            if meta.get("archived") or meta.get("disabled") or meta.get("private"):
                rejected += 1
                continue
            issue = fetch("/repos/%s/issues/%s" % (repo, number))
            if not seed.get("bounty_url") and not any(
                "bounty" in label.get("name", "").lower()
                for label in issue.get("labels", [])):
                rejected += 1
                continue
            row = append(issue, meta, external=bool(seed.get("bounty_url")))
            if row:
                row["bounty_url"] = seed.get("bounty_url")
                row["advertised_sats"] = seed.get("advertised_sats")
                row["advertised_usd"] = seed.get("advertised_usd")
                row["source"] = "Tracked platform listing + live GitHub state"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append("%s#%s: %s" % (
                seed.get("repo"), seed.get("issue"), exc))

    # GitHub's search rate limit is lower than its normal issue API limit.
    # Run two global searches, then small organization-specific searches.
    queries = ['is:issue is:open label:"💎 Bounty" -label:"💰 Rewarded"',
               'is:issue is:open label:bounty -label:"💰 Rewarded"']
    for org in ("tenstorrent", "stakwork", "tscircuit"):
        queries.append("org:%s is:issue is:open label:bounty" % org)

    for query in queries:
        if len(rows) >= target:
            break
        pages = 4 if not query.startswith("org:") else 1
        for page in range(1, pages + 1):
            if len(rows) >= target:
                break
            try:
                data = fetch("/search/issues?" + urllib.parse.urlencode(
                    {"q": query, "per_page": 100, "page": page,
                     "sort": "updated", "order": "desc"}))
                items = data.get("items", [])
                for item in items:
                    matched = ISSUE_URL.match(item.get("html_url") or "")
                    if not matched or matched.group(1).lower() not in allow:
                        continue
                    append(item, metadata(matched.group(1)))
                    if len(rows) >= target:
                        break
                if len(items) < 100:
                    break
            except (OSError, ValueError, KeyError, TypeError) as exc:
                errors.append("Search %s page %s: %s" % (query, page, exc))
                break

    # An issue can still be OPEN after eight competing complete submissions.
    for repo in sorted({row["repo"] for row in rows}):
        try:
            prs = []
            for page in range(1, 4):
                page_data = fetch(
                    "/repos/%s/pulls?state=open&per_page=100&page=%d"
                    % (repo, page))
                if not isinstance(page_data, list):
                    raise ValueError("Non-list response to pull request API")
                prs.extend(page_data)
                if len(page_data) < 100:
                    break
            for row in rows:
                if row["repo"] != repo:
                    continue
                marker = re.compile(
                    r"(?<![0-9])#%d(?![0-9])" % row["issue"])
                row["competing_prs"] = [
                    {"number": pr["number"], "url": pr["html_url"]}
                    for pr in prs if marker.search(
                        (pr.get("title") or "") + "\n" +
                        (pr.get("body") or ""))]
                if row["competing_prs"]:
                    row["status"] = (
                        "CONTESTED: %d open referencing PRs; payment not verified"
                        % len(row["competing_prs"]))
                elif row["stale_over_180_days"]:
                    row["status"] = "STALE >180d; sponsor/payment not verified"
                else:
                    row["status"] = "OPEN; no referencing PR found; funding not verified"
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append("PR check %s: %s" % (repo, exc))
    return rows, rejected, errors



def submission_blockers(row):
    """Hard blockers: listing != contract and an open issue != unclaimed work."""
    blockers = []
    if not row.get("funding_verified_live", False):
        blockers.append("FUNDING_NOT_VERIFIED")
    if row.get("assignees"):
        blockers.append("ALREADY_ASSIGNED")
    if row.get("competing_prs") is None:
        blockers.append("PR_CHECK_UNKNOWN")
    elif row["competing_prs"]:
        blockers.append("OPEN_REFERENCING_PRS")
    if row.get("stale_over_180_days"):
        blockers.append("STALE_ISSUE")
    if not any(row.get(key) is not None for key in
               ("advertised_usd", "advertised_sats", "observed_usd")):
        blockers.append("NO_ADVERTISED_AMOUNT")
    if row.get("repo", "").lower().startswith("tenstorrent/"):
        blockers.append("TENSTORRENT_REQUIRES_ASSIGNMENT_BEFORE_PR")
        amount = row.get("advertised_usd")
        if amount is None:
            amount = row.get("observed_usd")
        if isinstance(amount, (int, float)) and amount > 3000:
            blockers.append("AMOUNT_EXCEEDS_PUBLISHED_3000_USD_TIER")
    return blockers


def report(rows, rejected, errors, target=TARGET):
    for row in rows:
        row["submission_blockers"] = submission_blockers(row)
        row["ready_for_submission"] = not row["submission_blockers"]
    ready = sum(row["ready_for_submission"] for row in rows)
    assigned = sum(bool(row.get("assignees")) for row in rows)
    competing = sum(bool(row.get("competing_prs")) for row in rows)
    lines = ["# OneHub 50-bounty discovery queue", "",
             "Checked UTC: " + dt.datetime.now(dt.timezone.utc).isoformat(),
             "Target: %d | Open issue leads: %d | Remaining: %d" %
             (target, len(rows), max(target - len(rows), 0)), "",
             "**Paid rewards verified: 0. Live escrow verified: 0.**",
             "**Eligible for immediate submission on verified evidence: %d**" % ready,
             "Already assigned: %d | with referencing PRs: %d" % (assigned, competing),
             "Bounty platform listing is NOT proof that funds can be collected.",
             "Check expiry, claims, competing work, location and sponsor approval.",
             "",
             "| # | GitHub issue | Advertised USD | PR refs | Assigned? | Blockers |",
             "|---:|---|---:|---:|---|---|"]
    for i, row in enumerate(rows, 1):
        v = row.get("advertised_usd")
        if v is None:
            v = row.get("observed_usd")
        price = "$%.2f" % v if v is not None else "Unverified"
        competing = row.get("competing_prs")
        lines.append("| %d | [%s#%d](%s) | %s | %s | %s | %s |" % (
            i, row["repo"], row["issue"], row["issue_url"],
            price, len(competing) if competing is not None else "Unknown",
            "Yes" if row.get("assignees") else "No",
            ", ".join(row["submission_blockers"])))
    lines += ["", "Excluded/duplicate: %d | errors: %d" % (
        rejected, len(errors))]
    for error in errors:
        lines.append("- " + error)
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=50)
    ap.add_argument("--seeds", type=Path,
                    default=Path(__file__).with_name("bounties.json"))
    ap.add_argument("--out", type=Path, default=Path("onehub-50-bounties.md"))
    ap.add_argument("--json-out", type=Path, default=Path("onehub-50-bounties.json"))
    args = ap.parse_args(argv)
    seeds = json.loads(args.seeds.read_text(encoding="utf8"))
    rows, rejected, errors = discover(target=args.target, seeds=seeds)
    args.out.write_text(report(rows, rejected, errors, args.target), encoding="utf8")
    args.json_out.write_text(json.dumps({
        "target": args.target, "discovered": len(rows), "funded_verified": 0,
        "ready_for_submission": sum(not submission_blockers(row) for row in rows),
        "entries": rows, "errors": errors}, indent=2), encoding="utf8")
    print("Target %d; discovered %d open leads; 0 funded verified; %d ready; %d errors" %
          (args.target, len(rows), sum(not submission_blockers(row) for row in rows),
           len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
