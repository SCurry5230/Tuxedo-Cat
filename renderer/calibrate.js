import {
  angleFromUpClockwise,
  clamp,
  frameForAngle,
  pointInEllipse,
  sortAnchors,
  spriteRect,
} from "./look.js";

const PREVIEW = 240;

const sheetCanvas = document.getElementById("sheet");
const preview = document.getElementById("preview");
const pctx = preview.getContext("2d");
const list = document.getElementById("list");
const status = document.getElementById("status");
const api = window.petAPI;

const fields = {
  frame: document.getElementById("frame"),
  angle: document.getElementById("angle"),
  label: document.getElementById("label"),
  cx: document.getElementById("cx"),
  cy: document.getElementById("cy"),
  rx: document.getElementById("rx"),
  ry: document.getElementById("ry"),
};

let config = null;
let contact = new Image();
let sprite = new Image();
let idleImg = new Image();
let selectedFrame = 0;
let mouse = { x: PREVIEW / 2, y: PREVIEW * 0.12 };

function layout() {
  const cols = config.spritesheet.cols;
  const rows = config.spritesheet.rows;
  const thumb = config.contactSheet?.thumb || 64;
  const labelH = config.contactSheet?.labelH || 18;
  return { cols, rows, thumb, labelH, cellW: thumb, cellH: thumb + labelH };
}

function assetUrl(rel) {
  return new URL(`../${rel}`, import.meta.url).href;
}

async function loadConfig() {
  if (api?.getAnchors) {
    config = await api.getAnchors();
    return;
  }
  const res = await fetch("../assets/angle-anchors.json");
  config = await res.json();
}

function syncHeadFields() {
  fields.cx.value = config.head.cx;
  fields.cy.value = config.head.cy;
  fields.rx.value = config.head.rx;
  fields.ry.value = config.head.ry;
}

function readHeadFields() {
  config.head.cx = Number(fields.cx.value);
  config.head.cy = Number(fields.cy.value);
  config.head.rx = Number(fields.rx.value);
  config.head.ry = Number(fields.ry.value);
}

function drawSheet() {
  const { cols, rows, thumb, cellW, cellH } = layout();
  const w = cols * cellW;
  const h = rows * cellH;
  sheetCanvas.width = w;
  sheetCanvas.height = h;
  const ctx = sheetCanvas.getContext("2d");
  ctx.drawImage(contact, 0, 0, w, h);
  const anchorFrames = new Set(config.anchors.map((a) => a.frame));
  for (let i = 0; i < config.frameCount; i++) {
    const r = Math.floor(i / cols);
    const c = i % cols;
    const x = c * cellW;
    const y = r * cellH;
    if (anchorFrames.has(i)) {
      ctx.strokeStyle = "#5b9cff";
      ctx.lineWidth = 2;
      ctx.strokeRect(x + 1, y + 1, thumb - 2, thumb - 2);
    }
    if (i === selectedFrame) {
      ctx.strokeStyle = "#ffd166";
      ctx.lineWidth = 3;
      ctx.strokeRect(x + 2, y + 2, thumb - 4, thumb - 4);
    }
  }
}

function renderList() {
  const sorted = sortAnchors(config.anchors);
  list.innerHTML = "";
  for (const a of sorted) {
    const li = document.createElement("li");
    li.textContent = `frame ${a.frame} → ${a.angle}° ${a.label || ""}`;
    if (a.frame === selectedFrame) li.classList.add("active");
    li.addEventListener("click", () => {
      selectedFrame = a.frame;
      fields.frame.value = a.frame;
      fields.angle.value = a.angle;
      fields.label.value = a.label || "";
      drawSheet();
      renderList();
    });
    list.appendChild(li);
  }
}

function drawPreview() {
  if (!config || !sprite.complete) return;
  readHeadFields();
  const { cols, frameWidth, frameHeight } = config.spritesheet;
  const hx = config.head.cx * PREVIEW;
  const hy = config.head.cy * PREVIEW;
  const rx = config.head.rx * PREVIEW;
  const ry = config.head.ry * PREVIEW;
  const dx = mouse.x - hx;
  const dy = mouse.y - hy;
  const onHead = pointInEllipse(dx, dy, rx, ry);
  pctx.clearRect(0, 0, PREVIEW, PREVIEW);
  pctx.fillStyle = "#1b2230";
  pctx.fillRect(0, 0, PREVIEW, PREVIEW);

  if (onHead && idleImg.complete) {
    pctx.drawImage(idleImg, 0, 0, PREVIEW, PREVIEW);
  } else {
    const frac = frameForAngle(
      angleFromUpClockwise(dx, dy),
      config.anchors,
      config.frameCount
    );
    const f0 = Math.floor(frac) % config.frameCount;
    const f1 = (f0 + 1) % config.frameCount;
    const t = frac - Math.floor(frac);
    const r0 = spriteRect(f0, cols, frameWidth, frameHeight);
    const r1 = spriteRect(f1, cols, frameWidth, frameHeight);
    pctx.globalAlpha = 1;
    pctx.drawImage(sprite, r0.sx, r0.sy, r0.sw, r0.sh, 0, 0, PREVIEW, PREVIEW);
    if (t > 0.02) {
      pctx.globalAlpha = t;
      pctx.drawImage(sprite, r1.sx, r1.sy, r1.sw, r1.sh, 0, 0, PREVIEW, PREVIEW);
      pctx.globalAlpha = 1;
    }
  }

  pctx.strokeStyle = onHead ? "#7dffa3" : "#ffd166";
  pctx.lineWidth = 1.5;
  pctx.beginPath();
  pctx.ellipse(hx, hy, rx, ry, 0, 0, Math.PI * 2);
  pctx.stroke();
}

sheetCanvas.addEventListener("click", (e) => {
  const rect = sheetCanvas.getBoundingClientRect();
  const scaleX = sheetCanvas.width / rect.width;
  const scaleY = sheetCanvas.height / rect.height;
  const x = (e.clientX - rect.left) * scaleX;
  const y = (e.clientY - rect.top) * scaleY;
  const { cols, rows, cellW, cellH } = layout();
  const c = clamp(Math.floor(x / cellW), 0, cols - 1);
  const r = clamp(Math.floor(y / cellH), 0, rows - 1);
  const frame = r * cols + c;
  if (frame >= config.frameCount) return;
  selectedFrame = frame;
  fields.frame.value = frame;
  const existing = config.anchors.find((a) => a.frame === frame);
  if (existing) {
    fields.angle.value = existing.angle;
    fields.label.value = existing.label || "";
  }
  drawSheet();
  renderList();
});

document.getElementById("add").addEventListener("click", () => {
  const frame = Number(fields.frame.value);
  const angle = ((Number(fields.angle.value) % 360) + 360) % 360;
  const label = fields.label.value.trim();
  const rest = config.anchors.filter((a) => a.frame !== frame);
  rest.push({ frame, angle, label });
  config.anchors = sortAnchors(rest);
  selectedFrame = frame;
  drawSheet();
  renderList();
  status.textContent = `已写入 frame ${frame} → ${angle}°（尚未保存到磁盘）`;
});

document.getElementById("del").addEventListener("click", () => {
  const frame = Number(fields.frame.value);
  config.anchors = config.anchors.filter((a) => a.frame !== frame);
  drawSheet();
  renderList();
  status.textContent = `已删除 frame ${frame} 的锚点`;
});

document.getElementById("save").addEventListener("click", async () => {
  readHeadFields();
  config.anchors = sortAnchors(config.anchors);
  if (api?.saveAnchors) {
    await api.saveAnchors(config);
    status.textContent = "已写入 assets/angle-anchors.json，桌宠会自动重载。";
    return;
  }
  const blob = new Blob([JSON.stringify(config, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "angle-anchors.json";
  a.click();
  status.textContent = "浏览器模式已下载 JSON，请放到 assets/angle-anchors.json。";
});

preview.addEventListener("mousemove", (e) => {
  const rect = preview.getBoundingClientRect();
  mouse = { x: e.clientX - rect.left, y: e.clientY - rect.top };
});

["cx", "cy", "rx", "ry"].forEach((id) => {
  fields[id].addEventListener("input", drawPreview);
});

function loop() {
  drawPreview();
  requestAnimationFrame(loop);
}

async function boot() {
  await loadConfig();
  syncHeadFields();
  fields.frame.value = 0;
  fields.angle.value = 0;
  fields.label.value = "up";
  selectedFrame = 0;
  await Promise.all([
    new Promise((res, rej) => {
      contact.onload = res;
      contact.onerror = rej;
      contact.src = assetUrl("assets/contactsheet.png");
    }),
    new Promise((res, rej) => {
      sprite.onload = res;
      sprite.onerror = rej;
      sprite.src = assetUrl(config.spritesheet.url);
    }),
    new Promise((res, rej) => {
      idleImg.onload = res;
      idleImg.onerror = rej;
      idleImg.src = assetUrl(config.idle);
    }),
  ]);
  drawSheet();
  renderList();
  loop();
}

boot().catch((err) => {
  status.textContent = String(err);
  console.error(err);
});
