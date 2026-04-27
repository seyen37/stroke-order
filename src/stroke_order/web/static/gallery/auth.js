// ======================================================================
// gallery/auth.js — login modal + magic-link UX + profile editor.
//
// API surface (called from gallery.js):
//   showLoginDialog()      open the email-input modal
//   showProfileDialog(me)  open the profile editor (display_name + bio)
//   logout()               POST /auth/logout, return to anonymous state
//   fetchMe()              GET /me   (logged_in: bool, user: {...})
//
// We expose `attachAuthHandlers(ctx)` so the main module can wire the
// dialog buttons + keep `ctx.refresh()` callbacks for after-action UI
// updates (re-render header / list).
// ======================================================================

const $ = id => document.getElementById(id);


// ----------------------------------------------------------- /me

export async function fetchMe() {
  const r = await fetch('/api/gallery/me', {
    credentials: 'same-origin',
  });
  if (!r.ok) {
    return { logged_in: false };
  }
  return r.json();
}


// ----------------------------------------------------------- login

export function showLoginDialog() {
  const dlg    = $('gl-login-dialog');
  const status = $('gl-login-status');
  status.hidden = true;
  status.textContent = '';
  status.classList.remove('ok', 'error', 'info');
  $('gl-login-email').value = '';
  $('gl-login-submit').disabled = false;
  if (typeof dlg.showModal === 'function') {
    dlg.showModal();
  } else {
    // Fallback for very old browsers — set 'open' attr
    dlg.setAttribute('open', '');
  }
}

export function hideLoginDialog() {
  const dlg = $('gl-login-dialog');
  if (dlg.open) dlg.close();
}

async function submitLogin(ev) {
  ev.preventDefault();
  const email  = ($('gl-login-email').value || '').trim();
  const status = $('gl-login-status');
  const submit = $('gl-login-submit');
  status.classList.remove('ok', 'error', 'info');
  if (!email || !email.includes('@')) {
    status.hidden = false;
    status.classList.add('error');
    status.textContent = '請輸入有效的 email';
    return;
  }
  submit.disabled = true;
  status.hidden = false;
  status.classList.add('info');
  status.textContent = '寄送中…';

  try {
    const r = await fetch('/api/gallery/auth/request-login', {
      method:  'POST',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify({email}),
      credentials: 'same-origin',
    });
    if (!r.ok) {
      const data = await r.json().catch(() => ({}));
      throw new Error(data.detail || `HTTP ${r.status}`);
    }
    status.classList.remove('info');
    status.classList.add('ok');
    status.innerHTML = (
      '✓ 登入連結已寄出，請查收信箱（含垃圾信件夾）。連結 15 分鐘內有效。' +
      '<br><small style="color:var(--gl-muted);">若您是部署者並啟用了 dev mode，' +
      '請查看伺服器 console 取得連結。</small>'
    );
  } catch (e) {
    status.classList.remove('info');
    status.classList.add('error');
    status.textContent = '寄送失敗：' + (e.message || e);
    submit.disabled = false;
  }
}


// ----------------------------------------------------------- logout

export async function logout() {
  await fetch('/api/gallery/auth/logout', {
    method:      'POST',
    credentials: 'same-origin',
  });
}


// ----------------------------------------------------------- profile

export function showProfileDialog(user) {
  const dlg    = $('gl-profile-dialog');
  const status = $('gl-profile-status');
  status.hidden = true;
  status.textContent = '';
  status.classList.remove('ok', 'error', 'info');

  $('gl-profile-display-name').value = user?.display_name || '';
  $('gl-profile-bio').value          = user?.bio || '';
  $('gl-profile-submit').disabled = false;
  if (typeof dlg.showModal === 'function') dlg.showModal();
  else dlg.setAttribute('open', '');
}

export function hideProfileDialog() {
  const dlg = $('gl-profile-dialog');
  if (dlg.open) dlg.close();
}

async function submitProfile(ev) {
  ev.preventDefault();
  const status = $('gl-profile-status');
  const submit = $('gl-profile-submit');
  status.classList.remove('ok', 'error', 'info');

  const body = {
    display_name: ($('gl-profile-display-name').value || '').trim(),
    bio:          ($('gl-profile-bio').value || '').trim(),
  };
  submit.disabled = true;
  status.hidden = false;
  status.classList.add('info');
  status.textContent = '儲存中…';

  try {
    const r = await fetch('/api/gallery/me', {
      method:  'PUT',
      headers: {'Content-Type': 'application/json'},
      body:    JSON.stringify(body),
      credentials: 'same-origin',
    });
    const data = await r.json().catch(() => ({}));
    if (!r.ok) {
      throw new Error(data.detail || `HTTP ${r.status}`);
    }
    status.classList.remove('info');
    status.classList.add('ok');
    status.textContent = '✓ 已儲存';
    return data.user;     // returned to caller for header re-render
  } catch (e) {
    status.classList.remove('info');
    status.classList.add('error');
    status.textContent = '儲存失敗：' + (e.message || e);
    submit.disabled = false;
    return null;
  }
}


// ----------------------------------------------------------- wiring

/**
 * Attach DOM handlers for login + profile dialogs.
 * @param {{ refresh: () => Promise<void> }} ctx
 *    `refresh` is called after a successful profile save / logout so
 *    the parent SPA can re-render its header & list.
 */
export function attachAuthHandlers(ctx) {
  // login dialog
  $('gl-login-form').addEventListener('submit', submitLogin);
  document.querySelector(
    '[data-action="login-cancel"]',
  ).addEventListener('click', () => hideLoginDialog());

  // profile dialog
  $('gl-profile-form').addEventListener('submit', async (ev) => {
    const updated = await submitProfile(ev);
    if (updated) {
      // Close after a brief moment so the user sees the success state
      setTimeout(() => {
        hideProfileDialog();
        ctx.refresh && ctx.refresh();
      }, 600);
    }
  });
  document.querySelector(
    '[data-action="profile-cancel"]',
  ).addEventListener('click', () => hideProfileDialog());
}
