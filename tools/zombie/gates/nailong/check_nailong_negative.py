# -*- coding: utf-8 -*-
"""奶龙僵尸 —— 闸门反向测试（negative tests）

对 NaiLong/ 的一份临时副本做定向破坏，断言对应闸门**确实报错**。
闸门如果只会在正确输入上通过、却抓不住错误输入，那就是假闸门。

用法： python check_nailong_negative.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.abspath(os.path.join(HERE, '..', '..'))          # .../tools/zombie
sys.path.insert(0, TOOLS)

import build_zombie_nailong as bz                                  # noqa: E402

SRC = bz.MOD_DIR


# ------------------------------------------------------------------ 破坏手法
def _tamper(root, rel, fn):
    p = os.path.join(root, rel.replace('/', os.sep))
    txt = open(p, encoding='utf8').read()
    out = fn(txt)
    assert out != txt, 'tamper produced no change for %s' % rel
    open(p, 'w', encoding='utf8', newline='\n').write(out)


def t_offset(t):
    return t.replace('offset = Vector2(0, 0)', 'offset = Vector2(-40, -80)')


def t_add_layervisible(t):
    return t.replace('Animation/Clip = "Idle1"',
                     'Animation/Clip = "Idle1"\nAnimation/LayerVisible/body = true')


def t_anim_ref(t):
    return t.replace('../../../../../Resources/Animations/NaiLong.tres',
                     'res://Resources/Animations/NaiLong.tres')


def t_dat_animefile(t):
    return t.replace('animeFile = "./NaiLong.dat"', 'animeFile = "./Wrong.dat"')


def t_clip_shift(t):
    return t.replace('"Laugh": Vector2i(56, 71)', '"Laugh": Vector2i(56, 70)')


def t_frame_max(t):
    import re
    return re.sub(r'^frameMax = (\d+)$', lambda m: 'frameMax = %d' % (int(m.group(1)) - 1),
                  t, count=1, flags=re.M)


def t_relative_script(t):
    # 角色包内的 Script 引用必须是 res://，否则 ModLoader 会剥掉/拒绝
    return t.replace('path="res://Script/Component/Runtime/CharacterComponentSet.cs"',
                     'path="../Script/CharacterComponentSet.cs"')


def t_cset_last(t):
    lines = t.split('\n')
    i = [k for k, l in enumerate(lines) if l.startswith('ComponentSet = ')][0]
    cs = lines.pop(i)
    j = [k for k, l in enumerate(lines) if l.startswith('config = ')][0]
    lines.insert(j + 1, cs)
    return '\n'.join(lines)


def t_script_override(t):
    return t.replace('ComponentSet = ExtResource("2")',
                     'ComponentSet = ExtResource("2")\n'
                     'script = ExtResource("3")')


# ---- 数值 / 速度 / 伤害类型（gate_attack_spec）----------------------------
def t_hp_wrong(t):
    return t.replace('hitpoints = 1350.0', 'hitpoints = 200.0')


def t_attack_wrong(t):
    return t.replace('attack = 100.0', 'attack = 80.0')


def t_near_death_wrong(t):
    return t.replace('hitpointsNearDeath = 70.0', 'hitpointsNearDeath = 1350.0')


def t_speed_drop(t):
    return t.replace('walkSpeedScale = 2.0\n', '')


def t_speed_wrong(t):
    return t.replace('walkSpeedScale = 2.0', 'walkSpeedScale = 1.0')


def t_attacktype_wrong(t):
    return t.replace('attackType = "Eat"', 'attackType = "Smash"')


def t_attacktype_drop(t):
    return t.replace('attackType = "Eat"\n', '')


def t_attack_wire(t):
    # 覆盖继承定义时 WireIndex 必须与内置一致，否则 CanReplaceInheritedDefinition 拒绝
    return t.replace('WireIndex = 0', 'WireIndex = 7')


def t_attack_instanceid(t):
    return t.replace('InstanceId = "character.attack.0"', 'InstanceId = "character.eat"')


def t_attack_hitbox(t):
    # useParentHitBox 决定啃食判定用不用父级碰撞盒，动了会静默改掉咬合范围
    return t.replace('useParentHitBox = true\n', '')


def t_cset_unlink(t):
    return t.replace('Components = [ExtResource("3")]', 'Components = []')


def t_handbook_hp(t):
    return t.replace('血量：[color=cc241d]1350[/color]',
                     '血量：[color=cc241d]999[/color]')


def t_handbook_speed(t):
    return t.replace('移速：[color=cc241d]快[/color]',
                     '移速：[color=cc241d]慢[/color]')


def t_handbook_raw_newline(t):
    # 把 \n 转义还原成裸换行 —— Godot 会整份资源解析失败
    return t.replace('\\n血量：', '\n血量：')


# ---- 根运动（gate_ground_motion）----------------------------------------
def t_dat_drop_ground(t):
    """把 .dat 的层数从 3 改成 2（等于删掉 _ground 层）⇒ 角色应当一步都走不了。"""
    import struct
    # 头部 18 字节 + pixels 之后是 media 数；先算出 media 段末尾的偏移
    fmx, aw, ah = struct.unpack_from('<HHH', t, 4)
    pbc, = struct.unpack_from('<q', t, 10)
    off = 18 + pbc
    nmedia, = struct.unpack_from('<H', t, off)
    off += 2
    for _ in range(nmedia):
        n, = struct.unpack_from('<I', t, off)
        off += 4 + n + 16
    b = bytearray(t)
    struct.pack_into('<H', b, off, 2)          # 层表只留 2 层
    return bytes(b)


def t_dat_ground_alpha(t):
    """把 _ground 元素的 alpha 从 0 改成 255 ⇒ 会画出来（可见的假图层）。"""
    import struct
    fmx, aw, ah = struct.unpack_from('<HHH', t, 4)
    pbc, = struct.unpack_from('<q', t, 10)
    off = 18 + pbc
    nmedia, = struct.unpack_from('<H', t, off)
    off += 2
    for _ in range(nmedia):
        n, = struct.unpack_from('<I', t, off)
        off += 4 + n + 16
    nlayer, = struct.unpack_from('<H', t, off)
    off += 2
    b = bytearray(t)
    for _ in range(nlayer):
        n, = struct.unpack_from('<I', b, off)
        name = bytes(b[off + 4:off + 4 + n]).decode('utf8')
        off += 4 + n
        for _f in range(fmx):
            cnt, = struct.unpack_from('<H', b, off)
            off += 2
            for _e in range(cnt):
                if name == '_ground':
                    struct.pack_into('<I', b, off + 26, 255)
                    return bytes(b)
                off += 30
    raise AssertionError('no _ground element found to tamper')


def t_dat_ground_backjump(t):
    """在 Walk1 正中间插一次回跳 ⇒ 会被当成倒着走一大步。"""
    import struct
    fmx, aw, ah = struct.unpack_from('<HHH', t, 4)
    pbc, = struct.unpack_from('<q', t, 10)
    off = 18 + pbc
    nmedia, = struct.unpack_from('<H', t, off)
    off += 2
    for _ in range(nmedia):
        n, = struct.unpack_from('<I', t, off)
        off += 4 + n + 16
    nlayer, = struct.unpack_from('<H', t, off)
    off += 2
    b = bytearray(t)
    for _ in range(nlayer):
        n, = struct.unpack_from('<I', b, off)
        name = bytes(b[off + 4:off + 4 + n]).decode('utf8')
        off += 4 + n
        for f in range(fmx):
            cnt, = struct.unpack_from('<H', b, off)
            off += 2
            for _e in range(cnt):
                if name == '_ground' and f == 26:      # Walk1 = 20..31 的中间
                    ox, = struct.unpack_from('<f', b, off + 18)
                    struct.pack_into('<f', b, off + 18, 0.0)   # 突然回到 0 ⇒ 负数位移
                    return bytes(b)
                off += 30
    raise AssertionError('no _ground frame 26 found to tamper')


CASES = [
    ('精灵 offset 非 (0,0) —— 会把整个动画整体平移',
     [('file', bz.P_SPRITE, t_offset)], 'gate_geometry'),
    ('精灵设了 Animation/LayerVisible —— 长度不匹配会被引擎重置',
     [('file', bz.P_SPRITE, t_add_layervisible)], 'gate_geometry'),
    ('精灵动画引用改成 res:// 绝对路径 —— 包内相对路径约定被破坏',
     [('file', bz.P_SPRITE, t_anim_ref)], 'gate_geometry'),
    ('.tres 的 animeFile 指向不存在的 .dat',
     [('file', bz.P_ANIM_TRES, t_dat_animefile)], 'gate_geometry'),
    ('Laugh 剪辑区间被改窄一帧',
     [('file', bz.P_ANIM_TRES, t_clip_shift)], 'gate_geometry'),
    ('.tres frameMax 与模型不一致',
     [('file', bz.P_ANIM_TRES, t_frame_max)], 'gate_geometry'),
    ('角色包内 Script 引用用了相对路径 —— ModLoader 会剥掉该行',
     [('file', bz.P_CSET, t_relative_script)], 'gate_structure'),
    ('ComponentSet 没有放在属性列表第一位',
     [('file', bz.P_SCENE, t_cset_last)], 'gate_runtime_order'),
    ('角色场景覆盖了 script —— 会丢掉基类通用僵尸行为',
     [('file', bz.P_SCENE, t_script_override)], 'gate_runtime_order'),
    ('删掉音效文件',
     [('delete', bz.P_AUDIO, None)], 'gate_structure'),
    ('mod.json 去掉 provides.Audio —— 音效会被静默丢弃',
     [('json_drop_audio', 'mod.json', None)], 'gate_structure'),
    ('mod.json 的 resources 漏列一个包内文件',
     [('json_drop_resource', 'mod.json', bz.P_ANIM_PNG)], 'gate_structure'),
    ('mod.json 的 runtimeEntryType 带上命名空间',
     [('json_set', 'mod.json', ('runtimeEntryType', 'X.Y.NaiLongRuntimeEntry'))],
     'gate_structure'),
    ('mod.json 的 runtimeAssembly 路径写错',
     [('json_set', 'mod.json', ('runtimeAssembly', 'ModAssembly.dll'))],
     'gate_structure'),
    ('.dat 头部 pixelByteCount 被破坏',
     [('dat_head', bz.P_ANIM_DAT, None)], 'gate_geometry'),
    ('音效被重采样到 22050Hz',
     [('wav_rate', bz.P_AUDIO, None)], 'gate_audio'),
    ('音效被截短',
     [('wav_truncate', bz.P_AUDIO, None)], 'gate_audio'),

    # ---- 数值 / 速度 / 伤害类型 ----
    ('生命值被改回 200（手册写 1350）',
     [('file', bz.P_CONFIG, t_hp_wrong)], 'gate_attack_spec'),
    ('啃食伤害被改成 80',
     [('file', bz.P_CONFIG, t_attack_wrong)], 'gate_attack_spec'),
    ('濒死掉血速率被误当成阈值填成 1350',
     [('file', bz.P_CONFIG, t_near_death_wrong)], 'gate_attack_spec'),
    ('移速 walkSpeedScale 整行被删 —— 退化回普通僵尸速度',
     [('file', bz.P_SCENE, t_speed_drop)], 'gate_attack_spec'),
    ('移速被改成 1.0（慢）',
     [('file', bz.P_SCENE, t_speed_wrong)], 'gate_attack_spec'),
    ('伤害类型被改成 Smash（砸击）',
     [('file', bz.P_ATTACK_DEF, t_attacktype_wrong)], 'gate_attack_spec'),
    ('攻击组件定义丢掉 attackType 行',
     [('file', bz.P_ATTACK_DEF, t_attacktype_drop)], 'gate_attack_spec'),
    ('攻击组件覆盖的 WireIndex 与内置不一致 —— 引擎会拒绝替换',
     [('file', bz.P_ATTACK_DEF, t_attack_wire)], 'gate_attack_spec'),
    ('攻击组件覆盖的 InstanceId 对不上内置 —— 会变成新增而非覆盖',
     [('file', bz.P_ATTACK_DEF, t_attack_instanceid)], 'gate_attack_spec'),
    ('攻击组件丢掉 useParentHitBox —— 静默改掉啃食判定范围',
     [('file', bz.P_ATTACK_DEF, t_attack_hitbox)], 'gate_attack_spec'),
    ('组件集不再引用攻击组件定义 —— 上面的定义成了死文件',
     [('file', bz.P_CSET, t_cset_unlink)], 'gate_attack_spec'),
    ('手册属性块写的血量与实际值不符',
     [('file', bz.P_PACKET, t_handbook_hp)], 'gate_attack_spec'),
    ('手册属性块写的移速与实际值不符',
     [('file', bz.P_CARD, t_handbook_speed)], 'gate_attack_spec'),
    ('删掉攻击组件定义文件',
     [('delete', bz.P_ATTACK_DEF, None)], 'gate_structure'),
    ('手册文本里出现裸换行 —— Godot 会整份资源解析失败',
     [('file', bz.P_PACKET, t_handbook_raw_newline)], 'gate_structure'),

    # ---- 根运动（僵尸能不能往前走）----
    ('.dat 里没有 _ground 层 —— 僵尸一步都走不了',
     [('binfile', bz.P_ANIM_DAT, t_dat_drop_ground)], 'gate_ground_motion'),
    ('_ground 层 alpha 不是 0 —— 会画出可见的假图层',
     [('binfile', bz.P_ANIM_DAT, t_dat_ground_alpha)], 'gate_ground_motion'),
    ('_ground 在剪辑中间回跳 —— 会看起来倒着走一大步',
     [('binfile', bz.P_ANIM_DAT, t_dat_ground_backjump)], 'gate_ground_motion'),
]


# ------------------------------------------------------------------ 执行
def apply_mutation(root, op):
    kind, rel, arg = op
    p = os.path.join(root, rel.replace('/', os.sep))
    if kind == 'file':
        _tamper(root, rel, arg)
    elif kind == 'binfile':
        raw = open(p, 'rb').read()
        out = arg(raw)
        assert out != raw, 'binary tamper produced no change for %s' % rel
        open(p, 'wb').write(out)
    elif kind == 'delete':
        os.remove(p)
    elif kind == 'json_drop_audio':
        import json
        d = json.load(open(p, encoding='utf-8'))
        del d['provides']['Audio']
        bz.w(p, json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    elif kind == 'json_drop_resource':
        import json
        d = json.load(open(p, encoding='utf-8'))
        d['resources'] = [x for x in d['resources'] if x != arg]
        bz.w(p, json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    elif kind == 'json_set':
        import json
        k, v = arg
        d = json.load(open(p, encoding='utf-8'))
        d[k] = v
        bz.w(p, json.dumps(d, ensure_ascii=False, indent=2) + '\n')
    elif kind == 'dat_head':
        import struct
        b = bytearray(open(p, 'rb').read())
        struct.pack_into('<q', b, 10, 12345)
        open(p, 'wb').write(bytes(b))
    elif kind == 'wav_rate':
        import soundfile as sf
        data, _r = sf.read(p, dtype='int16', always_2d=True)
        sf.write(p, data[::2], 22050, format='WAV', subtype='PCM_16')
    elif kind == 'wav_truncate':
        import soundfile as sf
        data, r = sf.read(p, dtype='int16', always_2d=True)
        sf.write(p, data[: len(data) // 3], r, format='WAV', subtype='PCM_16')
    else:
        raise AssertionError('unknown op %r' % kind)


def run_gate(name, anim, audio):
    if name == 'gate_structure':
        return bz.gate_structure()[0]
    if name == 'gate_geometry':
        return bz.gate_geometry(anim)
    if name == 'gate_audio':
        return bz.gate_audio(audio)
    if name == 'gate_runtime_order':
        return bz.gate_runtime_order()
    if name == 'gate_attack_spec':
        return bz.gate_attack_spec()
    if name == 'gate_ground_motion':
        return bz.gate_ground_motion(anim)
    raise AssertionError('unknown gate %r' % name)


def main():
    print('源包: %s' % SRC)
    print('先把干净包过一遍闸门（应当全绿）…')
    sys.path.insert(0, TOOLS)
    import nailong_skin as ns
    m = ns.build()
    anim = dict(frame_max=m['frame_max'], clips=m['clips'], atlas=m['atlas'],
                frames=m['frames'], media=m['media'], feet=ns.FEET_Y, lifted=m['lifted'],
                ground=m['ground'], ground_clips=list(ns.GROUND_CLIPS),
                ground_px_per_frame=ns.GROUND_PX_PER_FRAME, frame_rate=ns.FRAME_RATE)
    import soundfile as sf
    data, rate = sf.read(os.path.join(SRC, bz.P_AUDIO), dtype='int16', always_2d=True)
    audio = dict(rate=rate, channels=int(data.shape[1]), frames=int(data.shape[0]),
                 src_duration=data.shape[0] / float(rate),
                 estimated_frames=int(data.shape[0]))
    clean = run_gate('gate_structure', anim, audio) + run_gate('gate_geometry', anim, audio) \
        + run_gate('gate_audio', anim, audio) + run_gate('gate_runtime_order', anim, audio) \
        + run_gate('gate_attack_spec', anim, audio) + run_gate('gate_ground_motion', anim, audio)
    if clean:
        print('  [FAIL] 干净包本来就不干净：')
        for x in clean:
            print('         %s' % x)
        return 1
    print('  OK 干净包无告警')
    print()

    npass = nfail = 0
    print('%-58s %-18s %s' % ('破坏手法', '期望闸门', '结果'))
    print('-' * 96)
    for title, ops, gate in CASES:
        tmp = tempfile.mkdtemp(prefix='nailong_neg_')
        root = os.path.join(tmp, 'NaiLong')
        shutil.copytree(SRC, root)
        old = bz.MOD_DIR
        try:
            for op in ops:
                apply_mutation(root, op)
            bz.MOD_DIR = root
            errs = run_gate(gate, anim, audio)
        finally:
            bz.MOD_DIR = old
            shutil.rmtree(tmp, ignore_errors=True)
        ok = len(errs) > 0
        npass += ok
        nfail += (not ok)
        mark = 'CAUGHT' if ok else '*** MISSED ***'
        print('%-58s %-18s %s' % (title[:58], gate, mark))
        if ok:
            print('         └─ %s' % errs[0][:100])
    print('-' * 96)
    print('反向测试：%d/%d 被抓到，%d 漏网' % (npass, npass + nfail, nfail))
    return 0 if nfail == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
