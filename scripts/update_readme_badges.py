"""自動更新 README badges（5ev／架構健檢 W2b）。

由收工檢查.bat 在 pytest 綠燈後呼叫：
    python scripts/update_readme_badges.py [pytest_report.xml]

- tests badge：讀 pytest --junitxml 產出的報告（tests - skipped - failures
  - errors ＝ passed），**抄實跑輸出、不用預估值**（PRINCIPLES 收工紀律）。
- version badge：讀 pyproject.toml（單一事實源）。

任何一步失敗以非零碼結束並印明原因——bat 端警告但不擋 commit
（badge 過期是 docs 債，不該擋住程式碼收工）。
"""
from __future__ import annotations

import re
import sys
import tomllib
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def passed_count(report_path: Path) -> int:
    root = ET.parse(report_path).getroot()
    suite = root if root.tag == "testsuite" else root.find("testsuite")
    if suite is None:
        raise SystemExit(f"junitxml 缺 testsuite 節點：{report_path}")
    tests = int(suite.attrib.get("tests", 0))
    skipped = int(suite.attrib.get("skipped", 0))
    failures = int(suite.attrib.get("failures", 0))
    errors = int(suite.attrib.get("errors", 0))
    if failures or errors:
        raise SystemExit(f"報告含紅燈（failures={failures} errors={errors}）——不更新 badge")
    return tests - skipped


def main() -> int:
    report = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "pytest_report.xml"
    if not report.is_file():
        raise SystemExit(f"找不到 pytest 報告：{report}（bat 需以 --junitxml 執行）")
    passed = passed_count(report)
    with open(ROOT / "pyproject.toml", "rb") as f:
        version = tomllib.load(f)["project"]["version"]

    text = README.read_text(encoding="utf-8")
    new = re.sub(
        r"badge/tests-\d+%20passed",
        f"badge/tests-{passed}%20passed",
        text,
    )
    new = re.sub(
        r"badge/version-[0-9.]+-",
        f"badge/version-{version}-",
        new,
    )
    if new != text:
        README.write_text(new, encoding="utf-8")
        print(f"README badges updated: tests-{passed} / version-{version}")
    else:
        print(f"README badges already current: tests-{passed} / version-{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
