#!/usr/bin/env python3
"""Fail fast when running on unsupported Python versions.

Chromadb (and its onnxruntime dependency) do not yet publish wheels for
Python 3.13+, so installs on very new interpreters tend to fail with
"No matching distribution found" errors. This helper exits with a clear
message before you spend time compiling large dependencies.
"""
from __future__ import annotations

import sys
from textwrap import dedent

MIN = (3, 10)
MAX_EXCLUSIVE = (3, 13)

current = sys.version_info[:2]
if not (MIN <= current < MAX_EXCLUSIVE):
    raise SystemExit(
        dedent(
            f"""
            Unsupported Python version detected: {sys.version.split()[0]}
            Use Python 3.10–3.12 (or run inside Docker/WSL). Newer versions like
            3.13/3.14 lack published wheels for some dependencies (e.g.,
            onnxruntime via ChromaDB), which leads to installation failures.
            """
        ).strip()
    )

print(f"Python version OK for catalogue-chat: {sys.version.split()[0]}")
