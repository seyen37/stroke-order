// ======================================================================
// canvas.js — Writing canvas for the handwriting practice page.
//
// Responsibilities
// ----------------
//   * Wire PointerEvents (mouse + touch + stylus unified) to the ink
//     canvas — `touch-action:none` on the element prevents the browser
//     from stealing the gesture for scroll/zoom.
//   * Draw user ink in real time, with stroke width influenced by
//     `pointerEvent.pressure` (touch / stylus only — mouse falls back).
//   * Honour `devicePixelRatio` so retina/HiDPI screens stay crisp.
//   * Auto-resize via ResizeObserver — works on rotation, window
//     resize, and viewport-fit changes (iOS).
//   * Record every sample as `[x, y, t_ms, pressure, tiltX, tiltY]` in
//     EM 2048 coordinates — the same coordinate system the existing
//     stroke-order engine uses, so the captured trace can be fed
//     directly into a writing-robot pipeline.
//
// Public API
// ----------
//   const canvas = new WritingCanvas({ ink, bg });
//   canvas.on('strokeEnd', (stroke) => { ... });
//   canvas.on('clear', () => { ... });
//   canvas.clear();
//   canvas.getTrace();   // → { em_size, canvas_size, strokes: [...] }
//   canvas.stats();      // → { strokes, points, duration_s }
//
// Trace format (per stroke)
// -------------------------
//   {
//     points:        [[x_em, y_em, t_ms, pressure, tiltX, tiltY], …],
//     duration_ms:   <number>,        // last point's t
//     pen_down_at:   [x_em, y_em],    // first point — robot landing
//     pen_up_at:     [x_em, y_em],    // last point — robot lift
//     device:        'mouse' | 'touch' | 'pen' | string
//   }
// ======================================================================

export const EM_SIZE = 2048;

// Strokes shorter than this many sample points are dropped on pointerup
// — they're invariably accidental taps.
const MIN_STROKE_POINTS = 2;

// CSS-pixel stroke width for the live preview. Pressure scales between
// the soft and firm bounds; mouse pointers fall back to a fixed 0.5
// pressure so the line is still visible.
const STROKE_WIDTH_BASE   = 1.5;
const STROKE_WIDTH_FACTOR = 4.0;
const STROKE_COLOR        = '#000';
const FALLBACK_PRESSURE   = 0.5;

export class WritingCanvas {
  /**
   * @param {{ ink: HTMLCanvasElement, bg?: HTMLCanvasElement }} els
   */
  constructor({ ink, bg }) {
    if (!ink) throw new Error('ink canvas element is required');
    this.ink = ink;
    this.bg  = bg || null;
    this.dpr = window.devicePixelRatio || 1;

    /** @type {Array<object>} committed strokes in trace order */
    this.strokes = [];
    /** @type {?object} stroke currently being drawn (null between strokes) */
    this._active = null;
    /** @type {?number} performance.now() of the very first stroke for total duration */
    this._sessionStart = null;

    /** @type {Map<string, Function[]>} */
    this._listeners = new Map();

    this._setup();

    // Recompute backing-store size on layout changes (rotation, resize).
    this._ro = new ResizeObserver(() => this._setup());
    this._ro.observe(this.ink);

    this._bindPointerEvents();
  }

  // ---------------------------------------------------------------- setup

  _setup() {
    // Use the bounding rect as the source of truth for CSS size, so the
    // backing store always matches whatever the layout decided.
    const rect = this.ink.getBoundingClientRect();
    const newW = Math.max(1, rect.width);
    const newH = Math.max(1, rect.height);
    const sizeChanged = (newW !== this._cssW) || (newH !== this._cssH);
    this._cssW = newW;
    this._cssH = newH;

    const bw = Math.max(1, Math.floor(this._cssW * this.dpr));
    const bh = Math.max(1, Math.floor(this._cssH * this.dpr));

    [this.ink, this.bg].filter(Boolean).forEach(el => {
      el.width  = bw;
      el.height = bh;
      const ctx = el.getContext('2d');
      // Reset transform so the next setTransform isn't compounded.
      ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
    });

    this._redrawAllInk();
    // Notify listeners (page-level renderBg() etc.) — only fire when the
    // size actually changed, not on the very first setup.
    if (sizeChanged && this._sizeReady) {
      this._emit('resize', { w: this._cssW, h: this._cssH });
    }
    this._sizeReady = true;
  }

  _bindPointerEvents() {
    const el = this.ink;
    el.addEventListener('pointerdown',   (e) => this._onDown(e));
    el.addEventListener('pointermove',   (e) => this._onMove(e));
    el.addEventListener('pointerup',     (e) => this._onUp(e));
    el.addEventListener('pointercancel', (e) => this._onUp(e));
    // Releasing outside the canvas: treat as stroke end if we had one.
    el.addEventListener('pointerleave',  (e) => {
      if (this._active) this._onUp(e);
    });
    // Belt-and-braces: stop default drag/select
    el.addEventListener('contextmenu',   (e) => e.preventDefault());
    el.addEventListener('dragstart',     (e) => e.preventDefault());
  }

  // -------------------------------------------------------- coord helpers

  _toEM(e) {
    const rect = this.ink.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width)  * EM_SIZE;
    const y = ((e.clientY - rect.top)  / rect.height) * EM_SIZE;
    // Clamp into [0, EM_SIZE] — out-of-bounds samples occasionally arrive
    // when the pointer leaves the canvas just as it's released.
    return [
      Math.max(0, Math.min(EM_SIZE, x)),
      Math.max(0, Math.min(EM_SIZE, y)),
    ];
  }

  // ------------------------------------------------------ pointer handlers

  _onDown(e) {
    e.preventDefault();
    try { this.ink.setPointerCapture(e.pointerId); } catch (_) {}
    const now = performance.now();
    if (this._sessionStart === null) this._sessionStart = now;

    const [x, y] = this._toEM(e);
    const pressure = (e.pressure > 0 ? e.pressure : FALLBACK_PRESSURE);
    this._active = {
      _t0:        now,                 // private — not in serialised stroke
      device:     e.pointerType || 'unknown',
      points: [[
        x, y, 0,
        pressure,
        e.tiltX || 0, e.tiltY || 0,
      ]],
    };
    this._emit('strokeStart', this._active);
  }

  _onMove(e) {
    if (!this._active) return;
    e.preventDefault();
    const [x, y] = this._toEM(e);
    const t = performance.now() - this._active._t0;
    const pressure = (e.pressure > 0 ? e.pressure : FALLBACK_PRESSURE);
    const point = [
      x, y, t,
      pressure,
      e.tiltX || 0, e.tiltY || 0,
    ];
    this._active.points.push(point);

    // Live preview: draw the segment from the previous point to this one.
    const pts = this._active.points;
    if (pts.length >= 2) {
      this._drawSegment(pts[pts.length - 2], pts[pts.length - 1]);
    }
    this._emit('pointerMove', point);
  }

  _onUp(e) {
    if (!this._active) return;
    if (e.preventDefault) e.preventDefault();
    try { this.ink.releasePointerCapture(e.pointerId); } catch (_) {}

    const stroke = this._active;
    this._active = null;

    if (stroke.points.length < MIN_STROKE_POINTS) {
      // Tap or accidental click — drop quietly.
      this._emit('strokeEnd', null);
      return;
    }

    const last = stroke.points[stroke.points.length - 1];
    const finalised = {
      points:      stroke.points,
      duration_ms: last[2],
      pen_down_at: [stroke.points[0][0], stroke.points[0][1]],
      pen_up_at:   [last[0], last[1]],
      device:      stroke.device,
    };
    this.strokes.push(finalised);
    this._emit('strokeEnd', finalised);
  }

  // ------------------------------------------------------------ rendering

  _drawSegment(p0, p1) {
    const ctx = this.ink.getContext('2d');
    const sx = this._cssW / EM_SIZE;
    const sy = this._cssH / EM_SIZE;
    ctx.lineCap   = 'round';
    ctx.lineJoin  = 'round';
    ctx.strokeStyle = STROKE_COLOR;
    // Use the second point's pressure (current tip)
    ctx.lineWidth = STROKE_WIDTH_BASE + (p1[3] || FALLBACK_PRESSURE) * STROKE_WIDTH_FACTOR;
    ctx.beginPath();
    ctx.moveTo(p0[0] * sx, p0[1] * sy);
    ctx.lineTo(p1[0] * sx, p1[1] * sy);
    ctx.stroke();
  }

  _redrawAllInk() {
    const ctx = this.ink.getContext('2d');
    ctx.clearRect(0, 0, this._cssW, this._cssH);
    for (const stroke of this.strokes) {
      const pts = stroke.points;
      for (let i = 1; i < pts.length; i++) {
        this._drawSegment(pts[i - 1], pts[i]);
      }
    }
    // Replay the in-flight stroke too (covers resize during drawing).
    if (this._active && this._active.points.length >= 2) {
      const pts = this._active.points;
      for (let i = 1; i < pts.length; i++) {
        this._drawSegment(pts[i - 1], pts[i]);
      }
    }
  }

  // ------------------------------------------------------------ public API

  clear() {
    this.strokes = [];
    this._active = null;
    this._sessionStart = null;
    const ctx = this.ink.getContext('2d');
    ctx.clearRect(0, 0, this._cssW, this._cssH);
    this._emit('clear', null);
  }

  /** Drop the most recently committed stroke (undo). */
  popLastStroke() {
    if (this.strokes.length === 0) return null;
    const removed = this.strokes.pop();
    this._redrawAllInk();
    this._emit('strokePop', removed);
    return removed;
  }

  /** Has the user drawn anything? */
  isEmpty() {
    return this.strokes.length === 0 && !this._active;
  }

  /** Snapshot the current trace. */
  getTrace() {
    return {
      em_size:     EM_SIZE,
      canvas_size: [Math.round(this._cssW), Math.round(this._cssH)],
      strokes:     this.strokes.map(s => ({
        points:      s.points,
        duration_ms: s.duration_ms,
        pen_down_at: s.pen_down_at,
        pen_up_at:   s.pen_up_at,
      })),
      device: this.strokes[0]?.device || 'unknown',
    };
  }

  /** Lightweight summary for the stats row. */
  stats() {
    let totalPts = 0;
    let totalMs  = 0;
    for (const s of this.strokes) {
      totalPts += s.points.length;
      totalMs  += s.duration_ms;
    }
    return {
      strokes:    this.strokes.length,
      points:     totalPts,
      duration_s: +(totalMs / 1000).toFixed(1),
    };
  }

  /** Access the bg canvas for renderers (grid, reference glyph, …). */
  bgContext() {
    if (!this.bg) return null;
    return this.bg.getContext('2d');
  }

  bgSize() {
    return [this._cssW, this._cssH];
  }

  /** EM coordinate system size — handy for renderers. */
  emSize() { return EM_SIZE; }

  // ---------------------------------------------------------------- events

  on(name, cb) {
    if (!this._listeners.has(name)) this._listeners.set(name, []);
    this._listeners.get(name).push(cb);
  }
  off(name, cb) {
    const arr = this._listeners.get(name);
    if (!arr) return;
    const i = arr.indexOf(cb);
    if (i >= 0) arr.splice(i, 1);
  }
  _emit(name, data) {
    const arr = this._listeners.get(name);
    if (!arr) return;
    for (const cb of arr) {
      try { cb(data); } catch (e) { console.error('handler error', e); }
    }
  }
}
