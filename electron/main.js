const { app, BrowserWindow, Tray, Menu, screen, ipcMain, nativeImage } = require("electron");
const path = require("path");
const fs = require("fs");

const ROOT = path.join(__dirname, "..");
const BUNDLED_ANCHORS = path.join(ROOT, "assets", "angle-anchors.json");
const TRAY_PATH = path.join(ROOT, "assets", "tray-icon.png");
let userAnchorsPath = null;

let petWindow = null;
let calibrateWindow = null;
let tray = null;
let locked = false;
let cursorTimer = null;

const PET_SIZE = 320;
const MARGIN = 16;

function isCalibrateFlag() {
  return process.argv.includes("--calibrate");
}

function createPetWindow() {
  const wa = screen.getPrimaryDisplay().workArea;
  const win = new BrowserWindow({
    width: PET_SIZE,
    height: PET_SIZE,
    x: wa.x + wa.width - PET_SIZE - MARGIN,
    y: wa.y + wa.height - PET_SIZE - MARGIN,
    frame: false,
    transparent: true,
    backgroundColor: "#00000000",
    alwaysOnTop: true,
    skipTaskbar: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    hasShadow: false,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  win.setAlwaysOnTop(true, "screen-saver");
  if (process.platform === "darwin") {
    win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true });
  }
  win.setIgnoreMouseEvents(false);
  win.loadFile(path.join(ROOT, "renderer", "pet.html"));
  win.once("ready-to-show", () => win.showInactive());
  win.on("closed", () => {
    petWindow = null;
  });
  return win;
}

function createCalibrateWindow() {
  if (calibrateWindow && !calibrateWindow.isDestroyed()) {
    calibrateWindow.show();
    calibrateWindow.focus();
    return calibrateWindow;
  }
  const win = new BrowserWindow({
    width: 1280,
    height: 860,
    title: "Cat Pet — Angle Anchors",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile(path.join(ROOT, "renderer", "calibrate.html"));
  win.on("closed", () => {
    calibrateWindow = null;
  });
  calibrateWindow = win;
  return win;
}

function applyLock(next) {
  locked = Boolean(next);
  if (petWindow && !petWindow.isDestroyed()) {
    petWindow.setIgnoreMouseEvents(locked, { forward: true });
    petWindow.webContents.send("lock-changed", locked);
  }
  buildTrayMenu();
  return locked;
}

function buildTrayMenu() {
  if (!tray) return;
  const menu = Menu.buildFromTemplate([
    { label: locked ? "已锁定（鼠标穿透）" : "未锁定（可拖动）", enabled: false },
    { type: "separator" },
    {
      label: locked ? "解锁" : "锁定",
      click: () => applyLock(!locked),
    },
    { label: "打开校准", click: () => createCalibrateWindow() },
    { type: "separator" },
    { label: "退出", click: () => app.quit() },
  ]);
  tray.setContextMenu(menu);
  tray.setToolTip(locked ? "Tuxedo Cat Pet · 已锁定" : "Tuxedo Cat Pet · 可拖动");
}

function startCursorLoop() {
  if (cursorTimer) clearInterval(cursorTimer);
  cursorTimer = setInterval(() => {
    if (!petWindow || petWindow.isDestroyed()) return;
    const pt = screen.getCursorScreenPoint();
    const b = petWindow.getBounds();
    petWindow.webContents.send("cursor", {
      x: pt.x,
      y: pt.y,
      wx: b.x,
      wy: b.y,
      ww: b.width,
      wh: b.height,
    });
  }, 8);
}

function anchorsFile() {
  if (userAnchorsPath && fs.existsSync(userAnchorsPath)) return userAnchorsPath;
  return BUNDLED_ANCHORS;
}

function setupIpc() {
  ipcMain.handle("get-anchors", () => {
    return JSON.parse(fs.readFileSync(anchorsFile(), "utf8"));
  });

  ipcMain.handle("save-anchors", (_e, data) => {
    const dest = userAnchorsPath || BUNDLED_ANCHORS;
    fs.mkdirSync(path.dirname(dest), { recursive: true });
    fs.writeFileSync(dest, JSON.stringify(data, null, 2), "utf8");
    if (petWindow && !petWindow.isDestroyed()) {
      petWindow.webContents.send("anchors-updated");
    }
    return true;
  });

  ipcMain.handle("set-locked", (_e, value) => applyLock(value));
  ipcMain.handle("get-locked", () => locked);

  ipcMain.on("move-window", (_e, pos) => {
    if (locked || !petWindow || petWindow.isDestroyed()) return;
    petWindow.setPosition(Math.round(pos.x), Math.round(pos.y));
  });
}

app.whenReady().then(() => {
  if (process.platform === "win32") {
    app.setAppUserModelId("local.desktop.catpet");
  }
  if (process.platform === "darwin" && app.dock) {
    app.dock.hide();
  }
  userAnchorsPath = path.join(app.getPath("userData"), "angle-anchors.json");
  setupIpc();

  const icon = nativeImage.createFromPath(TRAY_PATH);
  const traySize = process.platform === "win32" ? 16 : 18;
  tray = new Tray(icon.isEmpty() ? nativeImage.createEmpty() : icon.resize({ width: traySize, height: traySize }));
  buildTrayMenu();

  petWindow = createPetWindow();
  if (isCalibrateFlag()) createCalibrateWindow();
  startCursorLoop();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  if (cursorTimer) clearInterval(cursorTimer);
});
