# -*- coding: utf-8 -*-
"""生成「奶龙僵尸」验收预览图：每个剪辑一行，4 帧采样 + 中文标签 + 接地线。

产物: .cache_nailong/_preview_all_clips.png
"""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, TOOLS)

import nailong_skin as ns   # noqa: E402

CACHE = os.path.join(TOOLS, '.cache_nailong')
OUT = os.path.join(CACHE, '_preview_all_clips.png')

ROWS = [
    ('Idle1', '待机 1', (0, 3, 6, 9)),
    ('Walk1', '行走 1', (0, 3, 6, 9)),
    ('Laugh', '大笑（旧）', (0, 5, 10, 15)),
    ('LaughWalk', '大笑+行走 3s', (0, 6, 12, 18, 24, 30)),
    ('Eat', '啃食', (0, 3, 6, 9)),
    ('Death1', '死亡 1', (0, 5, 11, 17)),
    ('Death2', '死亡 2', (0, 5, 11, 17)),
    ('Swim', '游泳', (0, 3, 6, 9)),
    ('Waterdeath', '水中死亡', (0, 4, 9, 13)),
]

ZOOM = 1.05
BOX = (-96.0, 96.0, -108.0, 72.0)


def font(size):
    for name in ('msyh.ttc', 'simhei.ttf', 'simsun.ttc'):
        p = os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts', name)
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def main():
    model = ns.build()
    fh = font(26)
    fw = font(20)

    tiles = []
    for clip, _label, picks in ROWS:
        s0, _s1 = model['clips'][clip]
        row = [ns._render_one(model, s0 + f, ZOOM, BOX) for f in picks]
        tiles.append((clip, _label, row))

    tw, th = tiles[0][2][0].size
    pad, lab_w, top = 6, 150, 46
    width = lab_w + len(ROWS[0][2]) * (tw + pad) + pad
    height = top + len(tiles) * (th + pad) + pad
    sheet = Image.new('RGBA', (width, height), (16, 17, 20, 255))
    d = ImageDraw.Draw(sheet)

    d.text((pad + 4, 10), '奶龙僵尸 · 自制皮肤全剪辑验收（灰线 = node-local y=45 接地线）',
           font=fh, fill=(238, 238, 242, 255))

    for i, (clip, label, row) in enumerate(tiles):
        y = top + i * (th + pad)
        d.rectangle([pad, y, lab_w - 2, y + th - 1], fill=(26, 28, 34, 255))
        d.text((pad + 10, y + th // 2 - 30), label, font=fh, fill=(255, 232, 150, 255))
        d.text((pad + 10, y + th // 2 + 2), clip, font=fw, fill=(150, 155, 168, 255))
        d.text((pad + 10, y + th // 2 + 26), '共 %d 帧' % (model['clips'][clip][1]
                                                        - model['clips'][clip][0] + 1),
               font=fw, fill=(120, 125, 138, 255))
        for k, t in enumerate(row):
            sheet.alpha_composite(t, (lab_w + k * (tw + pad), y))

    sheet.convert('RGB').save(OUT)
    print('->', OUT, sheet.size)


if __name__ == '__main__':
    main()
