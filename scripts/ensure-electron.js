#!/usr/bin/env node
"use strict";

const { execSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");

const electronDir = path.join(__dirname, "..", "node_modules", "electron");
const dist = path.join(electronDir, "dist");
const framework = path.join(
  dist,
  "Electron.app",
  "Contents",
  "Frameworks",
  "Electron Framework.framework"
);
const pathTxt = path.join(electronDir, "path.txt");
const macBin = "Electron.app/Contents/MacOS/Electron";

function hasRuntime() {
  if (process.platform === "darwin") {
    return fs.existsSync(framework) && fs.existsSync(path.join(dist, macBin));
  }
  return fs.existsSync(path.join(dist, process.platform === "win32" ? "electron.exe" : "electron"));
}

function writePathTxt() {
  const value =
    process.platform === "darwin"
      ? macBin
      : process.platform === "win32"
        ? "electron.exe"
        : "electron";
  fs.writeFileSync(pathTxt, value);
}

function unzipFromCache() {
  const cacheRoot = path.join(os.homedir(), "Library", "Caches", "electron");
  if (!fs.existsSync(cacheRoot)) return false;
  const zips = [];
  for (const dir of fs.readdirSync(cacheRoot)) {
    const folder = path.join(cacheRoot, dir);
    if (!fs.statSync(folder).isDirectory()) continue;
    for (const name of fs.readdirSync(folder)) {
      if (name.endsWith(".zip") && name.includes("electron")) {
        zips.push(path.join(folder, name));
      }
    }
  }
  if (!zips.length) return false;
  zips.sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  fs.rmSync(dist, { recursive: true, force: true });
  fs.mkdirSync(dist, { recursive: true });
  execSync(`unzip -q -o "${zips[0]}" -d "${dist}"`);
  writePathTxt();
  return hasRuntime();
}

function main() {
  if (!fs.existsSync(electronDir)) return;
  if (hasRuntime()) {
    if (!fs.existsSync(pathTxt)) writePathTxt();
    return;
  }
  try {
    execSync("node install.js", { cwd: electronDir, stdio: "inherit" });
  } catch {
    // continue to unzip fallback
  }
  if (hasRuntime()) {
    if (!fs.existsSync(pathTxt)) writePathTxt();
    return;
  }
  if (process.platform === "darwin" && unzipFromCache()) return;
  console.warn("Electron runtime looks incomplete. Try deleting node_modules/electron and running npm install again.");
}

main();
