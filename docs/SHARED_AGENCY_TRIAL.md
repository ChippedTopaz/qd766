# Shared registration link — local acceptance first

One shared link, sent through Zalo or other channels, permits Google-authenticated users to select their own province and child agency. It never grants province/national/admin privileges. The token is only shown once, hashed in storage, passed through the URL fragment and bound to the server-side OAuth attempt. The link expires after 1–30 days and has a 1–1000 registration capacity. Capacity is consumed at submission, not at opening the link or logging in. Rejection does not reset capacity; revocation/expiry prevents new submissions, not admin review of submissions already received.

Draft and pending users can only access registration status and the directory of agency names, with session authentication. They cannot access dashboard data, exports, paid requests, Credit administration or admin APIs. Submissions and all administrator changes require CSRF. Submitted registrations are immutable to the applicant. Admin can correct province/agency before reviewing. Bulk review handles at most 100 distinct IDs, transactionally, with row locks; retries skip reviewed registrations.

Approval sets the account to agency scope and begins one free calendar month with 100 subscription Credit using the existing subscription and wallet ledger. No renewal/reapproval/login grants a second trial. Approval does not invalidate the pending login session: the waiting screen polls status every 15 seconds when visible and exposes “Vào hệ thống”. Returning users log in at the homepage using the same Google identity without the invitation link. No automatic email or Zalo messaging is implemented.

## Local check

Restart the reviewed source-wallet local Google trial on port 8771. The launcher explicitly enables shared registration and creates missing tables only in its isolated test schema. Administrator: Mời dùng thử → Link đăng ký dùng chung. Pending submissions: Đăng ký chờ duyệt → select rows → Duyệt đã chọn. Test new identities in a separate browser/profile. Existing admitted identities retain their scope and trial; they do not register again.

## Production release gate

Update 2026-10-05: database migration 0016/0017 is applied. Public launcher now supports explicit `--real-wallet --shared-registration`; it verifies the real wallet and registration schema read-only before starting. Windows registration/restart preserves and verifies the flag. Feature is NOT enabled in the currently running public task until the operator runs:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\register_public_backend_task.ps1 -ReplaceExisting -RealWallet -SharedRegistration
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\restart_public_backend.ps1
```

Expected check/runtime output includes `SHARED_REGISTRATION=True`. Task XML is backed up before replacement. This does not create invitations, approve accounts, issue extra Credit or deploy Netlify. Existing individual invitations continue working. After matching frontend release, administrator can create a shared link and approve agency-only registrations. Do not share a new link before the matching frontend is published.

Production remains unchanged. `shared_registration_enabled` defaults to false and is deliberately NOT inherited from environment. Before a separate approved release, back up PostgreSQL, apply reviewed migration `20261005_0016`, explicitly enable shared registration in the public launcher with invite-only login and source wallet, restart, then deploy matching UI. Never enable the feature against an unmigrated database. Existing single-use invitations remain supported.

## Security checks

Tests cover pending data denial, agency-only scope, wrong-province/root rejection, unauthorized/CSRF denial, capacity, expiry/revocation, repeated submission, repeated approval/login, 100 Credit once, rejection, administrator correction, batch rollback, existing direct invitations, and disabled-feature behavior. Google token exchange is mocked in automated tests; real OAuth and browser acceptance must be checked separately.
