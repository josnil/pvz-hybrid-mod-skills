# 僵尸的发射体系 + 子弹生成点（对齐炮口）

> 本文件是 `pvz-hybrid-zombie-authoring` 的 reference。
> 内容全部来自「超级机枪读报僵尸」的实际踩坑与源码查证，行号已核对。

## 1. 僵尸发射 vs 植物发射

| | 植物 | 僵尸 |
|---|---|---|
| 组件 | 自带 Attack/Fire | **默认没有 FireComponent**（只有 Armor/Attack-Eat） |
| 触发 | 内置「发射动画 + `events.fire`」链 | 没有 ⇒ **必须插件自建节拍** |
| 朝向 | 朝右 | **朝左** ⇒ `speed` 写**负值**、`projectileFlip = true` |
| 判定 | `idle fire check` | 复用 `CanFireCheckOnceByData()`（见 §4） |

**数据侧只做两件事**：① 组件集加 FireComponent；② 发射定义 `.tres` 指对 `Marker2D` + **只留 1 条** projectile config。

> `Fire()` 一次遍历 `fireProjectileList` 全部元素 ⇒ 「7 颗连发 / 300 颗散射」这类
> **必须**在插件里逐颗调 `Fire()`，并每次都先把 config 的 `dir` 写成目标角度。

## 2. ★★★ 子弹生成点的真源（顺源码查，别凭插槽名字猜）

```
<包>…/Scene/<Key>FireComponentDefinition.tres
    firePosMarkerPaths = [NodePath("SpriteGroup/TransformPoint/ZombiePaper/HeadSlot/FireMarker")]
        │
        │  FireComponentFireProjectileConfig.cs:10   public int firePosId;   （默认 0 ⇒ 取第 0 个）
        ▼
FireComponent.CreateProjectile()            FireComponent.cs:2698-2714
    logicalGlobalPosition = parent.GetLogicalGlobalPosition(marker2D)
        │
        ▼
TowerDefenseCharacter.cs:1607-1619
    GetLogicalGlobalPosition(Node2D descendant) => descendant.GlobalPosition
        │
        ▼
                    ★ 生成点 = marker2D.GlobalPosition ★
```

旁路（一般都不生效，可先排除）：

| 机制 | 源码 | 说明 |
|---|---|---|
| 同格吸附 | `FireComponentDefinition.cs:121` `snapStraightProjectileToSameCellTarget` | 默认 false |
| 挡路改 x | `FireComponent.ResolveOffsetLineRoute()`（`:759`） | 只在子弹会撞到东西时改 x |

⚠️ **`HeadSlot` 不是「头部的插槽」** —— 它是**原版给护具 / DamagePoint 用的静态插槽**
（原版 `Asset/Anime/Character/Zombie/Chapter1/Paper/Scene/TowerDefenseZombiePaper.tscn:67-71`）：

```gdscript
[node name="HeadSlot" parent="SpriteGroup/TransformPoint/ZombiePaper" index="1"]
drawLayerId = -2
position = Vector2(-14.015516, -40.408867)
rotation = -0.27867758        # 弧度！≈ −15.9670°
scale = Vector2(0.79857695, 0.79857695)
```

它的 `position` **不跟头部美术**；护具看着贴在头上，是**护具自己的 `offset` 补掉了这段差**。
⇒ 「`FireMarker` 挂在 `HeadSlot` 下 ⇒ 自动跟随头部动画」是**错的**（我踩过：子弹从头顶上方 80.77px 出膛）。

## 3. ★ Godot `Transform2D` 只把 `position` 当平移

所以 `FireMarker.position` 一旦不是 `(0, 0)`，父节点的 rot/scale 就会作用在它身上：

```
space(FireMarker) = HeadSlot.pos + M(θ_slot, s_slot)·FireMarker.pos + BODY_OFFSET
                  = HeadSlot.pos + M(θ_slot, s_slot)·FireMarker.pos + (-40, -80)
```

`M(θ, sx, sy) = [[cosθ·sx, −sinθ·sy], [sinθ·sx, cosθ·sy]]`。

⚠️ **旧写法 `space = (HeadSlot.pos + marker) + BODY_OFFSET` 只在 `marker == (0,0)` 时等价**。
这个坑很隐蔽：改 marker 之前一切正常，改完就悄悄错掉。

**反解**（要 marker 落在给定 space 点时）：

```
head_local   = muzzle_pose + head_offset              # 头节点局部空间
muzzle_space = A·head_local + node                    # A = rot_scale(跟随层旋转, −1, +1)
Q            = muzzle_space − BODY_OFFSET             # 身体精灵局部
p            = (1/s)·R(−θ)·(Q − HeadSlot.pos)         # ⇒ FireMarker.position
```

反解必须**指定参考帧**（`body_frame`）—— 一般取 `0`，并且与头的 `offset` 反解同口径。

## 4. 射击判定：`CanFireCheckOnceByData`（不是 `CanFire`）

自建节拍的插件里，「没有植物不开火 / 还没进场不开火」这样写：

```csharp
// 自己找目标（植物），找到才打
if (!HasFireTarget(zombie)) { return; }
if (!fire.CanFireCheckOnceByData(...)) { return; }   // ★ 用这个
fire.Fire();
```

* `CanFire()` 会**多一道 `timer > 0`** 的状态机节拍 ⇒ 自建毫秒节拍会被它再拖一轮（节奏不对）。
* 与原生 `idle fire check` 用的是**同一套判定**，所以「植物僵尸共用」是自然的。

## 5. ★★ 两层实现：静态兜底 + 插件每帧覆写

**为什么不能只改场景里的 `FireMarker.position`**：只要头会动（跟 `anim_head1` 逐帧摆、
或播开火动画），**炮口每帧都在动**。实测扫描（扫全部身体 clip 的炮口 space 范围）：

| clip | 帧 | 炮口 x 跨 | 炮口 y 跨 |
|---|---|---|---|
| Idle | 0..24 | 4.85 | 20.12 |
| Walk | 25..71 | 23.66 | 53.97 |
| Eat | 72..95 | 42.76 | 78.20 |
| AngryWalk | 145..191 | 23.66 | 53.97 |
| AngryEat | 192..215 | 42.76 | 78.20 |
| Death 96..131 / Gasp 132..144 | — | 该段跟随层无切片（头不跟随） | |

⇒ 静态值**只能对上参考帧**（实测 Idle 段最大离线 10.86px，理论上限 ~44px）。

### 层 1：静态兜底（场景值，参考帧 bf=0）

```gdscript
[node name="FireMarker" type="Marker2D" parent="SpriteGroup/TransformPoint/ZombiePaper/HeadSlot" index="0"]
position = Vector2(-35.697232, 94.988609)     # HeadSlot 局部；反解回代差 0.000004px
```

### 层 2：插件每帧覆写（真正保证每一帧都对齐）

在**每帧同步头位姿的那一环**里补一句：

```csharp
// HeadMuzzleLocal = muzzle_pose + head_offset（头绘制是 transform.Translated(offset) 再画 pose 点
//                  ⇒ 头节点局部点 = pose + offset）
private static readonly Vector2 HeadMuzzleLocal = new Vector2(28.6143f, 20.1485f);

// 必须在抄完 Position/Rotation **之后**（GlobalTransform 跟着这两个量变）
if (pair.Marker != null && GodotObject.IsInstanceValid(pair.Marker))
{
    Vector2 muzzle = pair.Visible.GlobalTransform * HeadMuzzleLocal;   // ★ 炮口世界坐标
    if (!pair.Marker.GlobalPosition.IsEqualApprox(muzzle))
    {
        pair.Marker.GlobalPosition = muzzle;
    }
}
```

**为什么这一行就够**：头节点的绘制变换是 `transform.Translated(offset)` 再画 pose 点，
所以「炮口在头节点局部空间」= `pose + offset`；`head.GlobalTransform` 已含头的
`Position`/`Rotation`（每帧从影子抄）与 `scale = (-1,1)` ⇒ 乘出来就是世界坐标，天然跟随。

**节点路径**（插件里用相对路径找，别写全路径）：

```csharp
private const string FireMarkerNodePath = "HeadSlot/FireMarker";   // 相对「身体精灵」
pair.Marker = body.GetNodeOrNull<Marker2D>(FireMarkerNodePath);    // 找不到只报一次日志，退回静态值
```

## 6. 炮口点怎么标定（两个独立来源互校）

**手法**：从「炮管轨（barrel）**完全伸出帧**」的**不透明区最右列中点**，映射到美术 pose 空间。

```
pose 点 = M · (局部像素点)      # M = 该切片的 6 元组矩阵（切片空间 → pose 空间）
```

实测（`SuperGatlingPea`）：

| 来源 | 值 |
|---|---|
| 植物侧标定 `ANCHOR_MUZZLE`（配 `ANCHOR_ROOT=(40,40)`） | `(88.552, 30.2)` |
| 独立反推：barrel 图层 id 19 / media 13，hf=62，局部像素 `(43.0, 24.0)` | `(88.5520, 30.2000)` |
| **差** | **0.0000 px** |

## 7. 判据怎么写（防假绿）

**两个来源必须互相独立**，否则就是「拿生成器常量比生成器常量」：

| 判据 | 来源 |
|---|---|
| 炮口点 | **从美术反推**（barrel 轨，不读任何常量） |
| 生成点 | **从生成的场景 `.tscn` 现场反读**（HeadSlot 的 rot/scale 会作用在 marker 局部坐标上） |

再配负向用例（全部必须被判「离线」）：

| 用例 | 实测离线 |
|---|---|
| marker 退回 `(0, 0)` | 81.04 px |
| 只改 y、x 忘改 | 28.51 px |
| 只改 x、y 忘改 | 75.86 px |
| 两个分量符号写反 | 162.07 px |
| 整体再偏 10px | 7.99 px |

**跨语言一致性**（改 `head_offset` 必须同步插件字面量）：生成器自检里用文本解析读
C# 源码的 `HeadMuzzleLocal = new Vector2(..., ...)`，与 `muzzle_pose + head_offset` 比（容差 1e-4，
因为 C# 侧是 `f` 后缀的 float）；闸门里再用**反射**读 DLL 的该字段比对。

## 8. 工具清单（可直接照搬）

| 工具 | 用途 |
|---|---|
| `_muzzle_probe.py` | 从美术反推炮口 pose 点；从**生成的场景 .tscn** 读 HeadSlot/FireMarker 并算生成点 space |
| `_muzzle_scan.py` | 扫全部身体 clip 的炮口范围（回答「静态值够不够」） |
| `_fire_marker_solve.py` | 反解 `FireMarker.position` + 回代验证 |
| `_marker_ab.py` | 三口径对照图：旧 `(0,0)` / 静态兜底 / 每帧真炮口 |

> 写这类脚本时的自证要求：**每个脚本自带「回代 / 交叉 / 独立反推」的一步**，
> 只输出「我算出来的值」而不验证的脚本，等于给假绿铺路。
