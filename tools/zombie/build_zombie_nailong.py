# -*- coding: utf-8 -*-
"""奶龙僵尸 —— .pmod 包生成器（数据 + 素材 + 托管运行时插件）

产物目录：<tools/zombie>/NaiLong/
    mod.json
    Resources/Animations/NaiLong.{dat,tres}  + NaiLongAtlas.png
    Resources/Cards/ZombieNaiLong.tres
    Resources/Characters/Zombies/ZombieNaiLong/Config/TowerDefenseZombieNaiLong.tres
    Resources/Characters/Zombies/ZombieNaiLong/Packet/ZombieNaiLong.tres
    Resources/Characters/Zombies/ZombieNaiLong/Scene/ZombieNaiLong.tscn
    Resources/Characters/Zombies/ZombieNaiLong/Scene/ZombieNaiLongComponentSet.tres
    Resources/Characters/Zombies/ZombieNaiLong/Sprite/ZombieNaiLong.tscn
    Assets/Audio/Sfx/nailong_laugh.wav
    Runtime/ModAssembly.dll
    奶龙僵尸.pvzmodeproject

用法：
    python build_zombie_nailong.py              # 生成到 NaiLong/
    python build_zombie_nailong.py --check      # 再生成一次并与 NaiLong/ 逐字节比对（幂等闸门）
    python build_zombie_nailong.py --pmod       # 额外产出 奶龙僵尸.pmod
    python build_zombie_nailong.py --install    # 安装进 Mods/ 并登记 enabled_mods.json
    python build_zombie_nailong.py --all        # = --pmod --install

关键设计约束（都有实测/源码依据，改动前请先看注释）：
  * 角色包内的 `[ext_resource type="Script"]` 必须用 res:// 绝对路径 —— ModLoader
    .SanitizeCharacterTextResource 会把非 res:// 的脚本引用整行剥掉（.tres 则直接拒绝）。
  * 精灵节点的 offset 必须是 (0,0)：AdobeAnimateSprite 在渲染时会做
    transform = transform.Translated(offset)（AdobeAnimateSprite.cs:7044），
    我们的 node-local 几何就是按不带 offset 烘焙的。
  * 不动画地线：FEET_Y = 45，与内置普通僵尸实测脚底 42..45 对齐。
  * provides 必须显式声明 "Audio": ["nailong_laugh"]，否则 ModLoader 的
    "resource is not unambiguously declared by manifest" 分支会静默丢掉音频。
"""

import argparse
import datetime
import hashlib
import io
import json
import os
import re
import shutil
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = HERE                                        # .../tools/zombie
MOD_DIR = os.path.join(WORKSPACE, 'NaiLong')
CACHE = os.path.join(WORKSPACE, '.cache_nailong')
RT_SRC = os.path.join(WORKSPACE, 'runtime_src_zombie_nailong')
MANIFEST = os.path.join(MOD_DIR, '.build_manifest.json')

# ---------------------------------------------------------------- 身份定义
MOD_ID = 'nailongzombie'
MOD_NAME = '奶龙僵尸'
CHAR = 'ZombieNaiLong'
ANIME = 'NaiLong'
AUDIO_KEY = 'nailong_laugh'
ENTRY = 'NaiLongRuntimeEntry'
AUTHOR = '云漫行'
VERSION = '1.0.0'

# ---------------------------------------------------------------- 外部输入
MP3 = r'D:\啊这\2819680957\FileRecv\枪械图片\识别结果\奶龙笑_爱给网_aigei_com.mp3'

MODS_DIR = os.path.join(os.environ.get('APPDATA', ''),
                        'Godot', 'app_userdata', '植物大战僵尸杂交版', 'Mods')

# 包内相对路径
P_ANIM_DAT = 'Resources/Animations/%s.dat' % ANIME
P_ANIM_TRES = 'Resources/Animations/%s.tres' % ANIME
P_ANIM_PNG = 'Resources/Animations/%sAtlas.png' % ANIME
P_CARD = 'Resources/Cards/%s.tres' % CHAR
P_BASE = 'Resources/Characters/Zombies/%s' % CHAR
P_CONFIG = '%s/Config/TowerDefense%s.tres' % (P_BASE, CHAR)
P_PACKET = '%s/Packet/%s.tres' % (P_BASE, CHAR)
P_SCENE = '%s/Scene/%s.tscn' % (P_BASE, CHAR)
P_CSET = '%s/Scene/%sComponentSet.tres' % (P_BASE, CHAR)
P_ATTACK_DEF = '%s/Scene/%sAttackComponentDefinition.tres' % (P_BASE, CHAR)
P_SPRITE = '%s/Sprite/%s.tscn' % (P_BASE, CHAR)
P_AUDIO = 'Assets/Audio/Sfx/%s.wav' % AUDIO_KEY
P_DLL = 'Runtime/ModAssembly.dll'
P_PROJ = '%s.pvzmodeproject' % MOD_NAME

# 内置资源（跨包引用，与内置普通僵尸完全一致，零新增资源）
G_ARMOR_DATA = 'res://Asset/Anime/Character/Zombie/Chapter1/Normal/Armor/ZombieNormalArmorData.tres'
G_ASH = 'res://Asset/Anime/Character/Zombie/Ash/General/ZombieGeneralAsh.tscn'
G_DMG_DATA = 'res://Asset/Anime/Character/Zombie/Chapter1/Normal/DamagePoint/ZombieNormalDamagePointData.tres'
G_DMG_ARM = 'res://Asset/Anime/Character/Zombie/Chapter1/Normal/DamagePoint/Config/ZombieNormalDamagePointArm.tres'
G_DMG_HEAD = 'res://Asset/Anime/Character/Zombie/Chapter1/Normal/DamagePoint/Config/ZombieNormalDamagePointHead.tres'
G_ARMOR = {k: 'res://Asset/Anime/Character/Zombie/Chapter1/Normal/Armor/Config/ZombieNormalArmor%s.tres' % k
           for k in ('BlackHelmet', 'Bucket', 'Cone', 'Helmet', 'Screendoor', 'SpecialHelmet')}
G_HITBOX = 'res://Resource/TowerDefense/Collision/CharacterHitBoxes/Rect_44x70_At_4_n2.tres'
S_ZOMBIE = 'res://Prefab/TowerDefense/Character/TowerDefenseZombie.tscn'
S_ZOMBIE_CSET = 'res://Prefab/TowerDefense/Character/ComponentSets/TowerDefenseZombieComponentSet.tres'
S_CSET_SCRIPT = 'res://Script/Component/Runtime/CharacterComponentSet.cs'
S_CONFIG_SCRIPT = 'res://Resource/TowerDefense/Character/Config/TowerDefenseZombieConfig.cs'
S_PACKET_SCRIPT = 'res://Registry/Battle/Feature/PacketBank/Resource/Packet/TowerDefensePacketConfig.cs'
S_SPRITE_SCRIPT = 'res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs'
S_ATTACK_DEF_SCRIPT = ('res://Script/Component/TowerDefense/Character/AttackComponent/'
                       'AttackComponentDefinition.cs')
S_ATTACK_SM = ('res://Script/Component/TowerDefense/Character/AttackComponent/'
               'AttackComponentStateMachine.tres')

# ---------------------------------------------------------------- 数值与规格
#
# 全部取自解包树的「现有示例与配置规范」，逐项对拍来源写在这里，方便复核。
#
# 血量 1350 / 啃食 100
#   · `TowerDefenseCharacterConfig.hitpoints`（Resource/TowerDefense/Character/Config/）
#     与 `TowerDefenseZombieConfig.attack`。参照 mod 超级机枪读报僵尸用的是
#     attack=800 / hitpoints=1180，说明这两个就是「本体血量」与「啃食伤害」本体。
#   · hitpointsNearDeath=70 与参照 mod 完全一致（该值在引擎里是**濒死期掉血速率**
#     而非阈值：TowerDefenseCharacter.cs 里 `DealHurt(hitpointsNearDeath*delta/3)`；
#     内置普通僵尸 200/70 与参照 mod 1180/70 都用 70，故不随血量缩放）。
#
# 移速「快」= walkSpeedScale 2.0
#   · `TowerDefenseZombie.walkSpeedScale`（Prefab/TowerDefense/Character/TowerDefenseZombie.tscn:17
#     默认 1.0）写在**角色场景**上，与内置僵尸同位置（HitBoxDefinition 之后）。
#   · 手册文案口径来自 Translate.zh.translation：
#       普通僵尸 walkSpeedScale=1.0  → 移速：慢
#       橄榄球僵尸 walkSpeedScale=2.0 → 移速：快
#     ⇒ 内置自认的「快」就是 2.0（0.25=非常慢、0.4=巨人、1.0=慢、2.0~3.0=快）。
#
# 伤害类型「啃食」= attackType "Eat"
#   · `AttackComponentDefinition.attackType`，`[Export(Enum, "Default,Eat,Smash,Chomp")]`
#     默认就是 "Eat"；模组编辑器 XWAttackContactPresenter 给的标题是
#       普通 / 啃咬 / 砸击 / 吞咬   ← "Eat" 即「啃咬（啃食）」
#   · 内置普通僵尸的 AttackComponentZombieDefinition.tres 没写这一行 ⇒ 走类默认 "Eat"，
#     所以我们显式写出来是**等值覆盖**（零行为变化），只为把规格固化进包、让编辑器可见。
#
# 手册文案格式：照抄内置的「属性块」写法（Translate.zh.translation 里
#   TOWERDEFENSE_ZOMBIE_*_HANDBOOK_EXPRESTION 的真实文本），红色统一 cc241d：
#       血量：[color=cc241d]…[/color]
#       伤害：[color=cc241d]100/s（啃食）[/color]   ← 「（啃食）」就是伤害类型的展示口径
#       佩戴：[color=cc241d]---[/color]
#       类型：[color=cc241d]小型僵尸[/color]
#       移速：[color=cc241d]快[/color]
HITPOINTS = 1350.0
ATTACK = 100.0
NEAR_DEATH = 70.0                 # 濒死掉血速率，与内置/参照 mod 同值（不随血量缩放）
WALK_SPEED_SCALE = 2.0            # 快
ATTACK_TYPE = 'Eat'               # 啃食
ATTACK_INSTANCE_ID = 'character.attack.0'      # 与内置 AttackComponentZombieDefinition 同 id
ATTACK_TYPE_ID = 'AttackComponent'             # 覆盖时必须与内置一致（CanReplaceInheritedDefinition）
ATTACK_WIRE_INDEX = 0                          # 同上
ATTACK_DEFINITION_ID = 'builtin.component.attack.zombie.primary'
SPEED_LABEL = '快'
PHYSIQUE_LABEL = '小型僵尸'

LAUGH_FREEZE_SEC = 3.0            # 大笑控场时长（植物停止发射 + 暂停行动）
LAUGH_HOLD_SEC = 3.0              # 大笑立绘保持时长（= LaughWalk 剪辑 36 帧 @12fps）

# 动画剪辑名（与 nailong_skin.CLIP_SPECS 一致）
C_WALK = 'Walk1&Walk2'
C_IDLE = 'Idle1&Idle2'
C_EAT = 'Eat'
C_DIE = 'Death1&Death2'
C_DIEWATER = 'Waterdeath'
C_SWIM = 'Swim'

DESCRIBE = ('普通僵尸的移动 / 啃食 / 受击 / 死亡，外加大笑控场：出场后每 10 秒大笑一次，'
            '切到大笑形象并播奶龙笑声，一边笑一边照常往前走；'
            '同时全场植物被笑得僵直 3 秒、完全无法发射子弹。')

# 手册正文：散文段 + 内置同款「属性块」。属性块里的数值必须与 stage_config /
# stage_character_scene 实际写出的值一一对应，由 gate_attack_spec() 强制核对。
HANDBOOK = (
    '奶龙僵尸：本体 %d 血，一口 %d 的啃食伤害，跑起来比普通僵尸快一倍——'
    '但它真正的本事是笑。\n'
    '出场之后每 10 秒大笑一次，一笑就换上那副咧嘴大笑的样子、放出奶龙标志性的笑声，\n'
    '脚下可一步没停：这 %.0f 秒里它是边笑边正常往前走的。\n'
    '被它笑到的植物会僵在原地 %.0f 秒：既动不了，也发不出子弹。\n'
    '要是它正好走到坚果墙前面笑起来，这 %.0f 秒就是你补种的机会——'
    '或者你丢掉一排的机会。\n'
    '血量：[color=cc241d]%d[/color]\n'
    '伤害：[color=cc241d]%d/s（啃食）[/color]\n'
    '佩戴：[color=cc241d]---[/color]\n'
    '类型：[color=cc241d]%s[/color]\n'
    '移速：[color=cc241d]%s[/color]'
) % (int(HITPOINTS), int(ATTACK), LAUGH_FREEZE_SEC, LAUGH_FREEZE_SEC, LAUGH_FREEZE_SEC,
     int(HITPOINTS), int(ATTACK), PHYSIQUE_LABEL, SPEED_LABEL)

STORY = '「哈哈哈哈哈哈——」\n（植物们：……到底有什么好笑的？）'


# ==================================================================== 工具
def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


def w(path, text):
    """统一 LF / UTF-8 无 BOM 写出。"""
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'w', encoding='utf8', newline='\n') as f:
        f.write(text)
    return path


def _tres_str(s):
    """把 Python 文本转成 .tres 里合法的**单行**字符串字面量（不含外层引号）。

    Godot 的 .tres 是单行 key = value 语法：字符串里不能有裸换行，必须写成 `\\n` 转义。
    内置僵尸的手册文本就是这么存的 —— Translate.zh.translation 里能直接看到
    `血量：[color=cc241d]270[/color]\\n伤害：…\\n移速：…` 这种单个字符串内嵌 \\n 的写法。
    反斜杠、双引号同理要转义。**少了这一步，资源文件在 Godot 里根本解析不开。**
    """
    out = s.replace('\\', '\\\\').replace('"', '\\"')
    return out.replace('\r\n', '\\n').replace('\n', '\\n').replace('\r', '\\n')


def wb(path, blob):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, 'wb') as f:
        f.write(blob)
    return path


# ==================================================================== 1. 动画
def stage_animations():
    """调用 nailong_skin 生成 .dat/.tres/.png 并落到包内 Resources/Animations/。"""
    sys.path.insert(0, HERE)
    import nailong_skin as ns

    m = ns.build()
    dat = os.path.join(CACHE, '%s.dat' % ANIME)
    tres = os.path.join(CACHE, '%s.tres' % ANIME)
    png = os.path.join(CACHE, '%sAtlas.png' % ANIME)
    m['atlas'].save(png)
    blob = ns.write_dat(dat, m['atlas'], m['media'], m['frames'], m['clips'], m['frame_max'],
                        ground=m['ground'])
    ns.write_tres(tres, m['media'], m['frames'], m['clips'], m['frame_max'],
                  anime_basename=ANIME, atlas_name='%sAtlas.png' % ANIME,
                  ground=m['ground'])

    wb(os.path.join(MOD_DIR, P_ANIM_DAT), blob)
    shutil.copyfile(tres, os.path.join(MOD_DIR, P_ANIM_TRES))
    shutil.copyfile(png, os.path.join(MOD_DIR, P_ANIM_PNG))

    return dict(frame_max=m['frame_max'], clips=m['clips'], atlas=m['atlas'],
                frames=m['frames'], media=m['media'], feet=ns.FEET_Y,
                lifted=m['lifted'], dat_bytes=len(blob), ground=m['ground'],
                ground_clips=list(ns.GROUND_CLIPS),
                ground_px_per_frame=ns.GROUND_PX_PER_FRAME,
                frame_rate=ns.FRAME_RATE)


# ==================================================================== 2. 音频
def stage_audio():
    """MP3 → 16bit PCM WAV，保持 44.1kHz 立体声、时长与解码后完全一致。"""
    import soundfile as sf
    import numpy as np

    data, rate = sf.read(MP3, dtype='int16', always_2d=True)
    # 注意：libsndfile 对 MP3 的 sf.info().frames 是按码率估算值（176797），
    # 真正解码出来的帧数是 libsndfile 去掉编码器补零后的长度（176256 ≈ 3.9967s）。
    # 以前者做基准会把「正确的无损转码」误判成丢帧。
    n_frames = int(data.shape[0])
    buf = io.BytesIO()
    # soundfile 写 WAV 默认 subtype 由 dtype 推出：int16 → PCM_16
    sf.write(buf, data, rate, format='WAV', subtype='PCM_16')
    blob = buf.getvalue()
    wb(os.path.join(MOD_DIR, P_AUDIO), blob)
    return dict(rate=rate, channels=1 if data.ndim == 1 else int(data.shape[1]),
                frames=n_frames,
                src_duration=n_frames / float(rate),
                estimated_frames=int(sf.info(MP3).frames),
                wav_bytes=len(blob),
                wav_seconds=n_frames / float(rate))


# ==================================================================== 3. 文本资源
def stage_config():
    w(os.path.join(MOD_DIR, P_CONFIG), '''\
[gd_resource type="Resource" script_class="TowerDefenseZombieConfig" format=3]

[ext_resource type="Resource" path="%s" id="1"]
[ext_resource type="PackedScene" path="%s" id="2"]
[ext_resource type="Resource" path="%s" id="3"]
[ext_resource type="Script" path="%s" id="4"]

[resource]
script = ExtResource("4")
attack = %.1f
name = "%s"
hitpointsNearDeath = %.1f
hitpoints = %.1f
damagePointData = ExtResource("3")
armorData = ExtResource("1")
customData = null
ashScene = ExtResource("2")
homeWorld = 1
cost = 50
plantGridType = [-1]
maskFlags = 9
metadata/_custom_type_script = "%s"
''' % (G_ARMOR_DATA, G_ASH, G_DMG_DATA, S_CONFIG_SCRIPT,
       ATTACK, CHAR, NEAR_DEATH, HITPOINTS, S_CONFIG_SCRIPT))


def stage_packet():
    w(os.path.join(MOD_DIR, P_PACKET), '''\
[gd_resource type="Resource" script_class="TowerDefensePacketConfig" format=3]

[ext_resource type="Resource" path="../../Config/TowerDefense%s.tres" id="1"]
[ext_resource type="Script" path="%s" id="2"]

[resource]
script = ExtResource("2")
saveKey = "%s"
unlockCheckList = []
name = "%s"
describe = "%s"
handbookDescribe = "%s"
handbookStory = "%s"
packetAnimeClip = "%s"
packetAnimeOffset = Vector2(25, 60)
packetAnimeScale = Vector2(0.75, 0.75)
characterConfig = ExtResource("1")
type = 6
override = null
metadata/_custom_type_script = "%s"
''' % (CHAR, S_PACKET_SCRIPT, CHAR, MOD_NAME, _tres_str(DESCRIBE),
       _tres_str(HANDBOOK), _tres_str(STORY), C_IDLE, S_PACKET_SCRIPT))


def stage_card():
    """选卡用的卡面（与 Packet 内容一致，只是相对路径层级不同）。"""
    w(os.path.join(MOD_DIR, P_CARD), '''\
[gd_resource type="Resource" script_class="TowerDefensePacketConfig" format=3]

[ext_resource type="Resource" path="../Characters/Zombies/%s/Config/TowerDefense%s.tres" id="1"]
[ext_resource type="Script" path="%s" id="2"]

[resource]
script = ExtResource("2")
saveKey = "%s"
unlockCheckList = []
name = "%s"
describe = "%s"
handbookDescribe = "%s"
handbookStory = "%s"
packetAnimeClip = "%s"
packetAnimeOffset = Vector2(25, 60)
packetAnimeScale = Vector2(0.75, 0.75)
characterConfig = ExtResource("1")
type = 6
override = null
metadata/_custom_type_script = "%s"
''' % (CHAR, CHAR, S_PACKET_SCRIPT, CHAR, MOD_NAME, _tres_str(DESCRIBE),
       _tres_str(HANDBOOK), _tres_str(STORY), C_IDLE, S_PACKET_SCRIPT))


def stage_cset():
    """本地组件集 = ParentSet(内置僵尸组件集) + 一个「攻击组件等值覆盖」。

    拍平语义（CharacterComponentSet.AppendFlattenedDefinitions / MergeDefinition）：
      · 先摊平父级定义，再按 InstanceId 合入本地 Components；
      · 本地 InstanceId 命中父级时**替换**，但要求 ComponentTypeId 与 WireIndex
        完全一致（CanReplaceInheritedDefinition），否则只报错、不替换。
    ⇒ 我们给出 InstanceId = "character.attack.0" / ComponentTypeId = "AttackComponent" /
      WireIndex = 0 —— 与内置 AttackComponentZombieDefinition 逐字一致，
      唯一多出来的是显式的 attackType = "Eat"（内置走类默认值，也是 "Eat"）
      ⇒ 行为零变化，只是把「伤害类型 = 啃食」固化进包、让编辑器能显示。
    """
    w(os.path.join(MOD_DIR, P_CSET), '''\
[gd_resource type="Resource" script_class="CharacterComponentSet" format=3]

[ext_resource type="Resource" path="%s" id="1"]
[ext_resource type="Script" path="%s" id="2"]
[ext_resource type="Resource" path="./%sAttackComponentDefinition.tres" id="3"]

[resource]
script = ExtResource("2")
ParentSet = ExtResource("1")
Components = [ExtResource("3")]
''' % (S_ZOMBIE_CSET, S_CSET_SCRIPT, CHAR))


def stage_attack_def():
    """攻击组件定义：显式声明攻击类型 attackType = "Eat"（啃食）。

    字段照抄内置 Script/Component/TowerDefense/Character/AttackComponent/
    AttackComponentZombieDefinition.tres，另加一行 attackType。
    `useParentHitBox = true` / `checkLine = true` 是内置僵尸啃食判定的原值，必须保留。
    """
    w(os.path.join(MOD_DIR, P_ATTACK_DEF), '''\
[gd_resource type="Resource" script_class="AttackComponentDefinition" format=3]

[ext_resource type="Resource" path="%s" id="1"]
[ext_resource type="Script" path="%s" id="2"]

[resource]
script = ExtResource("2")
attackType = "%s"
useParentHitBox = true
checkLine = true
ComponentTypeId = "%s"
DefinitionId = "%s"
InstanceId = "%s"
WireIndex = %d
StateMachineDefinition = ExtResource("1")
LegacyNodeNames = [&"AttackComponent"]
''' % (S_ATTACK_SM, S_ATTACK_DEF_SCRIPT, ATTACK_TYPE, ATTACK_TYPE_ID,
       ATTACK_DEFINITION_ID, ATTACK_INSTANCE_ID, ATTACK_WIRE_INDEX))


def stage_sprite_scene():
    """独立自制皮肤精灵场景。

    offset 必须是 Vector2(0, 0)：引擎渲染时会 transform.Translated(offset)
    （AdobeAnimateSprite.cs:7044），我们的 node-local 几何是按不带 offset 烘焙的。
    不设 Animation/LayerVisible/* —— 默认全层可见，两个 pseudo 层（AnimeClips/
    AnimeEvents）没有 slice，画不出东西，零风险。
    """
    # 槽位位置：按奶龙实际比例给（站立 bbox x∈[-33,30] y∈[-78,45]，头在左上部）
    slots = [
        ('HeadSlot', (-14.0, -44.0)),
        ('ArmSlot', (16.0, -25.0)),
        ('ConeSlot', (-18.0, -70.0)),
        ('BucketSlot', (-18.0, -64.0)),
        ('ScreendoorSlot', (-30.0, -10.0)),
        ('GroundSlot', (-31.0, -40.0)),
    ]
    L = []
    L.append('[gd_scene load_steps=3 format=3]')
    L.append('')
    L.append('[ext_resource type="Script" path="%s" id="1_sprite"]' % S_SPRITE_SCRIPT)
    L.append('[ext_resource type="Resource" path="../../../../../%s" id="2_data"]' % P_ANIM_TRES)
    L.append('')
    L.append('[node name="%sSprite" type="Node2D"]' % CHAR)
    L.append('script = ExtResource("1_sprite")')
    L.append('flashAnimeData = ExtResource("2_data")')
    L.append('useMultiMesh = true')
    L.append('offset = Vector2(0, 0)')
    L.append('trueFrameRate = 180.0')
    L.append('useTween = false')
    L.append('Animation/Clip = "Idle1"')
    L.append('metadata/mod_resource_kind = "CharacterSprite"')
    L.append('metadata/mod_preview_source = '
             '"自制皮肤：站立图 + 大笑图 两张素材，10 个剪辑 / 132 帧（离线程序化生成）"')
    L.append('')
    for i, (nm, pos) in enumerate(slots):
        if i:
            L.append('')
        L.append('[node name="%s" type="Node2D" parent="."]' % nm)
        L.append('position = Vector2(%.2f, %.2f)' % pos)
    L.append('')
    w(os.path.join(MOD_DIR, P_SPRITE), '\n'.join(L))


def stage_character_scene():
    """角色场景：mirror 内置 TowerDefenseZombieNormal.tscn（但不覆盖 script，
    直接继承 TowerDefenseZombie.cs 的通用僵尸行为）。

    ComponentSet 放在属性列表第一位（与原版/其它 mod 一致）。
    """
    L = []
    L.append('[gd_scene format=3]')
    L.append('')
    L.append('[ext_resource type="PackedScene" path="%s" id="1"]' % S_ZOMBIE)
    L.append('[ext_resource type="Resource" path="./%sComponentSet.tres" id="2"]' % CHAR)
    L.append('[ext_resource type="Resource" path="%s" id="3"]' % G_HITBOX)
    L.append('[ext_resource type="Resource" path="../Config/TowerDefense%s.tres" id="4"]' % CHAR)
    L.append('[ext_resource type="Resource" path="%s" id="5"]' % G_DMG_ARM)
    L.append('[ext_resource type="Resource" path="%s" id="6"]' % G_ARMOR['BlackHelmet'])
    L.append('[ext_resource type="Resource" path="%s" id="7"]' % G_ARMOR['Bucket'])
    L.append('[ext_resource type="Resource" path="%s" id="8"]' % G_ARMOR['Cone'])
    L.append('[ext_resource type="Resource" path="%s" id="9"]' % G_DMG_HEAD)
    L.append('[ext_resource type="Resource" path="%s" id="10"]' % G_ARMOR['Helmet'])
    L.append('[ext_resource type="Resource" path="%s" id="11"]' % G_ARMOR['Screendoor'])
    L.append('[ext_resource type="Resource" path="%s" id="12"]' % G_ARMOR['SpecialHelmet'])
    L.append('[ext_resource type="PackedScene" path="../Sprite/%s.tscn" id="13"]' % CHAR)
    L.append('')
    L.append('[node name="%s" node_paths=PackedStringArray("sprite", "headSlot") '
             'instance=ExtResource("1")]' % CHAR)
    L.append('ComponentSet = ExtResource("2")')
    L.append('HitBoxDefinition = ExtResource("3")')
    # 移速：快。写在角色场景上（内置僵尸都写这儿，位置紧随 HitBoxDefinition）。
    L.append('walkSpeedScale = %.1f' % WALK_SPEED_SCALE)
    L.append('walkAnimeClip = "%s"' % C_WALK)
    L.append('swimAnimeClip = "%s"' % C_SWIM)
    L.append('dieAnimeClip = "%s"' % C_DIE)
    L.append('dieWaterAnimeClip = "%s"' % C_DIEWATER)
    L.append('attackAnimeClip = "%s"' % C_EAT)
    L.append('waterHeight = 25.0')
    L.append('idleAnimeClip = "%s"' % C_IDLE)
    L.append('config = ExtResource("4")')
    L.append('sprite = NodePath("SpriteGroup/TransformPoint/%s")' % CHAR)
    L.append('headSlot = NodePath("SpriteGroup/TransformPoint/%s/HeadSlot")' % CHAR)
    L.append('damagePart = {')
    L.append('"Arm": ExtResource("5"),')
    L.append('"BlackHelmet": ExtResource("6"),')
    L.append('"Bucket": ExtResource("7"),')
    L.append('"Cone": ExtResource("8"),')
    L.append('"Head": ExtResource("9"),')
    L.append('"Helmet": ExtResource("10"),')
    L.append('"Screendoor": ExtResource("11"),')
    L.append('"SpecialHelmet": ExtResource("12")')
    L.append('}')
    L.append('damagePartSlot = {')
    L.append('"Arm": NodePath("SpriteGroup/TransformPoint/%s/ArmSlot"),' % CHAR)
    L.append('"BlackHelmet": NodePath("SpriteGroup/TransformPoint/%s/HeadSlot"),' % CHAR)
    L.append('"Bucket": NodePath("SpriteGroup/TransformPoint/%s/BucketSlot"),' % CHAR)
    L.append('"Cone": NodePath("SpriteGroup/TransformPoint/%s/ConeSlot"),' % CHAR)
    L.append('"Head": NodePath("SpriteGroup/TransformPoint/%s/HeadSlot"),' % CHAR)
    L.append('"Helmet": NodePath("SpriteGroup/TransformPoint/%s/HeadSlot"),' % CHAR)
    L.append('"Screendoor": NodePath("SpriteGroup/TransformPoint/%s/ScreendoorSlot"),' % CHAR)
    L.append('"SpecialHelmet": NodePath("SpriteGroup/TransformPoint/%s/HeadSlot")' % CHAR)
    L.append('}')
    L.append('metadata/mod_resource_kind = "Character"')
    L.append('metadata/mod_display_name = "%s"' % MOD_NAME)
    L.append('metadata/mod_character_category = "Zombie"')
    L.append('metadata/mod_character_config_path = "../Config/TowerDefense%s.tres"' % CHAR)
    L.append('metadata/mod_character_sprite_scene = "../Sprite/%s.tscn"' % CHAR)
    L.append('')
    # 与内置普通僵尸一模一样的摆放：TransformPoint(12,33) + sprite(-12,-33) ⇒ 净 (0,0)
    L.append('[node name="TransformPoint" parent="SpriteGroup" index="0"]')
    L.append('position = Vector2(12, 33)')
    L.append('')
    L.append('[node name="%s" parent="SpriteGroup/TransformPoint" index="0" '
             'instance=ExtResource("13")]' % CHAR)
    L.append('position = Vector2(-12, -33)')
    L.append('')
    L.append('[editable path="SpriteGroup/TransformPoint/%s"]' % CHAR)
    L.append('')
    w(os.path.join(MOD_DIR, P_SCENE), '\n'.join(L))


# ==================================================================== 4. 清单
def stage_mod_json():
    resources = [P_ANIM_DAT, P_ANIM_TRES, P_ANIM_PNG, P_AUDIO, P_CARD,
                 P_CONFIG, P_PACKET, P_SCENE, P_CSET, P_ATTACK_DEF, P_SPRITE, P_DLL]
    manifest = {
        'schemaVersion': 2,
        'id': MOD_ID,
        'name': MOD_NAME,
        'version': VERSION,
        'author': AUTHOR,
        'description': DESCRIBE + '（含托管运行时插件 Runtime/ModAssembly.dll）',
        'dependencies': [],
        'conflicts': [],
        'provides': {
            # Audio 必须显式声明：否则 ModLoader 会走
            # "resource is not unambiguously declared by manifest" 静默丢弃音频候选。
            'Audio': [AUDIO_KEY],
            'Character': [CHAR],
            'CharacterSprite': [CHAR],
            'Packet': [CHAR],
        },
        'overrides': {},
        'scripts': [],
        'runtimeAssembly': P_DLL,
        'runtimeEntryType': ENTRY,
        'runtimeApiVersion': 1,
        'runtimeAssemblyPolicy': 'optional',
        'blueprints': [],
        'translations': [],
        'resources': sorted(resources),
    }
    w(os.path.join(MOD_DIR, 'mod.json'), json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')


def stage_project_file():
    """奶龙僵尸.pvzmodeproject —— 编辑器工程描述。时间戳沿用已存在的值以保持幂等。"""
    path = os.path.join(MOD_DIR, P_PROJ)
    ts = None
    if os.path.exists(path):
        try:
            old = json.load(open(path, encoding='utf-8'))
            ts = (old.get('CreatedDate'), old.get('LastModifiedDate'))
        except Exception:
            ts = None
    if not ts or not ts[0]:
        now = datetime.datetime.now().astimezone().isoformat()
        ts = (now, now)
    obj = {
        'Name': MOD_NAME,
        'Version': VERSION,
        'Author': AUTHOR,
        'Description': '新增僵尸「%s」（数据 + 托管运行时插件）' % MOD_NAME,
        'ExportDirectory': MODS_DIR.replace('\\', '/') + '/',
        'GameDirectory': '',
        'CreatedDate': ts[0],
        'LastModifiedDate': ts[1],
    }
    w(path, json.dumps(obj, ensure_ascii=True, indent=2) + '\n')


# ==================================================================== 5. 运行时
def stage_runtime(check_mode=False):
    """调用 build_runtime.py 重新编译托管插件（确定性构建），再拷进包内。"""
    import subprocess
    cmd = [sys.executable, 'build_runtime.py']
    if check_mode:
        cmd.append('--check')
    godot_ref = os.path.join(r'D:\zzz\植物大战僵尸杂交版0.28.1',
                             '植物大战僵尸杂交重制版', 'data_PlantsVsZombies_windows_x86_64')
    if os.path.isdir(godot_ref):
        cmd += ['--godot-ref-dir', godot_ref]
    r = subprocess.run(cmd, cwd=RT_SRC, capture_output=True, text=True, encoding='utf8',
                       errors='replace')
    print('  [runtime] ' + '\n            '.join((r.stdout or '').strip().splitlines()))
    if r.returncode != 0:
        raise SystemExit('build_runtime.py failed (rc=%d)\n%s\n%s'
                         % (r.returncode, r.stdout, r.stderr))
    dll = os.path.join(MOD_DIR, P_DLL)
    if not os.path.exists(dll):
        raise SystemExit('ModAssembly.dll missing at %s' % dll)
    return dict(dll_bytes=os.path.getsize(dll), dll_sha256=_sha256(dll)[:16])


# ==================================================================== 6. 闸门
def _walk_files(root):
    out = []
    for dp, _dn, fn in os.walk(root):
        for n in fn:
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, root).replace('\\', '/')
            if rel == os.path.basename(MANIFEST):
                continue
            out.append(rel)
    return sorted(out)


def compute_manifest():
    root = MOD_DIR
    return {rel: _sha256(os.path.join(root, rel)) for rel in _walk_files(root)}


def gate_structure():
    """结构闸门：文件齐全 + 角色包路径段数正确 + 脚本引用全 res:// + 无 GDScript。"""
    errs, warns = [], []
    required = [P_ANIM_DAT, P_ANIM_TRES, P_ANIM_PNG, P_CARD, P_CONFIG, P_PACKET,
                P_SCENE, P_CSET, P_ATTACK_DEF, P_SPRITE, P_AUDIO, P_DLL, 'mod.json', P_PROJ]
    for rel in required:
        if not os.path.exists(os.path.join(MOD_DIR, rel)):
            errs.append('missing file: %s' % rel)

    # ModLoader.TryInferCharacterScene 要求恰好 6 段
    for rel, folder in ((P_SCENE, 'Scene'), (P_SPRITE, 'Sprite')):
        seg = rel.split('/')
        if len(seg) != 6:
            errs.append('%s must be 6 path segments, got %d' % (rel, len(seg)))
        if seg[4] != folder:
            errs.append('%s must sit in %s/, got %s' % (rel, folder, seg[4]))
        if os.path.splitext(seg[5])[0] != CHAR:
            errs.append('%s stem must equal %s' % (rel, CHAR))

    # 角色包内脚本引用必须 res://，且不得出现 GDScript/CSharpScript
    base = os.path.join(MOD_DIR, P_BASE)
    for dp, _dn, fn in os.walk(base):
        for n in fn:
            if not n.endswith(('.tscn', '.tres')):
                continue
            p = os.path.join(dp, n)
            rel = os.path.relpath(p, MOD_DIR).replace('\\', '/')
            txt = open(p, encoding='utf8').read()
            for bad in ('type="GDScript"', 'type="CSharpScript"'):
                if bad in txt:
                    errs.append('%s contains %s (ModLoader rejects)' % (rel, bad))
            for line in txt.splitlines():
                if line.startswith('[ext_resource') and 'type="Script"' in line:
                    q = line.split('path="', 1)
                    if len(q) < 2 or not q[1].startswith('res://'):
                        errs.append('%s has non-res:// Script ext_resource: %s' % (rel, line))

    # ── 文本字面量必须单行 ────────────────────────────────────────────────
    # .tres/.tscn 是单行 key = value 语法；字符串里出现裸换行会让 Godot **整个资源解析失败**。
    # （曾经真的踩过：手册正文写成多行散文，包能打出来、闸门全绿，进游戏才发现读不了。）
    # 判定：任何 `声明的key = "…"` 行必须也以 `"` 收尾，且该行引号数为偶数。
    for rel in _walk_files(MOD_DIR):
        if not rel.endswith(('.tres', '.tscn')):
            continue
        p = os.path.join(MOD_DIR, rel)
        for ln, line in enumerate(open(p, encoding='utf8').read().splitlines(), 1):
            if ' = "' not in line or line.lstrip().startswith('['):
                continue
            if line.count('"') % 2 != 0 or not line.rstrip().endswith('"'):
                errs.append('%s:%d quoted string must be single-line (use \\n escapes): %s'
                            % (rel, ln, line[:60]))

    # mod.json 自检
    mj = json.load(open(os.path.join(MOD_DIR, 'mod.json'), encoding='utf-8'))
    if mj['runtimeAssembly'] != 'Runtime/ModAssembly.dll':
        errs.append('runtimeAssembly must be literally Runtime/ModAssembly.dll')
    if mj['runtimeApiVersion'] != 1:
        errs.append('runtimeApiVersion must be 1')
    if '.' in mj['runtimeEntryType']:
        errs.append('runtimeEntryType must have no namespace')
    for cat in ('Audio', 'Character', 'CharacterSprite', 'Packet'):
        if not mj['provides'].get(cat):
            errs.append('provides.%s missing' % cat)
    # resources 清单必须覆盖包内所有「资源」文件
    # （mod.json / *.pvzmodeproject 属于包元数据，参照内置 mod 的写法不列入 resources）
    listed = set(mj['resources'])
    actual = {r for r in _walk_files(MOD_DIR)
              if not r.startswith('.')
              and r != 'mod.json'
              and not r.endswith('.pvzmodeproject')}
    for rel in sorted(actual - listed):
        errs.append('file not declared in mod.json resources: %s' % rel)
    for rel in sorted(listed - actual):
        errs.append('mod.json declares a missing resource: %s' % rel)
    return errs, warns


def gate_geometry(anim):
    """.dat/.tres 结构闸门 + 接地线闸门 + 与 .dat 的一致性。"""
    errs = []
    dat = os.path.join(MOD_DIR, P_ANIM_DAT)
    tres = os.path.join(MOD_DIR, P_ANIM_TRES)
    buf = open(dat, 'rb').read()
    # 头部布局：f32 frameRate@0, u16 frameMax@4, u16 atlasW@6, u16 atlasH@8,
    #           i64 pixelByteCount@10  ⇒ 共 18 字节（无对齐填充）
    import struct
    fr, fm, aw, ah = struct.unpack_from('<fHHH', buf, 0)
    pb, = struct.unpack_from('<q', buf, 10)
    if pb != aw * ah * 4:
        errs.append('.dat pixelByteCount %d != %d*%d*4' % (pb, aw, ah))
    if 18 + pb > len(buf):
        errs.append('.dat truncated: header+pixels=%d > file=%d' % (18 + pb, len(buf)))
    if int(round(fr)) != 12:
        errs.append('.dat frameRate %r != 12' % fr)
    if fm != anim['frame_max']:
        errs.append('.dat frameMax %d != model %d' % (fm, anim['frame_max']))
    if (aw, ah) != (anim['atlas'].width, anim['atlas'].height):
        errs.append('.dat atlas %dx%d != model %dx%d'
                    % (aw, ah, anim['atlas'].width, anim['atlas'].height))

    d = anim
    if d['frame_max'] != 168:
        errs.append('frameMax expected 168, got %d' % d['frame_max'])
    clips = d['clips']
    for nm in ('Idle1', 'Idle2', 'Walk1', 'Walk2', 'Eat', 'Laugh', 'LaughWalk',
               'Death1', 'Death2', 'Swim', 'Waterdeath', 'Idle'):
        if nm not in clips:
            errs.append('clip missing: %s' % nm)
    if clips.get('Laugh', (0, 0))[1] - clips.get('Laugh', (0, 0))[0] + 1 != 16:
        errs.append('Laugh must be 16 frames')
    # LaughWalk：3 秒 = 36 帧 @12fps，且必须是 12 的整数倍（整周期播完）
    lw = clips.get('LaughWalk', (0, 0))
    if lw[1] - lw[0] + 1 != 36:
        errs.append('LaughWalk must be 36 frames (3.0s @12fps), got %d'
                    % (lw[1] - lw[0] + 1))

    # 接地线：站姿剪辑的最低可见像素必须落在 FEET_Y 上，不许穿地
    from PIL import Image
    atlas = Image.open(os.path.join(MOD_DIR, P_ANIM_PNG)).convert('RGBA')
    media, frames, feet = d['media'], d['frames'], d['feet']

    def bottom(el):
        _n, (rx, ry, rw, rh) = media[el['mediaId']]
        bb = atlas.crop((int(rx), int(ry), int(rx + rw), int(ry + rh))).getbbox()
        ys = [el['xy'] * vx + el['yy'] * vy + el['oy']
              for vx, vy in ((bb[0], bb[1]), (bb[2] - 1, bb[1]),
                             (bb[0], bb[3] - 1), (bb[2] - 1, bb[3] - 1))]
        return max(ys)

    for nm in ('Idle1', 'Idle2', 'Walk1', 'Walk2', 'Eat', 'Laugh', 'LaughWalk',
               'Swim', 'Death1'):
        s0, s1 = clips[nm]
        bots = [bottom(frames[f]) for f in range(s0, s1 + 1)]
        if max(bots) > feet + 0.75:
            errs.append('%s sinks below ground: max bottom=%.2f > %.2f' % (nm, max(bots), feet))
        if max(bots) < feet - 6.0:
            errs.append('%s floats above ground: max bottom=%.2f << %.2f' % (nm, max(bots), feet))
    # 死亡剪辑应当沉下去（设计预期），反向断言，防止误"修好"
    for nm in ('Death2', 'Waterdeath'):
        s0, s1 = clips[nm]
        if bottom(frames[s1]) <= feet + 1.0:
            errs.append('%s should sink/drop below the ground line by design' % nm)

    # .tres 与 .dat 的 frameMax/clip 区间一致
    txt = open(tres, encoding='utf8').read()
    if 'frameMax = %d' % d['frame_max'] not in txt:
        errs.append('.tres frameMax disagrees with model (%d)' % d['frame_max'])
    for nm, (s0, s1) in clips.items():
        if 'Vector2i(%d, %d)' % (s0, s1) not in txt:
            errs.append('.tres clip %s = (%d,%d) not found in file' % (nm, s0, s1))
    # 合成图引用必须指向包内相对路径
    if 'animeFile = "./%s.dat"' % ANIME not in txt:
        errs.append('.tres animeFile must be ./%s.dat' % ANIME)
    # 精灵场景必须 offset=(0,0) 且引用包内 .tres
    spr = open(os.path.join(MOD_DIR, P_SPRITE), encoding='utf8').read()
    if 'offset = Vector2(0, 0)' not in spr:
        errs.append('sprite scene offset must be Vector2(0, 0)')
    if '../../../../../%s' % P_ANIM_TRES not in spr:
        errs.append('sprite scene must reference ../../../../../%s' % P_ANIM_TRES)
    if 'Animation/LayerVisible' in spr:
        errs.append('sprite scene must not set Animation/LayerVisible (length mismatch risk)')
    return errs


def gate_audio(audio):
    errs = []
    import soundfile as sf
    p = os.path.join(MOD_DIR, P_AUDIO)
    i = sf.info(p)
    if i.samplerate != 44100:
        errs.append('wav samplerate %d != 44100' % i.samplerate)
    if i.channels != audio['channels']:
        errs.append('wav channels %d != source %d' % (i.channels, audio['channels']))
    if i.frames != audio['frames']:
        errs.append('wav frames %d != source decoded %d' % (i.frames, audio['frames']))
    if i.subtype != 'PCM_16':
        errs.append('wav subtype %s != PCM_16' % i.subtype)
    if abs(i.duration - audio['src_duration']) > 1e-6:
        errs.append('wav duration %.6f != source %.6f' % (i.duration, audio['src_duration']))
    # 音效键必须等于文件名 stem（ModLoader: key = Path.GetFileNameWithoutExtension）
    if os.path.splitext(os.path.basename(P_AUDIO))[0] != AUDIO_KEY:
        errs.append('audio filename stem must equal %s' % AUDIO_KEY)
    return errs


def gate_ground_motion(anim):
    """根运动闸门：证明「僵尸真的能往前走」。

    这是本轮需求的**事实核对**，而且直接读**落盘的 .dat 字节**（不是读模型），
    所以「模型对了但写歪了」也会被抓到。

    验四件事：
      1. `.dat` 里存在名为 `_ground` 的层（GroundMoveComponent 按名解析，
         没有它 = 一步都走不了）；
      2. 该层元素 alpha = 0（只做根运动，不能画出来）；
      3. 带根运动的每个剪辑里，位移是**单调**的（= 一条完整锯齿，不在剪辑中间回跳
         —— 中间回跳会被当成倒着走一大步）；
      4. 每个剪辑的**总位移**与配置的速率一致，且**回跳只出现在剪辑边界**。
    """
    import struct
    errs = []
    clipped = anim.get('clips') or {}
    want_clips = set(anim.get('ground_clips') or [])
    step = float(anim.get('ground_px_per_frame') or 0.0)

    # ---- 解析 .dat（与 anime_io.parse_dat 同布局，这里只取 layer 段）----
    buf = open(os.path.join(MOD_DIR, P_ANIM_DAT), 'rb').read()
    off = 0
    _fr, fmx, _aw, _ah = struct.unpack_from('<fHHH', buf, off); off += 4 + 6
    pbc, = struct.unpack_from('<q', buf, off); off += 8
    off += pbc
    nmedia, = struct.unpack_from('<H', buf, off); off += 2
    for _ in range(nmedia):
        n, = struct.unpack_from('<I', buf, off); off += 4 + n + 16
    nlayer, = struct.unpack_from('<H', buf, off); off += 2
    layers = {}
    for _ in range(nlayer):
        n, = struct.unpack_from('<I', buf, off); off += 4
        lname = buf[off:off + n].decode('utf8'); off += n
        per_frame = []
        for _f in range(fmx):
            cnt, = struct.unpack_from('<H', buf, off); off += 2
            els = []
            for _e in range(cnt):
                mid, = struct.unpack_from('<H', buf, off)
                xx, xy, yx, yy = struct.unpack_from('<ffff', buf, off + 2)
                ox, oy = struct.unpack_from('<ff', buf, off + 18)
                alpha, = struct.unpack_from('<I', buf, off + 26)
                els.append(dict(mediaId=mid, xx=xx, xy=xy, yx=yx, yy=yy,
                                ox=ox, oy=oy, alpha=alpha))
                off += 30
            per_frame.append(els)
        layers[lname] = per_frame

    # 1) 层存在
    if '_ground' not in layers:
        errs.append('.dat has no "_ground" layer — GroundMoveComponent cannot resolve it, '
                    'the zombie will NEVER move forward')
        return errs

    gf = layers['_ground']
    # 2) 不可见
    for f, els in enumerate(gf):
        for el in els:
            if el['alpha'] != 0:
                errs.append('_ground frame %d alpha=%d, must be 0 (invisible)' % (f, el['alpha']))
                break
        else:
            continue
        break

    # 3) 每个剪辑：单调递增；总位移 = 帧数 × 每帧位移
    for nm in sorted(want_clips):
        s0, s1 = clipped[nm]
        n = s1 - s0 + 1
        vals = [gf[f][0]['ox'] if gf[f] else None for f in range(s0, s1 + 1)]
        if any(v is None for v in vals):
            errs.append('%s: _ground slice missing in some frame' % nm)
            continue
        for k in range(1, n):
            if vals[k] <= vals[k - 1]:
                errs.append('%s: _ground must move monotonically (frame %d: %.4f -> %.4f)'
                            % (nm, s0 + k, vals[k - 1], vals[k]))
                break
        total = vals[-1] - vals[0] + step      # 第 k 帧 = (k+1)·step
        if abs(total - n * step) > 1e-3:
            errs.append('%s: _ground total drift %.4f != %d frames * %.4f = %.4f'
                        % (nm, total, n, step, n * step))

    # 4) 不在带根运动的剪辑里时，必须没有位移（否则原地站着也会滑走）
    for nm in ('Idle1', 'Idle2', 'Eat', 'Death1', 'Death2', 'Waterdeath'):
        s0, s1 = clipped[nm]
        if any(gf[f] for f in range(s0, s1 + 1)):
            errs.append('%s must NOT have _ground drift (character is not walking)' % nm)

    # 5) 回跳只在剪辑边界：任意相邻两帧的位移只能是 +step，或落在剪辑边界上
    bounds = set()
    for nm in want_clips:
        s0, s1 = clipped[nm]
        bounds.add(s1 + 1)          # 下一帧是边界的「回跳帧」
    for f in range(1, fmx):
        prev, cur = gf[f - 1], gf[f]
        if not prev or not cur:
            continue
        d = cur[0]['ox'] - prev[0]['ox']
        if d < 0 and f not in bounds:
            errs.append('_ground reset at frame %d is NOT on a clip boundary '
                        '(would look like a backwards jump)' % f)
            break
    return errs


def gate_runtime_order():
    """角色场景里 ComponentSet 必须出现在其它 [Export] 之前（与内置/其它 mod 一致）。"""
    errs = []
    txt = open(os.path.join(MOD_DIR, P_SCENE), encoding='utf8').read()
    body = txt.split('instance=ExtResource("1")]\n', 1)
    if len(body) < 2:
        errs.append('character scene node header not found')
        return errs
    props = [l.split(' = ', 1)[0].strip() for l in body[1].splitlines()
             if ' = ' in l and not l.lstrip().startswith('[')]
    if not props or props[0] != 'ComponentSet':
        errs.append('ComponentSet must be the first property, got %r' % (props[:3],))
    if 'script' in props:
        errs.append('character scene should not override script (inherit TowerDefenseZombie.cs)')
    return errs


def gate_attack_spec():
    """数值 / 速度 / 伤害类型 规格闸门。

    这是本次需求的**事实核对**：把「说明书里写的」与「引擎真正读的」逐条对上，
    任何一边被改坏都会在这里炸——防止出现「手册写了 1350、实际还是 200」这种漂移。
    """
    errs = []

    # ---- 1) 本体数值：攻击力 / 血量 / 濒死速率
    cfg = open(os.path.join(MOD_DIR, P_CONFIG), encoding='utf8').read()
    want = {'attack': ATTACK, 'hitpoints': HITPOINTS, 'hitpointsNearDeath': NEAR_DEATH}
    for key, val in want.items():
        m = re.search(r'^%s = ([-\d.]+)$' % key, cfg, re.M)
        if not m:
            errs.append('config missing %s' % key)
        elif float(m.group(1)) != val:
            errs.append('config %s = %s, expected %s' % (key, m.group(1), val))
    if 'smashAttack' in cfg:
        errs.append('config should not set smashAttack for a chewing zombie')

    # ---- 2) 移速：角色场景上的 walkSpeedScale
    scn = open(os.path.join(MOD_DIR, P_SCENE), encoding='utf8').read()
    m = re.search(r'^walkSpeedScale = ([-\d.]+)$', scn, re.M)
    if not m:
        errs.append('character scene missing walkSpeedScale (speed tier)')
    elif float(m.group(1)) != WALK_SPEED_SCALE:
        errs.append('walkSpeedScale = %s, expected %s' % (m.group(1), WALK_SPEED_SCALE))

    # ---- 3) 伤害类型：攻击组件定义 attackType，且覆盖三要素必须与内置一致
    ad = open(os.path.join(MOD_DIR, P_ATTACK_DEF), encoding='utf8').read()
    m = re.search(r'^attackType = "([^"]*)"$', ad, re.M)
    if not m:
        errs.append('attack definition missing attackType')
    elif m.group(1) != ATTACK_TYPE:
        errs.append('attackType = %r, expected %r' % (m.group(1), ATTACK_TYPE))
    for key, val in (('InstanceId', ATTACK_INSTANCE_ID),
                     ('ComponentTypeId', ATTACK_TYPE_ID),
                     ('WireIndex', str(ATTACK_WIRE_INDEX))):
        pat = r'^%s = "?([^"\n]*?)"?$' % key
        mm = re.search(pat, ad, re.M)
        if not mm:
            errs.append('attack definition missing %s' % key)
        elif mm.group(1).strip() != val:
            errs.append('attack definition %s = %r, expected %r'
                        % (key, mm.group(1).strip(), val))
    # 内置僵尸的啃食判定开关：改写会静默改掉咬不到/咬得到的范围
    for flag in ('useParentHitBox = true', 'checkLine = true'):
        if flag not in ad:
            errs.append('attack definition must preserve %r' % flag)
    if 'StateMachineDefinition = ExtResource' not in ad:
        errs.append('attack definition must keep StateMachineDefinition')

    # ---- 4) 组件集确实引用了这个定义（否则上面的定义是死文件）
    cs = open(os.path.join(MOD_DIR, P_CSET), encoding='utf8').read()
    if '%sAttackComponentDefinition.tres' % CHAR not in cs:
        errs.append('component set does not reference the attack definition')
    if not re.search(r'^Components = \[ExtResource\("\d+"\)\]$', cs, re.M):
        errs.append('component set Components must contain exactly the attack override')

    # ---- 5) 手册属性块必须与实际数值一致（照抄内置文案口径）
    for pkt in (P_PACKET, P_CARD):
        t = open(os.path.join(MOD_DIR, pkt), encoding='utf8').read()
        for frag in ('血量：[color=cc241d]%d[/color]' % int(HITPOINTS),
                     '伤害：[color=cc241d]%d/s（啃食）[/color]' % int(ATTACK),
                     '移速：[color=cc241d]%s[/color]' % SPEED_LABEL,
                     '类型：[color=cc241d]%s[/color]' % PHYSIQUE_LABEL,
                     '佩戴：[color=cc241d]---[/color]'):
            if frag not in t:
                errs.append('%s handbook missing %r' % (pkt, frag))
    return errs


# ==================================================================== 7. 打包
def package_pmod():
    out = os.path.join(WORKSPACE, '%s.pmod' % MOD_NAME)
    if os.path.exists(out):
        os.remove(out)
    files = _walk_files(MOD_DIR)
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        # mod.json 放最前，便于流式读取
        ordered = ['mod.json'] + [f for f in files if f != 'mod.json']
        for rel in ordered:
            z.write(os.path.join(MOD_DIR, rel), rel)
    return out, len(files), os.path.getsize(out)


def install():
    """安装到 Mods/<奶龙僵尸>/ 并登记 enabled_mods.json（先备份）。"""
    dst = os.path.join(MODS_DIR, MOD_NAME)
    moved = []
    if os.path.isdir(dst):
        # 只清掉包自身管理的文件，不做递归删除
        for rel in _walk_files(dst):
            moved.append(rel)
            os.remove(os.path.join(dst, rel))
    os.makedirs(dst, exist_ok=True)
    for rel in _walk_files(MOD_DIR):
        if rel.startswith('.'):
            continue
        d = os.path.join(dst, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(d), exist_ok=True)
        shutil.copyfile(os.path.join(MOD_DIR, rel), d)
    dst_proj = os.path.join(dst, P_PROJ)
    if not os.path.exists(dst_proj):
        shutil.copyfile(os.path.join(MOD_DIR, P_PROJ), dst_proj)

    # enabled_mods.json
    em = None
    for cand in (os.path.join(MODS_DIR, 'enabled_mods.json'),
                 os.path.join(os.path.dirname(MODS_DIR), 'enabled_mods.json')):
        if os.path.exists(cand):
            em = cand
            break
    added = False
    if em:
        bak = em + '.bak-nailong'
        if not os.path.exists(bak):
            shutil.copyfile(em, bak)
        lst = json.load(open(em, encoding='utf-8'))
        if MOD_ID not in lst:
            lst.append(MOD_ID)
            added = True
        w(em, json.dumps(lst, ensure_ascii=False, indent=2) + '\n')
    return dst, em, added, len(moved)


# ==================================================================== main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='重建并与现有 NaiLong/ 逐字节比对')
    ap.add_argument('--pmod', action='store_true', help='额外产出 .pmod')
    ap.add_argument('--install', action='store_true', help='安装进 Mods/ 并登记 enabled_mods.json')
    ap.add_argument('--all', action='store_true', help='= --pmod --install')
    a = ap.parse_args()
    if a.all:
        a.pmod = a.install = True

    before = compute_manifest() if a.check else {}

    print('== 1/6 皮肤动画 ==')
    anim = stage_animations()
    print('   atlas %dx%d  frames=%d  lifted=%d  .dat=%d bytes'
          % (anim['atlas'].width, anim['atlas'].height, anim['frame_max'],
             anim['lifted'], anim['dat_bytes']))

    print('== 2/6 音效 ==')
    audio = stage_audio()
    print('   %d Hz %dch %d frames  %.4fs  wav=%d bytes'
          % (audio['rate'], audio['channels'], audio['frames'],
             audio['wav_seconds'], audio['wav_bytes']))

    print('== 3/6 文本资源 ==')
    stage_config()
    stage_packet()
    stage_card()
    stage_cset()
    stage_sprite_scene()
    stage_character_scene()
    stage_attack_def()
    stage_mod_json()
    stage_project_file()
    print('   config/packet/card/cset/attackdef/scene/sprite/mod.json/pvzmodeproject 已写')

    print('== 4/6 托管运行时 ==')
    rt = stage_runtime(check_mode=False)
    print('   ModAssembly.dll %d bytes  sha256=%s' % (rt['dll_bytes'], rt['dll_sha256']))

    print('== 5/6 离线闸门 ==')
    errs = []
    e, _w = gate_structure(); errs += e
    errs += gate_geometry(anim)
    errs += gate_audio(audio)
    errs += gate_runtime_order()
    errs += gate_attack_spec()
    errs += gate_ground_motion(anim)
    if errs:
        for x in errs:
            print('   [FAIL] %s' % x)
        raise SystemExit('闸门未通过：%d 项' % len(errs))
    print('   OK  结构 / 几何 / 接地线 / 音频 / 导出顺序 / 数值规格 / 根运动')

    print('== 6/6 清单 ==')
    after = compute_manifest()
    w(os.path.join(MOD_DIR, MANIFEST),
      json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print('   %d 个文件' % len(after))

    if a.check:
        keys = sorted(set(before) | set(after))
        diff = [k for k in keys if before.get(k) != after.get(k)]
        if not before:
            print('   [idem] 首次构建，已记录基线（再跑一次 --check 才真正校验）')
        elif diff:
            for k in diff:
                print('   [idem] CHANGED %s' % k)
            raise SystemExit('幂等性失败：%d 个文件变化' % len(diff))
        else:
            print('   [idem] OK  与上一次构建逐字节一致（%d 文件）' % len(after))

    if a.pmod:
        out, n, size = package_pmod()
        print('   .pmod -> %s (%d files, %d bytes)' % (out, n, size))

    if a.install:
        dst, em, added, cleaned = install()
        print('   安装 -> %s  (清掉旧文件 %d 个)' % (dst, cleaned))
        if em:
            print('   enabled_mods.json -> %s  (新增登记: %s)' % (em, added))
        else:
            print('   [warn] 没找到 enabled_mods.json，需手动启用')

    print('\n完成。包目录: %s' % MOD_DIR)


if __name__ == '__main__':
    main()
