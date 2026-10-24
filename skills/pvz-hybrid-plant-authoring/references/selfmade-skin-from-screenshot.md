# 自制皮肤：从「一张游戏内截图」到可玩图集（单/多层 · 程序化动画）

> 2026-09-30 实测落地：**超级汉堡射手**（`BurgerSkin/build_skin.py`）。
> 场景：用户只给一张全身图（**截图品质、有纹理底、带相框**），要求「裁素材 → 游戏里重拼」，
> 且要复用另一个 mod 的全部逻辑。本文只讲**素材与结构**这部分，其余照常走主流程。

## 0. 什么时候用本文

| 情形 | 走哪条 |
|---|---|
| 解包树里有该角色的 `*.reanim.compiled` | 走「官方素材直转」（主 SKILL 的路线 A），别自制 |
| 只有一张 PNG/JPG 截图，角色本身游戏里**不存在** | **本文** |
| 只改数值不改画 | 复用原版贴图（路线 C） |

## 1. 抠像：**「描边当屏障的 flood fill」是唯一稳的**

底图是**有纹理的草坪/泥地**时，颜色法必然失败。三轮实证：

| 做法 | 结果 |
|---|---|
| 扩散掩码 = 「绿色」 | ✗ 抗锯齿把角色自身的绿和背景的绿**连成一个连通域**，叶子被整块吃掉 |
| 植株 = 「暗像素」 | ✗ 角色投在底图上的**暗影**（亮度≈53）也被算进来 |
| **✔ 屏障 = `content & (亮度 < T) & ~强绿`，从背景连通域 flood，掩码 = `~屏障`** | 正确：扩散被描边挡住，植株内部（含叶子/绿件）整块留下，背景与暗影连成一片被冲掉 |

```python
content    = (alpha > 0) & (rgb.min(axis=2) < 232)          # 排除透明边 + 纯白
stronggreen = (g > r + 45) & (g > b + 45)                   # 草坪 + 暗影都会中
barrier    = content & (lum < 85) & (~stronggreen)          # 只有「暗且不绿」= 描边/黑件
free       = ~dilate(barrier, disk(K))                      # ★ 先膨胀屏障
outside    = binary_propagation(lawn_cc & free, mask=free)  # lawn_cc = greenish 的最大连通域
plant      = erode(content & ~outside, disk(K))             # ★ 再腐蚀回来
```

### 1.1 三个必踩的坑

1. ★★ **屏障有 k 像素级缺口 ⇒ flood 会渗进角色内部**。
   必须「**先膨胀屏障 K=5 → flood → 结果腐蚀 K**」，**不是** `binary_closing`
   （closing 补不上 5px 的缺口；实测 K=2~4 时底部面包内部仍被冲空，K≥5 才封死）。
2. ★★ **工作区必须内缩**：截图的**深色相框本身就是一道闭合环**，它也是
   `content & ~outside`（flood 进不去）⇒ 一旦被当成候选，末尾的 `binary_fill_holes`
   会把**整幅图**吃掉（实测 15500+ px）。做法 = 草坪 bbox 内缩 7px 再取候选。
3. ★ 腐蚀回退会把描边外侧的**暗绿背景**带回来一点 ⇒ 收尾补 `binary_opening(disk(1))`，
   并在最终产物上放大 8× 人眼复核（本项目产 `_sil_v8_k5_9x.png` 那类对照图）。

### 1.2 验收口径

`silhouette` 出来后**先量 bbox**（本项目 71×77，与内置植物 ~90×86 同量级 ⇒ 1:1 显示即可），
再看逐行宽度剖面找「颈部」定分层线。

## 2. 分层：切哪一刀、为什么要「重叠带」

* 切分线挑**最窄的那一道**（副产物：`SPLIT_Y`）。
* ★ **身体层要多带 `BODY_OVERLAP`（本项目 8px）像素的「重叠带」**：
  头做呼吸/后坐时，接缝处不会露出背景色（头是画在身体之上的）。
* ★★ **每层贴图各自裁到自己的 bbox**，把「左上角在完整画布里的坐标」写进该层 slice 的 `ox/oy`。
  两个好处：图集更小；**body 层的变换不会是 `Transform2D.Identity`**
  （引擎在 `UpdateChild():5247` 里把 Identity 当「无位姿」，会 `continue` 掉位置更新/隐藏子精灵）。
  ⇒ 收尾加一条断言：`assert body_origin != (0, 0)`。

## 3. 结构：**头必须挂普通 `Node2D` 下**

```
Root 精灵（clip = BodyIdle，只画 body 层）
  └─ HeadHolder  (普通 Node2D)
        └─ Head  （clip = HeadIdle / HeadFire，只画 head 层）**独立渲染**
```

源码依据（`addons/AdobeAnimateEditor/Node/AdobeAnimateSprite.cs`）：

* `_Draw():9534` 首判 `IsRenderedByParentSpriteForRender()` → `父.OwnsSpriteChildForRender(本)`(`:7774`)
  → 要求本精灵在父的 `_spriteChildren` 里；
* `_spriteChildren` 由 `CollectOwnedChildBindings`(`:5365-5401`) 收集，**判定是「节点类型」**：
  遇到 `AdobeAnimateSlot` 会继续下钻并把 `collectSpriteChildren` 置 true，
  遇到**其它有子节点的普通节点则置 false** ⇒ **挂普通 `Node2D` 下的精灵不会被收**。
* 连带好处：**`Head.position` 不会被 `UpdateChild()` 每帧覆写**
  （那个覆写 = `被跟随层 pose.Origin + 父 offset`，只对「父的直接子精灵」生效）。

> ⇒ 老口径「子精灵必被父代画、必须走三精灵换头」**只在「父的直接子精灵」时成立**。
> 同一份 `.tres` 的两层结构，直接挂容器下就是最简方案，**不需要插件同步位姿**。

## 4. 落点通式（把「偏移该写多少」一次算清）

渲染链：`local = sliceOrigin + offset`，再乘节点变换
（`BuildSliceTransform` / `AppendInterpolatedLayerElementsForRender`）。

令 `anchor` = **画布坐标里的种植点**（本包 `=(帧宽/2, 帧高 − GROUND_DROP)`，`GROUND_DROP≈36` 贴地面阴影线），
「物体空间 = 画布坐标 − anchor」，则：

```
Root 节点净位置 = 0
   0 + (body_origin + root_offset) = body_origin − anchor        ⇒ root_offset = −anchor

Head.position = head_position（**不会被覆写**，因为我们挂在容器下）
   head_position + head_origin + head_offset = head_origin − anchor
                                                                ⇒ head_position + head_offset = −anchor
```

* 本项目取 `head_offset = (0,0)`、`head_position = −anchor`（两者之和恰好 −anchor）。
* ★ **`Marker2D` 挂在 `Head` 下 ⇒ 它的 local 坐标就是画布坐标**
  （Head 节点原点 = 画布原点）⇒ `MARKER2D = 炮口画布坐标`。
  ⚠️ **不要**照抄「`MARKER2D = 炮口 + HEAD_OFFSET`」那条公式 ——
  那是「Head 节点位置被引擎写成 `pose.Origin + 父offset`」的结构下的口径，两者不通用。

标定值全部写进 `<Key>_skin_params.json`，**让生成器读它**（别让常量与产物各说各话）。

## 5. 程序化动画（单张图也能「活」）

素材只有一张 ⇒ 用 slice 的 `ox/oy` 做**平移级**动画，零新素材：

| clip | 做法 |
|---|---|
| `BodyIdle(0..24)` | 身体静止 |
| `HeadIdle(25..49)` | `dy = round(A·sin(2πj/25))`，A=2 |
| `HeadFire(50..86)` | 开火帧 `50+12` 处后坐峰值 −4px，两侧递减收回 |

* ★ `events` 表仍必须写**真实开火帧**的 `{"Command":"fire"}`（换皮肤不会自动带上它）。
* ★ 若同时改了「常规射击由插件接管」（`fireEventName = "modfire"`），动画事件只是**冗余保险**，
  但**照写**，免得日后改回引擎驱动时踩「只有动画没有子弹」。

## 6. 移植既有 mod 时新增的两条坑

### 6.1 ★★ 生成器的包目录里**不能放工具脚本**

`build_plant_*.py` 末尾的 `sweep_stale_files(MOD_ROOT, keep)` 会删掉包目录里
**「本次不产出的文件」** —— 把 `build_skin.py` 放在 `<BUILD_DIR>/` 下，**跑一次就被删**（实测）。
⇒ 外观工具放**独立目录**（本项目 `ModWorkspace/BurgerSkin/`），或放 `.cache/`。

### 6.2 ★★ `TowerDefensePlantGatlingPea/CatGatlingPea.projectileName` 会把 `fireCheckList[0]` 强转

```csharp
// TowerDefensePlantGatlingPea.cs:73（setter）与 :134（ImportVariantSave）
((FireComponentProjectileSingle)_fireComponent.fireCheckList[0].projectile).projectileName = value;
```

⇒ 想用 **`FireComponentProjectileWeight`（随机子弹）** 时把它放 `[0]` 会抛 `InvalidCastException`
（`ImportVariantSave` 在运行期确实会被调用：`TowerDefensePlantMagicBean.cs:113` 等）。
**解法**：`fireCheckList = [0] 占位单体(Pea) + [1] 随机池`，9 条发射配置一律 `checkProjectileId = 1`，
插件取弹种也按 `fireProjectileList[0].checkProjectileId` 取（**不要写死 `checks[0]`**）。

### 6.3 随机子弹的标准结构（照抄内置 `Gold/Hamburger`）

```
FireComponentCheckConfig.projectile = Weight(外层)
   ├─ WeightItem(0.97) → Weight(内层, averageWeight = true) → 10 × WeightItem(权重 1) → Single → CreateData
   └─ WeightItem(0.03) → Single → Butter
```

`GetProjectile(null)` 内部走 `GD.Randf()` ⇒ **真随机**；`Fire()` 每条配置各调一次
⇒ **每颗独立掷**。注意伤害覆盖随种类走（火焰豌豆 `baseDamage=40/damageFlags=7`、
地刺 `damageFlags=2/fireMethodFlags=5`、西瓜 80 …），这是「与内置一致」的必然代价。

## 7. 自检清单（本项目实测全过的那些）

```python
assert d["end"] == len(dat_bytes)              # .dat 全文解包终点 == 文件长
assert (frameMax, media, layers, clips, events) == 期望
assert body_origin != (0, 0)                   # 防 body 层恒为 Identity
assert root_offset == -anchor
assert head_position + head_offset == -anchor  # 头会整体偏移的根因
assert max(物体空间炮口 x) <= 40                # 炮口收拢在本格内（过火前提）
assert 两次运行 14 个产物逐字节一致              # 幂等
```

外加（生成器侧）：
* 精灵场景**禁用** `Animation/LayerVisible/<名>` / `Animation/MediaReplace/<名>` / `Animation/Clip`
  三个简写键（静默失效），只用 `clip` + `layerVisible=[…]` + `mediaReplaceAtlasPaths=[…]` + `mediaReplaceUse=[…]`；
* 通用扫描：任何 `[node ` 开头的行**必须以 `]` 收尾**（写成 `>` 会被 Godot 静默吞行）；
* 黑名单**不能用 `GatlingPea.tres`**（自己的 `BurgerGatlingPea.tres` 就含这个子串 ⇒ 假红）。
