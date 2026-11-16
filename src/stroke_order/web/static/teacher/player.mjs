// ======================================================================
// teacher/player.mjs — 教師主題共用：筆順播放器（DESIGN.md §10）
//
// 用在 /teach（R2）與 /class（R3）。字形資料取自 /api/character/{ch}
// 的 strokes（hanzi-writer 慣例：1024 em、Y 朝上、ascender=900），
// 以 g transform 翻回螢幕座標——與既有 teach.html 的 glyphSvg 同一公式。
//
// 兩層：ghost（全字淡灰底，可關）＋ ink（逐筆顯示；目前這一筆用朱紅
// 標示＝§10.1「朱紅＝筆順重點」）。顏色全由 theme.css 的 .t-glyph 規則
// 決定，本模組不寫色值。
// ======================================================================

export const SPEEDS = { slow: 650, normal: 380, fast: 200 };

/** 單層 SVG（離線教學單檔沿用；不含 ghost 層）。 */
export function glyphSvg(strokes) {
  const paths = (strokes || []).map(d => `<path d="${d}"/>`).join('');
  return `<svg viewBox="0 0 1024 1024" aria-label="筆順動畫">` +
    `<g transform="translate(0, 900) scale(1, -1)">${paths}</g></svg>`;
}

/** 兩層 SVG（ghost＋ink）。 */
export function playerSvg(strokes) {
  const ps = (strokes || []).map(d => `<path d="${d}"/>`).join('');
  return `<svg viewBox="0 0 1024 1024" role="img" aria-label="筆順動畫">` +
    `<g class="ghost" transform="translate(0, 900) scale(1, -1)">${ps}</g>` +
    `<g class="ink" transform="translate(0, 900) scale(1, -1)">${ps}</g></svg>`;
}

export class StrokePlayer {
  /**
   * @param {HTMLElement} box 容器（通常是 .t-mizi.t-glyph）
   * @param {{onChange?: (shown:number, total:number) => void}} [opt]
   */
  constructor(box, opt = {}) {
    this.box = box;
    this.onChange = opt.onChange || (() => {});
    this.interval = SPEEDS.normal;
    this.timers = [];
    this.paths = [];
    this.shown = 0;
  }

  get total() { return this.paths.length; }

  load(strokes) {
    this.stop();
    this.box.innerHTML = playerSvg(strokes);
    this.paths = [...this.box.querySelectorAll('.ink path')];
    this._show(0);
  }

  setSpeed(key) { this.interval = SPEEDS[key] || SPEEDS.normal; }
  setGhost(on) { this.box.classList.toggle('no-ghost', !on); }

  stop() { this.timers.forEach(clearTimeout); this.timers = []; }

  _show(n) {
    this.shown = Math.max(0, Math.min(n, this.total));
    this.paths.forEach((p, i) => {
      p.classList.toggle('on', i < this.shown);
      p.classList.toggle('cur', i === this.shown - 1 && this.shown < this.total);
    });
    this.onChange(this.shown, this.total);
  }

  /** 從第一筆完整播放一次。 */
  play() {
    this.stop();
    this._show(0);
    for (let i = 1; i <= this.total; i++) {
      this.timers.push(setTimeout(() => this._show(i),
                                  200 + (i - 1) * this.interval));
    }
  }

  /** 逐筆：多顯示一筆；已全部顯示則從頭（第 1 筆）開始。 */
  step() {
    this.stop();
    this._show(this.shown >= this.total ? 1 : this.shown + 1);
  }

  showAll() { this.stop(); this._show(this.total); }
}
