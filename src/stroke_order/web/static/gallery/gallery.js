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
// r29f: URL hash <-> state pure helpers (testable from Node)
import { stateToHash, parseHash } from './hash.mjs';
// r29h: toast notification (替換散點 alert)
import { showToast } from './toast.mjs';
// r29j: avatar render helper（img / initials fallback）
import { avatarHtml } from './avatar.mjs';

const $ = id => document.getElementById(id);

const state = {
  me:   null,        // user dict | null
  page: 1,
  size: 12,
  total: 0,
  items: [],
  // Phase 5b r28: kind filter ('' = 全部, 'psd' / 'mandala')
  kindFilter: '',
  // Phase 5b r29b/r29c: sort ('newest' / 'likes' / 'hot')
  sort: 'newest',
  // Phase 5b r29b: 「我的收藏」filter（true 時只列當前 user bookmark 的 upload）
  bookmarkedOnly: false,
  // Phase 5b r29c: search query（空字串 → 不送 ?q=）
  q: '',
  // Phase 5b r29d: user filter (profile page) — null = 全部，否則 user_id
  userFilter: null,
  // Phase 5b r29d: 當前 profile data（userFilter set 時 fetch /users/{id}）
  profile: null,
  // Phase 5b r29g: deep-link 單張 upload — id 寫進 hash, full obj 用於 prepend
  deepLinkUploadId: null,
  deepLinkUpload: null,
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
    // r29j: 名字旁加 24x24 avatar（gl-user-label 用 innerHTML，
    // 因為 avatarHtml 自己 escape 過）
    $('gl-user-label').innerHTML =
      avatarHtml(state.me, 24) +
      `<span class="gl-user-label-name">${_escape(_displayName(state.me))}</span>`;
  } else {
    $('gl-login-btn').hidden = false;
    $('gl-user-menu').hidden = true;
    $('gl-user-dropdown').hidden = true;
  }
  // r29b: 「我的收藏」filter tab — 只登入後可見
  const bookmarkTab = $('gl-filter-bookmark');
  if (bookmarkTab) {
    bookmarkTab.hidden = !state.me;
    // 登出後若還在 bookmarked filter view → 自動切回全部
    if (!state.me && state.bookmarkedOnly) {
      state.bookmarkedOnly = false;
      state.kindFilter = '';
      _syncFilterTabsActive();
    }
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

  // r29g: scroll deep-link card into view（render 完才 scroll）
  if (state.deepLinkUpload) {
    const dlCard = root.querySelector('.gl-card--deeplink');
    if (dlCard) {
      // 用 rAF 避免 layout race
      requestAnimationFrame(() => {
        dlCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
      });
    }
  }

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
        showToast('刪除失敗：' + (e.message || e), 'error');
      }
    });
  });

  // r29: Wire like buttons
  root.querySelectorAll('[data-action="like"]').forEach(btn => {
    btn.addEventListener('click', async (ev) => {
      const id = parseInt(ev.currentTarget.dataset.id, 10);
      if (!Number.isInteger(id)) return;
      // 未登入 → 提示登入再操作
      if (!state.me) {
        if (confirm('需要登入才能讚。要前往登入嗎？')) {
          showLoginDialog();
        }
        return;
      }
      try {
        const r = await fetch(`/api/gallery/uploads/${id}/like`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        if (!r.ok) {
          const data = await r.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${r.status}`);
        }
        const data = await r.json();
        // Optimistic UI update — 不 refresh 整頁，省 API call
        const card = ev.currentTarget.closest('.gl-card');
        if (card) {
          const heart = card.querySelector('.gl-heart');
          const cnt = card.querySelector('.gl-like-count');
          const button = card.querySelector('.gl-btn-like');
          if (heart) heart.textContent = data.liked ? '❤️' : '🤍';
          if (cnt) cnt.textContent = String(data.like_count);
          if (button) {
            button.classList.toggle('is-liked', data.liked);
            button.title = data.liked ? '取消讚' : '讚';
          }
        }
        // 同步 state.items 對應 item（不 refresh，下次 list 才會重 fetch）
        const it = state.items.find(x => x.id === id);
        if (it) {
          it.liked_by_me = data.liked;
          it.like_count = data.like_count;
        }
      } catch (e) {
        showToast('讚操作失敗：' + (e.message || e), 'error');
      }
    });
  });

  // r29d: Wire uploader-name links (filter to user)
  root.querySelectorAll('[data-action="filter-user"]').forEach(link => {
    link.addEventListener('click', async (ev) => {
      ev.preventDefault();
      const uid = parseInt(ev.currentTarget.dataset.userId, 10);
      if (!Number.isInteger(uid)) return;
      if (state.userFilter === uid) return;
      state.userFilter = uid;
      state.page = 1;
      // 清掉其他 filter 跟 search（profile view 視為獨立）
      state.kindFilter = '';
      state.bookmarkedOnly = false;
      state.q = '';
      const searchInput = $('gl-search');
      if (searchInput) searchInput.value = '';
      await refresh();
    });
  });

  // r29b: Wire bookmark buttons
  root.querySelectorAll('[data-action="bookmark"]').forEach(btn => {
    btn.addEventListener('click', async (ev) => {
      const id = parseInt(ev.currentTarget.dataset.id, 10);
      if (!Number.isInteger(id)) return;
      if (!state.me) {
        if (confirm('需要登入才能收藏。要前往登入嗎？')) {
          showLoginDialog();
        }
        return;
      }
      try {
        const r = await fetch(`/api/gallery/uploads/${id}/bookmark`, {
          method: 'POST',
          credentials: 'same-origin',
        });
        if (!r.ok) {
          const data = await r.json().catch(() => ({}));
          throw new Error(data.detail || `HTTP ${r.status}`);
        }
        const data = await r.json();
        // Optimistic UI
        const card = ev.currentTarget.closest('.gl-card');
        if (card) {
          const icon = card.querySelector('.gl-bookmark-icon');
          const button = card.querySelector('.gl-btn-bookmark');
          if (icon) icon.textContent = data.bookmarked ? '📌' : '📍';
          if (button) {
            button.classList.toggle('is-bookmarked', data.bookmarked);
            button.title = data.bookmarked ? '取消收藏' : '收藏';
          }
        }
        const it = state.items.find(x => x.id === id);
        if (it) it.bookmarked_by_me = data.bookmarked;
        // 若當前在「我的收藏」filter 且這次取消收藏 → 該 card 應從列表消失
        if (state.bookmarkedOnly && !data.bookmarked) {
          await refresh();
        }
      } catch (e) {
        showToast('收藏操作失敗：' + (e.message || e), 'error');
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

function _kindThumbnail(item) {
  // r28b: mandala kind 才嘗試載 thumbnail；onerror 隱藏自己（mandala+md upload 沒
  // thumbnail 時 endpoint 回 404，img 自動被隱藏）。PSD 跳過。
  const kind = item.kind || 'psd';
  if (kind !== 'mandala') return '';
  return `<div class="gl-card-thumb">
    <img src="/api/gallery/uploads/${item.id}/thumbnail"
         alt="${_escape(item.title)} 縮圖"
         loading="lazy"
         onerror="this.parentElement.style.display='none'">
  </div>`;
}

// r29: like button
function _likeButton(item) {
  const liked = item.liked_by_me === true;
  const count = item.like_count || 0;
  const heart = liked ? '❤️' : '🤍';
  const titleAttr = liked ? '取消讚' : '讚';
  return `<button class="gl-btn gl-btn-like ${liked ? 'is-liked' : ''}"
    data-action="like" data-id="${item.id}"
    type="button" title="${titleAttr}">
    <span class="gl-heart">${heart}</span>
    <span class="gl-like-count">${count}</span>
  </button>`;
}

// r29b: bookmark button (私人收藏)
function _bookmarkButton(item) {
  const bookmarked = item.bookmarked_by_me === true;
  const icon = bookmarked ? '📌' : '📍';
  const titleAttr = bookmarked ? '取消收藏' : '收藏';
  return `<button class="gl-btn gl-btn-bookmark ${bookmarked ? 'is-bookmarked' : ''}"
    data-action="bookmark" data-id="${item.id}"
    type="button" title="${titleAttr}">
    <span class="gl-bookmark-icon">${icon}</span>
  </button>`;
}

function _card(item) {
  const isOwn  = state.me && state.me.id === item.user_id;
  const author = item.uploader_display_name
              || _emailHandle(item.uploader_email);
  const kind   = item.kind || 'psd';
  // r29j: 把 uploader 視為 user-shape 給 avatarHtml 用
  const uploaderUser = {
    id: item.user_id,
    email: item.uploader_email,
    display_name: item.uploader_display_name,
    avatar_url: item.uploader_avatar_url || null,
  };
  // r29d: uploader name 變 link → 切到 user filter view
  // r29j: 加 24x24 avatar 在 link 內
  const authorHtml =
    `<a href="#" data-action="filter-user" data-user-id="${item.user_id}"
        class="gl-card-author-link">${avatarHtml(uploaderUser, 24)}` +
    `<span class="gl-card-author-name">${_escape(author)}</span></a>`;
  // r29g: deep-link target → 加 class 顯眼放大 + flash
  const isDeepLink = state.deepLinkUpload
                  && state.deepLinkUpload.id === item.id;
  const dlClass = isDeepLink ? ' gl-card--deeplink' : '';
  return `
    <article class="gl-card${dlClass}" data-id="${item.id}" data-kind="${_escape(kind)}">
      ${_kindThumbnail(item)}
      <div class="gl-card-header">
        <div class="gl-card-title">${_escape(item.title)}${_kindBadge(kind)}</div>
        <div class="gl-card-author">${authorHtml}</div>
      </div>
      <div class="gl-card-meta">${_kindMeta(item)}</div>
      <div class="gl-card-styles">${_kindStyles(item)}</div>
      ${ item.comment
         ? `<div class="gl-card-comment">${_escape(item.comment)}</div>`
         : '' }
      <div class="gl-card-time">${_formatRelativeTime(item.created_at)}</div>
      <div class="gl-card-actions">
        ${_likeButton(item)}
        ${_bookmarkButton(item)}
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


// ============================================================ hash route (r29f)

// 自家 hash 寫入時 skip own hashchange（避免 loop）
let _writingHash = false;

function _writeHash() {
  const target = stateToHash(state);
  const current = window.location.hash;
  if (current === target) return;
  // 空 target 仍視為「清掉」— 用 replaceState 不留下 trailing '#'
  _writingHash = true;
  try {
    if (target === '') {
      // 清 hash：用 replaceState 留乾淨 URL（hashchange 不觸發）
      const cleanUrl = window.location.pathname + window.location.search;
      history.replaceState(null, '', cleanUrl);
    } else {
      // hash 已含 leading '#'，但 location.hash setter 兩種寫法都可
      window.location.hash = target;
    }
  } finally {
    // hashchange 是 macrotask；用 setTimeout(0) 排在它之後解 flag
    setTimeout(() => { _writingHash = false; }, 0);
  }
}

function _applyHashPatchToState(patch) {
  // r29g: 若 hash 帶 upload deep-link → 強制清 sort / kind / user / q 到 default
  // 確保 list 乾淨，prepend 那張必然在最頂
  if (patch.deepLinkUploadId) {
    state.userFilter = null;
    state.sort = 'newest';
    state.q = '';
    state.kindFilter = '';
    state.bookmarkedOnly = false;
    state.profile = null;
  } else {
    state.userFilter = patch.userFilter;
    state.sort = patch.sort;
    state.q = patch.q;
    state.kindFilter = patch.kindFilter;
    if (patch.userFilter === null) state.profile = null;
  }
  // bookmarkedOnly / page 不從 hash 還原 — 翻頁從 1 起，bookmarked 是私人 view
  state.page = 1;
  state.deepLinkUploadId = patch.deepLinkUploadId;
}

function _syncUiFromState() {
  // 把 state 推回 UI 控件（hash 進入時用）
  const sortEl = $('gl-sort');
  if (sortEl && sortEl.value !== state.sort) sortEl.value = state.sort;
  const searchEl = $('gl-search');
  if (searchEl && searchEl.value !== state.q) searchEl.value = state.q;
  _syncFilterTabsActive();
}

function _onHashChange() {
  if (_writingHash) return;  // 自家寫入觸發 — 略過
  const patch = parseHash(window.location.hash);
  _applyHashPatchToState(patch);
  _syncUiFromState();
  refresh();
}


// ============================================================ data fetch

async function refresh() {
  // r29f: state 變動 → 同步進 hash（refresh 是 mutation 統一入口）
  _writeHash();
  // r29d: 若 userFilter set，多 fetch 一個 profile request
  const fetches = [
    fetchMe().catch(() => ({logged_in: false})),
    _fetchUploads().catch(err => ({_error: err})),
  ];
  if (state.userFilter) {
    fetches.push(_fetchUserProfile(state.userFilter).catch(() => null));
  }
  // r29g: 若 deep-link upload 還沒 fetch 過，並行 fetch upload detail
  const dlFetchIdx = (state.deepLinkUploadId
                      && (!state.deepLinkUpload
                          || state.deepLinkUpload.id !== state.deepLinkUploadId))
    ? fetches.push(_fetchUploadDetail(state.deepLinkUploadId).catch(() => null)) - 1
    : -1;
  const results = await Promise.all(fetches);
  const meData = results[0];
  const listData = results[1];
  const profileData = state.userFilter ? results[2] : null;

  state.me = meData.logged_in ? meData.user : null;
  state.profile = profileData;
  if (dlFetchIdx >= 0) {
    const dl = results[dlFetchIdx];
    if (dl) {
      state.deepLinkUpload = dl;
      // r29g: 4 秒後清 highlight（hash 留 — reload 仍重 trigger）
      setTimeout(() => {
        state.deepLinkUpload = null;
        state.deepLinkUploadId = null;
        _writeHash();
        renderList();
      }, 4000);
    } else {
      // r29h: 上傳已不存在 / 隱藏 → toast 友善提示（取代 r29g 的 console.warn）
      showToast(
        `分享的作品 #${state.deepLinkUploadId} 已不存在或已被隱藏`,
        'warning',
      );
      state.deepLinkUpload = null;
      // 清掉 hash 中的 upload key — 避免 user reload 又看到同樣 toast
      state.deepLinkUploadId = null;
      _writeHash();
    }
  }
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

  // r29g: prepend deep-link upload + dedup
  if (state.deepLinkUpload) {
    const dlId = state.deepLinkUpload.id;
    state.items = state.items.filter(it => it.id !== dlId);
    state.items.unshift(state.deepLinkUpload);
  }

  renderHeader();
  renderStats();
  renderProfileBanner();
  renderList();
}

// r29g: fetch single upload detail (既有 endpoint，無 backend change)
async function _fetchUploadDetail(uploadId) {
  const r = await fetch(`/api/gallery/uploads/${uploadId}`, {
    credentials: 'same-origin',
  });
  if (!r.ok) return null;
  return r.json();
}

// r29d: fetch profile JSON
async function _fetchUserProfile(userId) {
  const r = await fetch(`/api/gallery/users/${userId}`, {
    credentials: 'same-origin',
  });
  if (!r.ok) {
    const data = await r.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// r29e: render top-uploads strip 內嵌 banner（最受歡迎前 N 件）
function _renderProfileTopStrip(topUploads) {
  if (!topUploads || topUploads.length === 0) return '';
  const items = topUploads.map((it, idx) => {
    const medal = ['🥇', '🥈', '🥉'][idx] || '⭐';
    const kind = it.kind || 'psd';
    // 只 mandala 有 thumbnail；其他 kind 用文字 placeholder
    const thumbHtml = (kind === 'mandala')
      ? `<img src="/api/gallery/uploads/${it.id}/thumbnail"
              alt="${_escape(it.title)}"
              loading="lazy"
              onerror="this.style.display='none'">`
      : `<span class="gl-profile-top-noimg">${_escape((it.title || '').slice(0, 2) || '?')}</span>`;
    const titleAttr = `${it.title} · ❤️ ${it.like_count}`;
    return `
      <a href="#" class="gl-profile-top-thumb"
         data-action="goto-upload" data-upload-id="${it.id}"
         title="${_escape(titleAttr)}">
        <span class="gl-profile-top-medal">${medal}</span>
        ${thumbHtml}
        <span class="gl-profile-top-likes">❤️ ${it.like_count}</span>
      </a>`;
  }).join('');
  return `
    <div class="gl-profile-top">
      <div class="gl-profile-top-label">🏆 最受歡迎</div>
      <div class="gl-profile-top-strip">${items}</div>
    </div>`;
}


// r29d: render profile banner above list (r29e: + top-uploads strip)
function renderProfileBanner() {
  let banner = $('gl-profile-banner');
  if (!state.userFilter || !state.profile) {
    if (banner) banner.hidden = true;
    return;
  }
  const u = state.profile.user;
  const s = state.profile.stats;
  const top = state.profile.top_uploads || [];
  const author = u.display_name || _emailHandle(u.email);
  const memberSince = _formatRelativeTime(s.member_since);
  const bioHtml = u.bio
    ? `<div class="gl-profile-bio">${_escape(u.bio)}</div>`
    : '<div class="gl-profile-bio gl-profile-bio--empty">（尚未填寫個人簡介）</div>';
  // r29i: 看自己 profile 時顯示 ✏️ 編輯快捷按鈕
  const isOwnProfile = state.me && state.me.id === u.id;
  const editBtnHtml = isOwnProfile
    ? `<button class="gl-btn gl-profile-edit" data-action="profile-edit"
                type="button" title="編輯個人資料">
         ✏️ 編輯
       </button>`
    : '';
  if (!banner) {
    // 動態建 banner element（避免修改 gallery.html）
    banner = document.createElement('section');
    banner.id = 'gl-profile-banner';
    banner.className = 'gl-profile-banner';
    const main = document.querySelector('.gl-main');
    if (main) main.parentNode.insertBefore(banner, main);
  }
  banner.hidden = false;
  banner.innerHTML = `
    <button class="gl-btn gl-profile-back" data-action="profile-back" type="button">
      ← 返回全部
    </button>
    <div class="gl-profile-avatar-wrap">${avatarHtml(u, 64)}</div>
    <div class="gl-profile-info">
      <div class="gl-profile-name">${_escape(author)}${editBtnHtml}</div>
      ${bioHtml}
      <div class="gl-profile-stats">
        <span><b>${s.total_uploads}</b> 個作品</span>
        <span>·</span>
        <span><b>${s.total_likes_received}</b> 個讚收到</span>
        <span>·</span>
        <span>加入 ${_escape(memberSince)}</span>
      </div>
      ${_renderProfileTopStrip(top)}
    </div>
  `;
  banner.querySelector('[data-action="profile-back"]').addEventListener('click', () => {
    state.userFilter = null;
    state.profile = null;
    state.page = 1;
    refresh();
  });
  // r29i: 編輯按鈕（只有看自己 profile 才存在）
  const editBtn = banner.querySelector('[data-action="profile-edit"]');
  if (editBtn) {
    editBtn.addEventListener('click', () => {
      // 編完成功 → auth.js submit handler 已 chain refresh()，
      // refresh 會自動重 fetch profile 並更新 banner
      showProfileDialog(state.me);
    });
  }
  // r29e: top-strip click → scroll 到對應 card 並高亮 2 秒
  banner.querySelectorAll('[data-action="goto-upload"]').forEach(link => {
    link.addEventListener('click', (ev) => {
      ev.preventDefault();
      const uid = Number(link.dataset.uploadId);
      const card = document.querySelector(`.gl-card[data-id="${uid}"]`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.classList.add('gl-card--highlight');
        setTimeout(() => card.classList.remove('gl-card--highlight'), 2000);
      }
    });
  });
}

async function _fetchUploads() {
  const params = new URLSearchParams({
    page: state.page,
    size: state.size,
  });
  // r28: kind filter ('' = 全部，不送)
  if (state.kindFilter) params.set('kind', state.kindFilter);
  // r29b/r29c: sort (newest / likes / hot)
  if (state.sort && state.sort !== 'newest') params.set('sort', state.sort);
  // r29b: bookmarked filter
  if (state.bookmarkedOnly) params.set('bookmarked', 'true');
  // r29c: search query
  if (state.q) params.set('q', state.q);
  // r29d: user_id filter (profile)
  if (state.userFilter) params.set('user_id', state.userFilter);
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

  // r28 / r29b: filter tabs (kind + bookmarked)
  document.querySelectorAll('.gl-filter-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      const isBookmarked = btn.dataset.bookmarked === 'true';
      // 切「我的收藏」
      if (isBookmarked) {
        // 未登入按 click（理論上不會，因為按鈕 hidden）→ 提示登入
        if (!state.me) {
          if (confirm('需要登入才能看「我的收藏」。要前往登入嗎？')) {
            showLoginDialog();
          }
          return;
        }
        if (state.bookmarkedOnly && state.kindFilter === '') return;
        state.bookmarkedOnly = true;
        state.kindFilter = '';   // bookmarked 跟 kind 互斥（簡化）
      } else {
        const kind = btn.dataset.kind || '';
        if (!state.bookmarkedOnly && state.kindFilter === kind) return;
        state.bookmarkedOnly = false;
        state.kindFilter = kind;
      }
      state.page = 1;
      _syncFilterTabsActive();
      refresh();
    });
  });

  // r29b: sort dropdown
  $('gl-sort').addEventListener('change', (ev) => {
    state.sort = ev.target.value;
    state.page = 1;
    refresh();
  });

  // r29c: search input — debounced 300ms 觸發 refresh
  let searchTimer = null;
  const searchInput = $('gl-search');
  if (searchInput) {
    searchInput.addEventListener('input', (ev) => {
      const q = (ev.target.value || '').trim();
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        if (state.q === q) return;  // 沒變化不打 API
        state.q = q;
        state.page = 1;
        refresh();
      }, 300);
    });
  }
}

// r29b: sync 哪個 filter tab 當前 active
function _syncFilterTabsActive() {
  document.querySelectorAll('.gl-filter-tab').forEach(b => {
    let active;
    if (b.dataset.bookmarked === 'true') {
      active = state.bookmarkedOnly === true;
    } else {
      active = !state.bookmarkedOnly && (b.dataset.kind || '') === state.kindFilter;
    }
    b.classList.toggle('is-active', active);
    b.setAttribute('aria-selected', active ? 'true' : 'false');
  });
}


// ============================================================ boot

(async function boot() {
  attachAuthHandlers({ refresh });
  attachUploaderHandlers({ refresh });
  _wireToolbar();
  // r29f: 讀 hash → 套進 state（在 first refresh 之前，避免閃畫面）
  _applyHashPatchToState(parseHash(window.location.hash));
  _syncUiFromState();
  // r29f: 監聽外部來源改 hash（user 上一頁 / 點 profile 連結進入 / 手動改網址）
  window.addEventListener('hashchange', _onHashChange);
  await refresh();
})();
