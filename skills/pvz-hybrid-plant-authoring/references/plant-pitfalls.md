# 踩坑总表（植物专场）—— 现象 · 触发场景 · 原因 · 正确做法

> 通用坑（打包/断言/交付/程序集/环境）见 `pvz-hybrid-mod-authoring/references/pitfalls.md`。
> 本文件只收**植物侧**特有的。
> 流程与规范正文在 `pvz-hybrid-plant-authoring/SKILL.md`；各专项展开在同目录其它 `references/*.md`。

---

## P. 建包与结构

### P-01 一颗弹打不出、零日志 ⇒ 多半是 `ComponentSet` 没声明
- **现象**：植物会动、会摆，就是不出弹；日志**什么都没有**。
- **触发场景**：手写角色场景时忘了写 `ComponentSet`。
- **原因**：角色场景**必须显式声明** `ComponentSet`（`./<Key>ComponentSet.tres`，写在 `script` **前**），
  否则基场景那份（无 FireComponent）生效。
- **正确做法**：场景里写 `ComponentSet = ExtResource("<n>")`，且**排在 `script` 之前**。

### P-02 只有动画没有子弹（零报错）⇒ `.dat` 的 `events` 表缺 `fire`
- **现象**：同上，但 `ComponentSet` 是对的。
- **触发场景**：自制/直转 `.dat` 时只做了画面、没做事件表。
- **原因**：发射链的**起点**是动画事件（见通用 `D-02`）。
- **正确做法**：`events` 里必须有 `{"Command":"fire","Argument":""}`；
  发射帧 = `HeadFire.start + 12`（本项目实测 f62）。

### P-03 `saveKey 与注册键不一致` ⇒ 整包被拒
- **现象**：包被拒，日志点名 `saveKey`。
- **触发场景**：改了角色 Key 但只改了一处。
- **原因**：`CHAR_KEY` 在**四处**必须一致（目录名 / 文件名 / 卡片文件名 / `saveKey`）。
- **正确做法**：生成器里把 Key 收敛成**一个常量**，四处都从它派生；加断言。

### P-04 包内多文件 / `.cs` 入包 ⇒ 整包拒收
- 见通用 `A-02`。

### P-05 只改生成器不改 `self_check()` ⇒ 下次重跑静默回退
- **现象**：改完生效了，重跑一次生成器又变回去。
- **触发场景**：手工修产物、没同步生成器；或改了生成器常量但自检还是老的。
- **原因**：自检与生成器是两套口径。
- **正确做法**：**改生成器 + 同步 `self_check()` + 加 on-disk 断言**（见通用 `B-07`）。

---

## Q. 外观与皮肤

### Q-01 自定义皮肤动画「完全静止、按 ESC 暂停一次跳一帧」
- **现象**：**能显示但不动**；按一次 ESC（暂停再恢复）才前进一帧。
- **触发场景**：皮肤走 standalone `.dat`（`animeFile = "./Xxx.dat"`）。
- **原因**：自制 `.dat` **不在引擎的全局图集清单**里 ⇒ `AdobeAnimateSprite.GpuPoseTextureRid` 无效
  ⇒ `_runtimeGpuClockInterpolationActive` 为假 ⇒ 只在 `RequestNodeRedraw` 时前进一帧。
- **正确做法**：运行期把该精灵切成**本地 CPU 姿态**渲染：
  ```csharp
  sprite.forceLocalRender = true;      // AdobeAnimateSprite.cs:1141
  sprite.forceCpuPoseRender = true;    // :1166
  ```
  **两者必须一起设**（官方 `PacketPickControl.cs:401-402` 就是两个一起；`Almanac.cs:1139` 只设了一个 ⇒ 图鉴预览仍静止）。
  ⚠️ 两者是 **`public` 但非 `[Export]`** ⇒ **写进 `.tscn` 完全无效**（Godot 静默忽略，连 warn 都没有），
  **只能插件运行时赋值**。⇒ 产物侧 `Sprite/*.tscn` 里**不该出现这两行**（出现既误导又没用）。
  ⚠️ 覆盖战斗 / 图鉴 / 选卡 / 种植预览（各自是**独立实例**）⇒ 必须**每 N 帧全树扫描**幂等打标。

### Q-02 病认错了：把「完全不显示」当成 Q-01 去治 ⇒ 白忙
- **现象**：精灵根本不显示，照着 Q-01 设了两个开关，没用。
- **触发场景**：混淆两类故障。
- **原因**：Q-01 治的是「**能显示但不动**」。
- **正确做法**：先分清「不显示」还是「不动」——不显示要查的是**图集/切片/子精灵父代画**（见 Q-03）。

### Q-03 子精灵被父代画 ⇒ `forceLocalRender` 形同废纸、皮肤被拿去采样共享大图
- **现象**：换头后的子精灵显示成「一团别的角色的图集碎片」（与截图逐像素吻合）。
- **触发场景**：把子精灵换成**另一份 `.tres`**（换头！）或自制皮肤。
- **原因**（链条完整）：
  1. `CollectOwnedChildBindings:5365`（判定 `:5385`）**只按 Godot 节点类型**收集子精灵，**完全不看 `parentSprite`**；
  2. ⇒ 只要是 Godot 子节点就进父的 `_spriteChildren` ⇒ `OwnsSpriteChildForRender:7774` true；
  3. ⇒ `IsRenderedByParentSpriteForRender():9559` true ⇒ `_Draw():9532-9537` **第一行 return**
     ⇒ 子精灵自己的 `_forceLocalRender`（`:9549`）**永远走不到**；
  4. ⇒ 切片由**父精灵的渲染批次**代画，page 取 `definition.MediaAtlasPages[mediaId]`；
  5. ⇒ mod 皮肤**不在全局图集清单** ⇒ page 解析不到 ⇒ 落 `BaseAtlasPage = 0`
     ⇒ 采样 `AdobeAnimateVisualTextureArray.png`（**全部角色拼在一起的共享大图**）⇒ 碎片。
- **正确做法**：**让可见头不再是身体的子精灵** —— 用**三节点**结构：
  ```text
  <Key>Sprite（身体）
  ├── HeadShadow  type="Node2D"   ① 位姿影子：**身体的直接子精灵**，visible=false + 全层 LayerVisible=false（零切片）
  │        parentSprite = NodePath("..")；Layer = insertLayerId = followParentSpriteLayerId = 16
  ├── HeadHolder  type="Node2D"   ② 普通容器（identity，不写 position/rotation/scale）
  │   └── Head    type="Node2D"   ③ 可见头：HeadHolder 的子精灵 ⇒ **独立渲染**
  ```
  两个头的 `scale` / `offset` / `offsetRotate` 必须**逐字相同**。
  **为什么挂在普通容器下仍能被引擎定位**：`ResolveSpriteChildFollowLayer` 最终用
  `_parentSprite = FindParentSpriteAncestor():7797`（最近**祖先精灵**）⇒ 穿过 `HeadHolder`。
  插件侧每帧把影子位姿拷给可见头。
- ⚠️ **两个"看起来能躲"但躲不掉的写法**：
  ① `insertLayerId = -1` **不等于**不插入（`ResolveSpriteChildInsertLayer:8039` 回落顶层）；
  ② 挂到普通 `Node2D` 容器下**也躲不掉**（`CollectOwnedChildBindings:5397` 只在中间节点有 `ownerSlot` 时截断）。
  **只有「不再是精灵的子精灵」才真正断开。**
- 官方先例：`Test/AdobeAnimateDetachedChildOwnershipProbe.cs` —— `RemoveChild` 后断言 `!IsRenderedByParentSpriteForRender()`。

### Q-04 `.tscn` 节点头收尾写成 `>` ⇒ Godot 静默吞行
- **现象**：节点根本没建出来，**零日志**。
- **触发场景**：手写/生成 `.tscn` 时把 `]` 写成 `>`。
- **正确做法**：**收尾必须是 `]`**；自检加通用扫描：
  `for ln in body.splitlines(): if ln.startswith("[node ") and not ln.endswith("]"): fail`。
  ⚠️ **断言别写成不带闭合括号的前缀匹配**（断言与实现同错 = 假绿）。
  ⚠️ **取证纪律**：结构类结论一律以**字节级读取**为准（`Read` 预览曾把 `>` **显示成** `]`）。

### Q-05 头位/头姿态的三个真旋钮：`offset` / `offsetRotate` / `useRotate`
- **现象**：改了 `Head.position`，头**纹丝不动**（或反过来，改了 `offset` 跑偏）。
- **触发场景**：想调头的位置/角度。
- **原因**：`UpdateChild():5255-5281` **每帧重写**子精灵：
  `child.Position = 被跟随图层 pose.Origin + 父精灵 offset`（在 `if (usePos)` 内）、
  `child.Rotation = pose.Rotation + child.offsetRotate`（在 `if (useRotate)` 内）。
  ⇒ 默认（两开关都 true）时，场景里写的 `Head.position` / `Head.rotation` 是**死值**。
- **正确做法**：
  - **要调头位 ⇒ 改 `offset`**（它只作用于本精灵自己那份美术与子精灵落位，**不影响 `Marker2D`**）。
  - **要「头摆正、不摆头」⇒ 场景写 `useRotate = false` + 显式 `rotation = <常量>`**（**必须成对**，否则 `rotation` 是死值 = 静默失效）。
  - **回退 = 把 `usePos` / `useRotate` / `rotation` 三行整段删掉**（一个都不写）。
    ⚠️ **只删一部分是半回退**（前者留死值、后者仍冻结）。
  - ⚠️ **单位是「弧度」不是「度」**（旧稿写错过：`offsetRotate = -0.25` 是 **−14.324°**）。
  - ⚠️ **「屏幕位移」不能直接加到 `offset` 上**：引擎真实变换 `P = A·(pose_art + offset) + node`，
    而 `A` 是**横翻**矩阵（第一列反号）⇒ 往 `offset` 上加 Δ **屏幕上是横向反向**。
    （实测 Δ=`(+6,−3)` ⇒ 屏幕 `(−6.36,−2.13)`）⇒ 位移要加在**锚点**上再反解 `offset`。

### Q-06 `scale` 是「显示缩放」，写 1.0 会让角色大 2.5~3 倍
- **现象**：角色尺寸离谱。
- **触发场景**：按"直觉"把 sprite 的 `scale` 写成 1。
- **原因**：该字段是**显示缩放**，不是美术缩放。
- **正确做法**：照抄同族内置角色的值，别凭直觉填。

### Q-07 `.tscn` 里选精灵属性只能用官方那三种键
- **现象**：写了属性但完全不生效（静默丢弃）；或"头上长叶子"。
- **触发场景**：用 `clip` / `mediaReplaceAtlasPaths` / `mediaReplaceUse` / `name_ignore` 这类裸名。
- **原因**：官方只认 `Animation/Clip`、`Animation/LayerVisible/<图层名>`、`Animation/MediaReplace/<媒体名>`（`_Set:2989-3057`）。
  裸 `layerVisible = [...]` 是 **id 序数组**，不能按名关层。
  实例后果：`Head._clip` 空 ⇒ `ApplyFlashAnimeDataChange()` 兜成 `clips.Keys[0]` = `BodyIdle`（茎叶段）⇒ 头上长叶子。
- **正确做法**：**一律用那三种带前缀的键**。
  ⚠️ **`flashAnimeData` 必须排在所有 `Animation/LayerVisible/*` 之前** ——
  否则 `_layerVisible.Count != 图层数` ⇒ 引擎整表 `Resize` 成全 `true`（`flashAnimeData` setter `:1092-1095` 内部就做那个 resize）。

### Q-08 手写角色 `.tscn` 的「三方一致」
- **现象**：节点找不到 / 层级错乱。
- **触发场景**：手写 `[node parent=...]` 与 `NodePath(...)`。
- **正确做法**：`[node parent]` / `NodePath` / 实际路径**三者逐字一致**，加断言。

---

## R. 发射与齐射

### R-01 齐射 = **N 条配置 + N 个 Marker**（不是插件连发）
- **现象**：想一次打一排，结果只出一颗 / 或重叠成一颗。
- **触发场景**：想实现"多管齐射"。
- **原因**：`Fire()`（`FireComponent.cs:3434`）一次调用遍历**全部** `fireProjectileList`。
- **正确做法**：`fireProjectileList` **N 条**（每颗 `firePosId` 各一次）+ `firePosMarkerPaths` **N 条**
  + **`lockProjectileGridY = true`**（不锁行 `BulletField.cs:1473` 会按像素窜排）
  + **刻意不写** `fireNumAtOnce` ⇒ 动画 fire 事件一次 `Fire()` 同帧打 N 颗。
- ⚠️ **与「逐颗发射」相反**：通用 `D-03` 那种逐发节拍要**收敛成 1 条 config**（否则 N×N 颗重叠）。
  **两种模式别混用。**

### R-02 齐射的「排列轴」= 弹道方向
- **现象**：想做"横向一排"，结果排成"一列"或落进植物身体。
- **触发场景**：按直觉沿 y 铺开多个 Marker。
- **原因**：豌豆沿 **+x** 飞（`dir=0` ⇒ `velocity = speed * Vector2.FromAngle(0) = (1,0)`；链路无镜像）。
- **正确做法**：**想排成屏幕水平「一排」就只能沿 x 铺开**（沿 y 铺是「一列」）。
  只向前铺（往后会落进植物身体/背后）；四判据写成不变量：
  条数 / **y 唯一** / **x 严格递增且步距恒定** / **首颗 x = 炮口 x**。

### R-03 「过火」不生效：豌豆穿过火焰树桩不变火球
- **现象**：前方一格有火炬树桩，豌豆**有概率**（实际是固定几颗）不过火。
- **触发场景**：把多个炮口 Marker 横向铺开、跨度超出本格。
- **原因**（三条叠加）：
  1. 过火由 `ChangeProjectileComponent` 实现，其 `checkShape` 只有 **100px 宽**
     （`FireOffset3Definition.tres`：`RectangleShape2D size=(100,98)`）；
  2. 过火检测是「按子弹**当前帧位置**的包围盒 ∩ 区域」（`BulletField.cs:6446-6485 ProcessZonesForBullet`），
     **没有任何扫掠/线段补偿**；
  3. ⇒ 出生点已经**越过火炬那一格**的豌豆，此后一直向前飞，**永远进不了那 100px 窗口**。
  对照：内置 `GatlingPea` 的炮口只有 1 个，X = **31.74**（本格内）。
- **正确做法**：**把炮口 X 收回本格内（≤ 内置炮口位置 31.74）**。
  ⚠️ 收拢之后**不要**再为了"视觉分开"去动炮口坐标 —— 那会让过火复发。
  要视觉分离走 `R-04`。

### R-04 同帧齐射 + 炮口收拢 ⇒ 视觉上 7 颗糊成一坨
- **现象**：豌豆挤在一起、看不出是几颗。
- **触发场景**：为了过火把炮口 X 收拢（间距只剩 4px），而 7 颗仍然**同帧**出膛。
- **原因**：同帧出膛会把那 4px 的炮口间距**原样带进飞行过程**。
  （横向无解：要过火出生点 X ≤ 31.74，而 7 颗 28px 宽的豌豆横着需要 196px ⇒ **放不下**。
  纵向错开也不是好解法——会改子弹高度/命中观感，且过火窗口只有 98px 高，物理上分不开 7 颗。）
- **正确做法**：**在时间上错开**（改成逐颗出膛），视觉间距由「弹速 × 间隔」决定：
  ```
  视觉间距(px) = 弹速(px/s) × 间隔(s)
  例：500 × 0.06 = 30px > 豌豆宽 28px ⇒ 相邻两颗不再重叠
  7 颗总时长 = 6 × 间隔 = 360ms，远小于攻击周期 1.5s
  ```
  两步（缺一不可）：
  1. **数据侧摘掉引擎齐射**：`FireComponentDefinition` 里写 `fireEventName = "modfire"`；
  2. **插件侧自己逐颗发**：`OnFireReady` 启动连发链，每帧按间隔调
     `CreateProjectileByData(posId, velocity, data, -1, PLANT, Vector2.Zero, overrides)`（`posId` = 0..6）。
  - 时间轴用「起点 + k × 间隔」算时刻（不是每次 `+=`），避免浮点累加漂移。
  - ⚠️ **想改回引擎齐射**：删掉 `fireEventName`（恢复默认 `"fire"`）**并**停掉插件连发链，两处一起动。

### R-05 `FireComponent` 不是 `GodotObject` ⇒ 写 `IsInstanceValid` 直接 CS1503
- **现象**：`error CS1503: 参数 1: 无法从"FireComponent"转换为"Godot.GodotObject?"`。
- **触发场景**：在插件里判组件有效性时顺手写了 `GodotObject.IsInstanceValid(fire)`。
- **原因**：`FireComponent` 继承 `CharacterComponentRuntime`，是**普通 C# 对象**，不是 GodotObject。
- **正确做法**：判 `fire == null || fire.IsReleased`。

### R-06 插件自建节拍用 `CanFire` ⇒ 刷屏报错
- 见通用 `D-04`。

---

## S. 与内置玩法的交互（容易被忽略的"数据开关"）

### S-01 全息投影花盆不投影 mod 植物 ⇒ `canCopy` 被写死 `false`
- **现象**：把植物种在全息投影花盆上，**完全不投影**。
- **触发场景**：生成器模板里显式写了 `canCopy = false`。
- **原因**：全息投影花盆 = 内置植物 **`PlantPotQX`**（`TOWERDEFENSE_PLANT_POTQX_NAME` → 「全息投影花盆」，
  `Asset/Anime/Character/Plant/Star/PotQX/`）。它的投影入口 `TowerDefensePlantPotQX.CreateHologramCharacter()`
  （开盆动画 `Open` 播完时触发）取**本格**角色列表，按四条筛选：
  ```csharp
  item != this
   && item.config.canCopy                                      // ★ 为 false 就永远不投影
   && item.camp == base.camp                                   // 同阵营
   && item.config.plantGridOverrideType == PLANTGRIDTYPE.NOONE  // 不是「占槽位」的植物
  ```
  再对每个候选取卡（`GetPacketConfig(ReadOnly)ByCharacterName(config.name)`），
  遍历**同列的其它行**逐格 `CanPacketPlant(packet)` 种一份全息副本
  （副本会打 `hologram` shader 参数 + `instance.hologram = true` + `canBeCollection = false` + 释放该格占用）。
- **正确做法**：config 里 `canCopy = true`（**或干脆不写这行**，默认就是 `true`）。
  **排查顺序**：① `canCopy` ② `plantGridOverrideType` ③ 同阵营 ④ `config.name` 能否查到卡 ⑤ `CanPacketPlant`。

### S-02 三个"默认值"决定能不能种 / 能不能被投影
| 字段 | 默认 | 影响 |
|---|---|---|
| `canCopy` | **`true`**（`TowerDefenseCharacterConfig.cs:40`） | **不写就是 true**；为 `false` ⇒ 永不被投影 |
| `plantGridType` | `[GROUND, POT, LILYPAD]`（`:107`） | 决定能种在哪；缺 `POT` 就种不到花盆上 |
| `plantGridOverrideType` | `NOONE`（`:115`） | 非 `NOONE` 会被投影筛选直接排除 |

`PLANTGRIDTYPE`：`ALL=-1, NOONE=0, SOIL=1, GROUND=2, WATER=3, AIR=4, LILYPAD=5, POT=6, …`（`TowerDefenseEnum.cs:145`）

### S-03 园丁僵尸接触植物 ⇒ 秒杀园丁 + 自损：靠 `spikeHurt` + `physiqueTypeFlags` 的 SPIKE 位
- **现象**：想让植物像「高冰果」那样，园丁一碰就自爆、植物掉固定血。
- **触发场景**：新增这类反制植物。
- **原因**：园丁 `TowerDefenseZombieGardener.WalkProcessing/AttackProcessing` 的分支条件是
  ```csharp
  (target.instance.physiqueTypeFlags & 0x10) != 0 && target.instance.spikeHurt != -1
  ⇒ target.Hurt(100000); instance.ArmorDelete("Barrow");
  ```
  `0x10` = **SPIKE 位**。内置「高冰果」类（`Gold/IceTallnut`、`Cover/TallnutPS`、`Other/PrimalNut`）
  都是 `spikeHurt = 1000` + **`physiqueTypeFlags = 17`**（= 1 | 16）。
- **正确做法**：config 里设 `spikeHurt = <自损血量>` + `physiqueTypeFlags = <原值 | 16>`。
  ⚠️ **顺带好处**：园丁只在 `(physiqueTypeFlags & 0x10) == 0` 时才 `Barrow()` ⇒
  加了 SPIKE 位后它**永远不会去搬这个植物**，也就绕开了「被搬起再放下后失效」那类问题。

### S-04 被魅惑后「不变色」/「还在烧自己人」/「还在产脑光」
- **现象**：mod 自制皮肤角色被魅惑后，表现与内置角色不一致。
- **触发场景**：mod 角色用**自制 `.dat` 皮肤**（走 `forceLocalRender`/`forceCpuPoseRender`），
  或插件里把阵营写死了。
- **原因**（三个独立根因，别混）：
  1. **不变色**：魅惑的染色是 `TowerDefenseCharacterBuffHypnoses.FrameMeshColorMultiplier => CHARM_COLOR`，
     经 `BuffComponent.RebuildFrameMeshColor:414` → `ApplyFrameMeshColor:421-428` 落到 **`sprite.meshColor`**；
     而 `meshColor` 是 **GPU 网格颜色**，自制皮肤走的 CPU 姿态路径（`AdobeAnimateSprite.cs:9553/9575`
     → `AdobeAnimateRenderManager.SubmitCpuPose`）**不消费它**。
  2. **还在烧自己人**：灼烧/光环若把 `CreateExplode(..., excludedCamp, ...)` 的 `excludedCamp` **写死**
     （如 `CHARACTER_CAMP.ZOMBIE`），魅惑后阵营已翻转，却仍在打原阵营。该参数语义是「**排除**该阵营」。
  3. **还在产脑光**：魅惑 buff 只翻转 `camp` + 置 `instance.hypnoses = true`，**不会**动 `ProduceComponent`。
- **正确做法**：
  1. 插件在魅惑态把同一颜色**补写到 `sprite.modulate`**（CPU 路径下该属性生效）；
  2. `excludedCamp` 传 **`character.camp`**（动态）而不是字面量；
  3. 逐帧按 `character.instance.hypnoses` **幂等同步** `ProduceComponent.produceType`：
     魅惑 ⇒ `"Sun"`，否则还原 `"BrainSun"`（该字段是 `public string { get; set; }`，
     且每轮产出时现读 ⇒ 运行期改写即时生效；女王与舞者共用 `character.produce` 这一个 InstanceId，可一次覆盖）。
  ⚠️ 解除魅惑**没有**对应的静态事件 ⇒ 用**逐帧比对状态**，别指望订阅。

### S-05 「有没有某个内置机制」先去源码里找，别猜
- **经验**：本项目的几个"纯数据做不到 / 数据能做到"的判断，全靠**读源码得出**（如 S-01 的四条筛选）。
  常见入口：`Asset/Anime/Character/Plant|Zombie/<分类>/<角色>/Scene/*.cs`、
  `Script/Component/TowerDefense/Character/*/`、`Prefab/TowerDefense/Character/`、
  以及本地化表 `Asset/Translate/Translate.csv`（**中文名 → 英文 Key 的最快反查表**，
  例：`TOWERDEFENSE_PLANT_POTQX_NAME` → 「全息投影花盆」）。

### S-06 ★★★ `fireEventName = "modfire"` 抄错 = 普攻永远不开火（2026-09-30 实机踩）
- `FireComponent.cs:3182-3183`：
  ```csharp
  this.OnFireReady?.Invoke();     // ← 插件的大招骰挂在这
  FireConfiguredVolley();         // ← 引擎齐射
  ```
  **两者在同一分支**，触发条件是动画事件 `cmd ∈ fireEventName.Split("&")`。
- `fireEventName` 默认 `"fire"`。写 `"modfire"` 的本意是**掐掉原版开火链**（让插件接管普攻）；
  全项目 grep `modfire` **零命中** ⇒ 它只是"一个不存在的名字"。
- ⚠️ **插件只管大招/不接管普攻时，必须用 `fire`（或删掉该行）**；否则普攻**一颗子弹都不出**，
  而且日志里**一条报错都没有**（整块静默跳过）——极难定位。
- 判断口径：内置 143 个植物里只有 3 个显式覆盖（`flame_fire` / `fire&tail_fire`）。

### S-07 ★★★ 装扮系统（`CharacterCustomData`）：图层默认全开是个大坑
- 机制：`TowerDefensePlantConfig.customData : CharacterCustomData`；
  `customList[]` 每条 `CharacterCustomConfig` 用 **`animeFliterOpen/Close`（`&` 分隔的 AdobeAnimate 图层名）**
  切显隐；按**卡**存装扮名（`TowerDefenseInGamePacketShow.cs:1209/1246`）→ `SetCustomFliters(sprite, name)`
  → `SetFlitersRecursive(Open, true)` + `(Close, false)`。
- ★★ **`AdobeAnimateSprite.ApplyFlashAnimeDataChange()`（:10193-10209）把 `_layerVisible` 全部置 `true`**；
  Sprite 场景里的 `Animation/LayerVisible/<层名>` 才逐条覆盖。
  ⇒ **一套图集装两套皮肤时，「第二套」的图层在场景里必须写 `= false`**，否则两套同时绘制，
  表现为「装扮能装备但贴图不换」（其实是一直叠着画）。
- 层名匹配走 `_flashAnimeData.layerDictionary[层名]`（`AdobeAnimateSprite.cs:5869-5905`）⇒ 层名两边要对齐。
- 复制一份图集做皮肤的最省事做法：把皮肤2 的画做成**同批 media**，图层整组复制成 `S2_*`，
  并把伪层 `AnimeClips/AnimeEvents` 的字典 id 挪到真图层之后（避免 id 撞车）。

### S-08 ★★ 子弹外观：BulletField 硬要求 + 灰烬别留坑
- `BulletField.TryGetStaticVisualTemplate`（:4807-4880）要求 `projectileScene` 实例化出 **Node2D + Sprite2D
  + 有效且可读的 `Texture2D`**（引擎还要读 `Image` 做运行时图集打包）。
  ⇒ **mod 包里的裸 PNG 没有 loader、`.dat` 那条分支只认 `externalAtlasTexturePath`** ⇒
  只能插件 `Image.LoadPngFromBuffer` → `ImageTexture.CreateFromImage` → `new Sprite2D{Texture}` →
  `PackedScene.Pack()` → 注入 `TowerDefenseProjectileRegistry.ProjectileDictionary[key].projectileScene`
  / `TowerDefenseManager.GetProjectileConfig(key)` / `BuildConfig()` 实例 + `InvalidateConfigCache()`；
  **任一步失败要把 `projectileName` 退回内置 `Pea`**，否则一发打不出。
- `BulletField.EnsureMountedOnCharacterNode()`（:5313-5342）三前置：
  `Instance != null` / `IsInstanceValid(currentControl)` / `IsInstanceValid(GetCharacterNode())`。
  插件从 `process_frame` 主动造弹时要**先自检**，否则非战斗时刻会刷几万条
  `E_FIELD_UNAVAILABLE` + `E_MAP_BOUNDS_UNAVAILABLE`。
- **灰烬不留地面坑洞**：`CraterCreate()` 是"在该格**种一个灰烬角色**"（就是坑）；
  只想让僵尸播化灰动画 ⇒ 用 **`TowerDefenseCharacter.AshDestroy()`**
  → `DestroyComponent.SpecialDestroyEntryAsync(SpecialDestroyType.Ash)`（`DestroyComponent.cs:305`）。

