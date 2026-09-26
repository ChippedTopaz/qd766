# M2 dashboard

The dashboard is a dependency-free prototype backed by the normalized M0
fixtures. Rebuild its data and start the local server from the repository root:

```text
python tools/build_web_data.py
python tools/serve_web.py
```

Open `http://127.0.0.1:8766`. API scores remain authoritative. The browser does
not read raw fixture responses or recalculate scores from unresolved formulas.
