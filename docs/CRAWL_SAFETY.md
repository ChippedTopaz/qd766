# DVCQG Crawler Safety Requirements

These are mandatory operational constraints for this project.

## Objective

Collect only the data needed for the DVCQG evaluation dataset while minimizing traffic, avoiding concurrent load, and failing closed when the site appears to reject or rate-limit requests.

## Mandatory safeguards

1. **Sequential only.** Maximum concurrency is 1 request/session at a time. Never use multiprocessing, async fan-out, request pools, or parallel province crawls.
2. **Low request rate.** Use a configurable delay between province requests, with random jitter. Default target is deliberately conservative rather than optimized for speed.
3. **One province at a time.** Prefer a fresh browser context/session per province when browser interaction is required, then close it before the next province.
4. **Respect server signals.** Treat HTTP 429, 403, WAF `Request Rejected`, repeated 5xx responses, timeouts, or abnormal HTML responses as stop/defer signals. Do not keep retrying aggressively.
5. **Circuit breaker.** After a small number of consecutive rejection/rate-limit signals, stop the run and record the reason. Do not continue hammering the endpoint.
6. **No evasion.** Do not rotate IPs, use proxy pools, spoof identities, bypass WAF controls, or otherwise attempt to evade access controls.
7. **No unnecessary requests.** Reuse the national discovery result, avoid recrawling unchanged data, and never request individual agencies/communes unless a confirmed endpoint requires it.
8. **Small daily budget.** The normal production run is limited to the required national/province dataset. Do not create hidden or repeated polling loops.
9. **Checkpoint immediately.** Persist success/failure status after each province so an interrupted run can resume without repeating successful requests.
10. **Fail closed.** If the site's behavior changes or the response cannot be verified as belonging to the requested province, record the failure and stop/defer rather than guessing.
11. **Preserve evidence.** Save the exact successful API response as RAW JSON and record timestamp, request scope, response hash, HTTP status, and verification status.
12. **No fabricated success.** Never mark a province successful based only on HTTP 200/201. The returned data must be verified against the requested province.

## Automation policy

The intended production schedule is one scheduled run per day around 00:00 Asia/Ho_Chi_Minh, but scheduling must not override safety controls. If the runner is blocked or receives rejection signals, the workflow should stop and report the condition rather than retrying throughout the night.

Before enabling unattended daily execution, validate the crawler on the actual GitHub Actions environment. If that environment is consistently rejected by the source, do not work around the rejection with IP/proxy rotation; evaluate a compliant alternative execution environment.
