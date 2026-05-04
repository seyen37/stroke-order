// ======================================================================
// gallery/toast.mjs — Phase 5b r29h: lightweight toast notification.
//
// API:
//   showToast(message, type='info', duration=5000)
//
//   - message:   string (auto-escaped in DOM via textContent)
//   - type:      'info' | 'warning' | 'error' (other → fallback 'info')
//   - duration:  ms (default 5000; not finite or <=0 → fallback 5000)
//
// Behavior:
//   - 同時最多 1 個 toast（新 toast 顯示前舊 toast 立刻消失，無 queue）
//   - Click toast / press ESC / wait `duration` → 關閉
//   - Container 動態 inject 到 document.body，無需 HTML 預埋
//
// Pure helper `_toastSpec()` 抽出輸入 validation logic，供 Node test。
// ======================================================================

const ALLOWED_TYPES = ['info', 'warning', 'error'];
const DEFAULT_DURATION = 5000;
const CONTAINER_ID = 'gl-toast-container';

/**
 * Pure: validate inputs and produce a spec object. No DOM access.
 *
 * @returns {{type, duration, classNames, message}}
 */
export function _toastSpec(message, type = 'info', duration = DEFAULT_DURATION) {
  const validType = ALLOWED_TYPES.includes(type) ? type : 'info';
  const validDuration = (Number.isFinite(duration) && duration > 0)
    ? duration
    : DEFAULT_DURATION;
  return {
    type: validType,
    duration: validDuration,
    classNames: `gl-toast gl-toast--${validType}`,
    message: String(message ?? ''),
  };
}

// 內部 state — 當前 toast element + dismiss timer + escape listener
let _currentToast = null;
let _currentTimer = null;
let _escListener = null;

function _ensureContainer() {
  let c = document.getElementById(CONTAINER_ID);
  if (!c) {
    c = document.createElement('div');
    c.id = CONTAINER_ID;
    c.className = 'gl-toast-container';
    c.setAttribute('aria-live', 'polite');
    c.setAttribute('aria-atomic', 'true');
    document.body.appendChild(c);
  }
  return c;
}

function _dismissCurrent() {
  if (_currentTimer) {
    clearTimeout(_currentTimer);
    _currentTimer = null;
  }
  if (_escListener) {
    document.removeEventListener('keydown', _escListener);
    _escListener = null;
  }
  if (_currentToast && _currentToast.parentNode) {
    // CSS 動畫 fade-out — 加 class 觸發 0.2s transition
    _currentToast.classList.add('is-leaving');
    const el = _currentToast;
    setTimeout(() => {
      if (el.parentNode) el.parentNode.removeChild(el);
    }, 220);
  }
  _currentToast = null;
}

/**
 * Show a toast. Supersedes any currently-visible toast.
 */
export function showToast(message, type, duration) {
  const spec = _toastSpec(message, type, duration);
  _dismissCurrent();  // 同時最多 1 個

  const container = _ensureContainer();
  const toast = document.createElement('div');
  toast.className = spec.classNames;
  toast.setAttribute('role', spec.type === 'error' ? 'alert' : 'status');

  const msgSpan = document.createElement('span');
  msgSpan.className = 'gl-toast-msg';
  msgSpan.textContent = spec.message;
  toast.appendChild(msgSpan);

  const closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'gl-toast-close';
  closeBtn.setAttribute('aria-label', '關閉提示');
  closeBtn.textContent = '×';
  closeBtn.addEventListener('click', _dismissCurrent);
  toast.appendChild(closeBtn);

  // Click on toast body (not close button) also dismisses
  toast.addEventListener('click', (ev) => {
    if (ev.target !== closeBtn) _dismissCurrent();
  });

  container.appendChild(toast);
  _currentToast = toast;

  // ESC 關閉（a11y）
  _escListener = (ev) => { if (ev.key === 'Escape') _dismissCurrent(); };
  document.addEventListener('keydown', _escListener);

  // Auto-dismiss
  _currentTimer = setTimeout(_dismissCurrent, spec.duration);

  return toast;
}
