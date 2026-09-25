# -*- coding: utf-8 -*-
"""_sq_sbs.py —— 把「参考图」与若干候选倍率的渲染图并排拼成一张对照图（按同一高度归一）。

用法: python .cache/_sq_sbs.py <out.png> <ref.png> <ref_box> <H> <img1> <img2> ...
"""
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
from PIL import Image  # noqa: E402


def fit(im, H):
    im = im.crop(im.getbbox())
    w = max(1, int(round(im.size[0] * H / float(im.size[1]))))
    return im.resize((w, H), Image.LANCZOS)


def main():
    out = sys.argv[1]
    ref = Image.open(sys.argv[2]).convert("RGBA")
    x0, y0, x1, y1 = [int(v) for v in sys.argv[3].split(',')]
    H = int(sys.argv[4])
    ref = fit(ref.crop((x0, y0, x1, y1)), H)
    tiles = [("REF", ref)]
    for p in sys.argv[5:]:
        tiles.append((p.split('/')[-1], fit(Image.open(p).convert("RGBA"), H)))
    gap = 12
    W = sum(t.size[0] for _, t in tiles) + gap * (len(tiles) + 1)
    canvas = Image.new("RGBA", (W, H + 2 * gap), (255, 255, 255, 255))
    x = gap
    for name, t in tiles:
        canvas.alpha_composite(t, (x, gap))
        x += t.size[0] + gap
        sys.stdout.write("  %-24s %s\n" % (name, t.size))
    canvas.save(out)
    sys.stdout.write("-> %s %s\n" % (out, canvas.size))
    return 0


if __name__ == "__main__":
    sys.exit(main())
