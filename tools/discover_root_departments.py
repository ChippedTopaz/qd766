#!/usr/bin/env python3
"""Backward-compatible entry point.

The discovery logic now lives in discover_dvc_structure.py because we need more
than rootDepartmentId discovery: we also need the province department identity
and the AGENCY/COMMUNE catalog derived from evaluation.
"""

from discover_dvc_structure import main


if __name__ == "__main__":
    raise SystemExit(main())
