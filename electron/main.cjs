const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn, execSync } = require('child_process');
const fs = require('fs');

let mainWindow = null;
let flaskProcess = null;
let backendLogs = [];

const FLASK_PORT = 5000;
const FLASK_URL = `http://localhost:${FLASK_PORT}`;
const IS_WIN = process.platform === 'win32';
const IS_MAC = process.platform === 'darwin';

function log(msg) {
  console.log(msg);
  backendLogs.push(msg);
  // Keep only last 50 lines
  if (backendLogs.length > 50) backendLogs.shift();
}

/**
 * Get the OS-specific writable data directory.
 */
function getDataDir() {
  const dir = app.getPath('userData');
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  return dir;
}

/**
 * Resolve the path to the bundled backend binary (packaged)
 * or fall back to spawning Python directly (dev mode).
 */
function getBackendCommand() {
  if (app.isPackaged) {
    const binaryName = IS_WIN ? 'api_secure.exe' : 'api_secure';
    const binaryPath = path.join(process.resourcesPath, 'backend', 'api_secure', binaryName);

    // Check if binary exists
    if (!fs.existsSync(binaryPath)) {
      log(`[Electron] ERROR: Backend binary not found at: ${binaryPath}`);
      // List what's actually in the resources dir for debugging
      try {
        const backendDir = path.join(process.resourcesPath, 'backend');
        if (fs.existsSync(backendDir)) {
          const files = fs.readdirSync(backendDir);
          log(`[Electron] Contents of ${backendDir}: ${files.join(', ')}`);
        } else {
          log(`[Electron] Backend directory does not exist: ${backendDir}`);
        }
      } catch (e) {
        log(`[Electron] Could not list backend dir: ${e.message}`);
      }
      return null;
    }

    // Ensure execute permission on macOS/Linux
    if (!IS_WIN) {
      try {
        fs.chmodSync(binaryPath, 0o755);
        log(`[Electron] Set execute permission on backend binary`);
      } catch (e) {
        log(`[Electron] WARNING: Could not chmod binary: ${e.message}`);
      }
    }

    return { command: binaryPath, args: [], isBundle: true };
  }

  // Dev mode: spawn Python directly
  const pythonCmd = IS_WIN ? 'python' : 'python3';
  const apiPath = path.join(__dirname, '..', 'api_secure.py');
  return { command: pythonCmd, args: [apiPath], isBundle: false };
}

function startFlask() {
  const backend = getBackendCommand();

  if (!backend) {
    log('[Electron] Cannot start backend - binary not found');
    return false;
  }

  const { command, args, isBundle } = backend;
  const dataDir = getDataDir();

  const cwd = isBundle
    ? path.join(process.resourcesPath, 'backend', 'api_secure')
    : path.join(__dirname, '..');

  const env = {
    ...process.env,
    PRICE_TRACKER_DATA: dataDir,
    ALLOWED_ORIGINS: `http://localhost:5173,http://localhost:${FLASK_PORT},file://`,
  };

  if (app.isPackaged) {
    env.PLAYWRIGHT_BROWSERS_PATH = path.join(process.resourcesPath, 'chromium');
  }

  log(`[Electron] Starting backend: ${command} ${args.join(' ')}`);
  log(`[Electron] Data dir: ${dataDir}`);
  log(`[Electron] CWD: ${cwd}`);
  log(`[Electron] Binary exists: ${fs.existsSync(command)}`);

  flaskProcess = spawn(command, args, {
    cwd,
    env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  flaskProcess.stdout.on('data', (data) => {
    log(`[Flask] ${data.toString().trim()}`);
  });

  flaskProcess.stderr.on('data', (data) => {
    log(`[Flask stderr] ${data.toString().trim()}`);
  });

  flaskProcess.on('close', (code) => {
    log(`[Flask] Process exited with code ${code}`);
    flaskProcess = null;
  });

  flaskProcess.on('error', (err) => {
    log(`[Flask] Failed to start: ${err.message}`);
    flaskProcess = null;
  });

  return true;
}

async function waitForFlask(maxRetries = 30) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(`${FLASK_URL}/api/health`);
      if (response.ok) {
        log('[Electron] Flask is ready');
        return true;
      }
    } catch {
      // Flask not ready yet
    }
    log(`[Electron] Waiting for Flask... (${i + 1}/${maxRetries})`);
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  return false;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    title: 'Price Tracker',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (!app.isPackaged && process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    const indexPath = path.join(__dirname, '..', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

function killFlask() {
  if (!flaskProcess) return;

  log('[Electron] Killing Flask process');

  if (IS_WIN) {
    spawn('taskkill', ['/pid', String(flaskProcess.pid), '/f', '/t']);
  } else {
    flaskProcess.kill('SIGTERM');
  }

  flaskProcess = null;
}

app.whenReady().then(async () => {
  const loadingWindow = new BrowserWindow({
    width: 400,
    height: 200,
    frame: false,
    resizable: false,
    alwaysOnTop: true,
    webPreferences: { contextIsolation: true },
  });
  loadingWindow.loadURL(`data:text/html,
    <html>
      <body style="display:flex;align-items:center;justify-content:center;height:100vh;margin:0;background:#1e293b;color:#fbbf24;font-family:system-ui;font-size:18px;">
        <div style="text-align:center">
          <div style="font-size:24px;margin-bottom:12px;">Price Tracker</div>
          <div>Starting server...</div>
        </div>
      </body>
    </html>`);

  const started = startFlask();

  if (!started) {
    loadingWindow.close();
    dialog.showErrorBox(
      'Server Failed to Start',
      'The backend binary was not found in the application bundle.\n\n' +
      'Debug info:\n' + backendLogs.join('\n')
    );
    app.quit();
    return;
  }

  const ready = await waitForFlask();

  loadingWindow.close();

  if (!ready) {
    const debugInfo = backendLogs.slice(-20).join('\n');

    dialog.showErrorBox(
      'Server Failed to Start',
      app.isPackaged
        ? `The backend server failed to start.\n\nLogs:\n${debugInfo}`
        : 'The Flask API server failed to start within 30 seconds.\n\nCheck that all Python dependencies are installed:\n  pip install -r requirements-secure.txt'
    );
    app.quit();
    return;
  }

  createWindow();
});

app.on('window-all-closed', () => {
  if (!IS_MAC) {
    app.quit();
  }
});

app.on('activate', () => {
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('before-quit', () => {
  killFlask();
});
