# -*- coding: utf-8 -*-
"""经典 PvZ reanim (.compiled) 完整解码器 + XML 对拍验证。

已验证结构（polejaker 对拍）：
  .compiled 外壳: d4feadde + u32(解压长) + zlib
  内层头 0x20 字节: magic c0b493b3 | u32@4 | u32@8=轨道数 | f32@c=fps | u32@10 | u32@14
  轨道表 @0x20: 轨道数 × 3×u32 = [帧数, ?, ?]
  之后逐轨道: 名字(ASCII,以','结尾) + 3 字节 + 帧数据[帧数 × 44B] + 尾部(图片名表等)
  帧记录 44B = 11 个 4B 字段:
     f0..f5 = x, y, kx, ky, sx, sy
     f6     = f   (图像帧索引; -1 = 沿用)
     f7     = a   (alpha)
     f8,f9,f10 = 未知(多为 0; 疑与图片名表索引相关)
  未设置字段 = 哨兵 -10000.0f
"""
import os, re, struct, zlib, sys, json

SENT = -10000.0
REC = 44

def unwrap(path):
    b = open(path, "rb").read()
    if b[:4] == b"\xd4\xfe\xad\xde":
        n = struct.unpack_from("<I", b, 4)[0]
        raw = zlib.decompress(b[8:])
        assert len(raw) == n, (len(raw), n)
        return raw
    return b

TRAILER_KEYS = ("MAGIC", "f0", "f1", "f2")

def decode(path, verbose=False):
    raw = unwrap(path)
    magic = raw[:4]
    v4 = struct.unpack_from("<I", raw, 4)[0]
    ntracks = struct.unpack_from("<I", raw, 8)[0]
    fps = struct.unpack_from("<f", raw, 0xC)[0]
    v10 = struct.unpack_from("<I", raw, 0x10)[0]
    v14 = struct.unpack_from("<I", raw, 0x14)[0]
    TABLE0 = 0x1C          # 已验证（polejaker）：头 28B，轨道表紧随其后
    table = [struct.unpack_from("<3I", raw, TABLE0 + 12 * i) for i in range(ntracks)]
    out = {"magic": magic.hex(), "v4": v4, "ntracks": ntracks, "fps": fps,
           "v10": v10, "v14": v14, "table": table, "tracks": []}
    body = raw[TABLE0 + 12 * ntracks:]
    base = TABLE0 + 12 * ntracks
    # sequential parse: name then 3 bytes then frames*44
    pos = 0
    for ti in range(ntracks):
        m = re.match(rb"[ -~]+?,", body[pos:pos + 128])
        if not m:
            # fallback: search
            m = re.match(rb"[ -~]+?,", body[pos:])
            if not m:
                out["tracks"].append({"error": "name@%d" % pos})
                break
        name = m.group()[:-1].decode()
        n = m.end()
        nframes = table[ti][1]        # 帧数在轨道表条目的第 2 个 u32
        fstart = pos + n + 3
        fend = fstart + nframes * REC
        frames = []
        for j in range(nframes):
            o = fstart + j * REC
            v = list(struct.unpack_from("<11f", body, o))
            frames.append(v)
        # trailer = until next name (or end)
        nm = re.search(rb"[ -~]+?,", body[fend:fend + 4096])
        tend = fend + (nm.start() if nm else 0)
        trailer = body[fend:tend]
        out["tracks"].append({
            "index": ti, "name": name, "nframes": nframes,
            "name_off": base + pos, "data_off": base + fstart,
            "trailer_len": len(trailer),
            "imgnames": [s.decode() for s in re.findall(rb"IMAGE_[A-Z0-9_]+", trailer)],
            "tail3": list(body[pos + n:pos + n + 3]),
            "tail32": struct.unpack_from("<3f", body, fend - 12) if trailer else None,
        })
        pos = tend
    return out


def parse_xml(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    fps = float(re.search(r"<fps>([\d.]+)</fps>", s).group(1))
    tracks = {}
    for tm in re.finditer(r"<track>(.*?)</track>", s, re.S):
        body = tm.group(1)
        name = re.search(r"<name>(.*?)</name>", body).group(1)
        frames = []
        for f in re.finditer(r"<t>(.*?)</t>", body, re.S):
            frames.append({k: float(v) for k, v in re.findall(r"<(\w+)>(-?[\d.eE+]+)</\1>", f.group(1))})
        tracks[name] = frames
    return fps, tracks


if __name__ == "__main__":
    BASE = r"D:\zzz\extract_1789988101"
    BIN = os.path.join(BASE, "compiled", "new", "Zombie_polejaker.reanim.compiled")
    XML = os.path.join(BASE, "compiled", "new", "Zombie_polejaker.reanim")
    d = decode(BIN)
    print(f"magic={d['magic']} v4={d['v4']} ntracks={d['ntracks']} fps={d['fps']} v10={d['v10']} v14={d['v14']}")
    for t in d["tracks"]:
        print(f"  [{t['index']:2d}] {t['name']:36s} n={t['nframes']} trailer={t['trailer_len']} imgs={len(t['imgnames'])} tail3={t['tail3']}")
        for im in t["imgnames"]:
            print("        img:", im)

    # ---- 对拍 XML ----
    fps2, xt = parse_xml(XML)
    tmap = {t["name"]: t for t in d["tracks"] if "name" in t}
    order = list(xt.keys())
    print("\n=== 对拍 ===")
    tot = ok = bad = 0
    for name, frames in xt.items():
        t = tmap.get(name)
        if t is None:
            print(f"  {name}: 二进制中缺失")
            continue
        dec = None
        # re-decode this track's frames
        raw = unwrap(BIN)
        o = t["data_off"]
        dec = [list(struct.unpack_from("<11f", raw, o + j * REC)) for j in range(t["nframes"])]
        keys = ("x", "y", "kx", "ky", "sx", "sy", "f", "a")
        for i, f in enumerate(frames):
            if not f:
                continue
            for ki, k in enumerate(keys):
                if k in f:
                    tot += 1
                    got = dec[i][ki]
                    if got == SENT:
                        bad += 1
                        print(f"  !! {name} f{i} {k}: xml={f[k]} bin=SENT")
                    elif abs(got - f[k]) <= max(1e-4, abs(f[k]) * 1e-6) + 1e-9:
                        ok += 1
                    else:
                        bad += 1
                        print(f"  !! {name} f{i} {k}: xml={f[k]} bin={got}")
    print(f"字段对拍: OK={ok} FAIL={bad} total={tot}")
