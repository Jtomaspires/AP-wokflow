"""Simulated shadow run (assistant Fase 7): same harness, separate artifact."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_harness import run_all_sync  # noqa: E402

OUT = ROOT / "golden_dataset" / "baselines" / "shadow_v1.json"


def main() -> int:
    report = run_all_sync()
    report["mode"] = "shadow"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"shadow success {report['success']:.2f} -> {OUT}")
    return 0 if report["success"] >= report["threshold"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
