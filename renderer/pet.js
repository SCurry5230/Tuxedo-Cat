import {
  angleFromUpClockwise,
  clamp,
  frameForAngle,
  pointInEllipse,
  shortestAngleDelta,
  spriteRect,
} from "./look.js";

const canvas = document.getElementById("pet");
const ctx = canvas.getContext("2d", { alpha: true });
const hint = document.getElementById("hint");
const api = window.petAPI;
const isElectron = Boolean(api?.isElectron);
const isPreview = !isElectron || new URLSearchParams(location.search).has("preview");

if (isPreview && !isElectron) {
  document.body.classList.add("preview");
  hint.hidden = false;
}

const SIZE = 320;
let config = null;
let idleImg = new Image();
let sheetImg = null;
let poseImgs = [];
let locked = false;
let dragging = false;
let dragOffX = 0;
let dragOffY = 0;
let mouseScreen = { x: 0, y: 0 };
let winBounds = { x: 0, y: 0, w: SIZE, h: SIZE };
let idling = true;
let idleInsideFor = 0;
let currentAngle = 0;
let targetAngle = 0;
let hasAngle = false;
let lastTs = 0;

function assetUrl(rel) {
  const v = config?.version ?? 10;
  return `${new URL(`../${rel}`, import.meta.url).href}?v=${v}`;
}

function setupCanvas() {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = Math.round(SIZE * dpr);
  canvas.height = Math.round(SIZE * dpr);
  canvas.style.width = `${SIZE}px`;
  canvas.style.height = `${SIZE}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.imageSmoothingEnabled = true;
  ctx.imageSmoothingQuality = "high";
}

async function loadConfig() {
  if (api?.getAnchors) {
    config = await api.getAnchors();
    return;
  }
  const res = await fetch("../assets/angle-anchors.json");
  config = await res.json();
}

function loadImage(img, rel) {
  return new Promise((resolve, reject) => {
    img.onload = () => resolve(img);
    img.onerror = reject;
    img.src = assetUrl(rel);
  });
}

function localMouse() {
  if (isElectron && !isPreview) {
    return { x: mouseScreen.x - winBounds.x, y: mouseScreen.y - winBounds.y };
  }
  return { x: mouseScreen.x, y: mouseScreen.y };
}

function wrap360(a) {
  return ((a % 360) + 360) % 360;
}

function poseCount() {
  return poseImgs.length || config?.poseCount || 32;
}

function poseIndex(angle) {
  const n = poseCount();
  const seg = 360 / n;
  return Math.floor((wrap360(angle) + seg / 2) / seg) % n;
}

function drawCurrentPose() {
  if (sheetImg && sheetImg.complete && config.spritesheet) {
    const n = config.frameCount || config.spritesheet.cols * config.spritesheet.rows;
    const f = config.anchors?.length
      ? frameForAngle(currentAngle, config.anchors, n)
      : (wrap360(currentAngle) / 360) * n;
    const idx = Math.round(f) % n;
    const { cols, frameWidth, frameHeight } = config.spritesheet;
    const { sx, sy, sw, sh } = spriteRect(idx, cols, frameWidth, frameHeight);
    ctx.drawImage(sheetImg, sx, sy, sw, sh, 0, 0, SIZE, SIZE);
    return;
  }
  const i = poseIndex(currentAngle);
  const tex = poseImgs[i];
  if (tex && tex.complete) ctx.drawImage(tex, 0, 0, SIZE, SIZE);
}

function tick(ts) {
  if (!config) {
    requestAnimationFrame(tick);
    return;
  }
  const dt = lastTs ? Math.min(0.05, (ts - lastTs) / 1000) : 1 / 60;
  lastTs = ts;
  const m = localMouse();
  const hx = (config.head?.cx ?? 0.5) * SIZE;
  const hy = (config.head?.cy ?? 0.28) * SIZE;
  const rx = (config.head?.rx ?? 0.2) * SIZE;
  const ry = (config.head?.ry ?? 0.16) * SIZE;
  const dx = m.x - hx;
  const dy = m.y - hy;
  const dist = Math.hypot(dx, dy);

  if (dist >= 8) {
    targetAngle = angleFromUpClockwise(dx, dy);
    if (!hasAngle) {
      currentAngle = targetAngle;
      hasAngle = true;
    }
  }

  const wasIdling = idling;
  const insideIdle = pointInEllipse(dx, dy, rx * 0.7, ry * 0.7);
  const outsideIdle = !pointInEllipse(dx, dy, rx * 1.25, ry * 1.25);
  if (insideIdle) {
    idleInsideFor += dt;
    if (idleInsideFor > 0.12) idling = true;
  } else {
    idleInsideFor = 0;
    if (outsideIdle) idling = false;
  }

  if (idling) {
    if (hasAngle && dist >= 8) currentAngle = targetAngle;
  } else if (wasIdling && hasAngle) {
    currentAngle = targetAngle;
  } else if (hasAngle) {
    const follow = config.motion?.follow ?? 18;
    const maxDegPerSec = config.motion?.maxDegPerSec ?? 720;
    const diff = shortestAngleDelta(currentAngle, targetAngle);
    const alpha = 1 - Math.exp(-follow * dt);
    const maxStep = maxDegPerSec * dt;
    currentAngle = wrap360(currentAngle + clamp(diff * alpha, -maxStep, maxStep));
  }

  ctx.clearRect(0, 0, SIZE, SIZE);
  ctx.globalAlpha = 1;
  if (idling && idleImg.complete) {
    ctx.drawImage(idleImg, 0, 0, SIZE, SIZE);
  } else {
    drawCurrentPose();
  }
  requestAnimationFrame(tick);
}

function onBrowserMouse(e) {
  const rect = canvas.getBoundingClientRect();
  mouseScreen = { x: e.clientX - rect.left, y: e.clientY - rect.top };
}

canvas.addEventListener("mousedown", (e) => {
  if (locked) return;
  dragging = true;
  canvas.classList.add("dragging");
  if (isElectron && api) {
    dragOffX = e.clientX;
    dragOffY = e.clientY;
  } else {
    dragOffX = e.clientX - mouseScreen.x;
    dragOffY = e.clientY - mouseScreen.y;
  }
  e.preventDefault();
});

window.addEventListener("mousemove", (e) => {
  if (!isElectron) onBrowserMouse(e);
  if (!dragging || locked) return;
  if (isElectron && api) api.moveWindow(mouseScreen.x - dragOffX, mouseScreen.y - dragOffY);
});

window.addEventListener("mouseup", () => {
  dragging = false;
  canvas.classList.remove("dragging");
});

async function loadAssets() {
  const jobs = [loadImage(idleImg, config.idle)];
  if (config.spritesheet?.url) {
    sheetImg = new Image();
    poseImgs = [];
    jobs.push(loadImage(sheetImg, config.spritesheet.url));
  } else {
    sheetImg = null;
    const poseList = config.poses || config.heads || [];
    poseImgs = poseList.map(() => new Image());
    for (let i = 0; i < poseList.length; i++) {
      jobs.push(loadImage(poseImgs[i], poseList[i]));
    }
  }
  await Promise.all(jobs);
}

async function boot() {
  setupCanvas();
  await loadConfig();
  await loadAssets();
  if (api) {
    api.onCursor((c) => {
      mouseScreen = { x: c.x, y: c.y };
      winBounds = { x: c.wx, y: c.wy, w: c.ww, h: c.wh };
    });
    api.onLockChanged((v) => {
      locked = v;
    });
    api.onAnchorsUpdated(async () => {
      await loadConfig();
      await loadAssets();
    });
    locked = await api.getLocked();
  } else {
    const rect = canvas.getBoundingClientRect();
    mouseScreen = { x: rect.width / 2, y: rect.height / 2 };
  }
  requestAnimationFrame(tick);
}

boot().catch((err) => console.error(err));
