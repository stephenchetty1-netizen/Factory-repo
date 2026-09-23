# OneHub Bounty Viability Scout

A **read-only** daily check of Bitcoin-funded bounty candidates, using GitHub's official API.

## Why it exists

PrimalHQ/primal-android-app#1055 advertises **50,000 sats** on Lightning Bounties,
but at the 23 September 2026 check multiple other contributors had already
submitted implementations. A reward listing by itself is not a viable paid
job, and a GitHub issue can be open even when several solutions await review.

The scout checks:

- whether the underlying GitHub issue is still open;
- whether it has an assignee;
- the number and URLs of open PRs that **explicitly** reference that issue;
- whether a closed issue is still advertised by a stale external bounty page.

It **does not verify live escrow or expiry** on the rewards platform.
Even a result of "UNCLAIMED ON GITHUB" requires human checks of funding,
reward lock/expiry, platform qualification, competing contributors, and the
maintainer's preferred approach. GitHub PR titles without explicit issue
references may be missed; a clean report is not a guarantee of exclusivity.

## Run

```sh
python3 -m unittest discover -s onehub-bounty-hunter -p 'test_*.py' -v
python3 onehub-bounty-hunter/bounty_scout.py \
  --out onehub-bounty-hunter/bounty-report.md \
  --json-out onehub-bounty-hunter/bounty-report.json
```

Python 3.12 standard library only. No wallet, seed phrase, exchange account,
paid API, miner, proxy, VPN or customer data is required. The optional
`GITHUB_TOKEN` environment variable raises API rate limits and is used for
read-only requests.

## Automation

GitHub Actions workflow `.github/workflows/onehub-bounty-viability.yml`
runs daily at 06:27 UTC and supports manual dispatch from the Actions tab.
It uploads the resulting markdown and JSON as run artifacts for 7 days.
Workflow runs are not guaranteed if Actions are disabled, the repo becomes
inactive, GitHub delays scheduled runs, or provider APIs fail. A successful
run is evidence of completed research **only**, not a BTC payment.

## Earning workflow

1. Verify a bounty is funded, open, claimable and realistically uncrowded.
2. Discuss the proposed implementation with maintainers if required.
3. Build an original solution against the official repository; run tests.
4. Submit a PR through an authorised fork and wait for maintainer acceptance.
5. Claim the reward using the platform's actual Lightning payout method.

OneHub does not claim bounty rewards, fake GitHub identities, send PR spam,
spend money, move Bitcoin or bypass exchange/payment rules.
