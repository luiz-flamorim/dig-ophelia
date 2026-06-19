#!/usr/bin/env python3
"""Alias for server — use main.py in production."""

from __future__ import annotations

import server

if __name__ == "__main__":
    raise SystemExit(server.main())
