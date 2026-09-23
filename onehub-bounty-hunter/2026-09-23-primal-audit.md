# Bounty audit — 2026-09-23

## Original target

- Issue: https://github.com/PrimalHQ/primal-android-app/issues/1055
- Publicly advertised reward: 50,000 sats.
- GitHub state at connector readback: **open**, **unassigned**.
- Crucial finding: eight open pull requests already implement or explicitly
  propose translations for the same issue:
  - https://github.com/PrimalHQ/primal-android-app/pull/1056
  - https://github.com/PrimalHQ/primal-android-app/pull/1068
  - https://github.com/PrimalHQ/primal-android-app/pull/1091
  - https://github.com/PrimalHQ/primal-android-app/pull/1094
  - https://github.com/PrimalHQ/primal-android-app/pull/1095
  - https://github.com/PrimalHQ/primal-android-app/pull/1102
  - https://github.com/PrimalHQ/primal-android-app/pull/1104
  - https://github.com/PrimalHQ/primal-android-app/pull/1111

There is no credible case for submitting a ninth near-duplicate without
maintainer direction. A reward shown in a public listing is **not** an
assurance of payout to another contributor.

## Cross-platform comparisons

- Web translation issue https://github.com/PrimalHQ/primal-web-app/issues/133
  is open with many competing open PRs.
- iOS translation issue https://github.com/PrimalHQ/primal-ios-app/issues/206
  is open with seven competing open translation PRs.

## Stale-listing control case

- https://github.com/MagnivOrg/prompt-layer-library/issues/254 is already
  **closed** even though an external Lightning Bounties listing still appears
  in search results with an advertised amount.

## What was actually executed

A read-only bounty viability scanner plus tests and daily GitHub Actions
workflow were committed to the user's separate Factory-repo under
`onehub-bounty-hunter/`. It produces research reports, not payments.
No upstream Primal change, reward claim, transaction or BTC receipt
has been made. Source packages were committed and read back successfully,
but the first hosted workflow run has not been verified.
