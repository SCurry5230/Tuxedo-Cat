/** Shared look-at math. Angle 0 = up, increases clockwise. */

export function clamp(n, a, b) {
  return Math.max(a, Math.min(b, n));
}

export function angleFromUpClockwise(dx, dy) {
  let deg = (Math.atan2(dx, -dy) * 180) / Math.PI;
  if (deg < 0) deg += 360;
  return deg;
}

export function shortestAngleDelta(from, to) {
  return ((((to - from) % 360) + 540) % 360) - 180;
}

export function lerpAngle(current, target, t) {
  return (current + shortestAngleDelta(current, target) * t + 360) % 360;
}

export function shortestFrameDelta(from, to, n) {
  if (n <= 0) return 0;
  let d = ((to - from) % n + n) % n;
  if (d > n / 2) d -= n;
  return d;
}

export function chaseFrame(current, target, n, maxStep) {
  const d = shortestFrameDelta(current, target, n);
  const step = clamp(d, -maxStep, maxStep);
  return ((current + step) % n + n) % n;
}

export function pointInEllipse(dx, dy, rx, ry) {
  if (rx <= 0 || ry <= 0) return false;
  return (dx * dx) / (rx * rx) + (dy * dy) / (ry * ry) <= 1;
}

export function sortAnchors(anchors) {
  return [...anchors].sort((a, b) => a.angle - b.angle || a.frame - b.frame);
}

/**
 * Map a compass angle to a (possibly fractional) frame index.
 * Interpolates between adjacent ANGLE ANCHORS. Wrap is allowed.
 * Does not assume anchors are evenly spaced in 360°.
 */
export function frameForAngle(angle, anchors, frameCount) {
  const sorted = sortAnchors(anchors);
  if (!sorted.length || frameCount <= 0) return 0;
  if (sorted.length === 1) return sorted[0].frame % frameCount;

  const ang = ((angle % 360) + 360) % 360;

  for (let i = 0; i < sorted.length; i++) {
    const cur = sorted[i];
    const nxt = sorted[(i + 1) % sorted.length];
    const last = i === sorted.length - 1;
    const a0 = cur.angle;
    const a1 = last ? nxt.angle + 360 : nxt.angle;
    const tAng = last && ang < nxt.angle ? ang + 360 : ang;
    if (tAng >= a0 && tAng <= a1) {
      const span = a1 - a0;
      const t = span <= 1e-6 ? 0 : (tAng - a0) / span;
      let f0 = cur.frame;
      let f1 = nxt.frame;
      if (f1 < f0) f1 += frameCount;
      const frame = f0 + t * (f1 - f0);
      return ((frame % frameCount) + frameCount) % frameCount;
    }
  }
  return sorted[0].frame % frameCount;
}

export function spriteRect(frameIndex, cols, frameWidth, frameHeight) {
  const i = Math.floor(frameIndex);
  const col = i % cols;
  const row = Math.floor(i / cols);
  return { sx: col * frameWidth, sy: row * frameHeight, sw: frameWidth, sh: frameHeight };
}
