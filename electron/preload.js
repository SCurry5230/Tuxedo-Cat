const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("petAPI", {
  isElectron: true,
  onCursor: (cb) => {
    ipcRenderer.on("cursor", (_e, data) => cb(data));
  },
  onLockChanged: (cb) => {
    ipcRenderer.on("lock-changed", (_e, locked) => cb(locked));
  },
  onAnchorsUpdated: (cb) => {
    ipcRenderer.on("anchors-updated", () => cb());
  },
  getAnchors: () => ipcRenderer.invoke("get-anchors"),
  saveAnchors: (data) => ipcRenderer.invoke("save-anchors", data),
  setLocked: (value) => ipcRenderer.invoke("set-locked", value),
  getLocked: () => ipcRenderer.invoke("get-locked"),
  moveWindow: (x, y) => ipcRenderer.send("move-window", { x, y }),
});
