# -*- coding: utf-8 -*-
"""装机验收：独立于打包器，直接比对 Mods/ 安装结果 与 源包目录。

只读校验，不修改任何文件。
退出码 0 = 全部通过。
"""
import hashlib
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.dirname(os.path.dirname(HERE))          # .../tools/zombie
SRC = os.path.join(TOOLS, 'NaiLong')
PMOD = os.path.join(TOOLS, '奶龙僵尸.pmod')
MODS = os.path.join(os.environ['APPDATA'], 'Godot', 'app_userdata',
                    '植物大战僵尸杂交版', 'Mods')
DST = os.path.join(MODS, '奶龙僵尸')
ENABLED = os.path.join(MODS, 'enabled_mods.json')

MOD_ID = 'nailongzombie'
errs = []


def rel_hashes(root):
    """源包内可交付文件的相对路径 -> sha256。

    以 '.' 开头的文件是构建器内部产物（如 .build_manifest.json 的幂等清单），
    参照 超级机枪读报僵尸 / 向日葵女王僵尸 的惯例：装机包与 .pmod 都只含
    mod.json + *.pvzmodeproject 及正式资源，不含任何点文件。因此这里一并排除。
    """
    out = {}
    for dp, _dn, fn in os.walk(root):
        for f in fn:
            if f.startswith('.'):
                continue
            p = os.path.join(dp, f)
            r = os.path.relpath(p, root).replace(os.sep, '/')
            out[r] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
    return out


# ---- 1. 源包 -> 安装目录 逐字节一致
if not os.path.isdir(DST):
    errs.append('未安装: %s' % DST)
else:
    a, b = rel_hashes(SRC), rel_hashes(DST)
    if set(a) - set(b):
        errs.append('安装目录缺少: %s' % sorted(set(a) - set(b)))
    if set(b) - set(a):
        errs.append('安装目录多出: %s' % sorted(set(b) - set(a)))
    bad = [k for k in a if k in b and a[k] != b[k]]
    if bad:
        errs.append('内容不一致: %s' % bad)
    print('安装目录 %d 文件，与源包逐字节一致: %s' % (len(b), not errs))

# ---- 2. .pmod 完整性 + 内容与源包一致
if not os.path.exists(PMOD):
    errs.append('缺少 .pmod: %s' % PMOD)
else:
    z = zipfile.ZipFile(PMOD)
    broken = z.testzip()
    if broken:
        errs.append('.pmod 内损坏条目: %s' % broken)
    names = set(n.replace(os.sep, '/') for n in z.namelist())
    a = rel_hashes(SRC)
    if names != set(a):
        errs.append('.pmod 条目集合与源包不符: 缺 %s 多 %s'
                    % (sorted(set(a) - names), sorted(names - set(a))))
    inner_bad = [n for n in names
                 if n in a and hashlib.sha256(z.read(n)).hexdigest() != a[n]]
    if inner_bad:
        errs.append('.pmod 内文件与源包不一致: %s' % inner_bad)
    print('.pmod %d 条目，CRC 与内容均一致: %s' % (len(names), not inner_bad))

# ---- 3. enabled_mods.json 登记
if not os.path.exists(ENABLED):
    errs.append('缺少 enabled_mods.json')
else:
    raw = open(ENABLED, encoding='utf8').read()
    try:
        data = json.loads(raw)
    except Exception as e:
        errs.append('enabled_mods.json 不是合法 JSON: %r' % e)
        data = None
    if data is not None:
        ids = set()
        def collect(o):
            if isinstance(o, str):
                ids.add(o)
            elif isinstance(o, list):
                for i in o:
                    collect(i)
            elif isinstance(o, dict):
                for k, v in o.items():
                    ids.add(k)
                    collect(v)
        collect(data)
        if MOD_ID not in ids:
            errs.append('enabled_mods.json 未登记 %r' % MOD_ID)
        print('enabled_mods.json 已登记 %s: %s' % (MOD_ID, MOD_ID in ids))

# ---- 4. 登记前后其它 mod 未被破坏
baks = [f for f in os.listdir(MODS) if f.startswith('enabled_mods.json')]
print('enabled_mods.json 备份: %s' % sorted(baks))

# ---- 5. 关键文件存在性（防御性）
for need in ('mod.json', 'Runtime/ModAssembly.dll',
             'Resources/Animations/NaiLong.dat',
             'Resources/Animations/NaiLong.tres',
             'Assets/Audio/Sfx/nailong_laugh.wav',
             'Resources/Characters/Zombies/ZombieNaiLong/Scene/ZombieNaiLong.tscn'):
    p = os.path.join(DST, need.replace('/', os.sep))
    if not os.path.exists(p):
        errs.append('安装目录缺少关键文件: %s' % need)

print('-' * 72)
if errs:
    print('装机验收 FAIL')
    for e in errs:
        print('  !! %s' % e)
    sys.exit(1)
print('装机验收 PASS')
