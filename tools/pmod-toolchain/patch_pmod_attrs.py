# -*- coding: utf-8 -*-
"""
patch_pmod_attrs.py —— 只有一个 .pmod 文件时，直接热补丁包内植物/僵尸数值属性。

.pmod = zip + 根 mod.json。所有数值属性（阳光/射速/血量/冷却/卡类型…）都是包内
.tres / .tscn 文本资源里的「列首 `键 = 值` 行」。本工具只改这些已存在的键，
不增删任何文件 ⇒ mod.json 的 resources 列表天然保持有效。

用法（命令行）:
  查看:
    python patch_pmod_attrs.py <pmod> --list
  常用数值糖:
    python patch_pmod_attrs.py <pmod> --cost 500 --fire-interval 1.0 \\
        --hitpoints 2000 --cost-rise -1 --cooldown 20 --card-type 1
  通用(改任意已存在键, 可用 --file 限定文件):
    python patch_pmod_attrs.py <pmod> --file "*ComponentSet*.tres" --set fireNum=2
  选项:
    --out PATH    写到新路径（默认原地改；原地改默认先备份 <名>.pmod.bak-时间戳）
    --dry-run     只预览不写包
    --no-backup   原地改时不做备份

字段 → 位置（2026-09-25 实测 15 个 pmod 的证据）:
  cost / costRise / costNight / packetCooldown / hitpoints
      → **/Config/TowerDefense*.tres 列首（植物与僵尸同规律）
  fireInterval → 植物: **/Scene/<Key>.tscn 列首; 僵尸: **/Scene/*FireComponentDefinition.tres 列首
  fireNum      → 场景 .tscn 与 ComponentSet .tres 各一处（两处会一起改，保持一致）
  type(卡类型) → **/Cards/*.tres 列首。枚举: NOONE=-1 WHITE=0 GOLD=1 DIAMOND=2
                 COLOUR=3 STAR=4 ORIGINAL=5 ZOMBIE=6 COVER=7 GRAY=8

安全设计:
  * 只改「已存在」的键，绝不新增（新增字段该放哪、类默认值是什么是另一门学问）；
    键不存在 ⇒ 报错并指出搜过哪些范围，退出码 2。
  * 浮点字段强制带小数点（Godot .tres 语法要求）；整数/布尔字段强类型校验。
  * 重打包逐条保留原 entry 顺序 / 压缩方式 / 时间戳 / 属性；zip 注释保留。
  * 写后自校验: 文件名清单与原包逐项一致、未改 entry CRC 一致、改动字段读回复核。
  * 改完建议跑 ModWorkspace/.cache/verify_pmod.py <pmod> 做结构闸门，然后重启游戏（勿删 ModsCache）。
"""
import argparse
import fnmatch
import os
import re
import sys
import time
import zipfile

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 字段注册表
def _is_cfg(n):   # Config .tres（植物/僵尸通用）
    return "/config/" in n.lower() and n.lower().endswith(".tres")

def _is_card(n):  # 卡片 .tres
    return "/cards/" in n.lower() and n.lower().endswith(".tres")

def _is_text(n):  # 任意 .tres/.tscn
    return n.lower().endswith((".tres", ".tscn"))

SUGAR = {
    "cost":           dict(fmt="int",   scope=_is_cfg,  desc="阳光花费"),
    "costRise":       dict(fmt="int",   scope=_is_cfg,  desc="种植涨价(-1=不涨)"),
    "costNight":      dict(fmt="int",   scope=_is_cfg,  desc="夜间价(-1=不用)"),
    "packetCooldown": dict(fmt="float", scope=_is_cfg,  desc="卡片冷却秒"),
    "hitpoints":      dict(fmt="float", scope=_is_cfg,  desc="血量"),
    "fireInterval":   dict(fmt="float", scope=_is_text, desc="射速(秒/轮)"),
    "fireNum":        dict(fmt="int",   scope=_is_text, desc="一次Fire()打几轮"),
    "fireNumAtOnce":  dict(fmt="bool",  scope=_is_text, desc="齐射开关"),
    "type":           dict(fmt="int",   scope=_is_card, desc="卡类型(-1..8)"),
}

# ---------------------------------------------------------------- 值格式化
def fmt_value(fmt, raw):
    s = str(raw).strip()
    if fmt == "int":
        try:
            return str(int(s)), None
        except ValueError:
            return None, "应为整数，得到 %r" % raw
    if fmt == "float":
        try:
            f = float(s)
        except ValueError:
            return None, "应为数字，得到 %r" % raw
        out = ("%.6f" % f).rstrip("0")
        if out.endswith("."):
            out += "0"
        return out, None
    if fmt == "bool":
        low = s.lower()
        if low in ("true", "1", "yes", "on"):
            return "true", None
        if low in ("false", "0", "no", "off"):
            return "false", None
        return None, "应为 true/false，得到 %r" % raw
    return str(raw), None

# ---------------------------------------------------------------- 行级补丁
# 只匹配「列首 key = value」；列首 = 行首无空白，且首字符不是 ; #[ （注释/段头）
LINE_RE = re.compile(r"^(?P<key>[A-Za-z_][A-Za-z0-9_]*)(?P<eq>\s*=\s*)"
                     r"(?P<val>[^;#\n]*?)(?P<trail>[ \t]*)$")

def patch_text(txt, wants):
    """wants: {key: new_token}. 返回 (new_txt, changes) changes=[(key, old, new)]"""
    changes = []
    lines = txt.splitlines(keepends=True)
    out = []
    for line in lines:
        body = line.rstrip("\r\n")
        eol = line[len(body):]
        new_body = body
        if body and body[0] not in " \t;#[":
            m = LINE_RE.match(body)
            if m and m.group("key") in wants:
                k = m.group("key")
                old = m.group("val").strip()
                new = wants[k]
                if old != new:
                    new_body = k + m.group("eq") + new + m.group("trail")
                    changes.append((k, old, new))
        out.append(new_body + eol)
    return "".join(out), changes

# ---------------------------------------------------------------- 包级操作
def iter_targets(znames, scope):
    for n in znames:
        if scope is None or scope(n):
            yield n

def read_entry(z, n):
    return z.read(n)

def collect_plan(z, wants_by_scope):
    """wants_by_scope: [(scope_or_None, {key: token})] → {entry: {key: token}}"""
    plan = {}
    names = z.namelist()
    for scope, wants in wants_by_scope:
        for n in iter_targets(names, scope):
            low = n.lower()
            if not low.endswith((".tres", ".tscn")):
                continue
            try:
                txt = z.read(n).decode("utf-8")
            except UnicodeDecodeError:
                continue
            found = {}
            for line in txt.splitlines():
                if not line or line[0] in " \t;#[":
                    continue
                m = LINE_RE.match(line.rstrip("\r\n"))
                if m and m.group("key") in wants:
                    found[m.group("key")] = wants[m.group("key")]
            if found:
                # ★ 同一文件可能命中多个 (scope, wants) 组合（如 cost+hitpoints 同在 Config）
                #   必须合并而不是覆盖 —— 覆盖会静默丢掉先前的键（dry-run 实测抓到过）。
                plan.setdefault(n, {}).update(found)
    return plan

def find_missing(z, wants_by_scope):
    """返回 [(key, scope名)]：注册表里请求了、但全包（对应 scope 内）根本没出现的键"""
    missing = []
    names = z.namelist()
    for scope, wants in wants_by_scope:
        scope_names = list(iter_targets(names, scope))
        for k in wants:
            hit = False
            for n in scope_names:
                if not n.lower().endswith((".tres", ".tscn")):
                    continue
                try:
                    txt = z.read(n).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                for line in txt.splitlines():
                    if line and line[0] not in " \t;#[":
                        m = LINE_RE.match(line.rstrip("\r\n"))
                        if m and m.group("key") == k:
                            hit = True
                            break
                if hit:
                    break
            if not hit:
                missing.append(k)
    return missing

def repack(src_path, dst_path, patched_bytes):
    """逐条保留原 entry 元数据重打包；patched_bytes: {name: bytes}"""
    with zipfile.ZipFile(src_path) as zin:
        comment = zin.comment
        infos = zin.infolist()
        data = {i.filename: zin.read(i.filename) for i in infos}
    for k, v in patched_bytes.items():
        data[k] = v
    tmp = dst_path + ".tmp-pmod"
    try:
        with zipfile.ZipFile(tmp, "w") as zout:
            zout.comment = comment
            for i in infos:
                zi = zipfile.ZipInfo(i.filename, date_time=i.date_time)
                zi.compress_type = i.compress_type
                zi.external_attr = i.external_attr
                zi.internal_attr = i.internal_attr
                zi.create_system = i.create_system
                zout.writestr(zi, data[i.filename])
        os.replace(tmp, dst_path)
    except BaseException:
        try:
            os.remove(tmp)   # 失败不留孤儿临时文件
        except OSError:
            pass
        raise

def verify_repack(src_path, dst_path, patched_names):
    """文件清单一致 + 未改 entry CRC 一致 + 改动 entry 可读"""
    with zipfile.ZipFile(src_path) as za, zipfile.ZipFile(dst_path) as zb:
        na, nb = za.namelist(), zb.namelist()
        if na != nb:
            return "文件清单不一致: 原 %d 项 → 新 %d 项" % (len(na), len(nb))
        for n in na:
            ca, cb = za.getinfo(n).CRC, zb.getinfo(n).CRC
            if n in patched_names:
                continue
            if ca != cb:
                return "未改动 entry CRC 变了: %s" % n
    return None

def backup_path(p):
    base = p + ".bak-" + time.strftime("%Y%m%d-%H%M%S")
    cand, k = base, 1
    while os.path.exists(cand):
        cand = "%s.bak-%s-%d" % (p, time.strftime("%Y%m%d-%H%M%S"), k)
        k += 1
    return cand

# ---------------------------------------------------------------- 主流程
def main(argv):
    ap = argparse.ArgumentParser(add_help=True, description="pmod 数值属性热补丁")
    ap.add_argument("pmod")
    ap.add_argument("--list", action="store_true", help="只列出各字段当前值与位置")
    ap.add_argument("--cost");        ap.add_argument("--cost-rise", dest="costRise")
    ap.add_argument("--cost-night", dest="costNight")
    ap.add_argument("--cooldown");    ap.add_argument("--hitpoints")
    ap.add_argument("--fire-interval", dest="fireInterval")
    ap.add_argument("--fire-num", dest="fireNum")
    ap.add_argument("--card-type", dest="type")
    ap.add_argument("--set", action="append", default=[],
                    help="键=值（任意已存在键；.tres/.tscn 列首属性）")
    ap.add_argument("--file", help="把 --set 限定到匹配的包内文件（fnmatch，大小写不敏感）")
    ap.add_argument("--out", help="写到新路径（默认原地改）")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args(argv)

    if not os.path.isfile(args.pmod):
        print("[ERR] 找不到文件: %s" % args.pmod); return 2

    # ---- 组装请求
    wants_by_scope = []   # [(scope, {key: token})]
    errors = []
    for key, raw in (("cost", args.cost), ("costRise", args.costRise),
                     ("costNight", args.costNight), ("packetCooldown", args.cooldown),
                     ("hitpoints", args.hitpoints), ("fireInterval", args.fireInterval),
                     ("fireNum", args.fireNum), ("type", args.type)):
        if raw is None:
            continue
        reg = SUGAR[key]
        tok, err = fmt_value(reg["fmt"], raw)
        if err:
            errors.append("--%s: %s" % (key, err))
        else:
            wants_by_scope.append((reg["scope"], {key: tok}))
    if args.set:
        manual = {}
        for item in args.set:
            if "=" not in item:
                errors.append("--set 需要 键=值 形式: %r" % item); continue
            k, v = item.split("=", 1)
            k = k.strip()
            if k in SUGAR:
                tok, err = fmt_value(SUGAR[k]["fmt"], v)
            else:
                tok = v.strip()   # 未知键不强校验类型（糖以外的键交给用户负责）
            if err:
                errors.append("--set %s: %s" % (k, err))
            else:
                manual[k] = tok
        if manual:
            scope = (lambda n, g=(args.file or "*"): fnmatch.fnmatch(n.lower(), g.lower())) \
                    if args.file else _is_text
            wants_by_scope.append((scope, manual))
    if errors:
        for e in errors:
            print("[ERR] %s" % e)
        return 2
    if args.list:
        pass  # list 模式不带改动请求也能跑
    elif not wants_by_scope:
        print("[ERR] 没有给出任何要改的键。用 --cost/--fire-interval/... 或 --set 键=值；"
              "先 --list 看现状。"); return 2

    # ---- 打开包
    try:
        z = zipfile.ZipFile(args.pmod)
    except Exception as e:
        print("[ERR] 不是有效的 zip/pmod: %s" % e); return 2
    names = z.namelist()
    print("包: %s (%d bytes, %d entries)" % (args.pmod, os.path.getsize(args.pmod), len(names)))

    # ---- --list：现状
    if args.list:
        print("\n── 各字段现状（列首属性） ──")
        for key, reg in SUGAR.items():
            hits = []
            for n in iter_targets(names, reg["scope"]):
                if not n.lower().endswith((".tres", ".tscn")):
                    continue
                try:
                    txt = z.read(n).decode("utf-8")
                except UnicodeDecodeError:
                    continue
                for i, line in enumerate(txt.splitlines(), 1):
                    if line and line[0] not in " \t;#[":
                        m = LINE_RE.match(line.rstrip("\r\n"))
                        if m and m.group("key") == key:
                            hits.append((n, i, m.group("val").strip()))
            if hits:
                for n, i, v in hits:
                    print("  %-14s = %-10s   %s  L%d" % (key, v, n, i))
            else:
                print("  %-14s (包内不存在)" % key)
        return 0

    # ---- 键存在性预检（只改已存在键）
    missing = find_missing(z, wants_by_scope)
    if missing:
        print("[ERR] 以下键在包内（对应范围）不存在，本工具不新增字段: %s" % ", ".join(missing))
        print("      若确需新增，请走生成器或手工编辑对应 .tres（注意类默认值与字段顺序）。")
        return 2

    # ---- 生成补丁计划
    plan = collect_plan(z, wants_by_scope)
    if not plan:
        print("[WARN] 没有任何文件需要改动（可能值本来就相同）。")
        return 3
    patched = {}
    total_changes = 0
    print("\n── 补丁计划 ──")
    for n in sorted(plan):
        try:
            txt = z.read(n).decode("utf-8")
        except UnicodeDecodeError:
            print("[ERR] %s 无法按 UTF-8 解码，跳过" % n); continue
        new_txt, chs = patch_text(txt, plan[n])
        if chs:
            patched[n] = new_txt.encode("utf-8")
            for k, old, new in chs:
                print("  %s\n      %s: %s  →  %s" % (n, k, old, new))
                total_changes += 1
    if not patched:
        print("[WARN] 所有键的值本来就相同，无需改动。")
        return 3
    print("共 %d 处改动，涉及 %d 个文件。文件集合不变 ⇒ mod.json 无需改动。" %
          (total_changes, len(patched)))
    if args.dry_run:
        print("\n[dry-run] 未写盘。去掉 --dry-run 执行。")
        return 0

    # ---- 写盘（原地 → 先备份；--out → 新路径）
    z.close()   # ★ Windows 原地替换前必须释放原包句柄，否则 os.replace 报 WinError 5
    dst = args.out or args.pmod
    if args.out:
        d = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(d, exist_ok=True)
    elif not args.no_backup:
        bak = backup_path(args.pmod)
        with open(args.pmod, "rb") as fi, open(bak, "wb") as fo:
            fo.write(fi.read())
        print("已备份原包 → %s" % bak)
    repack(args.pmod, dst, patched)
    err = verify_repack(args.pmod, dst, set(patched))
    if err:
        print("[ERR] 写后校验失败: %s" % err); return 2

    # ---- 读回复核
    ok = True
    with zipfile.ZipFile(dst) as zc:
        for n in patched:
            txt = zc.read(n).decode("utf-8")
            for line in txt.splitlines():
                if line and line[0] not in " \t;#[":
                    m = LINE_RE.match(line.rstrip("\r\n"))
                    if m and m.group("key") in plan[n]:
                        want = plan[n][m.group("key")]
                        if m.group("val").strip() != want:
                            print("[ERR] 读回不符 %s: %s 应为 %s" % (n, m.group("key"), want))
                            ok = False
    if not ok:
        return 2
    print("\n[OK] 已写入 %s（%d bytes）" % (dst, os.path.getsize(dst)))
    print("     下一步: 结构闸门 verify_pmod.py；然后重启游戏（勿删 ModsCache）读数验收。")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
