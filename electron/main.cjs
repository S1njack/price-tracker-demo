const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

let mainWindow = null;
let flaskProcess = null;

const FLASK_PORT = 5000;
const FLASK_URL = `http://localhost:${FLASK_PORT}`;
const IS_WIN = process.platform === 'win32';
const IS_MAC = process.platform === 'darwin';

/**
 * Get the OS-specific writable data directory.
 * Electron's app.getPath('userData') resolves to:
 *   macOS:   ~/Library/Application Support/Price Tracker/
 *   Windows: %APPDATA%/Price Tracker/
 *   Linux:   ~/.config/Price Tracker/
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
    // Packaged: PyInstaller binary lives in resources/backend/
    const binaryName = IS_WIN ? 'api_secure.exe' : 'api_secure';
    const binaryPath = path.join(process.resourcesPath, 'backend', 'api_secure', binaryName);
    return { command: binaryPath, args: [], isBundle: true };
  }

  // Dev mode: spawn Python directly
  const pythonCmd = IS_WIN ? 'python' : 'python3';
  const apiPath = path.join(__dirname, '..', 'api_secure.py');
  return { command: pythonCmd, args: [apiPath], isBundle: false };
}

function startFlask() {
  const { command, args, isBundle } = getBackendCommand();
  const dataDir = getDataDir();

  // Working directory: project root in dev, resources/backend in packaged
  const cwd = isBundle
    ? path.join(process.resourcesPath, 'backend', 'api_secure')
    : path.join(__dirname, '..');

  const env = {
    ...process.env,
    PRICE_TRACKER_DATA: dataDir,
    ALLOWED_ORIGINS: `http://localhost:5173,http://localhost:${FLASK_PORT},file://`,
  };

  // Point Playwright at the bundled Chromium when packaged
  if (app.isPackaged) {
    env.PLAYWRIGHT_BROWSERS_PATH = path.join(process.resourcesPath, 'chromium');
  }

  console.log(`[Electron] Starting backend: ${command} ${args.join(' ')}`);
  console.log(`[Electron] Data dir: ${dataDir}`);
  console.log(`[Electron] CWD: ${cwd}`);

  flaskProcess = spawn(command, args, {
    cwd,
    env,
    stdio: ['pipe', 'pipe', 'pipe'],
  });

  flaskProcess.stdout.on('data', (data) => {
    console.log(`[Flask] ${data.toString().trim()}`);
  });

  flaskProcess.stderr.on('data', (data) => {
    console.error(`[Flask] ${data.toString().trim()}`);
  });

  flaskProcess.on('close', (code) => {
    console.log(`[Flask] Process exited with code ${code}`);
    flaskProcess = null;
  });

  flaskProcess.on('error', (err) => {
    console.error(`[Flask] Failed to start: ${err.message}`);
    flaskProcess = null;
  });
}

async function waitForFlask(maxRetries = 30) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      const response = await fetch(`${FLASK_URL}/api/health`);
      if (response.ok) {
        console.log('[Electron] Flask is ready');
        return true;
      }
    } catch {
      // Flask not ready yet
    }
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
    // Dev mode: load from Vite dev server
    mainWindow.loadURL('http://localhost:5173');
    mainWindow.webContents.openDevTools();
  } else {
    // Production: load built files
    const indexPath = path.join(__dirname, '..', 'dist', 'index.html');
    mainWindow.loadFile(indexPath);
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Kill the Flask backend process (cross-platform).
 */
function killFlask() {
  if (!flaskProcess) return;

  console.log('[Electron] Killing Flask process');

  if (IS_WIN) {
    // Windows: use taskkill to kill the process tree
    spawn('taskkill', ['/pid', String(flaskProcess.pid), '/f', '/t']);
  } else {
    // macOS/Linux: SIGTERM for graceful shutdown
    flaskProcess.kill('SIGTERM');
  }

  flaskProcess = null;
}

app.whenReady().then(async () => {
  // Show loading window
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

  startFlask();

  const ready = await waitForFlask();

  loadingWindow.close();

  if (!ready) {
    const message = app.isPackaged
      ? 'The backend server failed to start.\n\nTry reinstalling the application.'
      : 'The Flask API server failed to start within 30 seconds.\n\nCheck that all Python dependencies are installed:\n  pip install -r requirements-secure.txt';

    dialog.showErrorBox('Server Failed to Start', message);
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
