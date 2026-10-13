# Worker recovery — 12/10/2026

## Incident / recovery

- Read-only audit at 14:29 Vietnam time: 11 queued jobs, one running since 08:45, 13 pending paid requests. Lease owner `VIET-HCC:2240` was absent on the same host; lease heartbeat and log stopped. Last success was 08:44.
- Circuit closed, no recent failed/halted jobs. Windows Event Log and Task Scheduler inspection denied in agent context, so the OS-level exit/termination cause is not established. Last saved task settings already had unlimited runtime, 10 restarts/minute, IgnoreNew and no battery stop; those are not evidence of the current stop cause.
- PostgreSQL backup before retry: `.tmp-worker-recovery-backups/qd766-20261012-143335.dump`, 64,288,247 bytes; SHA256 `1C8B2C9C53A72F99B813E6468048E78AE319FEDA7086CC01B81AFFC81680F421`.
- Background wrapper launch did not persist in agent environment. Recovery ran the existing controlled worker directly with `--once`, preserving SQL lease fencing, stale-job requeue and safety stops. No new paid requests, no manual lease clearing or SQL financial edits.
- Stuck job `cd5a60b1-e455-45fa-8c5d-747a24a8d58e` succeeded at 14:35; remaining backlog plus one new job succeeded by 14:37. Total: 13 jobs serving 14 requests. Read-only settlement audit: 14 ready requests, 70 Credit, exactly 14 source charge events, no legacy charge events. No duplicate charge.
- At 14:41: queue IDLE, queued=0, running=0, lease cleared.

## Recurrence mitigation / limits

- `start_controlled_worker.ps1` supervises child exits, retries after 5/10/20/40/60 seconds, logs start/exit/exception type without secrets. Does not kill running jobs or bypass collector circuit.
- `run_collection_worker.py` logs PID/start and unexpected/startup fatal exception type, exits nonzero, disposes resources. Existing lease/retry/Credit settlement unchanged.
- `harden_collection_worker_task.ps1` validates existing action, backs up task XML and reports previous run/result. Adds one idempotent two-minute keep-alive trigger while preserving existing triggers/action/principal; IgnoreNew avoids interrupting a live task. Daily collection task unchanged.
- Use Disable-ScheduledTask for intentional worker maintenance; Stop alone permits the keep-alive trigger to start it again. Collector safety circuit still prevents provider requests when open.
- PowerShell syntax, offline supervisor imports and two recovery tests PASS; final full regression rerun performed separately. Persistent supervisor/task activation still requires human execution because Task Scheduler access is unavailable here. No guarantee against machine/power/OS outages.

## Activation verified

- Human applied hardening and restart at 14:45: WORKER_SETTINGS=PASS, WORKER_RESTART=PASS. Saved task XML confirms IgnoreNew, unlimited runtime and `QD766WorkerKeepAlive` repeating every two minutes, starting 14:47:03.
- Previous Task result 3221225786 = 0xC000013A, STATUS_CONTROL_C_EXIT (Microsoft NTSTATUS). This identifies a console-interruption termination status, not the actor or action that generated it; do not attribute it to a user, antivirus, runtime limit or power condition without event evidence.
- Native worker log confirms start at 14:45:21 and successful automatic processing of new job `d19ee55f-2488-49ed-9d6e-a44cae1026af` at 14:47:02, followed by idle.
- At 14:50:02 Vietnam time: IDLE, queued=0, running=0, no lease. Final full regression run: 493 tests PASS; recovery tests also rerun after startup-fatal logging adjustment.
- Direct PID inspection in the restricted agent session does not establish host process visibility; live Task state comes from human output and operation is corroborated by database/job logs.
- Reference: https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/596a1078-e883-4972-9bbc-49e60bebca55
