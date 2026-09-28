# M2 dashboard

The dashboard reads the PostgreSQL API at `http://127.0.0.1:8767` and falls
back to the normalized M0 fixture file when the API is unavailable. Start the
backend and dashboard from the repository root:

```text
tools\start_backend.ps1
python tools/serve_web.py
```

Open `http://127.0.0.1:8766`. API scores remain authoritative. The browser does
not read raw fixture responses or recalculate scores from unresolved formulas.
Set `window.QD766_API_BASE` before `app.js` when deploying against a public
HTTPS backend URL.
