# -*- coding: utf-8 -*-
"""_sq_refmeasure.py —— 量「参考图」里角色的轮廓（用于定头身比）。

分割：从图像**四边**泛洪填充「草坪或黑框」像素（4 邻域），
      填不到的连通块 = 角色。比单纯阈值稳（草坪上的浅色斑点不会被误判成角色）。

判定：
  lawnish(p) = g - max(r,b) > 8      （草坪绿，含浅色斑点）
  darkish(p) = max(r,g,b) < 45       （黑框 / 描边）

用法: python .cache/_sq_refmeasure.py <png> [step]
"""
import sys
from collections import deque

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image  # noqa: E402


def main():
    if len(sys.argv) < 2:
        sys.stdout.write("usage: _sq_refmeasure.py <png> [step=2]\n")
        return 2
    path = sys.argv[1]
    step = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    im = Image.open(path).convert("RGB")
    W, H = im.size
    px = im.load()
    sys.stdout.write("size = %d x %d  step=%d\n" % (W, H, step))

    allowed = bytearray(W * H)
    for y in range(H):
        for x in range(W):
            r, g, b = px[x, y]
            if (g - max(r, b) > 8) or (max(r, g, b) < 45):
                allowed[y * W + x] = 1

    bg = bytearray(W * H)
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            i = y * W + x
            if allowed[i] and not bg[i]:
                bg[i] = 1
                q.append(i)
    for y in range(H):
        for x in (0, W - 1):
            i = y * W + x
            if allowed[i] and not bg[i]:
                bg[i] = 1
                q.append(i)
    while q:
        i = q.popleft()
        y, x = divmod(i, W)
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= nx < W and 0 <= ny < H:
                j = ny * W + nx
                if allowed[j] and not bg[j]:
                    bg[j] = 1
                    q.append(j)

    # 角色 = 非 allowed 且非 bg 的主连通块（取最大的）
    seen = bytearray(W * H)
    best = None
    for y in range(H):
        for x in range(W):
            i = y * W + x
            if allowed[i] or seen[i]:
                continue
            comp = []
            q.append(i)
            seen[i] = 1
            while q:
                k = q.popleft()
                comp.append(k)
                ky, kx = divmod(k, W)
                for nx, ny in ((kx - 1, ky), (kx + 1, ky), (kx, ky - 1), (kx, ky + 1)):
                    if 0 <= nx < W and 0 <= ny < H:
                        j = ny * W + nx
                        if not allowed[j] and not seen[j]:
                            seen[j] = 1
                            q.append(j)
            if best is None or len(comp) > len(best):
                best = comp

    if not best:
        sys.stdout.write("没找到角色连通块\n")
        return 1
    sys.stdout.write("角色像素数 = %d（最大的非背景连通块）\n" % len(best))

    rows = {}
    for k in best:
        y, x = divmod(k, W)
        a, b = rows.get(y, (x, x))
        rows[y] = (min(a, x), max(b, x))
    ys = sorted(rows)
    ya, yb = ys[0], ys[-1]
    X0 = min(rows[y][0] for y in ys)
    X1 = max(rows[y][1] for y in ys)
    sys.stdout.write("角色 y = %d .. %d  (高 %d)\n" % (ya, yb, yb - ya + 1))
    sys.stdout.write("角色 x = %d .. %d  (宽 %d)\n" % (X0, X1, X1 - X0 + 1))
    sys.stdout.write("\n%5s %5s %5s %5s\n" % ("y", "x0", "x1", "w"))
    for y in range(ya, yb + 1, step):
        if y in rows:
            a, b = rows[y]
            sys.stdout.write("%5d %5d %5d %5d\n" % (y, a, b, b - a + 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
