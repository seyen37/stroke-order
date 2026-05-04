// ======================================================================
// gallery/gallery.js — main SPA orchestrator.
//
// Boot:
//   1. Fetch /api/gallery/me → render header (anonymous vs logged-in)
//   2. Fetch /api/gallery/uploads → render card grid
//   3. Wire toolbar buttons (login, logout, upload, profile, paginate)
//
// Re-render is driven by `refresh()` which re-fetches both endpoints.
// All mutations (login/upload/profile/delete) call refresh on success.
// ======================================================================

import {
  fetchMe, showLoginDialog, showProfileDialog, logout,
  attachAuthHandlers,
} from './auth.js';
import { showUploadDialog, attachUploaderHandlers } from './uploader.js';

const $ = id => document.getElementById(id);

const state = {
  me:   null,        // user dict | null
  page: 1,
  size: 12,
  total: 0,
  items: [],
  // Phase 5b r28: kind filter ('' = 全部, 'psd' / 'mandala')
  kindFilter: '',
};

// ============================================================ helpers

function _emailHandle(email) {
  return (email || '').split('@')[0] || '匿名';
}

function _displayName(user) {
  if (!user) return '我';
  return user.display_name || _emailHandle(user.email);
}

function _formatRelativeTime(iso) {
  if (!iso) return '';
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return iso;
  const diff = Date.now() - t;
  const s = diff / 1000;
  if (s < 60)        return '剛剛';
  if (s < 3600)      return `${Math.floor(s / 60)} 分鐘前`;
  if (s < 86400)     return `${Math.floor(s / 3600)} 小時前`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)} 天前`;
  // Older — show YYYY/MM/DD
  const d = new Date(iso);
  return `${d.getFullYear()}/${String(d.getMonth()+1).padStart(2,'0')}/` +
         `${String(d.getDate()).padStart(2,'0')}`;
}

function _escape(s) {
  return String(s ?? '').replace(/[<>&"']/g, ch => ({
    '<':'&lt;', '>':'&gt;', '&':'&amp;', '"':'&quot;', "'":'&#39;',
  })[ch]);
}


// ============================================================ render

function renderHeader() {
  if (state.me) {
    $('gl-login-btn').hidden = true;
    $('gl-user-menu').hidden = false;
    $('gl-user-label').textContent = _displayName(state.me);
  } else {
    $('gl-login-btn').hidden = false;
    $('gl-user-menu').hidden = true;
    $('gl-user-dropdown').hidden = true;
  }
}

function renderStats() {
  const txt = state.total === 0
    ? '— 筆'
    : `共 ${state.total} 筆 · 第 ${state.page} 頁`;
  $('gl-stats').textContent = txt;
}

function renderList() {
  const root = $('gl-list');
  const empty = $('gl-list-empty');
  const error = $('gl-list-error');
  error.hidden = true;

  if (state.items.length === 0) {
    root.innerHTML = '';
    empty.hidden = false;
    $('gl-pagination').hidden = true;
    return;
  }
  empty.hidden = true;

  const cards = state.items.map(_card).join('');
  root.innerHTML = cards;

  // Wire delete buttons (own items only)
  root.querySelectorAll('[data-action="delete"]').forEach(btn => {
    btn.addEventListener('click', async (ev) => {
      const id = parseInt(ev.currentTarget.dataset.id, 10);
      if (!Number.isInteger(id)) return;
      if (!confirm('要刪除這筆上傳嗎？此動作無法復原。')) return;
      try {
        const r = await fetch(`/api/gallery/uploads/${id}`, {
          method: 'DELETE',
          credentials: 'same-origin',
        });
        if (!r.ok) {
          const data = await r.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${r.status}`);
        }
        await refresh();
      } catch (e) {
        alert('刪除失敗：' + (e.message || e));
      }
    });
  });

  // Pagination visibility
  const totalPages = Math.max(1, Math.ceil(state.total / state.size));
  $('gl-pagination').hidden = totalPages <= 1;
  $('gl-page-prev').disabled = state.page <= 1;
  $('gl-page-next').disabled = state.page >= totalPages;
  $('gl-page-label').textContent = `${state.page} / ${totalPages}`;
}

function _kindBadge(kind) {
  const labels = { psd: '抄經', mandala: '曼陀羅' };
  const k = kind || 'psd';
  return `<span class="gl-card-kind gl-card-kind-${_escape(k)}">${
    _escape(labels[k] || k)
  }</span>`;
}

function _kindMeta(item) {
  // r28: kind-specific summary line（取代寫死的 trace_count / unique_chars）
  const kind = item.kind || 'psd';
  const summary = item.summary || {};
  if (kind === 'mandala') {
    const parts = [];
    if (summary.layer_count != null) {
      parts.push(`<span><b>${summary.layer_count}</b> 裝飾層</span>`);
    }
    if (summary.ring_count != null) {
      parts.push(`<span>·</span><span><b>${summary.ring_count}</b> 環</span>`);
    }
    if (summary.center_text) {
      parts.push(`<span>·</span><span>中心 <b>${_escape(summary.center_text)}</b></span>`);
    }
    return parts.join(' ');
  }
  // psd: legacy trace_count / unique_chars
  return (
    `<span><b>${item.trace_count}</b> 筆軌跡</span>` +
    `<span>·</span>` +
    `<span><b>${item.unique_chars}</b> 字</span>`
  );
}

function _kindStyles(item) {
  // psd: styles_used pills；mandala: mandala_style + composition_scheme pills
  const kind = item.kind || 'psd';
  if (kind === 'mandala') {
    const s = item.summary || {};
    const pills = [];
    if (s.mandala_style) {
      pills.push(`<span class="gl-pill">${_escape(s.mandala_style)}</span>`);
    }
    if (s.composition_scheme) {
      pills.push(`<span class="gl-pill">${_escape(s.composition_scheme)}</span>`);
    }
    return pills.join(' ');
  }
  return (item.styles_used || []).map(s =>
    `<span class="gl-pill">${_escape(s)}</span>`,
  ).join('');
}

function _downloadLabel(kind) {
  return kind === 'mandala' ? '↓ 下載 (.md / .svg)' : '↓ 下載 JSON';
}

function _card(item) {
  const isOwn  = state.me && state.me.id === item.user_id;
  const author = item.uploader_display_name
              || _emailHandle(item.uploader_email);
  const kind   = item.kind || 'psd';
  return `
    <article class="gl-card" data-id="${item.id}" data-kind="${_escape(kind)}">
      <div class="gl-card-header">
        <div class="gl-card-title">${_escape(item.title)}${_kindBadge(kind)}</div>
        <div class="gl-card-author">${_escape(author)}</div>
      </div>
      <div class="gl-card-meta">${_kindMeta(item)}</div>
      <div class="gl-card-styles">${_kindStyles(item)}</div>
      ${ item.comment
         ? `<div class="gl-card-comment">${_escape(item.comment)}</div>`
         : '' }
      <div class="gl-card-time">${_formatRelativeTime(item.created_at)}</div>
      <div class="gl-card-actions">
        <a href="/api/gallery/uploads/${item.id}/download"
           class="gl-btn" download>${_downloadLabel(kind)}</a>
        ${ isOwn
           ? `<button class="gl-btn gl-btn-danger"
                       data-action="delete" data-id="${item.id}"
                       type="button">刪除</button>`
           : '' }
      </div>
    </article>
  `;
}


// ============================================================ data fetch

async function refresh() {
  // Both fetches in parallel — they're independent
  const [meData, listData] = await Promise.all([
    fetchMe().catch(() => ({logged_in: false})),
    _fetchUploads().catch(err => ({_error: err})),
  ]);

  state.me = meData.logged_in ? meData.user : null;
  if (listData._error) {
    $('gl-list-error').hidden = false;
    $('gl-list-error').textContent =
      '載入失敗：' + (listData._error.message || listData._error);
    state.items = [];
    state.total = 0;
  } else {
    state.items = listData.items || [];
    state.total = listData.total || 0;
  }

  renderHeader();
  renderStats();
  renderList();
}

async function _fetchUploads() {
  const params = new URLSearchParams({
    page: state.page,
    size: state.size,
  });
  // r28: kind filter ('' = 全部，不送)
  if (state.kindFilter) params.set('kind', state.kindFilter);
  const r = await fetch(`/api/gallery/uploads?${params}`, {
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${r.status}`);
  }
  return r.json();
}


// ============================================================ wiring

function _wireToolbar() {
  $('gl-login-btn').addEventListener('click', showLoginDialog);
  $('gl-upload-btn').addEventListener('click', () => {
    if (!state.me) {
      showLoginDialog();
      return;
    }
    showUploadDialog();
  });

  // User menu (dropdown)
  $('gl-user-btn').addEventListener('click', (ev) => {
    ev.stopPropagation();
    const dd = $('gl-user-dropdown');
    dd.hidden = !dd.hidden;
  });
  document.addEventListener('click', (ev) => {
    const menu = $('gl-user-menu');
    if (!menu.contains(ev.target)) {
      $('gl-user-dropdown').hidden = true;
    }
  });

  document.querySelector(
    '[data-action="open-profile"]',
  ).addEventListener('click', () => {
    $('gl-user-dropdown').hidden = true;
    showProfileDialog(state.me);
  });
  document.querySelector(
    '[data-action="logout"]',
  ).addEventListener('click', async () => {
    $('gl-user-dropdown').hidden = true;
    await logout();
    state.me = null;
    state.page = 1;
    await refresh();
  });

  // pagination
  $('gl-page-prev').addEventListener('click', () => {
    if (state.page > 1) { state.page--; refresh(); }
  });
  $('gl-page-next').addEventListener('click', () => {
    const totalPages = Math.max(1, Math.ceil(state.total / state.size));
    if (state.page < totalPages) { state.page++; refresh(); }
  });

  // r28: kind filter tabs
  document.querySelectorAll('.gl-filter-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const kind = btn.dataset.kind || '';
      if (state.kindFilter === kind) return;
      state.kindFilter = kind;
      state.page = 1;
      // Update aria + active class
      document.querySelectorAll('.gl-filter-tab').forEach(b => {
        const active = (b.dataset.kind || '') === kind;
        b.classList.toggle('is-active', active);
        b.setAttribute('aria-selected', active ? 'true' : 'false');
      });
      refresh();
    });
  });
}


// ============================================================ boot

(async function boot() {
  attachAuthHandlers({ refresh });
  attachUploaderHandlers({ refresh });
  _wireToolbar();
  await refresh();
})();
