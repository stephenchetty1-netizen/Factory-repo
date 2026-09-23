#!/usr/bin/env python3
"""Read-only funded-bounty viability checks. No mining, claims, transfers or trades."""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": "OneHub-Bounty-Scout/1.0"}
if os.environ.get("GITHUB_TOKEN"):
    HEADERS["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]


def github_json(path):
    if not path.startswith("/") or "://" in path:
        raise ValueError("Expected a GitHub API path")
    req = urllib.request.Request(API + path, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.load(response)


def relevant_pr(pr, number):
    # GitHub may keep an issue open while many contributors have submitted a fix.
    # A PR reference in its body/title is the strongest inexpensive signal.
    text = (pr.get("title") or "") + "\n" + (pr.get("body") or "")
    pattern = r"(?<![0-9])#" + re.escape(str(number)) + r"(?![0-9])"
    return bool(re.search(pattern, text))


def verify(entry, fetch=github_json):
    repo = entry["repo"]
    number = int(entry["issue"])
    issue = fetch("/repos/%s/issues/%s" % (repo, number))
    if issue.get("pull_request"):
        raise ValueError("Seed points to a PR, not an issue")
    matching = []
    for page in range(1, 6):
        prs = fetch("/repos/%s/pulls?state=open&per_page=100&page=%s" % (repo, page))
        for pr in prs:
            if relevant_pr(pr, number):
                matching.append({"number": pr["number"], "title": pr["title"],
                                 "url": pr["html_url"]})
        if len(prs) < 100:
            break

    state = issue.get("state", "unknown")
    if state != "open":
        verdict = "CLOSED: do not work or assume payout"
    elif matching:
        verdict = "COMPETING PULL REQUESTS: seek maintainer direction before work"
    elif issue.get("assignee") or issue.get("assignees"):
        verdict = "ASSIGNED: seek maintainer direction before work"
    else:
        verdict = "UNCLAIMED ON GITHUB: funding and acceptance still require verification"
    return {
        "repo": repo, "issue": number, "title": issue.get("title", ""),
        "issue_url": issue.get("html_url", ""), "issue_state": state,
        "issue_updated_at": issue.get("updated_at"),
        "advertised_sats": entry.get("advertised_sats"),
        "bounty_url": entry.get("bounty_url"),
        "funding_verified_live": False,  # Never mistake advertised sats for escrowed funds.
        "open_competing_prs": matching, "verdict": verdict,
    }


def render(rows, errors):
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    out = ["# OneHub funded-bounty viability report", "", "Checked: " + now, "",
           "This is READ-ONLY research. A listed reward is NOT payment or confirmed escrow.",
           "Verify platform funding, expiry, eligibility, and maintainer acceptance separately.", ""]
    for row in rows:
        out += ["## " + row["repo"] + "#" + str(row["issue"]), "",
                row["title"], "",
                "GitHub issue: " + row["issue_url"],
                "Advertised sats: " + str(row["advertised_sats"]),
                "Funding page: " + str(row["bounty_url"]),
                "State: " + row["issue_state"],
                "Open PRs that explicitly reference issue: " + str(len(row["open_competing_prs"])),
                "Decision: " + row["verdict"], ""]
        for pr in row["open_competing_prs"]:
            out.append("- #" + str(pr["number"]) + " " + pr["url"])
        out.append("")
    if errors:
        out += ["## Retrieval errors", ""]
        for err in errors:
            out.append("- " + err)
    return "\n".join(out) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=Path, default=Path(__file__).with_name("bounties.json"))
    parser.add_argument("--out", type=Path, default=Path("bounty-report.md"))
    parser.add_argument("--json-out", type=Path, default=Path("bounty-report.json"))
    args = parser.parse_args(argv)
    seeds = json.loads(args.seeds.read_text(encoding="utf-8"))
    rows, errors = [], []
    for entry in seeds:
        try:
            rows.append(verify(entry))
        except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
            errors.append("%s#%s: %s" % (entry["repo"], entry["issue"], str(exc)))
    args.out.write_text(render(rows, errors), encoding="utf-8")
    args.json_out.write_text(json.dumps({"results": rows, "errors": errors},
                                        indent=2), encoding="utf-8")
    print("Checked %s issues; %s errors; output %s" % (len(rows), len(errors), args.out))
    # Never report stale/failed network queries as a clean result.
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
