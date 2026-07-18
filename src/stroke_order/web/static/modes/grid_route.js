// W4-R2：本檔為 ES module（零被依賴、自有作用域、嚴格模式）。
// ============================================================
// Phase 5cd: 字帖模式「部首家族」— 組件教學路線帶入
// ============================================================
let gridRouteLoaded = false;
async function loadRadicalRoute() {
  if (gridRouteLoaded) return;
  const sel = document.getElementById("grid-radical");
  try {
    const r = await fetch(
      `${API_BASE}/api/radical-route?coverset=cjk_common_808`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    sel.innerHTML = '<option value="">（選部首）</option>';
    for (const u of data.route) {
      const opt = document.createElement("option");
      opt.value = u.radical;
      opt.textContent =
        `${u.radical}（${u.strokes ?? "?"}畫）家族 ${u.family_size} 字`;
      sel.appendChild(opt);
    }
    gridRouteLoaded = true;
  } catch (e) {
    sel.innerHTML =
      `<option value="">（教學路線載入失敗：${e.message}）</option>`;
  }
}
document.getElementById("grid-radical")
  .addEventListener("focus", loadRadicalRoute);
document.getElementById("grid-radical-fill").onclick = async () => {
  const radical = document.getElementById("grid-radical").value;
  const hint = document.getElementById("grid-radical-hint");
  if (!radical) { hint.textContent = "請先選一個部首"; return; }
  try {
    const r = await fetch(
      `${API_BASE}/api/components/${encodeURIComponent(radical)}` +
      `/family?coverset=cjk_common_808&limit=40`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const fam = await r.json();
    document.getElementById("grid-chars").value =
      fam.chars.join("").slice(0, 40);
    hint.textContent = `${radical} 家族共 ${fam.family_size} 字，` +
      `已帶入前 ${Math.min(fam.chars.length, 40)} 字（部首本字領頭）`;
  } catch (e) {
    hint.textContent = `帶入失敗：${e.message}`;
  }
};

