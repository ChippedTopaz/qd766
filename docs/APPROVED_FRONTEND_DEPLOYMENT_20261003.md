# Approved frontend integration — 2026-10-03

The user approved the Bento frontend, formula handbook, read-only preview operations and compact leadership Excel headers/column widths. Main baseline before integration: `e4307bd`; reviewed frontend: `8d126ce`. Existing pre-Bento tag remains available for source rollback.

The existing annual refresh batch `8b023c82-022e-45f0-94aa-323e10cc3334` completed 34/34 provinces with zero failed at 08:27 Vietnam time. Completion does not prove every subordinate agency has every field supplied by the source.

This session was not granted write permission to `D:\QD766\app\web`. Production deployment must therefore be run by the user:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\deploy_reviewed_frontend.ps1
```

The script backs up the existing assets in the ignored `.tmp-frontend-backups` directory, checks SHA256, copies only CSS/compiled JS/vendor files and publishes index last. It does not copy fixture data, change configuration/secrets, migrate the database, create jobs, alter circuit state or stop/restart scheduled tasks. It restores backed-up assets if copying fails. The backup directory must be retained.

Rollback using the exact directory printed as `FRONTEND_BACKUP`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\deploy_reviewed_frontend.ps1 -RestoreBackup "<FRONTEND_BACKUP directory>"
```

After deployment, refresh 8767 with Ctrl+F5 and check overview, formula handbook, operations and leadership Excel export. Production UI verification is pending until the user runs deployment. Authentication, trial credit and payment integration are outside this deployment.

## Integration verification

- 87 Python tests passed.
- Leadership Excel, Bento, formula handbook and summary-only UI tests passed.
- Fresh-directory Netlify packaging and asset allowlist checks passed. An initial attempt refused an existing stale `netlify-public` directory by design; that directory was preserved.
- Frontend deployment and checksum-verified restore succeeded against an isolated workspace test target. No production files were written during this test.
