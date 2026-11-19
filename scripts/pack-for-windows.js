#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const ROOT = path.join(__dirname, "..");
const OUT_DIR = path.join(ROOT, "dist", "desktop-cat-pet");
const ZIP = path.join(ROOT, "dist", "desktop-cat-pet-windows.zip");

const FILES = [
  "package.json",
  "package-lock.json",
  "start-windows.bat",
  "build-windows.bat",
  "WINDOWS.txt",
  "electron/main.js",
  "electron/preload.js",
  "renderer/pet.html",
  "renderer/pet.js",
  "renderer/pet.css",
  "renderer/look.js",
  "renderer/calibrate.html",
  "renderer/calibrate.js",
  "renderer/calibrate.css",
  "scripts/start-electron.js",
  "scripts/ensure-electron.js",
  "assets/idle.png",
  "assets/tray-icon.png",
  "assets/icon.png",
  "assets/icon.ico",
  "assets/angle-anchors.json",
];

function copyFile(rel) {
  const src = path.join(ROOT, rel);
  const dest = path.join(OUT_DIR, rel);
  if (!fs.existsSync(src)) {
    console.warn("skip missing", rel);
    return;
  }
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
}

function copyDir(rel) {
  const src = path.join(ROOT, rel);
  if (!fs.existsSync(src)) return;
  for (const name of fs.readdirSync(src)) {
    const from = path.join(src, name);
    if (!fs.statSync(from).isFile()) continue;
    copyFile(path.join(rel, name));
  }
}

function main() {
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });
  for (const rel of FILES) copyFile(rel);
  copyDir("assets/poses");

  if (fs.existsSync(ZIP)) fs.rmSync(ZIP);
  execSync(`ditto -c -k --norsrc --keepParent "${OUT_DIR}" "${ZIP}"`, {
    env: { ...process.env, COPYFILE_DISABLE: "1" },
  });
  console.log("packed", ZIP);
  console.log("also at", OUT_DIR);
}

main();
