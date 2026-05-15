"""Admin panel UI — vanilla JS SPA rendered as HTML."""

from __future__ import annotations

from starlette.responses import HTMLResponse

CONTENT = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Web MCP — Admin</title>
<style>
:root { --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a; --text: #e4e4e7; --muted: #71717a; --accent: #6366f1; --accent-hover: #818cf8; --danger: #ef4444; --success: #22c55e; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); line-height: 1.6; }
.container { max-width: 960px; margin: 0 auto; padding: 2rem 1rem; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border); }
header h1 { font-size: 1.5rem; font-weight: 600; }
header .badge { background: var(--accent); color: #fff; padding: 0.25rem 0.75rem; border-radius: 999px; font-size: 0.75rem; }
.card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 1.5rem; margin-bottom: 1rem; }
.card h2 { font-size: 1.1rem; margin-bottom: 1rem; }
.btn { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.5rem 1rem; border: 1px solid var(--border); border-radius: 6px; background: var(--surface); color: var(--text); cursor: pointer; font-size: 0.875rem; transition: all 0.15s; }
.btn:hover { border-color: var(--accent); }
.btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
.btn-primary:hover { background: var(--accent-hover); }
.btn-danger { background: var(--danger); border-color: var(--danger); color: #fff; }
.btn-sm { padding: 0.25rem 0.5rem; font-size: 0.8rem; }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 0.75rem; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; }
.tag { display: inline-block; padding: 0.15rem 0.5rem; border-radius: 4px; font-size: 0.75rem; background: var(--border); color: var(--muted); margin-right: 0.25rem; }
.tag-ro { background: #1e3a2f; color: var(--success); }
.tag-destructive { background: #3b1a1a; color: var(--danger); }
.form-group { margin-bottom: 1rem; }
.form-group label { display: block; font-size: 0.875rem; color: var(--muted); margin-bottom: 0.25rem; }
.form-group input, .form-group textarea, .form-group select { width: 100%; padding: 0.5rem 0.75rem; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-size: 0.875rem; }
.form-group input:focus, .form-group textarea:focus { outline: none; border-color: var(--accent); }
.form-row { display: flex; gap: 1rem; }
.form-row > .form-group { flex: 1; }
.tools-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 0.5rem; }
.tool-check { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem; border: 1px solid var(--border); border-radius: 6px; cursor: pointer; font-size: 0.875rem; }
.tool-check:hover { border-color: var(--accent); }
.tool-check input { accent-color: var(--accent); }
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; }
.modal { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 1.5rem; max-width: 500px; width: 90%; max-height: 80vh; overflow-y: auto; }
.modal h2 { margin-bottom: 1rem; }
.modal-actions { display: flex; gap: 0.5rem; justify-content: flex-end; margin-top: 1.5rem; }
.toast { position: fixed; bottom: 1rem; right: 1rem; padding: 0.75rem 1.25rem; border-radius: 8px; font-size: 0.875rem; z-index: 200; animation: slideIn 0.3s ease; }
.toast-success { background: var(--success); color: #fff; }
.toast-error { background: var(--danger); color: #fff; }
@keyframes slideIn { from { transform: translateY(1rem); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
.hidden { display: none !important; }
.empty { color: var(--muted); font-style: italic; padding: 2rem; text-align: center; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Web MCP Admin</h1>
    <div style="display:flex;align-items:center;gap:0.75rem;">
      <span class="badge">v1.0.0</span>
      <button class="btn" onclick="handleLogout()">Logout</button>
    </div>
  </header>

  <div id="toast" class="toast hidden"></div>

  <!-- Tools List -->
  <div class="card">
    <h2>Available Tools</h2>
    <div id="toolsList" class="tools-grid"></div>
  </div>

  <!-- Path Configurations -->
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem;">
      <h2 style="margin:0;">Path Configurations</h2>
      <button class="btn btn-primary" onclick="openModal()">+ Add Path</button>
    </div>
    <div id="pathsList"></div>
  </div>
</div>

<!-- Modal -->
<div id="modalOverlay" class="modal-overlay hidden" onclick="if(event.target===this)closeModal()">
  <div class="modal">
    <h2 id="modalTitle">Add Path</h2>
    <form id="pathForm" onsubmit="return savePath(event)">
      <input type="hidden" id="editPath">
      <div class="form-group">
        <label>Path</label>
        <input type="text" id="formPath" placeholder="/search" required>
      </div>
      <div class="form-group">
        <label>Name</label>
        <input type="text" id="formName" placeholder="Search tools" required>
      </div>
      <div class="form-group">
        <label>Description</label>
        <textarea id="formDesc" rows="2" placeholder="Optional description"></textarea>
      </div>
      <div class="form-group">
        <label>Enabled Tools</label>
        <div id="formTools" class="tools-grid"></div>
      </div>
      <div class="form-group">
        <label>
          <input type="checkbox" id="formAuth" checked> Requires auth
        </label>
      </div>
      <div class="modal-actions">
        <button type="button" class="btn" onclick="closeModal()">Cancel</button>
        <button type="submit" class="btn btn-primary">Save</button>
      </div>
    </form>
  </div>
</div>

<script>
const API = '';
let allTools = [];

async function fetchJSON(url, opts) {
  const res = await fetch(url, opts);
  if (res.status === 401) {
    window.location.href = '/admin/login';
    return null;
  }
  if (!res.ok) throw new Error(await res.text() || res.status);
  return res.json();
}

async function handleLogout() {
  try {
    await fetch('/admin/logout', { method: 'POST' });
  } catch {}
  window.location.href = '/admin/login';
}

async function loadTools() {
  try {
    const data = await fetchJSON(API + '/admin/tools');
    allTools = data ? data.tools : [];
    renderTools(allTools);
    renderFormTools(allTools);
  } catch(e) { showToast('Failed to load tools: ' + e.message, 'error'); }
}

function renderTools(tools) {
  document.getElementById('toolsList').innerHTML = tools.map(t =>
    '<div class="tool-check"><span>' + t.name + '</span>' +
    '<span class="tag ' + (t.is_read_only ? 'tag-ro' : 'tag-destructive') + '">' +
    (t.is_read_only ? 'read-only' : 'destructive') + '</span></div>'
  ).join('');
}

function renderFormTools(tools) {
  document.getElementById('formTools').innerHTML = tools.map(t =>
    '<label class="tool-check"><input type="checkbox" value="' + t.name + '"> ' + t.name + '</label>'
  ).join('');
}

async function loadPaths() {
  try {
    const paths = await fetchJSON(API + '/admin/config/paths');
    if (!paths || typeof paths !== 'object') return;
    const keys = Object.keys(paths);
    if (!keys.length) {
      document.getElementById('pathsList').innerHTML = '<div class="empty">No paths configured. Click "+ Add Path" to create one.</div>';
      return;
    }
    document.getElementById('pathsList').innerHTML = '<table><thead><tr><th>Path</th><th>Name</th><th>Tools</th><th>Auth</th><th></th></tr></thead><tbody>' +
      keys.map(p => '<tr>' +
        '<td><code>' + p + '</code></td>' +
        '<td>' + paths[p].name + '</td>' +
        '<td>' + paths[p].enabled_tools.map(t => '<span class="tag">' + t + '</span>').join('') + '</td>' +
        '<td>' + (paths[p].requires_auth ? 'Yes' : 'No') + '</td>' +
        '<td><button class="btn btn-sm" onclick="editPath(\\'' + p + '\\')">Edit</button> ' +
        '<button class="btn btn-sm btn-danger" onclick="deletePath(\\'' + p + '\\')">Delete</button></td></tr>'
      ).join('') + '</tbody></table>';
  } catch(e) { showToast('Failed to load paths: ' + e.message, 'error'); }
}

function openModal() {
  document.getElementById('modalTitle').textContent = 'Add Path';
  document.getElementById('pathForm').reset();
  document.getElementById('editPath').value = '';
  document.getElementById('modalOverlay').classList.remove('hidden');
}

function closeModal() {
  document.getElementById('modalOverlay').classList.add('hidden');
}

async function editPath(path) {
  try {
    const config = await fetchJSON(API + '/admin/config/paths/' + encodeURIComponent(path));
    if (!config) return;
    document.getElementById('modalTitle').textContent = 'Edit Path';
    document.getElementById('editPath').value = path;
    document.getElementById('formPath').value = path;
    document.getElementById('formPath').disabled = true;
    document.getElementById('formName').value = config.name;
    document.getElementById('formDesc').value = config.description || '';
    document.getElementById('formAuth').checked = config.requires_auth;
    document.getElementById('modalOverlay').classList.remove('hidden');
    // Check tools
    document.querySelectorAll('#formTools input[type=checkbox]').forEach(cb => {
      cb.checked = (config.enabled_tools || []).includes(cb.value);
    });
  } catch(e) { showToast('Failed to load path: ' + e.message, 'error'); }
}

async function savePath(e) {
  e.preventDefault();
  const editPath = document.getElementById('editPath').value;
  const path = document.getElementById('formPath').value;
  const name = document.getElementById('formName').value;
  const description = document.getElementById('formDesc').value;
  const requires_auth = document.getElementById('formAuth').checked;
  const enabled_tools = [...document.querySelectorAll('#formTools input:checked')].map(cb => cb.value);

  if (!enabled_tools.length) { showToast('Select at least one tool', 'error'); return false; }

  const body = { path, name, description, enabled_tools, requires_auth };

  try {
    if (editPath) {
      await fetchJSON(API + '/admin/config/paths/' + encodeURIComponent(editPath), {
        method: 'PUT', body: JSON.stringify(body)
      });
      showToast('Path updated', 'success');
    } else {
      await fetchJSON(API + '/admin/config/paths?path=' + encodeURIComponent(path), {
        method: 'POST', body: JSON.stringify(body)
      });
      showToast('Path created', 'success');
    }
    closeModal();
    loadPaths();
  } catch(err) { showToast('Save failed: ' + err.message, 'error'); }
  return false;
}

async function deletePath(path) {
  if (!confirm('Delete ' + path + '?')) return;
  try {
    await fetchJSON(API + '/admin/config/paths/' + encodeURIComponent(path), { method: 'DELETE' });
    showToast('Path deleted', 'success');
    loadPaths();
  } catch(err) { showToast('Delete failed: ' + err.message, 'error'); }
}

function showToast(msg, type) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast toast-' + type;
  t.classList.remove('hidden');
  setTimeout(() => t.classList.add('hidden'), 3000);
}

loadTools();
loadPaths();
</script>
</body>
</html>"""

LOGIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Web MCP — Admin Login</title>
<style>
:root { --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a; --text: #e4e4e7; --muted: #71717a; --accent: #6366f1; --accent-hover: #818cf8; --danger: #ef4444; }
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: var(--bg); color: var(--text); display: flex; align-items: center; justify-content: center; min-height: 100vh; }
.login-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 2.5rem; width: 100%; max-width: 380px; }
.login-card h1 { font-size: 1.5rem; font-weight: 600; text-align: center; margin-bottom: 0.25rem; }
.login-card .subtitle { color: var(--muted); text-align: center; font-size: 0.875rem; margin-bottom: 2rem; }
.form-group { margin-bottom: 1.25rem; }
.form-group label { display: block; font-size: 0.875rem; color: var(--muted); margin-bottom: 0.5rem; }
.form-group input { width: 100%; padding: 0.625rem 0.875rem; border: 1px solid var(--border); border-radius: 6px; background: var(--bg); color: var(--text); font-size: 0.875rem; transition: border-color 0.15s; }
.form-group input:focus { outline: none; border-color: var(--accent); }
.btn { width: 100%; padding: 0.625rem 1rem; border: none; border-radius: 6px; background: var(--accent); color: #fff; cursor: pointer; font-size: 0.875rem; font-weight: 500; transition: background 0.15s; }
.btn:hover { background: var(--accent-hover); }
.error-msg { color: var(--danger); font-size: 0.8125rem; margin-top: 0.75rem; text-align: center; min-height: 1.25rem; }
</style>
</head>
<body>
<div class="login-card">
  <h1>Web MCP Admin</h1>
  <p class="subtitle">Sign in to manage your server</p>
  <form onsubmit="return handleLogin(event)">
    <div class="form-group">
      <label for="password">Password</label>
      <input type="password" id="password" name="password" placeholder="Enter admin password" autocomplete="current-password" required>
    </div>
    <button type="submit" class="btn">Sign in</button>
  </form>
  <div id="error" class="error-msg"></div>
</div>
<script>
async function handleLogin(e) {
  e.preventDefault();
  const password = document.getElementById('password').value;
  const errorEl = document.getElementById('error');
  errorEl.textContent = '';
  try {
    const res = await fetch('/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password })
    });
    const data = await res.json();
    if (res.ok && data.status === 'ok') {
      window.location.href = '/admin/';
    } else {
      errorEl.textContent = data.error || 'Login failed';
    }
  } catch {
    errorEl.textContent = 'Connection error';
  }
  return false;
}
</script>
</body>
</html>"""


class AdminUI:
    """Serves the admin panel HTML."""

    @staticmethod
    def serve_index(request):  # noqa: ARG004
        """Serve the admin panel index page."""
        return HTMLResponse(content=CONTENT)

    @staticmethod
    def serve_login(request):  # noqa: ARG004
        """Serve the login page."""
        return HTMLResponse(content=LOGIN_HTML)
