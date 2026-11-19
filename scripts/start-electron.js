#!/usr/bin/env node
"use strict";

const { spawn } = require("child_process");
const path = require("path");

require("./ensure-electron");

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

const electronPath = require("electron");
const root = path.join(__dirname, "..");
const extra = process.argv.slice(2);
const child = spawn(electronPath, [root, ...extra], {
  stdio: "inherit",
  env,
  windowsHide: false,
});

child.on("exit", (code, signal) => {
  if (signal) process.kill(process.pid, signal);
  process.exit(code ?? 0);
});
