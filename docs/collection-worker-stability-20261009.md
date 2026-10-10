# TTHC worker stability review — 09/10/2026

## Incident and live recovery

Operator output: worker started 05/10 15:24:13, state Ready, runtime cap PT72H, result 267014 (0x41306 terminated). Live read-only audit: last successful job 08/10 15:26:45; 14 jobs queued with attempts=0, no running job, circuit closed, lease empty. Operator backed up Task XML, changed limit to PT0S and started the worker. All 14 backlog jobs subsequently succeeded. Live health check at 08:09:17 Vietnam: IDLE, queued=0, running=0. Daily refresh remains 05:00 and was not changed or restarted.

## Implemented source changes (not activated on the running process)

- Worker task creation explicitly uses unlimited runtime; dedicated worker settings do not alter backend or daily-task settings.
- Controlled HTTP guard renews both the global lease and running-job lock before every source request, preventing a long paginated collection from being reclaimed after 30 minutes while it is still active. This is request-driven renewal, not a standalone background heartbeat.
- Publication, credit settlement, retry and failure mutation require current ownership of BOTH global and job lease. A stale worker cannot publish or charge/refund someone else's job. Lock ordering is control then job, matching claims.
- SQLAlchemy failures in the outer worker loop retry at 5/10/20/40/60 seconds, capped at 60; logs contain exception type, not SQL/credentials. A lost lease does not kill the worker loop. Other fatal errors still rely on Task Scheduler failure restart, rather than suppressing programmer/configuration errors indefinitely.
- Worker state logs include UTC time and duration for capacity observation.
- `check_collection_worker_health.py`: read-only queue/lease diagnostic. Reports QUEUE_STALLED when pending work is older than 10 minutes, no lease and no completion within 10 minutes; LEASE_STALE after 30 minutes. It does not send notifications or automatically restart tasks. SAFETY_PAUSED is deliberately not auto-resumed.
- `harden_collection_worker_task.ps1 -Confirm`: backs up XML, retains actions/principal/triggers, sets PT0S and 10 failure restart attempts at one-minute intervals. Does not stop/start workers or touch database. Without Confirm it is check-only.

## Conservative operating envelope

Retain one globally leased job at a time; at most 3 source HTTP requests concurrently; 0.4-second pacing; 10-second connection and 45-second HTTP timeouts. Source 401/403/429 or rejection HTML still trigger safety stop; no bypass or automatic circuit reset. Request failures retain bounded HTTP retries/checkpoints and maximum three job attempts. Successful group checkpoints are reused on retry. Per-account pending limit remains two; idempotency/dataset reuse remains in place. No change to pricing, approval, permissions or subscription grants.

These limits bound outbound pressure; they are not a promise that an unlimited number of users will receive immediate results. Distinct requests accumulate in PostgreSQL. No new global queue-admission cap or automatic watchdog was introduced. Monitor oldest waiting time; if >10 minutes, check worker health and upstream state before increasing concurrency. Saturation beyond this envelope requires measured provider behavior and a separate admission-control decision.

## Verification

- Full backend suite: 419 tests passed, including the additional sustained-concurrency test. Targeted suite: 7 concurrent-collection tests and 5 worker-resilience tests passed.
- Simulated queue burst: 1,000 sequential submissions, 100 unique jobs, deduplicated and processed once each; approximately 0.5–0.7 seconds for the in-memory queue test with mocked import. This is not external/API throughput or a concurrent PostgreSQL benchmark.
- Simulated transport: 20 consecutive snapshots/120 HTTP responses, peak at most 3 active calls, no threads left active. Existing tests cover checkpoint resume, pagination, corrupt checkpoint rejection and source safety stops.
- Fault injection: lost ownership blocks import and settlement; lease renewal prevents premature takeover; three failed job attempts do not prevent the next job; transient DB outage resumes without logging secrets.
- Three edited/new PowerShell scripts parsed successfully. Real Task Scheduler modification was not performed by this task (restricted permissions); operator's earlier PT0S change is already active.

## Rollout boundary

No frontend, database migration, live queue records, Credit ledger or formula configuration changed by this optimization. No source load test was run against DVCQG. The running worker loaded code before these changes: new behavior requires a separately reviewed worker restart/rollout. Keep pending public-registration changes out of a worker-only release. Registration schema 0025 is not required by these worker-only changes. Before activation, back up the worker source/task XML, verify no active job, verify exact task/process identity, and restart only QD766 Worker. Preserve existing environment and 05:00 scheduler. Never run the broad task-registration script merely to activate this fix; it manages other tasks too.
