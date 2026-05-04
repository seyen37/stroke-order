#!/usr/bin/env python3
"""
HISTORY.md cherry-pick — 2026-05-04
====================================

把 r25-r28 共通性沉澱的修訂 entry + 案例索引插入 personal-playbook 的 HISTORY.md。

Inserts:
- §A 加：「### 2026-05-04（第十一次修訂）」entry
- §B 加 B.12 / B.13 / B.14 三個案例索引

Idempotent：重跑檢查 marker 已在則 skip。

執行（在 personal-playbook 根目錄）：

    python3 history_cherry_pick_2026-05-04.py

完成後：

    git diff HISTORY.md
    git add PROJECT_PLAYBOOK.md HISTORY.md
    git commit -m "feat(playbook): r25-r28 共通性原則 + SoT 漂移修復"
    git push origin main
"""
from pathlib import Path
import sys

HISTORY = Path("HISTORY.md")
if not HISTORY.exists():
    sys.exit("❌ HISTORY.md 不在當前目錄；請 cd 到 personal-playbook 根目錄")


# =====================================================================
# Patch 1：§A 第十一次修訂 entry
# =====================================================================

PATCH_1_REVISION = """
### 2026-05-04（第十一次修訂）

**8 處變動，r25–r28 共通性沉澱 + SoT 漂移修復**：

- **§3.6 補強**：PowerShell 指令給法補完整 4 條規則（禁尖括號 placeholder / 禁 `&&` / `git add` 分行 / `HEAD~N` 相對引用），原本只有 lock file + `::` 註解 2 條
- **§3.10（新）Cowork sandbox git index 操作 SOP**：補 §3.9 跨 session race 的具體 mitigation — `rm + read-tree` 重建 + 單一 batched `git add`，避開連續 add 撞 `bad signature 0x00000000`
- **§3.11（新）i18n 檔名：原文 + slug 雙存**：跨平台檔名穩 + 內容保語意（中文標題 + 拼音 slug + inline 註解對照）
- **§5.8（新）跨 phase 共享檔的 commit：誠實標註 > hunk 強拆**：累積多 phase 改動沒 commit 時，commit message 註明「同檔含其他 phase 改動」比 hunk staging 風險低
- **§8.13 / §8.14 / §8.15（補回 SoT 漂移）**：此 3 章原於 stroke-order 副本累積（4/29 SoT 規則確立**前**寫的），自 5/2 起再多次補強內容後從未 sync 回 SoT，此次一併補回到 SoT
- **§8.16（新）Mixed-arity tuple 解構 pattern**：tuple 加 element 用 `[:N]` 解構 + `*_` trailing，向後兼容多解構點
- **§8.17（新）多輪 reference-image 視覺迭代 SOP**：擴展 §8.15，含 plan + design Q + 視覺驗證 + bump 每輪 SOP
- **§8.18（新）AI-friendly 設定檔 = YAML frontmatter + Markdown body 雙層**：給 AI/人類雙讀的設定檔黃金標準，frontmatter 機器精確 + body 給 AI/人類
- **§8.19（新）Schema versioning：嚴格 + migration table + 友善錯誤**：schema 字串 baked into file，未知 schema 嚴格拒絕但訊息列已知版本，避免沉默吞錯
- **§8.20（新）By-kind dispatch dict 取代 if/elif 鏈**：endpoint 通用化用 VALIDATORS / SUMMARIZERS dict 集中派遣，加新 kind 不動核心邏輯
- **§8.21（新）Schema 通用化時 dual-write 漸進遷移**：加新通用欄位時 legacy 欄位繼續寫，後續 phase 慢慢遷移；不 big-bang 切換

緣由：stroke-order 2026-05-04 一場 cowork session 跑完 r25 ring UI / r26 線條顏色 + G-code 分組 / r27 .mandala.md 純前端 export-import / r28 gallery 接 mandala upload 4 個 phase。過程中浮現的共通性原則 + 4/29 SoT 規則確立後 stroke-order 副本累積但未同步的 §8.13-15，此次一併沉澱進 SoT。

詳見 stroke-order 的：
- `docs/decisions/2026-05-04_phase5b_r25_mandala_ring_ui.md`
- `docs/decisions/2026-05-04_phase5b_r26_mandala_colors_and_warning.md`
- `docs/decisions/2026-05-04_phase5b_r27_mandala_state_export_import.md`
- `docs/decisions/2026-05-04_phase5b_r28_gallery_mandala_upload.md`
- `docs/journal/2026-05-04_session_log.md`

跨 ref（§B）：B.12 / B.13 / B.14 三案例索引（見下）。

"""


# =====================================================================
# Patch 2：§B 加 B.12 / B.13 / B.14 三個案例索引
# =====================================================================

PATCH_2_CASES = """
### B.12 § 8.18 + §8.19 + §8.13 frontmatter + body 雙層 schema — stroke-order .mandala.md export/import (r27)

**起源**：stroke-order 2026-05-04 Phase 5b r27。User 要求曼陀羅模式提供「下載自己繪製設定 → 跨機帶走 → 匯入繼續編輯」的本機檔機制，且要 AI 能解讀此檔重現視覺。

**抽象結論**：給 AI / 人類雙讀的設定檔，純 JSON 不夠 AI-friendly、純散文不夠機器精確。**YAML frontmatter（機器嚴格 parse）+ Markdown body（人類 / AI 自由 prose）** 雙層是黃金標準。同檔共用 schema 字串 (`stroke-order-mandala-v1`) 給 migration table 嚴格驗證，避免沉默吞錯。中文 / 非 ASCII 標題場景另用「原文 + slug 雙存」(§3.11)。

**驗證真實案例**：`docs/decisions/2026-05-04_phase5b_r27_mandala_state_export_import.md`
- 雙 tier：Tier 1 `.mandala.md`（YAML frontmatter + auto prose body）+ Tier 2 SVG 內嵌 `<metadata><mandala-config>` JSON
- 完全純前端（js-yaml + pinyin-pro CDN）— 不上傳任何資料到伺服器
- 14 schema validation tests（PyYAML round-trip + inline 拼音註解 + body 兩 section 結構）

### B.13 § 8.20 + §8.21 + §3.11 by-kind dispatch + dual-write + i18n filename — stroke-order gallery 通用化 (r28)

**起源**：stroke-order 2026-05-04 Phase 5b r28。把既有 5g 公眾分享庫從「PSD only」通用化成「多 kind」（先收 mandala），對齊未來 user 上傳 + 評分機制需求。

**抽象結論**：endpoint / service 通用化給多 kind 時，最常見 anti-pattern 是 if/elif 鏈散在 create/list/download 多處。用 **dict-of-functions（VALIDATORS / SUMMARIZERS）** 集中派遣，加新 kind 只動 dict 不動核心邏輯。Schema 升版時 legacy column 繼續 dual-write 給後續 phase 慢慢遷移空間，不 big-bang 切換避免 rollback 困難。

**驗證真實案例**：`docs/decisions/2026-05-04_phase5b_r28_gallery_mandala_upload.md`
- DB schema 加 `kind` + `summary_json`（PSD 仍寫 legacy `trace_count` / `unique_chars` / `styles_used`）
- VALIDATORS / SUMMARIZERS dict 派遣，create_upload / list_uploads / download endpoint 核心邏輯零變動
- 內容偵測 (`<svg` / `---` / `{`) 不靠副檔名信任
- 雙入口：mandala 模式按鈕 + gallery 頁面 file picker
- 20 r28 tests + 237 累計 pass + E2E 全綠

### B.14 § 3.6 + §3.10 + §5.8 PowerShell 規則 + cowork sandbox git index + 跨 phase commit — stroke-order 2026-05-04 commit 整理踩雷

**起源**：stroke-order 2026-05-04 整理 r4–r28 累積多 phase 工作為 4 commit 時，連續撞 cowork sandbox git index corruption + PowerShell 指令給法錯誤 + 多 phase 共享檔 hunk 拆分風險。

**抽象結論**：

1. PowerShell 指令給法 4 條鐵律：禁尖括號 placeholder、禁 `&&`、`git add` 分行、`HEAD~N` 相對引用
2. Cowork sandbox git index 在連續寫入時會 corruption — 預先 `rm + read-tree` 重建 + 單一 batched `git add` 是穩定 SOP
3. 多 phase 累積改動的共享檔 commit，誠實在 message 註明「同檔含其他 phase 改動」比 hunk-by-hunk staging 風險低且 `git log -p` 可追蹤完整 diff

**驗證真實案例**：`docs/journal/2026-05-04_session_log.md`
- 多個 commit 串聯：5b r1+r3 / 5b r4-r26 mandala / 12m-7 r39 rect_title / 5b r27 / 5b r28 / addenda 草稿
- 共享檔（server.py + index.html）含兩 phase 改動，commit message 誠實註明
- Cowork sandbox 一次 session 內踩中 3 個槽 → 全部沉澱回 SoT 變成可重用 SOP

"""


# =====================================================================
# Helper
# =====================================================================

def insert_before(text, anchor, payload, *, skip_if):
    """Insert payload immediately before anchor. Skip if marker already present."""
    if skip_if in text:
        print(f"  SKIP — {skip_if[:60]}... already present")
        return text
    idx = text.find(anchor)
    if idx == -1:
        sys.exit(f"❌ Anchor not found: {anchor[:60]}")
    print(f"  INSERT — before '{anchor[:50]}...'")
    return text[:idx] + payload + text[idx:]


# =====================================================================
# Main
# =====================================================================

def main():
    text = HISTORY.read_text(encoding="utf-8")
    original_len = len(text)
    print(f"HISTORY.md: {original_len} chars, {text.count(chr(10))} lines\n")
    print("Applying cherry-pick (bottom-up)...")

    # Patch 2: §B B.12-14 → 塞在 ## §C 之前
    text = insert_before(
        text,
        anchor="## §C",
        payload=PATCH_2_CASES,
        skip_if="### B.12 § 8.18",
    )

    # Patch 1: §A 第十一次修訂 → 塞在 ## §B 之前
    text = insert_before(
        text,
        anchor="## §B",
        payload=PATCH_1_REVISION,
        skip_if="### 2026-05-04（第十一次修訂）",
    )

    if len(text) != original_len:
        HISTORY.write_text(text, encoding="utf-8")
        print(f"\n✓ Wrote HISTORY.md")
        print(f"  Before: {original_len} chars")
        print(f"  After:  {len(text)} chars (+{len(text) - original_len})")
    else:
        print("\n→ No changes (all sections already present)")


if __name__ == "__main__":
    main()
