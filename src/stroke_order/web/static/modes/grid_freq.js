// ======================================================================
// W4 分級選字 — DOM 接線（純邏輯在 grid_freq_core.mjs，node 直測）
//
// 老師照字頻出字帖：起始名次＋字數 →「帶入」→ 填進 grid 的生字輸入框。
// **填入而非鎖定**——帶入後仍可手動增刪，下游（注音欄、W2 頁尾資訊、
// PDF）全部照舊能用。同 grid_route.js（部首家族帶入）的既有模式。
//
// 零新端點：/api/coverset/moe_elementary_5021 的 chars 順序 ≡ 字頻名次
// （契約由 pytest 鎖住），前端切片即選字。首次點擊才 fetch（61 KB），
// 之後留在模組快取。
// ======================================================================
import { API_BASE } from "./core.js?v=__V__";
import { pickByRank, pickHint } from "./grid_freq_core.mjs?v=__V__";

let freqChars = null;   // 字頻序字表快取（fetch 一次）
let freqTitle = "";

async function loadFreqChars() {
  if (freqChars) return freqChars;
  const r = await fetch(`${API_BASE}/api/coverset/moe_elementary_5021`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  const data = await r.json();
  freqChars = data.chars;
  freqTitle = data.title || "";
  // 起始名次的上限跟著字表走——不在 HTML 硬寫總字數（那會是第二事實源）
  document.getElementById("grid-freq-from").max = String(freqChars.length);
  return freqChars;
}

document.getElementById("grid-freq-fill").onclick = async () => {
  const hint = document.getElementById("grid-freq-hint");
  try {
    const chars = await loadFreqChars();
    const pick = pickByRank(
      chars,
      document.getElementById("grid-freq-from").value,
      document.getElementById("grid-freq-count").value,
    );
    if (!pick) { hint.textContent = "字表是空的（載入異常）"; return; }
    document.getElementById("grid-chars").value = pick.chars.join("");
    // 夾限後的實際值寫回輸入框，使用者看得到「你要的 0 被夾成 1」
    document.getElementById("grid-freq-from").value = String(pick.from);
    document.getElementById("grid-freq-count").value =
      String(pick.chars.length);
    hint.textContent = pickHint(pick, chars.length);
    hint.title = freqTitle;
  } catch (e) {
    hint.textContent = `帶入失敗：${e.message}`;
  }
};
