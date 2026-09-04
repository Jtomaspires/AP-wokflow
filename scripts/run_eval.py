"""Write golden_dataset/baselines/v1.json. Exit 1 if success < threshold."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.eval_harness import run_all_sync  # noqa: E402

OUT = ROOT / "golden_dataset" / "baselines" / "v1.json"


def main() -> int:
    report = run_all_sync()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    success = report["success"]
    threshold = report["threshold"]
    print(f"workflow success {success:.2f} (threshold {threshold:.2f}) -> {OUT}")
    for row in report["results"]:
        mark = "ok" if row["workflow_ok"] else "FAIL"
        print(f"  {row['id']}: {mark}")
        if not row["workflow_ok"]:
            for name, passed in row["dimensions"].items():
                if not passed:
                    print(
                        f"    {name}: actual={row['actual'].get(name)!r} "
                        f"expected={row['expected'].get(name)!r}"
                    )
    return 0 if success >= threshold else 1


if __name__ == "__main__":
    raise SystemExit(main())
