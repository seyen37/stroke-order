// ======================================================================
// teacher/dictcard.mjs — 教師主題共用：教育部字義→字義卡（DESIGN.md §10）
//
// 教育部《國語辭典簡編本》為 CC BY-ND：**內容逐字保留、不改寫**。這裡只
// 做版面切分——依行首「1.」「2.」切成義項、依第一個「[例]」把釋義與例句
// 分開；所有文字原樣保留（例句段內後續的「[例]」也原樣保留）。
// ======================================================================

export const esc = s => String(s).replace(/[&<>"']/g,
  c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/**
 * @param {string} def 教育部釋義原文（或老師改過的內容）
 * @returns {{n: string, text: string, ex: string}[]}
 */
export function parseSenses(def) {
  const lines = String(def || '').split('\n').map(s => s.trim()).filter(Boolean);
  const out = [];
  for (const line of lines) {
    const m = line.match(/^(\d+)\.\s*(.*)$/);
    if (m || !out.length) {
      const body = m ? m[2] : line;
      const k = body.indexOf('[例]');
      out.push({
        n: m ? m[1] : '',
        text: (k < 0 ? body : body.slice(0, k)).trim(),
        ex: k < 0 ? '' : body.slice(k + 3).trim(),
      });
    } else {
      // 非編號續行：併入上一義項（原文換行處以空白相接，不丟字）
      const last = out[out.length - 1];
      if (last.ex) last.ex += ' ' + line; else last.text += ' ' + line;
    }
  }
  return out;
}

export function sensesHtml(def) {
  return parseSenses(def).map(s =>
    `<div class="t-sense">` +
    (s.n ? `<span class="n">${esc(s.n)}.</span>` : '') +
    `${esc(s.text)}` +
    (s.ex ? `<div class="ex"><span class="lab">例</span>${esc(s.ex)}</div>` : '') +
    `</div>`).join('');
}

/** 詞條釋義的第一條例句（取出不改寫；頓號串列的例詞不當句子）。 */
export function firstExample(def) {
  const m = String(def || '').match(/\[例\]([^\n]+)/);
  if (!m) return '';
  const seg = m[1].trim();
  return seg.includes('、') && !/[。！？]/.test(seg) ? '' : seg;
}
