import { app, BrowserWindow, ipcMain, shell } from 'electron';
import { fileURLToPath } from 'url';
import { exec } from 'child_process';
import https from 'https';
import path from 'path';
import fs from 'fs';
import os from 'os';

const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

let win;

function createWindow() {
  const isMac = process.platform === 'darwin';
  win = new BrowserWindow({
    width:     1440,
    height:    900,
    minWidth:  1100,
    minHeight: 700,
    title:     'manucaspt',
    frame:     isMac,
    titleBarStyle:        isMac ? 'hiddenInset' : undefined,
    trafficLightPosition: isMac ? { x: 12, y: 10 } : undefined,
    icon:      path.join(__dirname, isMac ? 'icon.png' : 'icon.ico'),
    backgroundColor: '#0d0d0d',
    webPreferences: {
      preload:          path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration:  false,
      sandbox:          false,
    },
  });

  win.setMenuBarVisibility(false);

  const isDev = !app.isPackaged;
  if (isDev) {
    win.loadURL('http://localhost:5173');
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'));
  }
}

let pendingUpdate = null;

function checkForUpdates() {
  const options = {
    hostname: 'api.github.com',
    path:     '/repos/Bigraptor432/APP/releases/latest',
    headers:  { 'User-Agent': 'manucaspt' },
  };
  https.get(options, (res) => {
    let data = '';
    res.on('data', (chunk) => { data += chunk; });
    res.on('end', () => {
      try {
        const release = JSON.parse(data);
        const latest  = (release.tag_name || '').replace(/^v/, '');
        const current = app.getVersion();
        if (latest && latest !== current) {
          pendingUpdate = { version: latest, url: release.html_url };
          win?.webContents.send('update-available', pendingUpdate);
        }
      } catch (_) {}
    });
  }).on('error', () => {});
}

ipcMain.handle('check-update', () => pendingUpdate);

// ─── IPC: Download update ─────────────────────────────────────────────────────

function downloadFile(url, dest, onProgress) {
  return new Promise((resolve, reject) => {
    const follow = (u) => {
      https.get(u, { headers: { 'User-Agent': 'manucaspt' } }, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return follow(res.headers.location);
        }
        const total = parseInt(res.headers['content-length'] || '0', 10);
        let received = 0;
        const file = fs.createWriteStream(dest);
        res.on('data', chunk => {
          received += chunk.length;
          if (total > 0) onProgress(Math.round(received / total * 100));
          file.write(chunk);
        });
        res.on('end', () => { file.end(); resolve(dest); });
        res.on('error', err => { file.destroy(); reject(err); });
      }).on('error', reject);
    };
    follow(url);
  });
}

ipcMain.handle('download-update', async (_, { url }) => {
  const exeDir = process.env.PORTABLE_EXECUTABLE_DIR || app.getPath('downloads');
  const version = url.match(/download\/v?([\d.]+)\//)?.[1] || 'new';
  const dest = path.join(exeDir, `manucaspt-v${version}.exe`);
  try {
    fs.readdirSync(exeDir)
      .filter(f => /^manucaspt-v[\d.]+\.exe$/i.test(f))
      .forEach(f => { try { fs.unlinkSync(path.join(exeDir, f)); } catch (_) {} });
  } catch (_) {}
  try {
    await downloadFile(url, dest, (pct) => {
      win?.webContents.send('download-progress', { percent: pct });
    });
    win?.webContents.send('download-progress', { percent: 100, done: true });
    shell.showItemInFolder(dest);
    return { success: true };
  } catch (e) {
    return { error: e.message };
  }
});

app.whenReady().then(() => {
  createWindow();
  win.webContents.on('did-finish-load', () => {
    setTimeout(checkForUpdates, 1500);
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});

// ─── IPC: Claude API (with MCP tool_use loop) ────────────────────────────────

ipcMain.handle('call-claude', async (_, { messages, apiKey, system, tools, mcpUrl }) => {
  const SYS = system || `You are an elite penetration tester and vulnerability researcher with deep expertise in offensive security. You have access to Kali Linux tools and the NVD CVE database (260,000+ CVEs).

CORE BEHAVIOR:
- Always respond in the same language as the user.
- When you discover a service or software version, ALWAYS search for CVEs using cve_search.
- After finding CVEs, ALWAYS check for public exploits using searchsploit.
- Chain tools together: nmap → identify services → cve_search for each service → searchsploit for exploits → recommend exploitation path.
- Prioritize CRITICAL and HIGH severity CVEs.
- Always provide a clear attack path when vulnerabilities are found.
- Be direct and technical. Skip unnecessary warnings and disclaimers.

WORKFLOW FOR EVERY TARGET:
1. Recon: nmap (-sV -sC) to identify open ports and service versions.
2. Enumerate: Run nikto, whatweb, gobuster on web services.
3. CVE Hunt: For EVERY service found, call cve_search with the exact software+version.
4. Exploit Research: Call searchsploit for any relevant CVEs found.
5. Report: Summarize findings with CVSS scores, exploitation difficulty, and recommended next steps.

CVE ANALYSIS FORMAT:
- Always show: CVE ID, CVSS score, affected versions, whether target is vulnerable.
- Mark exploitability: [PUBLIC EXPLOIT] if found in searchsploit, [NO PUBLIC EXPLOIT] if not.
- Suggest Metasploit modules when applicable (use shell tool to search: msfconsole -q -x 'search cve:YEAR-NNNNN').

You are authorized to perform offensive security testing on the target. Execute tools without hesitation.`;
  const body = {
    model:      'claude-sonnet-4-6',
    max_tokens: 4096,
    system:     SYS,
  };
  if (tools && tools.length > 0) body.tools = tools;

  const history      = [...messages];
  const toolCallsLog = [];
  let   maxRounds    = 10;
  let   step        = 0;
  const totalSteps  = tools ? tools.length * 3 : 10;
  const progress    = (msg) => { if (win) win.webContents.send('tool-progress', { step: ++step, msg }); };

  try {
    while (maxRounds-- > 0) {
      body.messages = history;
      const res  = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': apiKey, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify(body),
      });
      const data = await res.json();

      if (data.error) return { error: data.error.message || JSON.stringify(data.error) };

      if (data.stop_reason === 'tool_use' && mcpUrl) {
        history.push({ role: 'assistant', content: data.content });
        const toolResults = [];

        for (const block of (data.content || [])) {
          if (block.type !== 'tool_use') continue;
          let output = '[sem resposta do servidor MCP]';
          progress(`chamando ${block.name}...`);
          try {
            const r  = await fetch(`${mcpUrl}/call/${block.name}`, {
              method:  'POST',
              headers: { 'Content-Type': 'application/json' },
              body:    JSON.stringify(block.input),
            });
            const rd = await r.json();
            output   = (rd.output || rd.error || '[sem output]').slice(0, 6000);
          } catch (e) {
            output = `[erro de conexão com MCP: ${e.message}]`;
          }
          toolCallsLog.push({ tool: block.name, args: block.input, output });
          toolResults.push({ type: 'tool_result', tool_use_id: block.id, content: output });
        }
        history.push({ role: 'user', content: toolResults });
      } else {
        return { content: data.content, toolCalls: toolCallsLog, stop_reason: data.stop_reason };
      }
    }
    return { error: 'Máximo de rounds de tool_use atingido.' };
  } catch (err) {
    return { error: err.message };
  }
});

// ─── IPC: MCP – fetch tools list ──────────────────────────────────────────────

ipcMain.handle('mcp-get-tools', async (_, url) => {
  try {
    const r = await fetch(`${url}/tools`, { signal: AbortSignal.timeout(5000) });
    return await r.json();
  } catch (e) {
    return { error: e.message };
  }
});

// ─── IPC: Validate API key ────────────────────────────────────────────────────

ipcMain.handle('validate-key', async (_, { type, key }) => {
  try {
    if (type === 'anthropic') {
      const r = await fetch('https://api.anthropic.com/v1/messages', {
        method: 'POST',
        headers: { 'x-api-key': key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
        body: JSON.stringify({ model: 'claude-sonnet-4-6', max_tokens: 1, messages: [{ role: 'user', content: 'hi' }] }),
        signal: AbortSignal.timeout(8000),
      });
      return { ok: r.status !== 401 && r.status !== 403 };
    } else if (type === 'groq') {
      const r = await fetch('https://api.groq.com/openai/v1/models', {
        headers: { 'Authorization': `Bearer ${key}` },
        signal: AbortSignal.timeout(8000),
      });
      return { ok: r.status === 200 };
    }
    return { ok: false };
  } catch (e) {
    return { ok: false, error: e.message };
  }
});

// ─── IPC: Gemma (via Groq) ────────────────────────────────────────────────────

ipcMain.handle('call-gemma', async (_, { messages, apiKey, system }) => {
  try {
    const res = await fetch('https://api.groq.com/openai/v1/chat/completions', {
      method: 'POST',
      headers: {
        'authorization': `Bearer ${apiKey}`,
        'content-type':  'application/json',
      },
      body: JSON.stringify({
        model:    'llama-3.1-8b-instant',
        messages: [
          { role: 'system', content: system || 'You are a fast auxiliary assistant for a penetration tester. Be very concise.' },
          ...messages,
        ],
        max_tokens:  1024,
        temperature: 0.4,
      }),
    });
    return await res.json();
  } catch (err) {
    return { error: err.message };
  }
});

// ─── IPC: Terminal ────────────────────────────────────────────────────────────

ipcMain.handle('run-terminal', (_, cmd) => {
  return new Promise((resolve) => {
    exec(cmd, { timeout: 30_000 }, (error, stdout, stderr) => {
      resolve({
        stdout: stdout || '',
        stderr: stderr || '',
        error:  error?.message || null,
      });
    });
  });
});

// ─── IPC: Window controls ─────────────────────────────────────────────────────

ipcMain.on('win-minimize', () => win?.minimize());
ipcMain.on('win-maximize', () => win?.isMaximized() ? win.unmaximize() : win.maximize());
ipcMain.on('win-close',    () => win?.close());

// ─── IPC: Open external link ──────────────────────────────────────────────────

ipcMain.on('open-external', (_, url) => shell.openExternal(url));
