"""《超级机枪射手》的 ModLoader 闸门静态复刻校验。

为什么要写这个：游戏侧「加载失败」不一定是脚本/逻辑问题，而是 ModLoader 的**静态闸门**
（路径推断 / manifest 声明 / 跨资源引用一致性）判不过 → 整包 apply 被拒。
本脚本不复刻整套代码，只把「会导致整包被拒」的判定逐条搬成 Python，离线跑。

对应的真实实现（V0.28 解包 addons/ModEditor/ModSystem/）：
  - ModLoader.TryInferCharacterScene()        → 6 段路径 + 文件名==目录名==<Key>
  - ModLoader.InferRuntimeEntry()             → 类别/键推断（含 17 条 .tres 前缀表）
  - ModLoader.IsCharacterPackageDependency()  → Resources/Characters/<类>/(>=5 段) 是包依赖
  - ModLoader.ApplyMod() / ValidateManifestRegistrations()
        · provides 里每个 key 都必须真的注册（否则整包失败）
        · 「资源未被 manifest 明确声明」→ 该资源被静默跳过
  - ModLoader.SanitizeCharacterTextResource()
        · 包内 .tres 的 Script 引用非 res:// → 直接拒绝整包
        · 包内出现 .scn/.res 二进制依赖 → 直接拒绝整包
        · 包内 .tscn 的 Script 引用非 res:// → 该脚本被剥离（不致命，但要记录）
  - ModLoader.TryGetGodotResourcePath()       → 包内文件映射为 user://ModsCache/<名>/…
        ⇒ .tscn/.tres 里的**相对引用**在包内解析；res:// 在游戏 pck 根解析
        ⇒ 因此 res://Resources/… 必然失败（游戏 pck 根没有 Resources/ 目录）
  - XWModContentValidation.Validate()
        · Packet.saveKey 必须 == 注册键（卡片文件名去扩展）
        · Packet.characterConfig.name 必须注册在 TOWERDEFENSE_CHARCATERS
        · CHARCTAER_SPRITE 必须有 saveKey（或 characterConfig.name）这一项
        · Packet.unlockCheckList 只允许空 或 XWModModProgressUnlockCondition

用法：python check_modloader_gates.py
输出：ok=/warn=/FAIL= 汇总，FAIL>0 时退出码 1。
"""

import io
import json
import os
import posixpath
import re
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WS = os.path.dirname(HERE)
MOD_ROOT = os.path.join(WS, "SuperGatlingPea")
PMOD = os.path.join(WS, "dist", "超级机枪射手.pmod")
GAME = r"D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28"

KEYS = {"Character": "SuperGatlingPea", "CharacterSprite": "SuperGatlingPea", "Packet": "SuperGatlingPea"}
CATEGORIES = {"Plants", "Zombies", "Props", "Vases", "Mowers", "Items", "Graves", "Craters"}

PREFIX_TABLE = [
    ("Battle/Features/", "Feature"),
    ("Battle/Processes/", "Process"),
    ("Resources/LevelCatalogs/", "Level"),
    ("Resources/Maps/", "Map"),
    ("Resources/Cards/", "Packet"),
    ("Resources/PacketBank/", "PacketBank"),
    ("Resources/Projectiles/", "Projectile"),
    ("Resources/ProjectileChanges/", "ProjectileChange"),
    ("Resources/Collectables/", "Collectable"),
    ("Resources/Mowers/", "Mower"),
    ("Resources/Shovels/", "Shovel"),
    ("Resources/Survivals/", "Survival"),
    ("Resources/Tutorials/", "Tutorial"),
    ("Resources/NpcTalks/", "NpcTalk"),
    ("Resources/Shops/", "Shop"),
    ("Resources/AnimationAtlasProfiles/", "AnimationAtlas"),
    ("Resources/BGMConfigs/", "BGM"),
]
TEXTURE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".bmp", ".tga"}
AUDIO_EXT = {".wav", ".ogg", ".mp3", ".flac"}

OK, WARN, FAIL = [], [], []


def ok(m):
    OK.append(m)


def warn(m):
    WARN.append(m)


def bad(m):
    FAIL.append(m)


# ------------------------------------------------------------ 复刻：路径/类别推断

def try_infer_character_scene(rel, folder="Scene"):
    a = rel.split("/")
    if len(a) != 6:
        return None
    if a[0].lower() != "resources" or a[1].lower() != "characters":
        return None
    if a[2] not in CATEGORIES:
        return None
    if a[4].lower() != folder.lower():
        return None
    if not a[5].lower().endswith(".tscn"):
        return None
    stem = a[5][:-len(".tscn")]
    if not a[3] or stem.lower() != a[3].lower():
        return None
    return a[3]


def is_character_package_dependency(rel):
    a = (rel or "").replace("\\", "/").strip("/").split("/")
    return len(a) >= 5 and a[0].lower() == "resources" and a[1].lower() == "characters" and a[2] in CATEGORIES


def infer_runtime_entry(rel):
    """→ (category, key) 或 None（= 该文件不会被注册）。"""
    ext = posixpath.splitext(rel)[1].lower()
    if rel.startswith("Assets/Audio/") and ext in AUDIO_EXT:
        return ("Audio", posixpath.splitext(rel)[0].split("/")[-1])
    if (rel.startswith("Assets/Textures/") or rel.startswith("Assets/Texture/")
            or rel.startswith("Assets/Images/")) and ext in TEXTURE_EXT:
        return ("Texture", posixpath.splitext(rel)[0].split("/")[-1])
    k = try_infer_character_scene(rel)
    if k:
        return ("Character", k)
    k = try_infer_character_scene(rel, "Sprite")
    if k:
        return ("CharacterSprite", k)
    if ext not in (".tres", ".res"):
        return None
    if rel.startswith("Resources/Tutorials/Conditions/") or rel.startswith("Resources/Tutorials/Steps/"):
        return None
    for pre, cat in PREFIX_TABLE:
        if rel.startswith(pre):
            return (cat, posixpath.splitext(rel)[0].split("/")[-1])
    return None


def normalize_category(c):
    c = (c or "").strip().lower()
    return {"characters": "Character", "character": "Character", "charactersprite": "CharacterSprite",
            "cards": "Packet", "card": "Packet", "packet": "Packet", "packets": "Packet",
            "images": "Texture", "image": "Texture", "texture": "Texture", "textures": "Texture"}.get(c, c)


# ------------------------------------------------------------ 解析器

EXT_RE = re.compile(r'\[ext_resource([^\]]*)\]')
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
PROP_RE = re.compile(r'^([A-Za-z_][\w/]*)\s*=\s*(.*)$', re.M)


def parse_ext_resources(text):
    out = []
    for m in EXT_RE.finditer(text):
        d = dict((k, v) for k, v in ATTR_RE.findall(m.group(1)))
        if "path" in d:
            out.append(d)
    return out


def parse_scalar(text, key, default=None):
    for m in PROP_RE.finditer(text):
        if m.group(1) == key:
            return m.group(2).strip()
    return default


# ------------------------------------------------------------ 主流程

def main():
    if not os.path.isfile(PMOD):
        bad(f"缺少产物 {PMOD}")
        return summary()

    # --- 1) 打包内容（源自 .pmod 本身，而不是工作区目录）
    with zipfile.ZipFile(PMOD) as z:
        names = z.namelist()
        raw = {n: z.read(n) for n in names}
        infos = z.infolist()
    entries = set(names)

    if names[0] != "mod.json":
        bad(f"包内第 0 个条目应为 mod.json，实际 {names[0]}")
    else:
        ok("包内 mod.json 位于第 0 个条目")

    hidden = [n for n in names if posixpath.basename(n).startswith(".")]
    if hidden:
        bad(f"包内混入隐藏文件：{hidden}")
    else:
        ok("包内无隐藏文件（.generated 等）")

    stamps = set((i.date_time for i in infos))
    if len(stamps) == 1:
        ok(f"zip 条目时间戳统一（{list(stamps)[0]}）→ 字节幂等")
    else:
        bad(f"zip 条目时间戳不统一：{sorted(stamps)}")

    if any(n.endswith((".uid", ".import")) or n.endswith(".cs") for n in names):
        bad("包内混入 .uid/.import/.cs")
    else:
        ok("包内无 .uid/.import/.cs（脚本复用游戏 res:// 版）")

    # --- 2) manifest
    mf = json.loads(raw["mod.json"].decode("utf-8-sig"))
    ok("mod.json 可解析")
    if mf.get("schemaVersion") == 2:
        ok("schemaVersion = 2")
    else:
        warn(f"schemaVersion = {mf.get('schemaVersion')}")

    # --- 3) 推断每个条目的类别/键 = 模拟注册结果
    registered = []      # (category, key, rel)
    unsupported = []
    for n in names:
        if n == "mod.json":
            continue
        r = infer_runtime_entry(n)
        if r is None:
            if is_character_package_dependency(n):
                continue          # 角色包依赖：允许、且不参与注册
            unsupported.append(n)
        else:
            registered.append((r[0], r[1], n))

    if unsupported:
        warn(f"不被任何类别识别（仅产生 unsupported 诊断，不致整包失败）：{unsupported}")
    else:
        ok("所有条目都能被「注册」或「角色包依赖」解释")

    reg_pairs = set(((c, k) for c, k, _ in registered))
    for cat, key, rel in sorted(registered):
        ok(f"注册 {cat}/{key}  ←  {rel}")

    # --- 4) provides ⊆ 实际注册（ModLoader.ValidateManifestRegistrations）
    prov = mf.get("provides") or {}
    for cat, keys in prov.items():
        for k in keys:
            if (normalize_category(cat), k) in reg_pairs or any(
                    normalize_category(c) == normalize_category(cat) and kk == k for c, kk, _ in registered):
                ok(f"provides {cat}/{k} 已注册")
            else:
                bad(f"provides {cat}/{k} 未注册 → ValidateManifestRegistrations 失败 → 整包被拒")
    for cat, key, rel in registered:
        if not any(normalize_category(c) == normalize_category(cat) and key in v
                   for c, v in prov.items()):
            bad(f"注册项 {cat}/{key}（{rel}）没有出现在 provides → 会被静默跳过或被误判歧义")

    # --- 5) 角色场景 / 精灵场景 6 段约束 + 键一致
    for cat, key, rel in registered:
        if cat in ("Character", "CharacterSprite"):
            a = rel.split("/")
            folder = a[4]
            if len(a) == 6 and a[3] == key and a[5] == key + ".tscn":
                ok(f"{cat} 路径合规：{rel}")
            else:
                bad(f"{cat} 路径不合规：{rel}")
            if key != KEYS[cat]:
                bad(f"{cat} 的键 {key} != 预期 {KEYS[cat]}")

    # --- 6) 包内自引用解析（复刻 user://ModsCache 下的相对解析）
    game_bad, rel_bad = [], []
    for n in names:
        if not n.endswith((".tscn", ".tres")):
            continue
        text = raw[n].decode("utf-8-sig", "replace")
        is_tscn = n.endswith(".tscn")
        for d in parse_ext_resources(text):
            p = d["path"]
            t = d.get("type", "")
            if p.startswith("res://"):
                if p.startswith("res://Resources/"):
                    game_bad.append(f"{n} → {p}（游戏 pck 根不存在 Resources/）")
                continue
            if p.startswith("user://") or p.startswith("/") or re.match(r"^[A-Za-z]:", p):
                game_bad.append(f"{n} → {p}（绝对/非法路径）")
                continue
            target = posixpath.normpath(posixpath.join(posixpath.dirname(n), p))
            if target not in entries:
                rel_bad.append(f"{n} → {p}（解析为 {target}，包内不存在）")
            if t == "Script" and not is_tscn and not p.startswith("res://"):
                bad(f".tres 的 Script 引用非 res://：{n} → {p}（SanitizeCharacterTextResource 直接拒包）")
    if rel_bad:
        bad("包内相对引用无法在包内解析：" + "; ".join(rel_bad))
    else:
        ok("包内所有相对引用都能在包内解析（= user://ModsCache 树内可解析）")
    if game_bad:
        bad("非法 res:// 自引用：" + "; ".join(game_bad))
    else:
        ok("没有 res://Resources/… 之类的非法自引用")

    # --- 7) 角色包内禁 .scn/.res + 禁内嵌脚本
    binary = [n for n in names if is_character_package_dependency(n)
              and posixpath.splitext(n)[1].lower() in (".scn", ".res")]
    if binary:
        bad(f"角色包内含二进制依赖（直接拒包）：{binary}")
    else:
        ok("角色包内无 .scn/.res")
    embedded = [n for n in names if n.endswith((".tscn", ".tres"))
                and ('type="CSharpScript"' in raw[n].decode("utf-8-sig", "replace")
                     or 'type="GDScript"' in raw[n].decode("utf-8-sig", "replace"))]
    if embedded:
        bad(f"含内嵌脚本：{embedded}")
    else:
        ok("无内嵌 GDScript/CSharpScript")

    # --- 8) 跨资源一致性（XWModContentValidation）
    card_rel = None
    for cat, key, rel in registered:
        if cat == "Packet":
            card_rel = rel
    save_key = ""
    if not card_rel:
        bad("没有注册到任何 Packet（卡片）")
    else:
        pk = raw[card_rel].decode("utf-8-sig", "replace")
        card_key = posixpath.splitext(posixpath.basename(card_rel))[0]
        save_key = (parse_scalar(pk, "saveKey") or '""').strip('"')
        if save_key == card_key:
            ok(f"Packet.saveKey({save_key}) == 注册键({card_key})")
        else:
            bad(f"Packet.saveKey({save_key}) != 注册键({card_key}) → XWModContentValidation 抛异常 → 整包被拒")

        uch = parse_scalar(pk, "unlockCheckList", "")
        if uch.strip() in ("[]", ""):
            ok("Packet.unlockCheckList 为空（允许；空表=直接可用）")
        elif "XWModProgressUnlockCondition" in uch:
            warn(f"Packet.unlockCheckList 使用了 Mod 专属条件：{uch[:80]}")
        else:
            bad(f"Packet.unlockCheckList 必须为空或 XWModProgressUnlockCondition，实际 {uch[:80]}")

        # characterConfig 必须能解析 + name 必须注册进 TOWERDEFENSE_CHARCATERS
        cfg_ext = [d for d in parse_ext_resources(pk) if d.get("id") == "1"]
        if not cfg_ext:
            bad("Packet 的 characterConfig 未通过 ext_resource id=1 绑定")
        else:
            tgt = posixpath.normpath(posixpath.join(posixpath.dirname(card_rel), cfg_ext[0]["path"]))
            if tgt not in entries:
                bad(f"Packet.characterConfig 指向 {tgt}，包内不存在")
            else:
                cfg_txt = raw[tgt].decode("utf-8-sig", "replace")
                cname = (parse_scalar(cfg_txt, "name") or '""').strip('"')
                char_keys = set(k for c, k, _ in registered if c == "Character")
                if cname in char_keys:
                    ok(f"characterConfig.name({cname}) ∈ TOWERDEFENSE_CHARCATERS({sorted(char_keys)})")
                else:
                    bad(f"characterConfig.name({cname}) 未注册为 Character → CreateCharacter 找不到场景")
                # 用户指定数值
                for field, want in (("hitpoints", "1000.0"),
                                    ("cost", "600"), ("costRise", "100"),
                                    ("packetCooldown", "30.0")):
                    got = parse_scalar(cfg_txt, field)
                    if got == want:
                        ok(f"config.{field} = {want}")
                    else:
                        bad(f"config.{field} 应为 {want}，实际 {got}")
        # type == GOLD(1)
        ty = parse_scalar(pk, "type")
        if ty == "1":
            ok("Packet.type = 1（GOLD 金卡）")
        else:
            bad(f"Packet.type 应为 1(GOLD)，实际 {ty}")

        # 2026-09-19：覆盖卡也能直接种在地上 = 内联 packet override 只开 coverCanDirectPlant。
        # 依据 TowerDefenseCellInstance.CanPacketPlant:787-800 —— 本卡 plantCover 非空（= 只能是
        # 双发射手底座），没有这个开关就会在空地种植时 return false。
        ov = parse_scalar(pk, "override")
        if ov == 'SubResource("PacketOverride_direct_plant")':
            ok("Packet.override 绑定内联 PacketOverride_direct_plant")
        else:
            bad(f"Packet.override 应为 SubResource(\"PacketOverride_direct_plant\")，实际 {ov}")
        if '[sub_resource type="Resource" id="PacketOverride_direct_plant"]' in pk:
            sub = pk.split('[sub_resource type="Resource" id="PacketOverride_direct_plant"]')[1].split("[resource]")[0]
            if "coverCanDirectPlant = true" in sub:
                ok("coverCanDirectPlant = true（空地可直接种，不必种在双发射手上）")
            else:
                bad("override 里缺 coverCanDirectPlant = true → 又变回只能种在双发射手上")
            extra = [ln.strip() for ln in sub.splitlines()
                     if ln.strip() and not ln.startswith(("script =", "coverCanDirectPlant", "metadata/", "["))]
            if extra:
                bad(f"override 只允许写 coverCanDirectPlant（多写字段可能顶掉 characterConfig 取值）：{extra}")
            else:
                ok("override 只写 coverCanDirectPlant（其余走类默认 = 不覆盖）")
            if ('path="res://Registry/Battle/Feature/PacketBank/Resource/Packet/Override/'
                    'TowerDefensePacketOverride.cs"') in pk:
                ok("override 脚本引用游戏自带 TowerDefensePacketOverride.cs")
            else:
                bad("override 缺 TowerDefensePacketOverride.cs 的 res:// 脚本引用")
        else:
            bad("Packet 缺内联 PacketOverride_direct_plant 子资源")

    # --- 9) CHARCTAER_SPRITE 里必须有 lookup 用的键
    sprite_keys = set(k for c, k, _ in registered if c == "CharacterSprite")
    lookup = save_key if (card_rel and save_key in sprite_keys) else None
    if lookup is None and card_rel:
        cfg_ext = [d for d in parse_ext_resources(raw[card_rel].decode("utf-8-sig", "replace")) if d.get("id") == "1"]
        tgt = posixpath.normpath(posixpath.join(posixpath.dirname(card_rel), cfg_ext[0]["path"])) if cfg_ext else ""
        cname = (parse_scalar(raw[tgt].decode("utf-8-sig", "replace"), "name") or '""').strip('"') if tgt in entries else ""
        lookup = cname if cname in sprite_keys else None
    if sprite_keys and lookup:
        ok(f"CHARCTAER_SPRITE 命中 {lookup}（GetPacketSpriteScene 不会抛 KeyNotFound）")
    else:
        bad(f"CHARCTAER_SPRITE({sorted(sprite_keys)}) 里既没有 saveKey 也没有 characterConfig.name"
            " → XWModContentValidation 抛「缺少 CharacterSprite/…」+ 运行时 KeyNotFoundException")

    # --- 10) manifest.resources 与包内容一致
    res_list = list(mf.get("resources") or [])
    missing_in_pkg = [r for r in res_list if r not in entries]
    if missing_in_pkg:
        bad(f"manifest.resources 声明了包内不存在的文件：{missing_in_pkg}")
    else:
        ok(f"manifest.resources（{len(res_list)} 项）全部存在于包内")
    undeclared = sorted(n for n in names if n != "mod.json" and n not in res_list
                        and not n.startswith("Localization/"))
    if undeclared:
        warn(f"包内存在未在 manifest.resources 里声明的文件：{undeclared}")

    # --- 11) res:// 指向的游戏资源确实在解包里（离线存在性）
    if os.path.isdir(GAME):
        seen = set()
        absent = []
        for n in names:
            if not n.endswith((".tscn", ".tres")):
                continue
            for d in parse_ext_resources(raw[n].decode("utf-8-sig", "replace")):
                p = d["path"]
                if not p.startswith("res://") or p in seen:
                    continue
                seen.add(p)
                disk = os.path.join(GAME, p[len("res://"):].replace("/", os.sep))
                if not os.path.isfile(disk):
                    absent.append(p)
        if absent:
            warn(f"以下 res:// 在解包中找不到（解包可能不完整，需人工确认）：{absent}")
        else:
            ok(f"{len(seen)} 个 res:// 外部引用在解包中全部存在")
    else:
        warn(f"未找到解包目录 {GAME}，跳过 res:// 存在性检查")

    return summary()


def summary():
    print("-" * 72)
    for m in OK:
        print("  [ok]  ", m)
    for m in WARN:
        print("  [warn]", m)
    for m in FAIL:
        print("  [FAIL]", m)
    print("-" * 72)
    print(f"ok={len(OK)} warn={len(WARN)} FAIL={len(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
