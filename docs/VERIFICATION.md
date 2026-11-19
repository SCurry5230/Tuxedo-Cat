# 桌宠验证说明

## 素材与抠图

源视频 `assets/source/cat-head-turn-7s.mp4` **没有真实 alpha**，是纯绿幕。透明帧由 `scripts/process_assets.py` 用 HSV 绿幕抠图生成，并对白毛/灰毛做了低饱和度保护与绿色溢色抑制。边缘不是实拍带 alpha 的质量；若白毛被咬掉，应调脚本里的饱和度阈值，而不是加大“绿色就删”。

交付：

- `assets/contactsheet.png`：抽帧总览，格子上的数字是 **frame index**（0 起）
- `assets/extracted-frames/`：视频原帧
- `assets/transparent-frames/`：连续透明 PNG（256×256）
- `assets/spritesheet.png`：运行时 sprite（15 列 × 14 行）
- `assets/idle.png`：正脸 idle（鼠标在猫头上时使用）
- `assets/angle-anchors.json`：ANGLE KEYS / ANGLE ANCHORS

## 方向锚点（不要假设均匀 360°）

约定：**0° = 屏幕正上，顺时针增大**。

- 鼠标在猫头**上方** → 接近 0° → 应抬头
- 鼠标在猫头**右方** → 接近 90° → 应按视频向右转头
- 鼠标在猫头**下方** → 接近 180° → 应低头
- 鼠标在猫头**左方** → 接近 270° → 应按视频向左转头
- 鼠标绕猫头一圈 → 应按 contact sheet / 视频的头部顺序 **连续插值**转一圈，而不是 8 个方向跳帧
- 鼠标落在猫头椭圆内 → 回到 idle 正脸

`angle-anchors.json` 里的 seed 锚点来自 **16 个姿势**（每 22.5° 一个），中间帧用光流插值，运行时再按角度平滑跟随。仍请用校准页确认方向；不要假设均匀 360° 是唯一真相。

### 校准步骤

1. 桌宠运行时：托盘菜单 → **打开校准**，或 `npm run calibrate`
2. 网页：`npm run preview` 后打开 `http://localhost:5173/renderer/calibrate.html`
3. 点击 contact sheet 某一格，看到黄框 = 当前帧
4. 填写该帧对应的鼠标方向角度，点 **写入锚点**
5. 建议至少标定：上 / 右上 / 右 / 右下 / 下 / 左下 / 左 / 左上
6. 右侧小窗：鼠标绕猫头转圈，确认中间帧是插值而不是跳切
7. 调 `cx cy rx ry` 直到绿/黄椭圆罩住猫头（不要罩到胸口）
8. **保存 angle-anchors.json**。Electron 下会直接写文件并让桌宠重载；浏览器模式会下载文件，需手动覆盖 `assets/angle-anchors.json`

相邻锚点之间用帧下标线性插值；越过 360° 时从最后一帧绕回第 0 帧。锚点可以不是均匀角度，也可以不是均匀帧间距。

## 连续转圈验证

1. `npm start`，桌宠出现在屏幕右下角
2. 把鼠标移到猫头上：必须是正脸 idle
3. 鼠标移到猫头正上方（不要压在头上）：抬头，对应 contact sheet 靠前的帧
4. 顺时针绕猫头一圈：头部应按视频顺序丝滑经过右 → 下 → 左 → 回到上
5. 中途不应只出现 8 张图的硬切；相邻帧会混合
6. 若某段转得过快/过慢或方向反了：打开校准，给那一段加锚点或改角度，不要改代码里的 8 方向表（代码里没有 8 方向表）

## 启动方式

在项目根目录：

```bash
npm install
npm start
```

`npm start` 会清掉 `ELECTRON_RUN_AS_NODE` 再拉起真正的 Electron 窗口。如果直接跑 `electron .` 却没有猫、终端报 `app.whenReady` 为 undefined，说明当前环境把 Electron 当成了 Node，请改用 `npm start`。

- 无边框、透明、置顶、默认右下角
- 默认可拖动
- 托盘：**锁定** 后鼠标穿透，可操作下面的窗口；猫头仍跟随全屏鼠标
- 托盘：**解锁** 后可再拖动
- 托盘：**打开校准** / **退出**

网页预览（同一套 `look.js`，不用全局鼠标而用页面鼠标）：

```bash
npm run preview
```

浏览器打开 `http://localhost:5173/` 或 `http://localhost:5173/renderer/pet.html`

## 回退方式

| 问题 | 回退 |
|------|------|
| 方向不准 / 转圈对不齐 | 用校准页改 `assets/angle-anchors.json`，不要重切视频 |
| 抠图吃白毛 | 改 `scripts/process_assets.py` 的饱和度阈值后执行 `npm run process`（需本机有 opencv 环境；本项目开发时用的是旁边 green-screen-cat 的 venv） |
| 透明窗在系统里异常 | 托盘退出；或从终端 Ctrl+C 结束 `npm start` |
| 锁定后点不到猫 | 托盘选 **解锁**。这是预期：锁定 = 鼠标穿透 |
| 想停用桌宠 | 托盘退出，或 Activity Monitor / 任务管理器结束 `Tuxedo Cat Pet` / `Electron` |
| 资源损坏 | 用 `assets/source/cat-head-turn-7s.mp4` 和 `idle-source.png` 重新 `process` |
| Windows 包 | 本机是 Mac，请在 Windows 上执行 `npm run dist:win`。Mac 包：`npm run dist:mac`（未签名，别人打开会有 Gatekeeper 提示） |

## 实现要点

- Electron 透明 `BrowserWindow` + 主进程 `screen.getCursorScreenPoint()` 每 ~16ms 推给渲染进程
- 锁定：`setIgnoreMouseEvents(true, { forward: true })`
- 运行时优先 sprite + 分数帧混合，不使用 8 方向切换
