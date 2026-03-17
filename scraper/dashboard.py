"""
scrapit dashboard — local web UI for browsing scrape results.

Usage:
    scrapit serve
    scrapit serve --port 8080 --no-browser

Requires: pip install scrapit[ui]
"""

import asyncio
import csv
import io
import json
import threading
from typing import Optional
from pathlib import Path
from datetime import datetime

from scraper.config import OUTPUT_DIR
from pathlib import Path as _Path
_DIRECTIVES_DIR = _Path(__file__).resolve().parent / "directives"

# job state: {name: {status, error, finished_at}}
_jobs: dict[str, dict] = {}

try:
    from fastapi import FastAPI, HTTPException, Depends, status
    from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
    from fastapi.security import HTTPBasic, HTTPBasicCredentials
    import uvicorn
except ImportError:
    raise ImportError(
        "fastapi and uvicorn are required for the dashboard.\n"
        "Install with: pip install scrapit[ui]"
    )


_auth_user: Optional[str] = None
_auth_pass: Optional[str] = None

security = HTTPBasic(auto_error=False)

def get_current_user(credentials: Optional[HTTPBasicCredentials] = Depends(security)):
    if not _auth_user or not _auth_pass:
        return True # auth disabled
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    import secrets
    correct_username = secrets.compare_digest(credentials.username, _auth_user)
    correct_password = secrets.compare_digest(credentials.password, _auth_pass)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

app = FastAPI(
    title="scrapit dashboard", 
    docs_url=None, 
    redoc_url=None,
    dependencies=[Depends(get_current_user)]
)

# ── Data helpers ──────────────────────────────────────────────────────────────

def _load_json(name: str) -> list[dict]:
    path = OUTPUT_DIR / f"{name}.json"
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else [data]
    except Exception:
        return []


def _list_directives() -> list[dict]:
    out = []
    for p in sorted(_DIRECTIVES_DIR.glob("*.yaml")):
        name = p.stem
        output_file = OUTPUT_DIR / f"{name}.json"
        count, last_run = 0, "—"
        if output_file.exists():
            try:
                data = json.loads(output_file.read_text(encoding="utf-8"))
                count = len(data) if isinstance(data, list) else 1
            except Exception:
                pass
            last_run = datetime.fromtimestamp(output_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        has_diff = (OUTPUT_DIR / f"{name}.diff.json").exists()
        out.append({"name": name, "count": count, "last_run": last_run, "has_diff": has_diff})
    return out


# ── API ───────────────────────────────────────────────────────────────────────

@app.get("/api/directives")
def api_directives():
    return _list_directives()


@app.get("/api/results/{name}")
def api_results(name: str, page: int = 1, per_page: int = 25):
    records = _load_json(name)
    if not records and not (OUTPUT_DIR / f"{name}.json").exists():
        raise HTTPException(404, f"No results found for '{name}'")
    total  = len(records)
    pages  = max(1, (total + per_page - 1) // per_page)
    page   = max(1, min(page, pages))
    start  = (page - 1) * per_page
    return {"records": records[start:start + per_page], "total": total, "page": page, "pages": pages}


@app.get("/api/diff/{name}")
def api_diff(name: str):
    path = OUTPUT_DIR / f"{name}.diff.json"
    if not path.exists():
        raise HTTPException(404, "No diff found")
    return json.loads(path.read_text(encoding="utf-8"))


@app.post("/api/run/{name}")
def api_run(name: str):
    yaml_path = _DIRECTIVES_DIR / f"{name}.yaml"
    if not yaml_path.exists():
        raise HTTPException(404, f"Directive '{name}' not found")
    if _jobs.get(name, {}).get("status") == "running":
        return {"status": "already_running"}

    _jobs[name] = {"status": "running", "error": None, "finished_at": None}

    def _run():
        try:
            from scraper.scrapers import grab_elements_by_directive
            from scraper.storage import json_file
            results = asyncio.run(grab_elements_by_directive(str(yaml_path)))
            if not isinstance(results, list):
                results = [results]
            OUTPUT_DIR.mkdir(exist_ok=True)
            json_file.save(results, name)
            _jobs[name] = {"status": "done", "error": None, "finished_at": datetime.now().isoformat()}
        except Exception as e:
            _jobs[name] = {"status": "error", "error": str(e), "finished_at": datetime.now().isoformat()}

    threading.Thread(target=_run, daemon=True).start()
    return {"status": "running"}


@app.get("/api/run/{name}/status")
def api_run_status(name: str):
    return _jobs.get(name, {"status": "idle"})


@app.get("/metrics")
def metrics():
    """Expose Prometheus metrics for scraping."""
    from scraper.metrics import get_metrics_content
    from fastapi.responses import Response
    try:
        from prometheus_client import CONTENT_TYPE_LATEST
    except ImportError:
        CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    return Response(get_metrics_content(), media_type=CONTENT_TYPE_LATEST)


@app.get("/export/{name}/json")
def export_json(name: str):
    records = _load_json(name)
    if not records:
        raise HTTPException(404)
    content = json.dumps(records, indent=2, default=str)
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{name}.json"'},
    )


@app.get("/export/{name}/csv")
def export_csv(name: str):
    records = _load_json(name)
    if not records:
        raise HTTPException(404)
    buf = io.StringIO()
    keys = list(records[0].keys())
    w = csv.DictWriter(buf, fieldnames=keys, extrasaction="ignore")
    w.writeheader()
    w.writerows(records)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'},
    )


# ── Frontend ──────────────────────────────────────────────────────────────────

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>scrapit dashboard</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

  :root {
    --bg:       #0f1117;
    --surface:  #1a1d27;
    --border:   #2a2d3e;
    --accent:   #6c63ff;
    --accent2:  #a78bfa;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --green:    #34d399;
    --red:      #f87171;
    --yellow:   #fbbf24;
    --radius:   8px;
    --font:     'Inter', system-ui, -apple-system, sans-serif;
  }

  body { background: var(--bg); color: var(--text); font-family: var(--font); display: flex; height: 100vh; overflow: hidden; }

  /* Sidebar */
  #sidebar {
    width: 260px; min-width: 220px; background: var(--surface); border-right: 1px solid var(--border);
    display: flex; flex-direction: column; overflow: hidden;
  }
  #sidebar-header {
    padding: 20px 16px 14px; border-bottom: 1px solid var(--border);
  }
  #sidebar-header h1 { font-size: 18px; font-weight: 700; letter-spacing: -.03em; color: var(--text); }
  #sidebar-header h1 span { color: #58a6ff; }
  #sidebar-header p  { font-size: 11px; color: var(--muted); margin-top: 2px; }
  #directive-list { flex: 1; overflow-y: auto; padding: 8px 0; }
  .directive-item {
    display: flex; align-items: center; justify-content: space-between;
    padding: 9px 16px; cursor: pointer; border-radius: 0;
    transition: background .15s; gap: 8px;
  }
  .directive-item:hover { background: rgba(108,99,255,.12); }
  .directive-item.active { background: rgba(108,99,255,.2); border-left: 3px solid var(--accent); padding-left: 13px; }
  .directive-item .d-name { font-size: 13px; font-weight: 500; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .directive-item .d-meta { font-size: 10px; color: var(--muted); white-space: nowrap; }
  .directive-item .d-badge {
    font-size: 10px; background: rgba(108,99,255,.25); color: var(--accent2);
    padding: 1px 6px; border-radius: 99px; white-space: nowrap;
  }
  .diff-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--yellow); flex-shrink: 0; }
  .run-btn {
    font-size: 10px; padding: 2px 8px; border-radius: 99px; border: 1px solid var(--border);
    background: transparent; color: var(--muted); cursor: pointer; transition: all .15s; white-space: nowrap;
  }
  .run-btn:hover { border-color: var(--green); color: var(--green); }
  .run-btn.running { border-color: var(--yellow); color: var(--yellow); cursor: default; animation: pulse 1s infinite; }
  .run-btn.error { border-color: var(--red); color: var(--red); }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }

  /* Main */
  #main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
  #topbar {
    padding: 14px 24px; border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
  }
  #topbar h2 { font-size: 15px; font-weight: 600; color: var(--text); }
  #topbar .actions { display: flex; gap: 8px; }
  .btn {
    padding: 6px 14px; border-radius: var(--radius); font-size: 12px; font-weight: 500;
    cursor: pointer; border: 1px solid var(--border); background: var(--surface);
    color: var(--text); transition: all .15s; text-decoration: none; display: inline-flex; align-items: center; gap: 5px;
  }
  .btn:hover { border-color: var(--accent); color: var(--accent2); }
  .btn-primary { background: var(--accent); border-color: var(--accent); color: #fff; }
  .btn-primary:hover { background: #5a52e8; color: #fff; }

  #content { flex: 1; overflow-y: auto; padding: 20px 24px; display: flex; flex-direction: column; gap: 16px; }

  /* Table */
  .table-wrap { border-radius: var(--radius); border: 1px solid var(--border); overflow: hidden; }
  table { width: 100%; border-collapse: collapse; font-size: 12px; }
  thead th {
    background: var(--surface); padding: 10px 12px; text-align: left;
    font-weight: 600; color: var(--muted); font-size: 11px; text-transform: uppercase;
    letter-spacing: .5px; border-bottom: 1px solid var(--border); white-space: nowrap;
  }
  tbody tr { border-bottom: 1px solid var(--border); transition: background .1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: rgba(255,255,255,.03); }
  tbody td { padding: 9px 12px; color: var(--text); max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  tbody td.null { color: var(--muted); font-style: italic; }

  /* Pagination */
  .pagination { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--muted); justify-content: flex-end; }
  .pagination .btn { padding: 4px 10px; }

  /* Diff panel */
  .diff-panel { border: 1px solid var(--border); border-radius: var(--radius); overflow: hidden; }
  .diff-panel-header { background: var(--surface); padding: 10px 16px; font-size: 12px; font-weight: 600; color: var(--yellow); border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 6px; }
  .diff-table { width: 100%; border-collapse: collapse; font-size: 12px; }
  .diff-table th { padding: 8px 14px; text-align: left; font-size: 11px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: .5px; background: rgba(0,0,0,.2); }
  .diff-table td { padding: 8px 14px; border-top: 1px solid var(--border); }
  .diff-table .field { font-weight: 500; font-family: monospace; font-size: 11px; color: var(--accent2); }
  .diff-table .old { color: var(--red); }
  .diff-table .new { color: var(--green); }

  /* Empty state */
  .empty { display: flex; flex-direction: column; align-items: center; justify-content: center; flex: 1; gap: 10px; color: var(--muted); padding: 60px; text-align: center; }
  .empty svg { opacity: .3; }
  .empty h3 { font-size: 15px; color: var(--text); }
  .empty p { font-size: 12px; max-width: 320px; line-height: 1.6; }

  /* Scrollbar */
  ::-webkit-scrollbar { width: 6px; height: 6px; }
  ::-webkit-scrollbar-track { background: transparent; }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
</style>
</head>
<body>

<nav id="sidebar">
  <div id="sidebar-header">
    <h1>scrap<span>it</span></h1>
    <p id="sidebar-subtitle">loading…</p>
  </div>
  <div id="directive-list"></div>
</nav>

<section id="main">
  <div id="topbar">
    <h2 id="topbar-title">Select a directive</h2>
    <div class="actions" id="topbar-actions" style="display:none">
      <a id="btn-export-json" class="btn" href="#" download>⬇ JSON</a>
      <a id="btn-export-csv"  class="btn" href="#" download>⬇ CSV</a>
    </div>
  </div>
  <div id="content">
    <div class="empty" id="empty-state">
      <svg width="48" height="48" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 7h16M4 12h10M4 17h6"/></svg>
      <h3>No directive selected</h3>
      <p>Pick a directive from the sidebar to view its scrape results.</p>
    </div>
  </div>
</section>

<script>
const $ = id => document.getElementById(id);
let _current = null, _page = 1, _pages = 1;
const _polling = {};

async function runDirective(name, btn) {
  btn.textContent = '…'; btn.className = 'run-btn running'; btn.disabled = true;
  await fetch('/api/run/' + name, {method: 'POST'});
  _polling[name] = setInterval(async () => {
    const s = await fetch('/api/run/' + name + '/status').then(r => r.json());
    if (s.status === 'done') {
      clearInterval(_polling[name]);
      btn.textContent = '▶'; btn.className = 'run-btn'; btn.disabled = false;
      await loadDirectives();
      if (_current === name) await renderResults(name, 1);
    } else if (s.status === 'error') {
      clearInterval(_polling[name]);
      btn.textContent = '✗'; btn.className = 'run-btn error'; btn.disabled = false;
      btn.title = s.error;
    }
  }, 1500);
}

async function loadDirectives() {
  const res = await fetch('/api/directives');
  const list = await res.json();
  const el = $('directive-list');
  const sub = $('sidebar-subtitle');
  sub.textContent = list.length + ' directive' + (list.length !== 1 ? 's' : '');
  el.innerHTML = '';
  if (!list.length) {
    el.innerHTML = '<div style="padding:20px;color:var(--muted);font-size:12px;text-align:center">No output files found in output/</div>';
    return;
  }
  list.forEach(d => {
    const item = document.createElement('div');
    item.className = 'directive-item';
    item.dataset.name = d.name;
    const runBtn = document.createElement('button');
    runBtn.className = 'run-btn'; runBtn.textContent = '▶';
    runBtn.title = 'Run scrape';
    runBtn.addEventListener('click', e => { e.stopPropagation(); runDirective(d.name, runBtn); });

    item.innerHTML = `
      <div style="flex:1;overflow:hidden">
        <div class="d-name">${d.name}</div>
        <div class="d-meta">${d.last_run}</div>
      </div>
      ${d.has_diff ? '<div class="diff-dot" title="has diff"></div>' : ''}
      <span class="d-badge">${d.count}</span>
    `;
    item.appendChild(runBtn);
    item.addEventListener('click', () => selectDirective(d.name));
    el.appendChild(item);
  });
}

async function selectDirective(name) {
  _current = name;
  _page = 1;
  document.querySelectorAll('.directive-item').forEach(el => {
    el.classList.toggle('active', el.dataset.name === name);
  });
  $('topbar-title').textContent = name;
  $('topbar-actions').style.display = 'flex';
  $('btn-export-json').href = '/export/' + name + '/json';
  $('btn-export-json').download = name + '.json';
  $('btn-export-csv').href  = '/export/' + name + '/csv';
  $('btn-export-csv').download = name + '.csv';
  await renderResults(name, 1);
}

async function renderResults(name, page) {
  const res  = await fetch(`/api/results/${name}?page=${page}&per_page=25`);
  if (!res.ok) { $('content').innerHTML = '<div class="empty"><h3>Error loading results</h3></div>'; return; }
  const data = await res.json();
  _page  = data.page;
  _pages = data.pages;

  const records = data.records;
  const content = $('content');
  content.innerHTML = '';

  if (!records.length) {
    content.innerHTML = '<div class="empty"><h3>No records</h3><p>This directive has no saved results yet.</p></div>';
    return;
  }

  // Table
  const keys = Object.keys(records[0]);
  const wrap = document.createElement('div');
  wrap.className = 'table-wrap';
  let rows = records.map(r => {
    const cells = keys.map(k => {
      const v = r[k];
      if (v === null || v === undefined) return '<td class="null">null</td>';
      const s = String(v);
      return `<td title="${escHtml(s)}">${escHtml(s.length > 80 ? s.slice(0,80)+'…' : s)}</td>`;
    }).join('');
    return '<tr>' + cells + '</tr>';
  }).join('');
  wrap.innerHTML = `<table>
    <thead><tr>${keys.map(k => `<th>${escHtml(k)}</th>`).join('')}</tr></thead>
    <tbody>${rows}</tbody>
  </table>`;
  content.appendChild(wrap);

  // Pagination
  if (data.pages > 1) {
    const pag = document.createElement('div');
    pag.className = 'pagination';
    pag.innerHTML = `
      <button class="btn" onclick="changePage(${_page-1})" ${_page<=1?'disabled':''}>← Prev</button>
      <span>Page ${_page} of ${_pages} &nbsp;·&nbsp; ${data.total} records</span>
      <button class="btn" onclick="changePage(${_page+1})" ${_page>=_pages?'disabled':''}>Next →</button>
    `;
    content.appendChild(pag);
  }

  // Diff panel
  try {
    const dr = await fetch('/api/diff/' + name);
    if (dr.ok) {
      const diff = await dr.json();
      if (diff.changed && diff.fields && Object.keys(diff.fields).length) {
        const panel = document.createElement('div');
        panel.className = 'diff-panel';
        const frows = Object.entries(diff.fields).map(([f, v]) =>
          `<tr><td class="field">${escHtml(f)}</td><td class="old">${escHtml(String(v.old))}</td><td class="new">${escHtml(String(v.new))}</td></tr>`
        ).join('');
        panel.innerHTML = `
          <div class="diff-panel-header">⚡ Changes detected &nbsp;<span style="font-weight:400;color:var(--muted)">${diff.timestamp || ''}</span></div>
          <table class="diff-table">
            <thead><tr><th>Field</th><th>Old value</th><th>New value</th></tr></thead>
            <tbody>${frows}</tbody>
          </table>`;
        content.appendChild(panel);
      }
    }
  } catch(_) {}
}

function changePage(p) {
  if (!_current || p < 1 || p > _pages) return;
  renderResults(_current, p);
}

function escHtml(s) {
  return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

loadDirectives();
</script>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def index():
    return _HTML


# ── Entry point ───────────────────────────────────────────────────────────────

def serve(host: str = "127.0.0.1", port: int = 7331, open_browser: bool = True, auth: str | None = None):
    """Start the scrapit dashboard server."""
    global _auth_user, _auth_pass
    import os
    
    env_u = os.environ.get("SCRAPIT_DASHBOARD_USER")
    env_p = os.environ.get("SCRAPIT_DASHBOARD_PASS")
    if env_u and env_p:
        _auth_user = env_u
        _auth_pass = env_p
        
    if auth:
        import sys
        if ":" in auth:
            _auth_user, _auth_pass = auth.split(":", 1)
        else:
            print("error: auth must be in 'user:pass' format", file=sys.stderr)
            sys.exit(1)
    url = f"http://{host}:{port}"
    print(f"→ dashboard at {url}")
    if open_browser:
        import threading
        import webbrowser
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host=host, port=port, log_level="warning")
