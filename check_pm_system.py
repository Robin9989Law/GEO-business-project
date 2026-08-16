#!/usr/bin/env python3
"""根目录入口。实现在 工程/check_pm_system.py。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "工程"))
import check_pm_system

if __name__ == "__main__":
    raise SystemExit(check_pm_system.main())
