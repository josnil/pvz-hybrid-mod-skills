# 踩坑总表（僵尸专场）—— 现象 · 触发场景 · 原因 · 正确做法

> 通用坑见 `pvz-hybrid-mod-authoring/references/pitfalls.md`；
> 与植物共通的（皮肤静止 / 子精灵父代画 / 齐射 / 过火 / 魅惑 / 全息投影花盆）见
> `pvz-hybrid-plant-authoring/references/plant-pitfalls.md`，本文件不重复。
> 流程正文在 `pvz-hybrid-zombie-authoring/SKILL.md`。

---

## Z. 行走与位移

### Z-01 僵尸「原地不动 / 原地滑步」⇒ 皮肤缺 `_ground` 根运动层
- **现象**：僵尸在原地滑步（位置不动但动画在走），或干脆完全不动。
- **触发场景**：自制皮肤（尤其从静止图程序化扩帧出来的）。
- **原因**：`GroundMoveComponent` **只认 `_ground` 层**的位姿来推进位移。
  皮肤缺 `_ground` 层动画 ⇒ 引擎算不出位移量 ⇒ 原地不动。
- **正确做法**：自制 `.dat` **必须带 `_ground` 层**（奶龙僵尸案例：`nailong_skin.py` 的
  `GROUND_PX_PER_FRAME` 一处可调，用它把每帧位移烘进去）。
  **排查口径**：先看 `.dat` 的 `layers` 里有没有 `_ground`，再量每帧 origin 变化。

### Z-02 行走速度不对
- **现象**：走得比预期快/慢。
- **触发场景**：换皮肤后。
- **原因**：位移由 `_ground` 层的每帧位移 × `walkSpeedScale` 共同决定。
- **正确做法**：改 `walkSpeedScale`（场景字段）或用 `GROUND_PX_PER_FRAME` 调基准；两者不要同时乱动。

---

## H. 换头与头部

### H-01 换头后头变成「一团别的角色的图集碎片」
- **现象**：头显示成乱码贴图。
- **触发场景**：把子精灵换成**另一份 `.tres`**。
- **原因 / 正确做法**：见植物 `Q-03`（子精灵被父代画 ⇒ 采样共享大图）—— 解法同为**三节点结构**
  （身体的直接子精灵 `HeadShadow` 当位姿影子 + 普通 `Node2D` 容器 + 独立渲染的 `Head`）。

### H-02 「头位」的真实旋钮
- **现象**：改 `Head.position` 无效 / 改 `offset` 跑偏。
- **原因 / 正确做法**：见植物 `Q-05`（`UpdateChild()` 每帧重写 `Position`/`Rotation`；真旋钮是 `offset` / `offsetRotate` / `useRotate`；单位是**弧度**；屏幕位移不能直接加到 `offset`）。

### H-03 `head_scale` 改完位置跟着漂
- **现象**：只调了放大倍数，头却移位了。
- **触发场景**：改 `head_scale`。
- **原因**：放大以**锚点**为基准，放大后要保持"看起来还在原位"必须重解位置。
- **正确做法**：用工具**一次解出「新 scale + 保位置」**（本项目 `head-tools/_j16_resize.py --scale`），
  别手算。改完跑几何门（头对位反解）确认。

### H-04 「整体移一点」要按屏幕口径重解
- **症状**：按直觉改 `offset` 后，头往**反方向**跑。
- **原因**：横翻矩阵把第一列反号（见植物 `Q-05` 末段）。
- **正确做法**：位移加在**锚点**上再反解 `offset`；工具 `head-tools/_j15_shift.py`。

### H-05 层级靠树序 ⇒ 不可靠
- **现象**：偶尔头被身体盖住。
- **触发场景**：用 `move_child` 式"排到后面"来控制层级。
- **原因**：全局排序键第一位是 `ZIndex`（`AdobeAnimateSortPath.cs:37-48`；统一排序
  `AdobeAnimateRenderManager.cs:753`），`EffectiveZIndex` = **沿父链累加** Godot `z_index`
  （`AdobeAnimateSprite.cs:6513-6531`）⇒ **对树序不敏感**。
- **正确做法**：**层级写 `z_index`**（只有可见 `Head` 写 `z_index = 1`；零切片的影子件不写）。
  且「头部层级必须高于身体」要写成**无开关的不变量**（防"门控共用"型假绿，见通用 `B-02`）。

### H-06 子精灵自己的 `z_index` 完全无效
- **现象**：给被父精灵代画的子精灵设 `z_index`，没用。
- **原因**：被父代画 ⇒ 它的绘制由**父精灵的批次**决定。
- **正确做法**：要么让它**不再是被代画的子精灵**（三节点），要么改父的排序。

---

## F2. 发射与炮口（僵尸）

### F2-01 「子弹生成点」= `firePosMarkerPaths` 指向的 `Marker2D.GlobalPosition`
- **现象**：子弹从僵尸**原点**或奇怪位置出来。
- **触发场景**：以为改僵尸原点或炮口节点就能改出膛点。
- **原因**：链路是 `.tres` 的 `firePosMarkerPaths` →（`FireComponentFireProjectileConfig.cs:10`
  `public int firePosId` 默认 0 ⇒ 取第 0 个）→ `FireComponent.CreateProjectile():2698-2714`
  → `parent.GetLogicalGlobalPosition(marker2D)` → 其实现就是 `descendant.GlobalPosition`。
- **正确做法**：**要改「子弹从哪出膛」只动这个 marker**。
- ⚠️ **`HeadSlot` 是原版给护具 / DamagePoint 用的静态插槽**，其 `position` **不跟头部美术**
  （`drawLayerId=-2` 固定值）；护具看着贴在头上是**护具自己的 `offset` 补掉了差**。
  ⇒ 「挂在 `HeadSlot` 下就跟着头动画」是**错的**。
- ⚠️ **Godot `Transform2D` 只把 `position` 当平移** ⇒ 子节点局部量会被父节点 rot/scale 作用：
  `space = HeadSlot.pos + M(θ_slot, s_slot)·marker + BODY_OFFSET`（漏掉 `M·` 只在 `marker==(0,0)` 时才对）。
- ⚠️ 头若逐帧摆 ⇒ 静态 marker 值**只能对上参考帧** ⇒ 「每帧都对齐」只能靠插件每帧覆写
  （`marker.GlobalPosition = head.GlobalTransform * HeadMuzzleLocal`；改 `HEAD_OFFSET` **必须同步插件字面量**）。

### F2-02 僵尸不开火 / 开火时头不动
- **触发场景**：给僵尸加发射，但没给开火动画。
- **正确做法**：僵尸原本常常**不播开火动画** ⇒ 插件要自己**续窗口**：
  每颗 `FirePea()` → `MarkHeadFire()`（`HeadFireUntilMsec = now + 220`，`HeadFire` 37 帧 ÷ `trueFrameRate 180` ≈ 206ms）
  → `SetHeadClip("HeadFire")`；每帧 `ExpireHeadFire()` 过窗回 `HeadIdle`。
  `SetHeadClip()` **只在 clip 真的变化时才 `SetClip()`**。
  ⚠️ 连带：`TryEnforceHeadSwap` 的 clip 判定要写成「既不是 `HeadIdle` **也不是** `HeadFire` 才纠」；
  找身体不能用 `sprite.GetParent() as AdobeAnimateSprite`（可见头挂在 `HeadHolder` 下 ⇒ 恒 `null`）
  ⇒ 用「沿祖先链找最近精灵」；`ResolveHeadForFire` 用
  `FindChild("Head", recursive: true, **owned: false**)`（新节点**没有 owner**）。

### F2-03 护具（Armor）三件套
- **经验**：僵尸护具是「DamagePoint + Armor Config + ArmorData」三件套，缺一不可；
  护具贴在头上靠的是**护具自己的 `offset`**，不是挂在头部节点上（见 F2-01）。

---

## D2. 死亡与消失

### D2-01 死亡后贴图残留、不渐隐、不消失
- **现象**：僵尸死后贴图**挂着不走**，很久才消失或压根不消失。
- **触发场景**：mod 僵尸的 `dieAnimeClip` 与它实际拥有的动画剪辑**对不上**。
- **原因**（两条独立，都会卡死）：
  1. **剪辑名不存在**：`dieAnimeClip` 没被覆盖 ⇒ 用基底的 `"Death"`；
     而自制皮肤 `.tres` 里只有别的剪辑名（如只有 `BodyIdle/HeadIdle/HeadFire`）⇒
     `ZombieDeathComponent.DieEntered():178-183` **不检查 `HasClip`** 就直接 `sprite.SetAnimation(dieAnimeClip, loop:false)`
     ⇒ 动画播不出 ⇒ 永不"播完" ⇒ `AnimeCompleted` 不触发 ⇒ **不渐隐、不 Destroy**。
  2. **多段名不匹配**：`dieAnimeClip = "Death1&Death2"`（多段名），
     `ZombieDeathComponent.RefreshDeathClips()` 把它按 `&` 拆成 `["Death1","Death2"]`，
     而 `AnimeCompleted(clip)` 收到的 `clip` 是 `_clip` 的**整串** `"Death1&Death2"`
     （`AdobeAnimateSprite.SetClip` 里 `_clip = clipName`）
     ⇒ `Array.IndexOf` 恒为 -1 ⇒ `IsLandDeathAnimationClip` false ⇒ 同样卡住。
- **正确做法**：让 `dieAnimeClip` 指向**真实存在**的剪辑（`.dat` 的剪辑名表可用
  `.cache/_datclips.py` 读出来核对）。
  - 若皮肤里有 `Death1`/`Death2` 这类多段 ⇒ **改单段**（如 `"Death1"`），或改成别的**存在**的剪辑。
  - 若皮肤里**完全没有**死亡剪辑 ⇒ 要么补一个，要么指向一个存在的剪辑。
  - ⚠️ 症状还可能来自**独立子精灵**（自制头）不在宿主的 modulate 渐隐链上 ⇒
    插件侧要补「死亡时把自己的皮肤精灵一起处理」。
  - **排查顺序**：① 读 `.dat` 的剪辑名表 ② 核对场景里 `dieAnimeClip` 的值
    ③ 确认 `AnimeCompleted` 收到的字符串形态（是否多段名）。

### D2-02 死亡动画不播 / 播一半
- 见 D2-01。

---

## B2. 多体节 BOSS

### B2-01 多体节僵尸：N 个受击判定共用一条血条
- **做法要点**：`physique = 6` 启用内置 Boss 血条；各体节是**独立受击判定**，
  但血条由主节统一显示；体节之间要**消接缝**（用 `seg_stretch` / 重叠覆盖）。
- **坑**：体节之间用「最小转弯半径 `R_min`」约束转向平滑度，值太小会打结、太大不跟路。

### B2-02 多部件图拼链时接缝明显
- **触发场景**：给几张部件图自行裁剪组装。
- **正确做法**：相邻节**重叠一小段** + 让身体自然弯曲（按曲率铺贴），别首尾严格对齐。

---

## G2. 图鉴与内容登记

### G2-01 图鉴僵尸页重复
- 见通用 `D-07`（僵尸侧去重口径：反射 `Almanac._zombieLogicalConfigs` 从后往前删，再 `QueueZombieVirtualRefresh()`）。

### G2-02 `CompanionOnly` 缺类 ⇒ 整包回滚
- **现象**：`CompanionOnly` 声明的伴随脚本类找不到时，**整个包**被回滚。
- **原因**：`CompanionOnly` 是**双刃** —— 声明了就必须存在。
- **正确做法**：要么把类补上，要么别声明。声明与实现要成对。

---

## A2. 动画不自然 —— 定位与修法（★ 从「录像 → 逐层渲染」的通用打法）

> 适用场景：主人说「动画僵硬 / 只有某个部位在动 / 走路像滑步」，
> 而你自己看渲染图觉得"挺对的"。**先别改参数** —— 八成是「件切错了层」。

### A2-01 ★★ 诊断三步（顺序不要换）

1. **抽帧看真机**：`cv2.VideoCapture` 读录像 + **`PIL.Image.save` 写**
   （⚠️ `cv2.imwrite` 写中文路径**静默失败**：目录建了、文件 0 个、不报错）。
   在草坪上按 `lum<95 & ~green` 找暗像素团定位角色，**记得排除顶部卡槽**（第一版把卡槽当成了角色）。
2. **逐层单独渲染**：`dat_lib.render_frame(d, f, visible={i})` 一层一层出图。
   ⚠️ `visible` 收的是**层索引集合**（不是层名）；只有 **`parse_dat()`** 的返回带 `aw/ah/px`
   （`parse_tres` 没有）⇒ **逐层渲染必须用 `.dat`**。
   ⚠️ 层索引会随 `LAYER_ORDER` 变 ⇒ 脚本里用 `{n: i for i, (n, _) in enumerate(d["layers"])}`，别写死。
3. **「隐藏一层看画面变多少」** —— 最省事的量化法：
   ```python
   full = render(f, ALL);  wo = render(f, ALL - {idx})
   n = (np.abs(np.asarray(full).astype(int) - np.asarray(wo).astype(int)).mean(2) > 26).sum()
   ```
   实测（阿尔法小队 v5.2）：隐藏 `Alpha_blade` 只变 **57 px**、隐藏 `Zombie_body` 只变 **221 px**
   ⇒ 说明「你以为在动的那个件」其实**被别的层盖死了**。

### A2-02 ★★★ 「件名 = 骨架槽位名」≠「件里装的是那个部位」

把整张成品图**按矩形框**切件时，框会互相重叠 —— 同一处像素会同时落进好几个件。
实测：腿的像素其实**在 `Zombie_body` 里**（body 的框切到了腿），
而 body 的 draw 序**在腿层之后** ⇒ **腿件怎么转都被盖住**。
- **判据**：跟**内置同类僵尸**同口径逐层渲染对比（`out/_builtin_normal.dat`，31 层）。
  内置的 body **只画躯干**、腿层是独立的 —— 这才是"对"的结构。
- **修法（路线 B「重排层结构」）**：
  ① 把该部位**从 `img_body` 抠掉**（`img_body[U_part] = 0`，`img_plain[U_part] = 0`），
     并让它**从原图裁**（`use = src`），像素才完整；
  ② 重划该部位的**切框到真实几何**（用逐行不透明区间定位，别凭感觉）；
  ③ 检查它的 draw 序是否被压在别人下面。
- ⚠️ 抠洞时**腿不能按亮度过滤**（腿是黑的）—— 与「手臂只挖亮部」（暗部留作隐形鬼影）不同。

### A2-03 ★★★ 源骨架本来就有完整动画 —— 别自己编，**借过来**

**最大的浪费**：自己写正弦步态，而源骨架的 Walk 里本来就有真走路循环。
实测 `ZombieTimeMage` 的 Walk：`innerleg_lower` 0→**−48.3°**、`innerleg_foot` 抬脚 **+21 px**、
`outerarm_hand` 摆动 **+27.5°**。

- **`animate()` 只取第 0 帧 + 套同一个刚性变换到所有层 = 「全身一块板」**，
  这是「腿永远不动 / 走路像滑步」的**精确成因**。检查你的 `animate()` 有没有这个模式。
- **正确做法**：给每层保留它**自己的逐帧变换**（锚点法 `O_our,f = O_tm,f + M_tm,f·C_tm − M_our,f·C_our`，
  其中 `C_tm` **整段恒定**、只用第 0 帧反解一次），即「`src` 模式」。
- ★ **必须阻尼**：源骨架常是**大 Boss**（腿长），抬脚 32 px 搬到一个 Q 版小角色上会**脱体**。
  做法 = 取「相对第 0 帧」的屏幕变换 `R = Mf·M0⁻¹`、`τ = Of − O0`，
  旋转按 `sr·θ`、平移按 `st·τ` 施加 ⇒ 腿 `(1.0, 0.35)`、臂/盾 `(0.5, 0.6)` 这样配。
- **验收**：走完全程算**整体 bbox**，确认不漂移（不滑步）；量两腿角度确认**反相**。

### A2-04 武器「举不起来」⇒ 枢轴半径太小 / 铰链是空转

- **现象**：整臂只绕**肘**转，刀在胸前画个小弧，读不出「举起武器」。
- **原因**：肘在**胸口**，手到肘只有 ~10 屏幕 px ⇒ **半径太小**。换**肩**当枢轴后半径 ~26px。
- ⚠️ **空转铰链**：写「肩 + 肘」两段时，若肩的旋转矩阵取自一个**全 0 的幅度表**
  （`Rs = _rot(ARM_SWING_UP[k])`，而 `ARM_SWING_UP = [0.0]*N`），
  那肩那段其实是**单位阵** —— 等于白写，实际只绕了肘。**先量实际输出角度，别信代码结构。**
- **旋转组要挑干净**：把「装的是衣服像素」的件（如 `Zombie_outerarm_lower` 在阿尔法小队里装的是**胸口布**）
  留在组里，一转就把衣服撕下来 ⇒ **组里只留真正看得见的持械部位**（手 + 武器）。
- ⚠️ **武器必须抬 draw 序**：`Alpha_blade` 停在中间层时**被上面好几层压死**
  （实测可见像素只占 1.8%）。提到 `LAYER_ORDER` **最后**即可 ——
  因各层像素同源，**原姿合成结果不变**（IoU 不掉），但挥砍时一定看得见。

### A2-05 静止姿是「原姿锚点」，必须每轮复测

任何切件 / 层序 / 动画改动后，都要重跑「静止帧 vs 原画」的 alpha **IoU**
（本项目靶值 ≥0.97；`_iou5.py` 会做 ±12px 平移搜索后再算）。
**IoU 掉了 ⇒ 改动把原姿弄坏了**，别继续往下做。

### A2-06 `.pmod` 打包只收资源后缀

`.md` / `.py` / 备份文件掉进 mod 目录就会**被 zip 进包**，闸门报
「包内有未列入 resources 的文件」。⇒ 打包 walk 白名单：
`.png / .dat / .tres / .tscn / .dll` + `mod.json`。


---

## A3 骨架与动画的正确做法（★ 2026-10-06 阿尔法小队 v7.0.0 定案）

> 主人原话：「**先学习 Godot 引擎中僵尸骨架与僵尸动画的正确制作方法，构建合理的骨骼结构，
> 再将各个身体部件正确拼装到骨架上**」。这一节就是那次「先学引擎」的结论。

### A3-01 ★★★ 内置僵尸**没有父子骨骼链** —— 别去找骨骼，去找「逐帧变换表」

- 权威文件：`addons/AdobeAnimateEditor/Node/AdobeAnimateSlot.cs`。它是**一根骨骼**：
  `mode`(Follow=0/Drive=1)、**`followSlotId`（父骨骼索引，1-based）**、
  `drawLayerId`（画在第几层；−1=跟父、−2=盖最顶）、`offset`（局部偏移）、
  `useRotate/useScale/useSkew`（继承哪些分量）。
  `Update()`(L434-463) = `TryGetInterpolatedSlotPose(followSlotId-1)` → `Translated(offset)` → 屏蔽分量 → `ApplyRuntimeTransform`。
- 但看场景 `Asset/.../Chapter10/TimeMage/ZombieTimeMage.tscn`（**只有 47 行**）：
  根 = **整个精灵**（44 层 + `layerVisible`），下面只挂 `HeadSlot`/`ArmSlot`/`GroundSlot`/`SpellMuzzleSlot`
  这种**附加槽**。
- **★ 结论**：僵尸的身体部件**不是父子骨骼链驱动的** —— 逐帧变换**全部预烘焙在 `.tres` 的 `sliceTransforms`**
  （每帧每层一个 2×3 矩阵），引擎只照表画；`AdobeAnimateSlot` 只是给**外挂件**（帽子/武器/特效）用的挂点。
  ⇒ **「正确的骨架」= 一张逐层逐帧变换表 + 正确的 draw 序。**
  ⇒ 我们要「构建骨骼」，实际就是**给每层算出正确的逐帧矩阵**，而不是搭 Node 树。

### A3-02 ★★★ 正解 =「根骨骼 + 局部关节」（v7 `"bone"` 模式）

单层直接取自己的逐帧变换（v6 的 `"src"` 模式）会**炸**：每层绕**自己的**关节、用**自己的**平移，
各层不共享刚性 ⇒ 头/颈/帽各飞各的（实测头平移被放大 6.2→8.2）。

正确做法（对齐 `AdobeAnimateSlot` 的「父变换 + 局部偏移」口径）：

```
① 根 = 躯干（如 Zombie_body）：
   R_root = M_body(f)·M_body(f_clip0)⁻¹ ，τ_root = O_body(f) − O_body(f_clip0)
   ⇒ 全身件【共享同一份 R_root/τ_root】 ← 这是「绝不错位」的保证
② 每层只叠自己的【局部】转动  θ_loc = θ_L − θ_root，绕【该层自己的关节】P：
   增益 LOC_GAIN：腿 0.85 / 近臂 0.60 / 远臂 0.60；未列入者 gain=0（刚性贴躯干）
③ 阻尼 ROOT_DAMP_ROT≈0.75 / ROOT_DAMP_TR≈0.60
```

- `gain=0` 的层（头/颈/帽）**天然刚性贴躯干** ⇒ 一举消灭「头飞」「颈冻」两类病。
- 实测根骨骼参数：`pivot=(22.1,40.6)`、`Walk 段 max|rot|=9.3°`、`max|tau|=7.1 px`。
- 腿要**真迈步**：腿增益给足（0.85），实测水平位移 ≈ 12% 身高才算走出来。

### A3-03 ★★ 攻击：先量「手 / 武器」相对肩的方位，再定角度符号

- **别凭感觉给角度**。先量两个向量（相对肩）：
  手套中心 d、**武器尖端 d** —— 两者常在肩的**两侧**（武器比手臂长）。
  本项目：手套 d=(−21,+76)、刀尖 d=(+106,+79)，僵尸**面朝左**。
- 扫档表（肩骨角 → 手 / 刀尖方位）：

  | 肩骨角 | 手 | 刀尖 | 读法 |
  |---|---|---|---|
  | 0° | 下左 | 下右 | 原姿 |
  | +60° | 下左 | 下左 | 劈到底 |
  | **+150°** | **上左** | **上左** | ★举武器过顶 |
  | −150° | 上右 | 上左 | **手甩身后**（典型的「武器向后抬」bug） |

- ⇒ 定案 `0° → +150°（举） → +60°（劈） → 0°`，武器层放 `LAYER_ORDER` **最后**（不被压死）。
- ⚠️ **腕骨角别乱加**：试给武器加 156° 相对转动 ⇒ 武器中心离握把 106 px ⇒ **整把武器甩飞**。
  定案：武器「长在手上」（腕骨角全 0），**由肩骨角决定武器朝向**。

### A3-04 ★★ 「挖空」之后必须「补背景」，否则抬腿/抬臂露洞

- `leg_group_mask()` 把腿从 `img_body` 挖出来之后，**原来的位置是空的** ⇒ 一抬腿就露洞。
- 正解：挖完立刻用 `coat_fill(arr, alpha, mask, inside)` **补上背景像素**（取色只从暗像素取）。
- **验收**：垫纯洋红底渲染，看有没有露出底色。

### A3-05 ★ 复用铁律：件名来自骨架槽位 ≠ 里面装的像素

`Zombie_outerarm_upper/_lower` 在阿尔法小队里装的其实是**胸口/黑大衣**，只是沿用了骨架槽位名。
⇒ **挂枢轴之前先「单独渲染该件」看它到底是什么**，否则一转就把衣服撕下来。

### A3-06 验收口径（v7 全绿）

| 项 | 值 |
|---|---|
| 静止姿 IoU | ≥ 0.97（本项目 0.975） |
| 走路 | 腿水平位移 ≈ 12% 身高；头 θ_loc ≈ 0（不飞） |
| 不露洞 | 洋红底渲染无底色 |
| 打包 | 幂等（两次同 sha256）；闸门 FAIL=0 |

### A3-07 ★★★ 抠部件禁用「硬亮度切割」—— 必须用「连通域 + 膨胀」（v7.1.0 血泪）

**症状**：想把白毛袖口/手套从整张图里抠出来，用 `lum > 阈值` 硬切 ⇒ 袖口**灰暗根部被切碎**，
渲染出来**手臂变成一堆麻点**。

**正解**（`_arm_keep_mask`）：
1. 用较宽松亮度取**种子**（`ARM_LUM`）；
2. `flood-fill` 求连通域，**只保留面积 ≥ `ARM_CC_MIN` 的块**（丢小碎块）；
3. 对保留块做 `ARM_GROW` 次**滚动膨胀**（`np.roll` 四邻域），每次只吃**相邻且在 alpha 内**的像素
   ⇒ 把灰暗根部 + 黑描边一起**吃回来**。

**扫档定值**：`ARM_CC_MIN` 150→250→400→600，**400 起稳定**（保留 4576 px）；`ARM_GROW=6`。

★ **通用结论**：凡「抠出语义部件（手臂/尾巴/披风/毛料）」且该部件**边缘渐暗或带描边** ⇒ 一律连通域生长，禁硬阈值。

### A3-08 ★★ 攻击「只有武器动、手臂不动」⇒ 手臂件没进武器组（v7.1.0）

**根因**：`ARM_GROUP` 只纳入了武器，手臂件（`_lower` 袖口 / `_hand` 手套）不在其中；
或它们的**框落在披风/衣领**上 ⇒ 位移实测 **0.00 px**。

**诊断**：逐层算「攻击**首帧 vs 峰值帧**的**中心位移**」一表列出，哪层该动却没动一眼可见（本项目 `_diag8c.py`）。
再「**每件单独贴出总览**」（`_diag8d.py`）确认「件里到底装了什么像素」。

**修法**：`ARM_GROUP = (袖口件, 手套件, 武器件)` **共用肩枢轴刚性同转**；枢轴要**按真手臂重新定标**
（v7.1：`ARM_PIVOT_XY` 由 (232,196) → **(198,222)**）。

**验收**：`袖口 11.6 px / 手套 12.7 px / 刀 8.1 px` **同帧同向**。

### A3-09 ★★ 「武器动完原位残留一份」⇒ 挖空只抹了亮部（v7.1.0）

**根因**：`make_clean_base()` 的挖空掩码**只抹亮部** ⇒ 武器**暗部描边**（本项目刀刃 1171 px）留在身体图上，
一动就是「另一把武器」。

**修法**：`U = U | U_blade_full`（**含暗部的完整足迹**）再去补背景 ⇒ **武器只有一个来源**。

**验收**：只显 `body + weapon` 全序列渲染，**无鬼影武器**（负向断言必须非空）。


## A4 部件图集装配 · 原版动画 · 动作微调（★ 2026-10-06 阿尔法小队 v8.0 / v8.1 定案）

### A4-01 ★★★ 先判断「拿到的是成稿图还是部件图集」
**症状**：按关节在图上切件后怎么调都对不上，且总有部件互相重叠／多出一个副本。
**自查**：① 尺寸是不是 512×1024 / 2048×2048 这类「图集尺寸」；
② 用 UnityPy / AssetStudio 看 Prefab 里各 `SpriteRenderer` 的 `sprite.rect` 是否**互不重叠地铺满**一张大图；
③ 数件数（本项目 26 个精灵）。
**结论**：是部件图集 ⇒ 配套一定有 **Prefab 层级 + 原版动画**，直接照层级装配 + 直接用原版动画，**别自己切**。

### A4-02 ★★★ 同名根陷阱——工具默认只抓第一个
**症状**：导出工具报「该 GameObject 没有 Animator」。
**根因**：同名 GameObject 有多个。本项目 `LegionZombie` root1 = 原点 / scale 1 / atlas A（**无 Animator**）；
root2 = scale **1.25** / x=6.41 / atlas B（**带 Animator**）。
**修法**：遍历同名根，记 `fallbackRoot`，遇到**被 Animator 引用的那个**再 `root = g`（`_tools/asexp/Program.cs` 已打补丁）。

### A4-03 ★★★ 层级递推必须走「全部」节点——含无精灵的中间节点
只走「有精灵的件」会**丢掉中间节点的动画**（本项目 `weapon_1` 的局部位移是相对 `weapon` 的）。
用 `chain`（根+子+孙 唯一键）按 `depth` 预序递推；`Trail_1` 这类重名节点靠 chain 避免成环。

### A4-04 ★★★ Unity 动画 → 画布切片：两处还原坑 + 三条放置口径
- `Translations` 是绑定局部的 **X 镜像** ⇒ **x 取反、Y 不变**
- `Rotations` 单位是**百分之一度**（×0.01）且需**取反**
- 放置：`X = A·u + B·v + Tx`，`k = 100/ptu`，**图集 rect 原点在左下**（媒体 y = `AH − ry − rh`）
- **只对子图做 AFFINE**；绘制序 = `sorting` **升序**（同序号保持 JSON 原始先后 = 稳定排序）

### A4-05 ★★ 左右臂「天然独立」—— 「动一只、另一只袖口跟着动」的根治
**根因**：是**自己造的联动**（把两侧件塞进同一个「手臂组」共用枢轴/同转），不是引擎行为。
**正解**：源预制体里两臂本来就是**两条互不相干的根级链**（各有独立动画 Path）⇒ 照层级装配即天然独立。
**验收**：两链 attack 段逐帧轨迹最大差 **> 5 px**（本项目 49.7 px）。

### A4-06 ★★ `_ground` 伪层口径（缺了 ⇒ 僵尸原地踏步）
内置 `ZombieNormal` / `ZombieTimeMage` 完全一致：**walk 段 ox −10 → +40 线性、oy = 40 常量**，其余 clip 空。
`GroundMoveComponent` 靠它推角色移动；`layerVisible[0] = False` 不渲染。

### A4-07 ★★★ 「某部件晃动太飘」⇒ 与上游关节做**保均值耦合**，别硬压幅度
```python
T' = ĥ + (1-k)*(b - b̂) + k*(h - ĥ)      # h=该件动画位移, b=上游关节位移, ĥ/b̂=各自在 clip 内的均值
```
- **不保均值**（误写成 `b + k*(h-b)`）会把部件**整体挪位**——本项目头部直接下沉 ~8 px、右移 ~5 px（往领口里沉）
- 上游件与目标件是**同级兄弟**时，局部位移可直接相减
- 本项目 k=0.20 ⇒ 头心摆幅 **31.0→14.8 px / 15.7→10.6 px**，且**轨迹包围盒中心不变**
- 只对需要安静的 clip 生效（本项目 `{walk, quickmove}`），idle/attack/die 一个像素不动

### A4-08 ★★★ 「改某部件的朝向」⇒ 把旋转加在**无精灵的中间父节点**上
带精灵的节点 pivot 常在**几何中心**（本项目刀 `weapon_1` rect 126×64 / pivot 0.5,0.5）⇒ 绕它转 = **自转**。
**无精灵的中间节点**（`weapon`）原点才是**关节**（本项目 ≈ 手套）⇒ 绕它转 = 手腕动作。
实现：局部矩阵**后乘** `L ← L·Rot(φ)`（只动 2×2，不动平移）。
**屏幕角与局部角的关系先扫档测出来再写死**（本项目实测线性 `θ = −22.8 − φ`，一个 for 循环就测完）。

### A4-09 ★★ 攻击时序：新动作要避开「本身有意义的阶段」
本项目源动画节奏 = 抬刀 f41→47 / 高位保持 f47→53 / 下砸 f53→55（**仅 2 帧**）/ 收势 f56→60。
把刀刃翻转放在**抬刀期** ⇒ 刀在**脸前面横穿**过去（渲染图一眼可见，已否）；放进「下砸 + 收势」才对。
**首尾帧必须回到原版朝向**，否则与相邻 clip 跳变。

### A4-10 ★★ 加了新动作后，「自动找极值帧」的判据必须复审
原来用「刀尖最低点」自动定命中帧；加了收势回摆后该点被带到 f58（伤害时序错 1 帧）。
改为「**刀刃首次抵达目标角的那一帧**」⇒ f56，与旧版一致。
**通用建议**：命中帧能显式定义就**显式写死**，别依赖极值搜。

### A4-11 ★★ 验收口径：**逐帧逐层 diff 旧版 `.dat`**
把「变了哪些层 / 哪些帧 / 落在哪个 clip」列成一表。本项目 v8.1 相对 v8.0 只有
`Zombie_head`（walk+quickmove，66 帧）与 `weapon_1`（attack，7 帧）有变化，其余**逐字节一致**。
这才是「只改了该改的」的证据；同时在闸门里加**回归守卫**（头摆幅阈值 / 命中帧刀刃角区间 / 首末帧角）。

---

## A5 完整逻辑 · 托管 DLL 防具换图 · 保 1 血 / 倒地 / 突进（★ 2026-10-06 阿尔法小队 v9.0.1.0 定案）

> 把「外观 Mod」升格为「有状态机、有防具分档、有倒地/突进、有托管 DLL」的完整单位时踩的坑。
> **最惨的一条总纲**：这一节里的 F1/F2/F3 三处缺陷，**离线闸门全部全绿、实机必然翻车** —— 闸门验数据，验不出运行期状态机打架。

### A5-01 ★★★ 防具 `typeData` 只认内置 `ArmorRegistry` ⇒ 自定义盾必须 DLL `RegisterArmor`
`TowerDefenseArmorInstance` 构造（`TowerDefenseArmorInstance.cs:98`）里
`typeData = TowerDefenseArmorRegistry.GetArmorType(slotConfig.armorName)`；**取不到就 `isRemove = true` 直接返回**（`:111`）
⇒ 盾牌静默不生效（无任何报错）。
内置注册表是 `res://Registry/Armor/ArmorRegistry.json`（43 条），**只读、不可由 config 追加**。
**正解**：在托管入口 `Initialize()` 里 `TowerDefenseArmorRegistry.RegisterArmor(new StringName("你的盾名"), typeData)`。
`RegisterArmor`（`:40`）**直接覆盖、不判重**；`GetArmorType`（`:45`）返回 **Duplicate**（改副本不影响注册表）。
`stagePersontage` setter 内部会**降序排序**，写的时候不用自己排。

### A5-02 ★★ 防具的「显隐/分档」是 flag + fliter 决定的，别指望 `DROPABLE`
- **分档开关 = `armorMethodFlags & 0x40`（`DAMAGEABLE`）**：`RefreshDamageStageFromHitPoints`（`:224`）开头
  `if (… || (armorMethodFlags & 0x40) == 0) return;` ⇒ 想用「原生三档贴图」必须置 `0x40`；
  若**故意留空** `stagePersontage`/`stageAnimeTexturePaths`，原生分档就**永不触发**（我们就是这样让 DLL 接管分档）。
- **`0x80`（`DROPABLE`）= 打穿时掉碎片**：`if (createDamagePart && (armorMethodFlags & 0x80) != 0) DamagePartCreate(velocity);`（`:187`）。
  **想「打穿不掉碎片」就别设 `0x80`**（不是靠设 `isRemove`）。
- **`0x04`（`SHIELD`）= 只挡直线伤害**：引擎 `FlagHurt` 的盾层判定含 `(damageFlags & HITSHIELD(1)) != 0` ⇒ 「只吸收直线伤害」是**引擎自带**，写对 flag 即可。
- **槽位侧**：`replaceMethod == "Media"` 时构造里会调 `character.SetArmor(slotConfig.armorName, 0)`（`:133`）；
  `(flags & 4) != 0` 时 `TowerDefenseShieldImpactBatch.Prepare(character)`（`:135`）。
- **我们选定的盾口径**（可照抄）：`damagePoint=6000` / `armorMethodFlags = 4|0x10|0x40 = 84`（**不设 `0x80`**）/
  `height=NORMAL` / `stagePersontage` 与 `stageAnimeTexturePaths` **故意留空**。
- **动态显隐**：`AdobeAnimateSprite.SetFliter(StringName, bool)`（`:5869`，**有 `layerDictionary.ContainsKey` 守卫**，不存在则 no-op）；
  `SetFliters(Array, bool)`（`:5899`）。碎掉/隐藏可用它，或 `SetAtlasReplace(media, "")`。

### A5-03 ★★★ 判「防具实例还活着」**不能只看 `isRemove`** —— `RemoveArmor` 不设它
`RemoveArmor(ArmorRemovalReason, bool dispatchBehavior = true)`（`:360`）**只做移除动作、不设 `isRemove`**；
`isRemove = true` 只在 `Draw()`（`:411`）与构造早退（`:104`/`:111`）里出现。
⇒ 盾被打碎后实例**仍留在 `inst.armorShield`**，且 `hitPoints == 0`。
**症状**：DLL 每帧找盾刷「严重破损」贴图时把它当成活盾 ⇒ 把贴图 **`SetReplace` 回已碎的盾**上（还会把 `_mediaReplaceUse` 改回 true）⇒ **碎盾「复活」**。
**正解**：判活条件必须叠加血量 —— `if (a != null && !a.isRemove && a.hitPoints > 0.0 && IsInstanceValid(a))`。
同理 `DispatchRemoved`（`:525`）只处理 behavior；`TryApplyStableDamage`（`:149`）在 `hitPoints` 掉到 0 时走
`RemoveArmor(ArmorRemovalReason.Broken, dispatchBehavior:false)`（`:199`）。

### A5-04 ⛔【已被 A7-01/A7-02 推翻 · v9.1.0.0】~~`.pmod` 内给防具换贴图**必须走 `SetReplace(Texture2D)`**~~
> **此结论错误，勿照做。** `.pmod` 里 `SetReplace` **不可能生效** —— 引擎只认预烘进全局 `Texture2DArray` 图集的纹理，
> mod 自带 PNG 会被 `DisableUnsharedMediaReplaceTextures` **整个禁用**。正解见 **A7-01 / A7-02**（烘进动画自带图集 + `SetFliter` 切层）。
> 下列内容仅作「当年的错误方向」存档。
`CharacterArmorData.SetArmorReplace`（`:157`）→ `sprite.SetAtlasReplace(replaceMediaName, stageAnimeTexturePaths[index])`；
而 `AdobeAnimateSprite.SetAtlasReplace`（`:6000`）**只存路径字符串**（`:6013 _mediaReplaceAtlasPaths[num] = value`），
真正解析只认 `res://` / `uid://` ⇒ **包内 PNG 静默不生效**（Surface 上你会看到防具「根本没换图」）。
**唯一可行口**：`AdobeAnimateSprite.SetReplace(StringName mediaName, Texture2D texture)`（`:5979`）——
命中 `mediaDictionary.ContainsKey(mediaName)` 才写入 `_mediaReplace[num]`、清空 `_mediaReplaceAtlasPaths[num]`、
置 `_mediaReplaceUse[num] = IsInstanceValid(texture)`，并 `QueueUpdateMediaReplace()`。
`Texture2D` 从哪来：包内贴图声明进 `provides.Texture` 后，用 `XWModRuntimeRegistry.TryGetRuntimeTexture(key, out tex)` 取（key = 文件名去扩展名）。

### A5-05 ★★ **媒体名带 `.png` 后缀** —— 别用 `Zombie_head`，要用 `Zombie_head.png`
> ⚠ **v9.1.0.0 补充**：本条的「媒体名带 `.png`」事实**依然成立**（`.dat` 媒体表就是这么存的），
> 但**它服务的 `SetReplace` 通路已在 `.pmod` 里失效**（见 A7-01）。若你走 A7-02 的「烘进图集 + `SetFliter`」方案，
> 换成按 **`.dat` 图层名**（本例 `Zombie_head` / `head1` / `head2` / `shield` / `shield1` / `shield2`，**不带 `.png`**）切层。
`AdobeAnimateData.cs:755-757` `mediaDictionary[result.MediaNames[i]] = i`，而 `MediaNames` **直接来自 .dat 的媒体表**
⇒ 本包媒体名就是 **`Zombie_head.png`**、**`shield.png`**（含扩展名）。
`SetReplace` / `SetAtlasReplace` / `GetReplace` 全部按这个字符串匹配，**写错一个字就静默 no-op**。
**自检**：`GetReplace(StringName)`（`:6038`）返回当前 `_mediaReplace[num]`，可用来**探测媒体名是否命中**（没命中就拿不到替换图）。

### A5-06 ★★★ `SetAnimation` **非幂等** —— 逐帧强压会把动画**永久冻结在第 0 帧**
`SetAnimation(string, bool loop=true, double blendTime=0.0)`（`:5751`）→ `ApplyImmediateAnimation`（`:5830`）→ `SetClip`（`:5651`），
而 `SetClip` 在 **`:5691 frameIndex = clipRange.X;`** **无条件**把播放位置重置回 clip 首帧。
⇒ 状态机若每帧 `sprite.SetAnimation(DownedClip, true)`，动画就永远停在 `downed` 的 f0（**看起来站着不动**）。
**正解**：只在 clip **真的变化**时才切（对齐引擎 `WalkEntered` 范式）：
```csharp
if (string.Equals(sprite.clip, clip, StringComparison.Ordinal)) return;   // 幂等守卫
sprite.SetAnimation(clip, true);
```
`clip` 属性可读：`[Export] public string clip { get => _clip; set => SetClip(value); }`（`:1341`）。
**注意**：「首次推入某 clip」仍要无条件调（那是真需要重置到 f0）；只有「持续保持」才加守卫。

### A5-07 ★★ **保 1 血三件套 + 真死流程**（「无临界值机制」的实现范式）
- **保 1 血**：`SkipInvincibleDealHurt`（`:1106`）内
  `:1131 if (damageHitpointsFloor > 0.0 && num > 0.0 && hitpoints > 0.0 && !die) num = Math.Min(num, Math.Max(0.0, hitpoints - damageHitpointsFloor));`
  ⇒ 设 `instance.damageHitpointsFloor = 1.0` 后，**血量恒不低于 1**。
- **关掉内置濒死/掉头**：`instance.hitpointsNearDeath = 0`（或 config 同名）+ `instance.keepAlive = true`
  ⇒ 濒死分支（`:1196`）与死亡分支（`:1210`）**都不触发**（`keepAlive` 保活、`damageHitpointsFloor` 保血）。
  引擎自带范式可参考「纸巾伽刚特尔」`TowerDefenseZombieGargantuarPaper.GaspEntered/GaspExited`（进入/退出时保存与恢复这两个字段）。
- **要真死时**（DLL 手写同构流程）：`TowerDefenseZombie.EnsureZeroHealthDeath()` 是 private，
  但它调的 `ConvergeZeroHealthDeath(instance)` 用的全是 **public**：
  `SkipInvincibleDealHurt(0.0, …)` → `nearDie = true` → `HitpointsNearDie()` → `DieMethod()` → `HitpointsEmpty()`。
  （先把自己设的 `damageHitpointsFloor`/`keepAlive` 复位，否则冻在 1 血。）
- 关键字段（`TowerDefenseCharacterInstance`）：`hitpoints`(`:47`) / `hitpointsBase`(`:70`) / `hitpointsSave`(`:44`) /
  `hitpointsNearDeath`(`:67`) / `keepAlive`(`:122`) / `damageHitpointsFloor`(`:124`) / `nearDie`(`:130`) / `die`(`:127`) /
  `armorShield`(`:165`)。事件 `:252-260`（`hitpointsNearDie`/`hitpointsEmpty`/`armorHitpointsEmpty`…）。

### A5-08 ★★ `attackEventName` 默认是 **`"attack"`**（不是 `"hit"`）⇒ 一般**不存在双重结算**
`AttackComponent.cs:532 attackEventName = "attack"`；`AnimeEvent`（`:3468`）只在
`CanExecuteGameplay && alive && IsInstanceValid(parent) && !parent.die && !parent.nearDie && command == attackEventName` 时才 `OnAttack?.Invoke()`。
⇒ 皮肤里叫 `hit` 的自定义事件**不会**触发 `OnAttack`。
（曾怀疑 `TowerDefenseCharacter.cs:2081` 与 `AttackComponent.cs:946` 双订阅会双结算 —— **不存在**：前者调基类 `AnimeEvent`，
而 `TowerDefenseCharacter.AnimeEvent` 在 **`:3866` 是空实现**。）
**攻击判定要点**：`AttackExecute(double)`（`:2942`）开头 `if (IsRemoteSyncedAttacker() || !CanExecuteGameplayEffect()) return num;`；
`target == null` 提前返回（`:2948`）；随后 `target.AttackDeal(parent, attackType, num)` → `cell.AttackDeal` → `EventExecute`
→ `skipDealHurtReduce = true` → `target.Hurt(num, true, Vector2.Zero)` → 复位。`attackType`(`:522`) 默认 `"Eat"`（挥砍填你自己的类型）。

### A5-09 ★★ `ArmorSlotConfig.replaceMethod` **默认就是 `"Media"`** —— 没写 ≠ 没配
`ArmorSlotConfig.cs:12 public string replaceMethod = "Media";`（`[Export(PropertyHint.Enum,"Media,Sprite")]`）。
铁栅门僵尸 `Asset/…/Normal/Armor/Config/ZombieNormalArmorScreendoor.tres` 就**没写这个字段**，仍然走 Media ⇒ 口径一致，别被「缺字段」吓到。
其余默认：`armorName=""` / `replaceMediaName=""` / `slotPath="HeadSlot"` / `damagePoint=-1.0`（负值 ⇒ 用 typeData 的）。
`CharacterArmorData.GetOrCreateSlotConfig`（`:205`）默认建的是 `replaceMethod="Sprite"`（另一条路），注意别混。

### A5-10 ★★ 僵尸速度**唯一来源是 `_ground` 伪层**；`walkSpeedScale` 全库无读取点
`GroundMoveComponent` 靠「参考帧 ox − 当前帧 ox」推位移（`WantsPhysicsProcess => HasMovementSource`，`:118`；`SetAlive(bool)`，`:169` **可逆**）——
**首尾帧位移被丢弃**。内置 `ZombieNormal` 的 `_ground`：walk 段 `ox −10 → +40` 线性、`oy = 40` 常量，其余 clip 空、`layerVisible[0]=False`。
`TowerDefenseZombie.walkSpeedScale`（`:108`）在整个程序集里**没有任何读取点** ⇒ 改它没用。
（所以我们算 `span = 50·nfr/47` 来对齐「与普通僵尸同速」；本项目均速 1.09043 px/帧 vs 内置 1.08696。）

### A5-11 ★★ 包内贴图必须在 `mod.json` 的 `provides.Texture` 声明，否则**整包被拒**
`ModLoader.InferRuntimeEntry`：路径以 `Assets/Textures/`|`Assets/Texture/`|`Assets/Images/` 开头且扩展名受支持 ⇒ `category="Texture"`，
**`key = Path.GetFileNameWithoutExtension(text)`**（去目录、去扩展名）。
**包内含 `Runtime/ModAssembly.dll` 时，每个自动发现候选都必须被 manifest 声明**，否则报
`"resource is not unambiguously declared by manifest"` ⇒ **整包拒绝加载**。
⇒ 有 DLL 的包，`provides` 必须把每张图写成 `Texture/<文件名去扩展名>`。

### A5-12 ★★ 换图预览要**写回图集媒体矩形**；动画源帧要按**量化判据**挑
- **预览**：想离线看「`SetReplace` 之后长什么样」，把新贴图 `paste` 回**图集的媒体矩形**
  （本包 媒体 1 `shield.png` rect `0,0,123,171`；媒体 16 `Zombie_head.png` rect `124,0,135,126`），再用自写 `render_at()` 渲染 ⇒ 与运行时**等价**。
- **挑源帧**：别凭感觉。本项目「倒地」一开始复刻 `fakedie` f111，看着像倒下，实测**头心距脚底 = 105.3/107.8 = 98% 站立高**（= 站着）。
  改用「**头心 Y − 脚底 Y**」做判据扫全 clip：站立基线 f20 = 107.8；f111 = 98%；f115 = 77%；**f116/f117/f118 = 72%（最低）**；
  quickmove f126/128/140 = 73%（属突进动画，不宜挪用）；die 最低 f90 = 85%。
  ⇒ `DOWNFALL_SRC` 111 → **116**，并把这个比值写成**闸门 G29（≤80%）**。
  ⚠ 若素材**没有真正的膝触地帧**（本例就是），老实标注为「低伏待援姿态」，别硬说成「单膝跪地」。
- **改源帧后必须逐帧逐层 diff**：本例相对上一版**只有 downed 段 144–155 变**，其余 156 帧逐字节不变。

---

## A6 程序化姿态装配 · 倒地入场 · 三档换图自愈（★ 2026-10-06 阿尔法小队 v9.0.2.0 定案）

> 触发场景：**素材里没有想要的姿态**（本例：全库 156 帧都没有「单膝跪地／膝触地」），
> 但需求又必须满足（主人给了参考图要求跪姿）。

### A6-01 ★★★ 素材里没有的姿态 —— 用「关节整组旋转」算出来，别硬等素材
- **判据先立**：先用「头心距脚底 / 站立基线」扫全库确认**真的没有**（本例最低 72%，且是「前冲深蹲」，
  6× 腿部特写逐帧看：低伏帧**脚掌均平贴地面**，没有膝触地）。
- **做法**：把每层当成刚体，绕一个**枢轴**整体转 —— **位置与朝向必须同时旋转**：
  ```python
  nxx = ca*xx - sa*xy;  nyx = ca*yx - sa*yy      # 朝向
  nxy = sa*xx + ca*xy;  nyy = sa*yx + ca*yy
  ox', oy' = px + ca*(ox-px) - sa*(oy-py) + dx, py + sa*(ox-px) + ca*(oy-py) + dy   # 位置
  ```
  `pivot` 可以是**世界坐标**（关节位置）、某层原点、或某层**不透明像素质心**。
- **分组**：后腿小腿+踝（折腿）、上身+头+近臂（回正）、持刀臂（下摆）、盾臂（后摆）……
  **臂组必须含武器层**，否则刀/枪与手脱节。
- **转末端器具**（刀、盾）要绕**它当前的实际握点**（手心的世界坐标）—— 手会先被臂摆带走，
  用初始手位当枢轴会脱节。
- **沉淀成 env 参数**（本例 7 个：`KNEEL_DROP/FOLD/STRAIGHT/ARM/WROT/SHIELD`），
  这样姿态可以大范围试参而不必改代码；bake 只要 2.6 s。

### A6-02 ★★★ 验收必须**像素级**：不透明像素质心 + PCA 主轴 —— 包围盒会被透明留白骗
- `.dat` 切片 rect（媒体矩形）**比实际像素大**（含透明留白），用 rect 四角算包围盒会得到错的「头心/刀尖」。
- 正解：裁出媒体矩形 → 遍历 `alpha > 16` 的像素 → 取质心 / 用 `np.linalg.eigh` 求 PCA 主轴 → 主轴两端点即「刀柄 / 刀尖」。
- 用具：`_sweep20.py --measure`、`_pose_lab.py`。

### A6-03 ★★★ 「静止摆一个姿势 12 秒」≠「有倒地动画」—— 入场必须有一段真实的过程动画
- 本例 `downed` 是「对最深帧做关节装配后**保持**」，从走路切过去是**瞬间**的，没有「倒下去」的过程。
- **零成本正解：直接复用源动画里的过程段**。把 `fakedie` f107→f118 逐帧渲出来后确认：
  **它本身就是一段 12 帧的「缓缓跪倒」**（f107≈站立 → f111 前倾 → f116–118 最深）。
- 实现（两段式，仍然只走 `EnsureClip`，不违反 A5-06）：
  ```csharp
  private const string FakedieClip = "fakedie";
  private const double FakedieSeconds = 0.92;   // 12 帧 @12fps = 1.00 s，留 8% 余量
  // EnterDownedOrDie：sprite.SetAnimation(FakedieClip, true);
  // StepDowned：      string want = (now - st.DownedAt) < FakedieSeconds ? FakedieClip : DownedClip;
  //                   EnsureClip(sprite, want, "倒地");
  ```
- ⚠ **源 clip 是循环播放的** ⇒ 复用某段做「播一次」必须**按时间提前切走**，压满整段会闪一帧起始姿势。
- ⚠ 复用的源 clip 的 `_ground` **必须为空**（本例只有 walk 段有 `_ground`）⇒ 否则会与 DLL 手动位移打架。

### A6-04 ⛔【已被 A7-01/A7-02 推翻 · v9.1.0.0】~~`SetReplace` 的 deferred 更新会**静默失效** ⇒ 换图必须「每帧校准 + 主动刷」~~
> **此「正解三步」方向错误，勿照做。** 真相不是「守卫卡住」，而是**纹理根本进不了共享 `Texture2DArray` 图集**，
> 引擎主动调 `DisableUnsharedMediaReplaceTextures` 把替换**整个关掉**；“每帧校准 + 主动刷”只会让它更快地被禁掉。
> 正解见 **A7-01 / A7-02**。下列内容仅作「当年的错误方向」存档。
- `SetReplace(name, tex)`（`AdobeAnimateSprite.cs:5979`）末尾只做 `QueueUpdateMediaReplace()`
  （`:9444`）—— **deferred 且带 `needMediaReplaceUpdate` 守卫**。守卫一旦卡住
  （或引擎在切 clip / 重设动画数据时重建了 `_mediaReplace`），替换就**静默失效**：
  **无异常、无日志，画面一直是 .dat 原图**。实机「盾/面具从不显示破损档」的直接原因就是这个。
- **正解三步**：
  1. 首次按**候选媒体名名单**探测（`SetReplace` → `UpdateMediaReplace` → `GetReplace` 反查命中的那个）；
  2. 之后**每帧校准**：`GetReplace(name)` 比对 `GetInstanceId()`，一致就 `return`（零开销 ——
     引擎的守卫会吞掉重复请求）；
  3. 不一致 ⇒ 补写一次并**主动**调 `sprite.UpdateMediaReplace()`（public，`:9458`）立刻落地。
- 候选名要兼容写法差异：`{"Zombie_head.png","Zombie_head","head"}` 这种。

### A6-05 ★★ 分档换图的**分母**别用 `hitpointsSave`
- `TowerDefenseCharacterInstance.hitpointsSave` 初值 **200.0**，部分创建路径下**不会被同步**成配置血量。
- 若用它当分母：`ratio = 6000/200 = 30` ⇒ 档位**永远算作 0** ⇒ 实机上「面具从不出现破损贴图」。
- 血量固定的 mod **直接用配置常量**当分母最稳。

### A6-06 ★★★ 「有同伴就保 1 血」判据必须排除**已经倒地的同伴**，否则永不真死
- 旧写法 `HasOtherLivingSquad`（只看「同 packet 且未 die/nearDie」）会把**正在倒地的同类**也算成援军
  ⇒ 全场最后一个倒地者会**一直保 1 血**，永远不真死。
- 正解 `HasOtherStandingSquad`：额外排除自己状态表里的 `ost.Downed`（倒地中）与 `ost.Dying`（已放行真死）。
- 需求口径（本例）：**全员进入倒地 ⇒ 立即真死**；单只在倒地期间检测到「场上已无站立同类」就 `TrueDeath`。

### A6-07 ★★ 闸门要给「新判据」配防回归项（本例 G30）
- 只查 DLL 字节分不清「条件调用 vs 无条件调用」，**必须查托管源码**（strip 注释后按方法体正则切块）。
- G30 六条：`ApplyReplace` 用 `SetReplace(` / 用 `GetReplace(` 反查 / 主动 `UpdateMediaReplace()`；
  旧符号 `HasOtherLivingSquad` **彻底移除**；`HasOtherStandingSquad` 同时排除 `ost.Downed`/`ost.Dying`；
  `StepDowned` 按 `FakedieSeconds` 在 `FakedieClip`/`DownedClip` 间切 + `EnterDownedOrDie` 入场即播 `fakedie`
  + 烘焙产物含 `fakedie` clip。
- 改了源码断言后**闸门自己的判据也要改**（本例 G27 的 `StepDowned` 断言从
  `EnsureClip(sprite, DownedClip,` 改成 `EnsureClip(sprite, want,`）—— 忘了改就会「明明改对了却 FAIL」。

### A6-08 ★★ 两份「同一指标」的口径可能不同 —— 都要打印，别只信一个
- 本例同一跪姿：bake 打印（不透明像素质心）**74%**；闸门 G29（bbox 角点）**78.8%**。
- 都过 80% 门槛，但**闸门口径余量只剩 1.2%** —— 只信 bake 就会误判「还有 6% 空间」。

### A6-09 ★★ bake 必须支持**输出目录环境变量**
- 本轮因实验烘焙直接覆盖了正式产物 `out_legion/`（`.tres` 由 518 261 → 518 257），多花一轮还原。
- 正解：`OUTD = os.path.join(HERE, os.environ.get("BAKE_OUTD", "out_legion"))`（渲染目录同理）。

### A6-10 ★★ 融合版素材两条事实（省一次探测）
1. `anim_*.json` 里 12 段动画的 `X_1` 与 `X` **逐字节完全相同**（walk/attack/idle/die/fakedie/quickmove
   六对 md5 全同）⇒ **不存在「第二半动画」**；烘焙取「非 `_1`」是对的。
2. `anim_LegionZombie.json` 是 **UTF-8 BOM** 文件 ⇒ 必须 `open(p, encoding='utf-8-sig')`，
   否则 `json.JSONDecodeError: Unexpected UTF-8 BOM`。

### A6-11 ★ 交付图要**成对**给：静帧对照 + 过程 GIF
- 静帧对照（参考 / 旧 / 新）定「像不像」；**过程 GIF** 定「动起来对不对」（本例 `v902_倒地入场.gif`：
  fakedie 12 帧入场 + downed 8 帧保持，带地面参考线）。
- 并排 GIF（`旧 | 新` + 角标）是主人过目最快的形式。


## A7 换图真根因 · 图集切层 · 生成替换钩子（★ 2026-10-06 阿尔法小队 v9.1.0.0 定案）

> ★★★ **本节推翻 A5-04 / A5-05 / A6-04 的结论**：`.pmod` 里 **`SetReplace` 不可能生效**。
> 若你正照 A5-04 写换图代码，**立刻停手**，改走 A7-01/A7-02 的「烘进图集 + `SetFliter` 切层」。

### A7-01 ★★★ AdobeAnimate 渲染**只认预烘进全局 `Texture2DArray` 的纹理** —— mod 自带 PNG 进不去
- **现象**：`.pmod` 里 `SetReplace(Texture2D)` 调完零报错、`GetReplace()` 也能反查命中，**但画面上什么都没变**。
- **实机日志**（决定性证据）：
  ```
  WARNING: AdobeAnimate media replacement texture is missing from the shared Texture2DArray atlas;
           replacement drawing was disabled for that sprite.
     at: AdobeAnimateSprite.DisableUnsharedMediaReplaceTextures(List<int>)
     [2] AdobeAnimateSprite.CreateMediaReplaceAtlas()
     [3] AdobeAnimateSprite.UpdateMediaReplaceData()
     [4] AlphaSquadMod.AlphaSquadRuntimeEntry.ApplyReplace(...)
  ```
  ⇒ 替换纹理进不了共享 `Texture2DArray` 图集，引擎把**该精灵的替换整个关掉**（`replacement drawing was disabled`）。
- **三条渲染通路全都要求「纹理已在预烘图集里」**：
  1. `AdobeAnimatePart._Draw()` → `DrawTextureArrayPrimitive(definition, mediaId, mediaRect, color)`（用 `definition.AtlasTextureArray`）；
  2. `AdobeAnimatePart.DrawExternalAtlasTexture()` → `TryResolveExternalAtlasAllocation` →
     `AdobeAnimateGlobalAtlasCache.TryGetReplaceTextureAllocation(path,…)`（**路径必须已在 `AdobeAnimateGlobalAtlasManifest.tres` 清单里**）；
  3. `AdobeAnimateManagedSprite2D.TryBuildGpuState` / `TryBuildExternalGpuState` / `TryBuildAtlasPartGpuState` ——
     失败串统一是 `"… texture is not in the owner's shared atlas array"`。
- **教训**：A5-04 / A6-04 的「每帧 `GetReplace()` 校准 ＋ 主动 `UpdateMediaReplace()`」不是修好了，是**让引擎更快地把它禁掉**。
  `SetReplace` 只是把纹理塞进一个**永远不会被采样的**替换槽。

### A7-02 ★★★ 正解 ＝「把三档图烘进动画自带图集 ＋ `SetFliter(层名, bool)` 切图层」
- `AdobeAnimateSprite.SetFliter(StringName layerName, bool open)`（`AdobeAnimateSprite.cs:5869`）与 `GetFliter(...)`（`:5882`）**是公开 API**：
  ```csharp
  public void SetFliter(StringName layerName, bool open) {
      if (_flashAnimeData != null && _flashAnimeData.layerDictionary != null
          && _flashAnimeData.layerDictionary.ContainsKey(layerName)) {
          int num = (int)_flashAnimeData.layerDictionary[layerName];
          if (num >= 0 && num < _layerVisible.Count) { _layerVisible[num] = open; MarkLayerStateChanged(); }
      }
  }
  ```
- **★ 静默语义**：`SetFliter` 对**不存在的层名静默无操作**；`GetFliter` 对**不存在的层名恒返回 false**。
  ⇒ 可做「打开 → 读回」**层名存在性自检**（`ProbeTierLayers`），否则层名写错 = **无声失效**（离线全绿、实机不换）。
- `.tres` 里 `layerVisible = [...]` 是**可直接序列化的属性**，顺序与长度必须与 `.dat` 的 layers **完全一致**。
- 切层写法（**先关全组、再开命中档**；且先 `GetFliter` 判同避免无谓 `MarkLayerStateChanged`）：
  ```csharp
  private static void SetTierLayers(AdobeAnimateSprite s, string[] layers, int tier)
      => SetAllTierLayers(s, layers, false, layers[tier]);
  private static void SetAllTierLayers(AdobeAnimateSprite s, string[] layers, bool open, string except = null) {
      for (int i = 0; i < layers.Length; i++) {
          bool want = open || (except != null && string.Equals(layers[i], except, StringComparison.Ordinal));
          StringName ln = new StringName(layers[i]);
          if (s.GetFliter(ln) == want) continue;
          s.SetFliter(ln, want);
      }
  }
  ```
- `_layerVisible` 只被三处写入（`_Set("Animation/LayerVisible/X")`／`SetFliter`／全 True 初始化），**引擎没有每帧重置它**。

### A7-03 ★★★ 「破损/分档贴图」大概率**本来就在源图集里**，而且是基础件的**兄弟部件** —— 先查 `parts_*.json` 的 `chain`
- 本例四张图一直存在，只是被 bake 的 `DROP = ("shield1","shield2","head1","head2")`（注释「受损档：本轮不做」）主动丢弃。
- 探测 `parts_LegionZombie_anim.json`：
  | 件 | chain | rect | 关系 |
  |---|---|---|---|
  | `head0` | `LegionZombie+Zombie_head` | `[135,138,135,126]` | 基础（完整） |
  | `head2` | `…+Zombie_head+head2` | `[135,272,135,126]` | 子节点（轻微） |
  | `head1` | `…+Zombie_head+head1` | `[135,4,135,126]` | 子节点（严重） |
  | `shield` / `shield1` / `shield2` | `…+shield` / `+shield1` / `+shield2` | `[4,4,123,171]` / `[4,183,123,171]` / `[4,362,123,165]` | 基础 / 轻微 / 严重 |
- **关键**：子件 `matrix` 与父件**逐位相同** ⇒ 走 `world_at` 递推天然得到与基础件**逐帧等价**的变换（离线验收几何差 = 0）。
  ⇒ 烘焙时**直接按子节点 chain 取图**即可，**不需要**自己算偏移。
- **教训（通用）**：要「同一部件的多个外观档」，先去 `parts_*.json` 里找 `chain` 上**挂在基础件下面的兄弟节点**，
  再去重画贴图。先做这步能省掉整整两版错误方向。

### A7-04 ★★★ 新增「同尺寸兄弟图层」时必须：①隔离归一化参数 ②统一媒体画布
- **归一化隔离**：新增档位图层**不参与**归一化参数（H / 脚底 / 横向中心）的计算；归一化只用「基础件」集合
  （`sp_base = [p for p in sp if p.get("sprite") not in DMG]`）。否则新图会**污染整段动画的缩放与对位**。
- **统一画布**：`slice_of()` 的 `pivot(0.5,0.5)` 语义 ⇒ **媒体矩形尺寸必须统一**，否则切档时整体偏移 `Δh/2`。
  本例 `shield2` 源图高 165 vs 基准 171 ⇒ 必须补齐到 `(123,171)`（否则偏 3 px）。
- 两项都要在 `meta.json` 落字段（`tier_layers` / `damage_layers`），让打包与闸门**同源读取**。

### A7-05 ★★ `layerVisible` 的**索引不要自行 ±1**
- `meta["layers"]` **已含 `_ground`**，所以 `layerVisible[i]` 与 `layers[i]` 一一对应；
  只有 `followSlotId` 这类「槽位号」才是 `layerIndex + 1`。
- 本例踩坑：`assert LVC[IDX[nm] + 1] ...` ⇒ `AssertionError: 受损档层 head1 的 layerVisible 初值必须是 false（当前 True）`。
- **正确**：`LVC[IDX[nm]]`。

### A7-06 ★★★ `BattleEventBus.OnCharacterSpawned` 是**死代码** —— 别拿它做「生成时注入」
- `Core/BattleEventBus/BattleEventBus.cs` 的 `OnCharacterSpawned`（`:54`）+ `EmitCharacterSpawned`（`:104`）
  在**全工程 4025 个 `.cs`** 里**零调用点**（Python `os.walk` 全量扫描确认）。
- **可用的生成路径**：`TowerDefenseCharacter.CreateCharacter(packetName, pos, gridPos, groundHeight)`
  （`Prefab/TowerDefense/Character/TowerDefenseCharacter.cs:4746`）→ `CreateCharacterCore`（`:4760`）。
- **轮询式兜底**（本轮 5% 替换的落地方式）：在 DLL 的 `_Process` 里 `Discover()` 扫场 + 实例 id 去重（`_rolled`）
  + **先造后删**（`CreateCharacter` 成功后再 `QueueFree()` 原体）；用 `_rolled.IntersectWith(_aliveIds)` 做**增量清理**防 id 无限增长。
  - 代价：**「原地变身」有延迟（本例 ≤6 帧）**。要求「刚生成就走出来前换掉」须改 `SceneTree.NodeAdded` 信号。

### A7-07 ★★ 权重/概率类改动别往 `WeightPickMathine` / `PacketBank` 上找
- `WeightPickMathine.Pick`（`Resource/Core/WeightPick/WeightPickMathine.cs`）**只用于图鉴预览**
  （`showCharacterList` / `ActivateLevelEntryPreview`），**不是关卡生成路径**。
- `PacketBank` 的 category 是**纯白名单、无权重** ⇒ 用权重法调不出「5%」这类概率。
- `TowerDefenseInGamePacketBank.cs` 是 **UI 卡池面板**，同样不是生成路径。
- `TowerDefenseEnum.CHARACTER_CAMP`（`Resource/TowerDefense/TowerDefenseEnum.cs:54`）：`NOONE=-1, PLANT, ZOMBIE, ALL`；
  判阵营用 `c.camp != TowerDefenseEnum.CHARACTER_CAMP.ZOMBIE`。

### A7-08 ★★ 闸门里写「方法体断言」**必须对齐真实调用链**
- 本例 G30 断言 `SetTierLayers` 体内含 `sprite.SetFliter(` —— 但它**委托**给了 `SetAllTierLayers`，体内根本没有 ⇒ FAIL 两条。
- **正确做法**：断言「`SetTierLayers` 委托 `SetAllTierLayers(`」+「`SetAllTierLayers` 先 `GetFliter` 再 `SetFliter`」。
- 闸门用到的**层名 / 画布尺寸常量必须与 bake 脚本同源**，否则离线全绿、实机换档失效。

### A7-09 ★★★ 版本号批量替换脚本**必须在编译前跑完** —— 否则 DLL 一定过期
- 本例 G28 抓到 warn「DLL(19456) **早于** 源码(58593)」：我在编译后跑了 `_bump30.py`（版本号替换）改了 `.cs`。
- **固定顺序（写进流程）**：**写完所有源码 → 跑版本号替换脚本 → 重新编译 DLL → 重新打包 → 重新跑闸门**。
- 闸门要有「DLL 时间戳 / 大小 vs 源码」的一致性检查（G28 就是干这个的，别关掉它）。

### A7-10 ★★ Python 生成器里的同名变量会取到**外层泄漏值**
- 错误：`base = set(i for n, _ in d["layers"] if n not in DMG)` —— 生成器里的 `i` **不是**循环变量，
  取到了外层 `for i in range(1,7)` **泄漏出来的** `i` ⇒ `base = {6}`，渲染只出一个层。
- **正确**：`base = {j for j, (n, _) in enumerate(dn["layers"]) if n not in DMG}`。
- **通用**：凡是「集合/字典推导式」里出现**与之前循环同名**的变量，一律显式 `enumerate` 重命名。

### A7-11 ★★ 统计「不透明像素」**必须用透明底渲染**，判据用「与完整档的差异像素」
- 错误：用不透明底渲染 ⇒ 三档统计值完全相同（2591/2595/2595、27360×3），等于没测。
- **正确**：`render_frame(..., pad=4, bg=(0,0,0,0), visible={idx[lyr]})`；
  判据改成「与完整档的**差异像素 > 0**」—— 因为「面具严重档」是「打掉一块、露出眼睛」，**面积不减反增**。

### A7-12 ★★★ 新增「生成时再生产一个」的机制后，**凡是「被别人变出来」的路径都要掐断派生**
> ⚠ **已被 v9.2.0.1 撤销（作为默认做法）**：主人最终选择「替换出来的那只**也带同伴**」（一次替换 = 本体 + 同伴一对，实际兵力约 10%）⇒ 本条**不是**本 mod 的最终做法。
> ★ 但**技术要点仍成立**：「置位要延迟到首次接管」这一条（见 A7-13）与「凡由派生链产出的单位都要审一遍 `IsFollower`」这两点请继续沿用。
- **症状**：给单位加了「出生时在身后再拉一名同伴」后，新加的「N% 概率替换成这个单位」机制
  变成了**一次替换出两只**（本体 + 刚出生的衍生体）⇒ 概率被悄悄翻倍（本例 5% → 约 10%）。
- **根因不是概率算错**，而是**新入口没有掐断既有的派生链**。
- **正解**：给状态加一个「不派生」位（本例 `NoFollower`），在新入口里登记，
  在**首次接管该单位时**置位，并在派生函数里加**早退兜底**：
  ```csharp
  // 新入口（替换）：
  _noFollower.Add(nz.GetInstanceId());            // 只登记，不建状态
  // 首次接管时消费：
  if (_noFollower.Remove(id)) { st.NoFollower = true; st.SpawnDone = true; }
  // 派生函数兜底：
  private void TrySpawnFollower(...) { st.SpawnDone = true;
      if (st.IsFollower) return; if (st.NoFollower) return; ... }
  ```
  （`Step` 里的触发条件本来就是 `if (!st.SpawnDone) TrySpawnFollower(...)` ⇒ 置 `SpawnDone` 是双保险。）
- **只掐「替换而来」的那条路**；玩家正常放置 / 关卡预置的单位**保持原设计**（本例仍然带同伴）。

### A7-13 ★★★ 「登记 / 置位」必须分两步 —— 别在 `CreateCharacter` 刚返回时就建状态
> ⚠ **本条描述的场景已被 v9.2.0.1 撤销**（`_noFollower` 机制整体移除）。
> ★ **但「`CreateCharacter` 刚返回时 `sprite` 可能没装配好、别抢先 `HookUnit`」这条警告依然完全有效** —— 任何在 `CreateCharacter` 之后立刻建状态/订阅事件的代码都要警惕。
- **坑**：`CreateCharacter` 刚返回时 `z.sprite` **可能还没装配完毕**。
  此时若立刻 `GetOrCreateState(...)` → `HookUnit(...)`，里面那条
  `sprite.OnAnimeEvent += ...`（靠 `st.HitHooked` 做**一次性**守卫）会因 `sprite == null` 判不过，
  而状态**已经建好**、`HookUnit` **不会再跑第二遍**
  ⇒ **动画事件永远订阅不上 ⇒ 靠事件结算的伤害静默失效**（典型「不报错、只是打不死植物」）。
- **正解**：新入口**只登记 id**；等该单位被正常轮询扫到、`sprite` 就绪时，
  由 `GetOrCreateState` **消费 id 并置位**。
- **通用判据**：凡 `HookUnit` / `OnReady` / 「首次创建状态」里有**一次性守卫**的订阅动作，
  都不要「抢先建状态」，而是把意图**延迟**到正常生命周期拐点执行。

### A7-14 ★★★ 凭空把单位挪到指定格 ＝ **三件事必须一起做**（`gridPos` / 格子中心 / 该格高度曲线）
- **需求形态**：「替换/传送出来的僵尸**直接出现在第 9 列**（9，1 到 9，X），X = 地图行数」。
- **三件套**（缺一件就出视觉 bug）：
  | 项 | 正确写法 | 漏了会怎样 |
  |---|---|---|
  | ① `gridPos` | `GetMapGridNum()` 取尺寸，**1-based** | 整体偏一格 / 越界 |
  | ② 世界坐标 | `mgr.GetMapCellPosCenter(target)`（**格子中心**）| 卡在格角、半身入土 |
  | ③ `groundHeight` | `TowerDefenseManager.GetMapCell(target).GetGroundHeight()` | **先按原行高度浮在半空，再被组件 lerp 拉回地面**（肉眼可见「飘一下」）|
- **第 ③ 件为什么必须是同一个函数、同一个默认参数**：
  `GroundHeightComponent.GetTargetHeight()` 末尾就是 `parent.cell.GetGroundHeight(parent.cellPercentage)`
  ⇒ 你传的初值与组件的计算路径不同源，就一定会有「先错后纠」的插值过程。
- **网格 API 速查**（`Core/TowerDefenseManager/TowerDefenseManager.cs`）：
  | API | 行 | 备注 |
  |---|---|---|
  | `GetMapGridPos(Vector2)` | `:1829` | `floor((pos−gridBeginPos)/gridSize)+One` ⇒ **1-based** |
  | `GetMapGridNum()` | `:1789` | 无地图特征时**默认 `(25,25)`** ⇒ 必须先判 `Instance == null` |
  | `GetMapGridSize()` | `:1799` | `config.gridSize * GlobalScale` |
  | `GetMapCellPosCenter(Vector2I)` | `:1841` | 中心；内部先 `gridPos -= One` |
  | `CheckMapGridPosIn(Vector2I)` | `:1847` | `1 ≤ X ≤ num.X` 且 `1 ≤ Y ≤ num.Y` |
  | `static GetMapCell(Vector2I)` | `:1856` | 取 `TowerDefenseCellInstance`（可 null）|
  | `cell.GetGroundHeight(0.5)` | `:1584` | 高度曲线采样；曲线无效返回 `0.0` |
- **`GetMapCellPosCenter` 与 `GetMapCellPlantPos` 是对偶的一对**（中心 vs 格角），**别混用**。
- **引擎自己的先例照抄口径**：`TowerDefenseFloorQX.SpawnHologramProjection`
  （`Asset/Anime/Character/GraveStone/FloorQX/Scene/TowerDefenseFloorQX.cs:95-118`）
  先 `if (row < 1 || row > GetMapGridNum().Y) return;` 再取格、`mapCell == null` 就放弃。
- **★★ 必须有兜底**：`Instance == null` / `gridNum < 1` / `CheckMapGridPosIn` 不过 ⇒
  **退回原位置**（`z.GetLogicalGlobalPosition() / z.gridPos / z.groundHeight`），
  千万别 `return` 掉整个替换 —— 否则开局加载期的一次 5% 触发就被静默吞掉。
- **★★ 地图尺寸实测（别以为「第 9 列」恒等于最右列）**：
  | 地图 | gridNum | 第 9 列＝最右列？ |
  |---|---|---|
  | Backyard / Valley | `(9, 6)` | 是 |
  | CreekLawn / MagicGarden | `(9, 5)` | 是 |
  | **FrontlawnBig** | **`(11, 7)`** | **否**（右起第 3 列）|
  | **FrontlawnSuperBig** | **`(27, 15)`** | **否**（草坪中部）|
  ⇒ 要「恒定最右列」就把目标列写成 `int col = gridNum.X;`（一行改动）。
  ⇒ 目标列务必抽成 `private const int ReplaceTargetColumn = 9;`，别撒魔法数字。
- 顺带：`attackType`/`Sprite` 之类的**渲染与结算字段**跟位置无关，挪位置**不需要**重新装配。

### A7-15 ★★ 走 `CreateCharacter` 造僵尸时，**不要重复补引擎已经做的事**
- **不要自己 `AddChild`**：`TowerDefenseCharacter.CreateCharacterCore`
  （`Prefab/TowerDefense/Character/TowerDefenseCharacter.cs:4760`）内部已经 `characterNode.AddChild(...)`。
- **不要补 `IsZombieWalk()`**：`TowerDefensePacketConfig.Create`
  （`Registry/Battle/Feature/PacketBank/Resource/Packet/TowerDefensePacketConfig.cs:1103-1106`）内部自带：
  ```csharp
  if (!isIdle && characterConfig is TowerDefenseZombieConfig && towerDefenseCharacter is TowerDefenseZombie character)
      IsZombieWalk(character);
  ```
  `IsZombieWalk`（`:1207`）是 `async void` —— 等一个 `PhysicsFrame` 后 `character.CallDeferred("Walk")`。
- **对照**：只有走 **`packetConfig.Create(pos, gridPos, groundHeight)`** 这条低层路径时，
  才可能需要自己补 `IsZombieWalk()`（见 A3 系列的「原地不动、零 ERROR」症状）。
  两条路径的差别只在**谁来 AddChild / 谁来发起 Walk**。

### A7-16 ★★★ **撤销 / 回退一个已上线机制时，闸门断言要翻成「负向」**
- **坑**：把旧断言**直接删掉** ⇒ 等于**丢掉防回归能力**。后人（或未来的自己）很容易顺手把旧机制抄回去。
- **正解**：**正向断言 → 负向断言**（「不该出现的必须不出现」）。
  本例：v9.1.0.1 的「5% 替换只出一只」有 6 条正向断言，撤销时翻转成 6 条负向，
  再补 2 条正向（确认该留的守卫还在）⇒ 共 8 条：
  ```python
  R("G31", 1 if "HashSet<ulong> _noFollower" not in code else -1, "源码已无 _noFollower 集合")
  R("G31", 1 if "public bool NoFollower;" not in code else -1, "SquadState 已无 NoFollower 字段")
  # ... 方法体内同理（RollReplace / GetOrCreateState / TrySpawnFollower 各一条）
  R("G31", 1 if "只出一只" not in code else -1, "源码无「只出一只」字样（日志与注释都改了口径）")
  # ★ 补两条「该留的还在」的正向断言：
  R("G31", 1 if "st.IsFollower" in _b_tsf else -1, "派生链仍不套娃：IsFollower 早退必须保留")
  R("G31", 1 if _b_rr is not None and _b_goc is not None else -1, "方法体仍可取到（结构未塌）")
  ```
- **★ 判据「哪些守卫要留」**：问「**那道守卫在旧功能里也有吗？**」
  有 ⇒ 留（它是别的需求的依赖）；没有 ⇒ 才删。
  本例 `IsFollower`（衍生体不再拉人）在 v9.1.0.1 **之前就存在**，与「只出一只」无关 ⇒ **必须保留**。
  删了它，一次替换就会变成「本体 + 同伴 + 同伴的同伴」= **套娃四只**。
- **回退优先「整体删除」而不是留 `bool Xxx = false` 开关**：死代码会让人误以为机制还在；
  机制来龙去脉写进文档后，需要时按文档重建成本极低。
- **兵力量化要说清并记权衡**：本例 5% 替换产出 2 只 ⇒ 实际约 10%。
  主人知情后仍选一对 ⇒ **记录权衡、停止重复提议**。

### A7-17 ★★ 核验 .NET DLL 里的字符串：**用 UTF-16LE，不是 UTF-8**
- **坑**：`s.encode("utf-8") in dll_bytes` 对 .NET 程序集**几乎全盘 False**
  （`#US` 字符串元数据是 **UTF-16LE**）⇒ 极易误判成「改动没编进 DLL」。
- **正解**：`s.encode("utf-16-le") in dll_bytes`。
  ```python
  b = zipfile.ZipFile(pmod).read("Runtime/ModAssembly.dll")
  assert "只出一只".encode("utf-16-le") not in b      # 撤销后：旧串应消失
  assert "本体 + 出生同伴一对".encode("utf-16-le") in b  # 新串应存在
  ```
- **但注释不进 DLL** ⇒ 想确认「历史说明注释是否清干净」**必须读源码**，别只看 DLL。
  源码里可能仍留着「★ v9.x：已整体移除」这类**有意保留的历史说明**，那是给人看的，不是死代码。
- 顺带：判定「旧机制是否真的删干净」要**双向查**——
  正向（`utf-16-le` 里有旧串 ⇒ 还在）＋ 反向（新口径串存在 ⇒ 新行为已编入）。

---

## A8 护具进阶 · 技能落点 · 伴生脚本（★ 2026-10-13 黑橄榄骑兵团 v1.0.0 定案）

> **场景**：一个包做三只僵尸 —— 机枪黑橄榄僵尸（本体 3000 + 橄榄盔 3000；每 0.1s 发射铁豆）、
> 黑橄榄骑兵僵尸（本体 3000 + **战马** 6000；冲锋 + 碾压；下马变机枪黑橄榄僵尸）、
> 机枪黑橄榄骑兵团长（本体 4500 + 战马 9000；每 1.5s 六连发；本体 <50% 每行召唤骑兵）。
> 主人的原始口径有三条**反直觉**要求：① 铁豆**不**施诅咒（诅咒铁豆才施）；② 坐骑防具**不掉落**；
> ③ ★★ **骑乘态只有坐骑的血量，下马后生成的僵尸才有它自己的血量**。以下全部是 V0.30 源码实证。

### A8-01 ★★★ 护具类型走 `TowerDefenseArmorRegistry`，**不是** `CharacterArmorData.armorDictionary`

- **坑**：在 `Armor/<Id>ArmorData.tres` 里把 `armorDictionary` 写全（含 `typeData`），
  运行时护具**静默完全失效**（不吸收任何伤害、也不报错）。
- **源码**：`TowerDefenseArmorInstance.cs:105-148` 构造函数做的是
  `TowerDefenseArmorRegistry.Init()` → `TowerDefenseArmorRegistry.GetArmorType(slotConfig.armorName)`；
  **`typeData == null` ⇒ `isRemove = true`**（护具作废）。`CharacterArmorData.armorDictionary`
  只是给编辑器/`SetArmorReplace` 用的缓存，**不是注册表**。
- **正解**：在托管 DLL 的入口里注册（幂等：先 `HasArmor` 再注册）：
  ```csharp
  TowerDefenseArmorRegistry.Init();
  if (!TowerDefenseArmorRegistry.HasArmor(name))
      TowerDefenseArmorRegistry.RegisterArmor(name, new TowerDefenseArmorTypeData {
          armorName = name, damagePoint = 6000.0, armorMethodFlags = 578,
          impactAudio = "ShieldHit",
          stagePersontage = new Godot.Collections.Array<double> { 0.66, 0.33 },
      });
  ```
  （`stagePersontage` 的 setter 会**降序排序**；`ArmorSlotConfig.damagePoint` 默认 **-1.0**、
  `TowerDefenseArmorTypeData.damagePoint` 默认 **370.0**、`armorMethodFlags` 默认 **200**。）
- **闸门**：包内回读 `.tres` 时，**`armorDictionary` 里的 `typeData` 写 `null` 是正常/正确的**
  （表示"运行期由 DLL 注册表补"）⇒ 别把它当缺陷去"修"。

### A8-02 ★★★ `slotConfig.damagePoint` **覆盖** `typeData.damagePoint` ⇒ 一个护具类型可以服务多个血量

- **源码**：`TowerDefenseArmorInstance.cs:121`
  `damagePointBase = slotConfig.damagePoint >= 0 ? slotConfig.damagePoint : typeData.damagePoint;`
- **用法**：骑兵战马 6000 / 团长战马 9000 ⇒ **只注册一个 `BlackOliveHorse`（6000）**，
  靠两份 `ArmorSlotConfig.damagePoint`（6000 / 9000）区分即可。
  ⇒ 不要为了"不同血量"去注册两个类型名（那会让图鉴/存档多出无意义的护具条目）。

### A8-03 ★★★ 「骑乘态只有坐骑的血量」= `ABSORBOVERFLOW(0x200)`，**别写 hack**

- **需求**：主人在马上的时候，本体血量**纹丝不动**；打光马之后下马，新形态才拿自己的满血。
- **正解**：护具 `armorMethodFlags` 打开 **`ABSORBOVERFLOW = 0x200 = 512`**。
  `TowerDefenseArmorInstance.cs:207`（`TryApplyStableDamage`）与 `:316-319`（`DealHurt`）都是
  `remainingDamage = ((armorMethodFlags & 0x200) != 0) ? 0.0 : num;`
  ⇒ 护具**吃满全部超量伤害**，本体一点都分不到。
- **反例（别这么干）**：每帧把本体血量回满、或每帧 `DealHurt(-x)` 补血、
  或监听 `hitpoints` 变化再写回 —— 都会与引擎的濒死/死亡判定打架（见 A7-13 一类教训）。
- ⚠️ **仍然有 7 条路绕过护具直扣本体**（必须自己补偿）：
  中毒 `TowerDefenseCharacterBuffPoisoning.cs:45 instance.DealHurt(20)`／蒜火／小推车／
  濒死抽血 `TowerDefenseCharacter.cs:2666`／`DIRECT_BODY` 投射物（`damageFlags & 0x10`）／
  `Die()` 秒杀／吞噬类（后三类可被 `blocksLethalEffects && limitMaxHit > 0` 挡）。
  ⇒ 本例的补偿 = 在 `DieProcessing` 里加**兜底下马**（本体被打穿也照样变骑兵僵尸）。

### A8-04 ★★ 「防具不掉落」与「头盔 + 坐骑共存」的两个 flags 陷阱

- ★★★ **不掉碎片 = 不设 `DROPABLE(0x80)`**：`TowerDefenseArmorInstance.cs:200`
  `if (createDamagePart && (armorMethodFlags & 0x80) != 0) DamagePartCreate(...)`
  —— **所有**掉碎片入口都在这个门后。⇒ 主人要求"马防具不会掉落" ⇒
  战马 flags = `BODY(2)|DAMAGEABLE(0x40)|ABSORBOVERFLOW(0x200)` = **578**，**不含 0x80**。
  （反证：官方 `Registry/Armor/Config/Paper.tres` flags = **68** = `DAMAGEABLE|SHIELD`，同样不掉碎片。）
- ★★ **`IsExclusiveWearableHelmet`**：对「`HELM(8)` + `DROPABLE(0x80)` + **非** `BODY(2)`」的组合互斥
  ⇒ **要让头盔与坐骑/盾牌共存，坐骑必须用 `BODY` 位**（不能也用 `HELM`）。
  双护具先例 `ZombieShieldArmor.tres:27` `initArmor = ["Shield", "HelmetEP"]`。
- **`ARMOR_METHOD_FLAGS` 全表**：`NOONE=1`｜`BODY=2`｜`SHIELD=4`｜`HELM=8`｜`METALLIC=0x10`｜
  `INVINCIBLE=0x20`｜`DAMAGEABLE=0x40`｜`DROPABLE=0x80(128)`｜`PASSDAMAGE=0x100(256)`｜
  `ABSORBOVERFLOW=0x200(512)`｜`CANT_PENETRATE=0x400`｜`HEAD_COVER=0x800`｜`BURST_WHEEL=0x1000`｜
  `BLOCK_PROJECTILE_EFFECTS=0x2000`。
- **承伤顺序恒为** `SHIELD(4) → HELM(8) → BODY(2) → 本体`
  （`TowerDefenseCharacterInstance.cs:1109/1115/1121/1127 DealHurtBody`），
  同层内按 `armorList` 顺序溢出。★ **没有 tier「一类/二类」字段**，分类全靠 flags 槽位组合。
- ★ **`HasStage` 的定义 = `stageAnimeTexturePaths.Count > 0`**（`CharacterArmorData.cs:167-171`）：
  有 ⇒ 走图集替换（`replaceMethod=="Media"` 且 `replaceMediaName` 非空）；
  无 ⇒ 走 `slotConfig.slotPath` 指向的**独立 sprite 结点**（`CreateArmorPartNode`）。

### A8-05 ★★ 伴生脚本（`CompanionOnly`）三件套 —— 类名 / 文件名 / 基类必须对齐

- **场景侧**（`.tscn` 根节点，绑**官方** `TowerDefenseZombie.cs`）：
  ```
  metadata/mod_character_script_path = "../Script/TowerDefenseZombieBlackOliveRider.cs"
  metadata/mod_character_script_binding = "CompanionOnly"
  ```
  ★ **包内不需要真的放那个 `.cs` 文件**（运行时只拿它取文件名）。
- **运行时**（`XWModCharacterCompanionRuntime.cs`）：
  `:228 expectedTypeName = Path.GetFileNameWithoutExtension(text)`（★ 只取名字）
  → `:229 SingleOrDefault(t => t.Name == expectedTypeName && authoredRoot.GetType().IsAssignableFrom(t))`
  ⇒ 三重约束：
  ① `type.Name` **等于** 文件名（`Path.GetFileNameWithoutExtension`，注意**无扩展名**）；
  ② 类型在**该 mod 自己的 DLL 程序集**里；
  ③ `authoredRoot.GetType().IsAssignableFrom(type)`，而 `authoredRoot` 绑了官方脚本
     ⇒ **伴生类必须继承官方脚本类**；
  ④ `:235 Activator.CreateInstance(type) is Node` ⇒ 需**公开无参构造**。
- **正解签名**：`[Tool] [GlobalClass] public partial class TowerDefenseZombieBlackOliveRider : TowerDefenseZombie`
  （文件名 `TowerDefenseZombieBlackOliveRider.cs`，`.tscn` metadata 里写的也是这个名字）。
- 之后：`:240-261` 改名 → `CopyStoredProperties`（**只拷"存储"属性**，`usage & 2 != 0`）+ `CopyMetadata`
  → 子节点逐个 `Reparent`（先 `Owner = null` 再 reparent 再设回 `Owner`）→ `authoredRoot.Free()`。
  ⇒ 所以 `.tscn` 上显式写的 `walkAnimeClip` / `currentArmor` / `sprite` 等**存储属性**会被搬到伴生实例上。
- ★ 推论：**一个包想给多只僵尸各写逻辑** ⇒ 在同一个 DLL 里声明多个
  `X : TowerDefenseZombie`（类名与各自 `.tscn` 的 metadata 文件名一一对应），**不必拆包**。

### A8-06 ★★ 技能落点速查：开火 / 碾压 / 变身 / 每行召唤

| 技能 | 落点与要点 |
|---|---|
| **周期性开火** | `TowerDefenseZombieComponentSet` **不含** FireComponent ⇒ 自建 `<Id>ComponentSet.tres`（`ParentSet = TowerDefenseZombieComponentSet.tres`，`Components=[自己的 FireComponentDefinition]`）+ `<Id>FireComponentDefinition.tres`。★ `fireAnimeClips` **直接写自己包内的剪辑名**（本例 01=`Shoot`、03=`BlackShoot`）。连发用 `fireNum` + `fireNumAtOnce=true`；`fireInterval` 控节拍（0.1s / 1.5s）。默认值：`fireIntervalBase=1.5`｜`fireIntervalOffset=0.1`｜`fireNum=1`｜`fireAudioName="ProjectileThrow"`｜`defaultCheckLengthWorld=2000`。弹体放 `Resources/Projectiles/<Key>.tres`（`ModLoader.cs:1715` 注册为 `Projectile` 类别），`projectileName` 写 **StringName 裸名**。 |
| **碾压** | 无专用字段，三条路选 **照抄雪橇车**：`AttackComponent.cs:3408 public void SmashAttackCell(double num)`（内部判 `IsRemoteSyncedAttacker`/`CanExecuteGameplayEffect`；目标是僵尸/墓碑/花瓶 ⇒ `SmashHurt`，是植物 ⇒ 转 `SmashAttackCell(num, gridPos)`）+ `:3432/:3440/:3454`。官方先例 `TowerDefenseZombieZamboni.cs:71-80`。⇒ 插件里「`CanAttack()` 通过且目标是 `TowerDefensePlant` → `SmashAttackCell(伤害)`」语义最干净。（另两条：`physique=CAR(5)`+`smashPlantAttack` 车类直 10000；`GargantuarSmashComponent`。） |
| **下马/变身** | `TowerDefenseCharacterEventTransform.cs:136 CanTransform` / `:163 Run` → `TowerDefenseCharacter.TransformTo:5205`（`syncCamp:true, **syncBodyHp:false**, syncHypnoses:true, removeSource:true`）→ `PublishSpawnedCharacter(..., walkAfterSpawn:true)`。★ **`syncBodyHp:false` ⇒ 新形态满血**，正是"下马后才有自己的血量"的落点。`CanTransform` 拒绝：非僵尸 / Imp 家族 / 同名 / `zombiePhysique==BOSS` / 已带 `CharacterTransform` meta。官方先例 `TowerDefenseZombiePaper.cs:132-152`。 |
| **每行召唤** | `TowerDefensePacketConfig.cs:1142 CanSpawn(int line)`（校验 `spawnLineNeed`/`excludeLineGridType`）/ `:1185 Spawn(int line, double offsetX, bool isIdle, EconomyAccountId)`。行数读 `GetMapFeature().config.gridNum.Y`。先例 `TowerDefenseZombieNecromancer.cs:111-149`。★ **幂等位只放实例字段** —— 静态 `HashSet` 会跨局残留（`GetInstanceId()` 会复用）。 |
| **护具三档外观** | `sprite.SetFliter(层名, i == stage)`（`AdobeAnimateSprite.cs:5872-5883`），在 `ArmorDamagePointReach` / `ArmorHitpointsEmpty` 两个钩子里响应 + **每 30 帧回读自愈**（引擎跨档会顶掉层状态）。★ 别盯 `armor.stageIndex`。 |
| **免疫击退** | `unUseBuffFlags = 512`（`CHARACTER_BUFF_FLAGS.BLOW`）。位表：减速 1／冻结 2／黄油 4／魅惑 8／红热 16／眩晕 32／中毒 64／蒜 128／睡眠 256／**击退 512**／樱桃 1024／乌贼 2048／EMP 4096／定身 8192／ALL -1。 |

### A8-07 ★★ 自烘动画必须注意 `animeFile` 口径（否则**角色隐形**）

- 详见 `pvz-hybrid-mod-authoring/references/pitfalls.md` **H-01**（含 5 条源码证据）：
  `animeFile` 必须写 **`"./<与 .tres 同名的>.dat"`**；
  **`res://ModAssets/` 这个前缀在 V0.30 里根本不存在**（全树 grep 为空）。
- ★ 补充一条僵尸侧现象判据：**隐形 ≠ 包没装**。僵尸隐形时，卡能选、能出场、
  甚至能看到脚下阴影（`ShadowSprite`）与血条，**只是没有像素**。
  ⇒ 出现这种"半透明僵尸"式症状，第一件事就是查 `animeFile` 与 `.dat` 是否同目录同名。

### A8-08 ★★★ 整包被拒头号元凶：`.tres` 里的 `type="Script"` **不享受豁免**（★ 2026-10-13 修复轮定案）

- **现象**：游戏 Mod 管理面板 `最近失败：Mod 包加载失败。`，
  `运行版本` / `运行 SHA256` / `实际模式` **三项全空**（= 从未成功应用）；
  `logs/godot.log` 里有
  `[ModLoader] package rejected: …: missing or nonportable resource reference: <包内文件>: <path>`。
- **根因**：`ModLoader.cs:657-663` 的豁免**必须三条件同时成立**：
  ① `type=="Script"`；② **本文件是 `.tscn`**；③ **本文件**在 `Resources/Characters/<8 类>/…`（≥5 段）。
  ⇒ **`.tres` 的 Script 引用一律要求 `res://` 路径真实存在**。僵尸包里最常踩的就是
  `<Id>ComponentSet.tres` 的 `[ext_resource type="Script" path="res://…/CharacterComponentSet.cs"]`
  —— 真路径是 **`res://Script/Component/Runtime/CharacterComponentSet.cs`**
  （**不是** `…/Component/TowerDefense/Character/…`）。参照工作区任一其它 `*ComponentSet.tres` 抄。
  ⇒ 另：**相对路径的 `.cs`**（`./X.cs`）也会抛，所以伴生脚本必须走 `.tscn` metadata（A8-05）。
- ★ **闸门铁律**：校验脚本**绝不能对 `type="Script"` 一刀切 `continue`**
  —— 这正是本次漏报的原因（该查 69 处、实际只查了 22 处）。
  被豁免的那部分**也要单独验存在性**（否则角色静默失去脚本）。
  详见 `pvz-hybrid-mod-authoring/references/pitfalls.md` 的 **H-02 / H-05**（含 G-A~G-F 六道闸门形状）。

### A8-09 ★★ 僵尸卡进不了卡池？先查 `overrides.PacketBank` 撞车（★ 同轮定案）

- 面板会出现 `OverrideConflict: 覆盖顺序：A → B；生效者：B`，键名 `legacy/packetbank/{GeneralZombie,TotalZombie,Total}`
  ⇒ **库名是全局固定的，两个包同时声明必然冲突**，加载顺序在后者 wins。
- ★★ **不要用 `overrides.PacketBank`**：改成 DLL 里直改运行时字典
  `ResourceManager.Instance.TOWERDEFENSE_PACKETBANKS[key].category["Zombie"]`
  （`Godot.Collections.Array`），并在 `SceneTree.process_frame` 里**每 10 帧自愈**
  （重读 → 缺则 `Add` / 重复则删到只剩 1）⇒ **与别人的静态覆盖顺序无关**。
  实证：`向日葵女王僵尸` / `奶龙僵尸` / `tour_dance_commander` 等僵尸包都这么做且**不声明** `overrides`。
- ★ **引擎不会自动把你的 Packet 塞进任何卡池**（`ResourceManager.cs:638-660` 只从
  `PacketBankResource.json` 展开），必须自己注入。
- ★ `ModsCache/<mod id>/<包 SHA256>/…` ⇒ 换包即换目录，旧失败缓存**不会**拖累复验。


### A8-10 ★★★ `UseBatch` 的僵尸：覆写 `_PhysicsProcess` **永远不会执行**（★ 2026-10-13 第 30 轮定案）

- `TowerDefenseZombie.UseBatch = true`（`:38`）⇒ 构造函数里 `SetPhysicsProcess(false)`（`:780` 分支）
  ⇒ **子类覆写的 `_PhysicsProcess` 一次都不会跑**。
- 真链路：`TowerDefenseZombieBatch._PhysicsProcess(:167+)` → `BatchUpdateValidated(:672)` →
  **`BatchUpdate(:658)`（`TowerDefenseCharacter` 的虚函数）**。
  `_Process` 那条支路只跑 `BatchProcessUpdate(:2509)`（状态机，不是物理）。
- ⇒ **所有逐帧物理逻辑（碾压 / 冲锋 / 召唤 / 自定义计时器）必须覆写在 `BatchUpdate(double delta)` 里**，
  并**删掉** `_PhysicsProcess` 覆写（否则非批处理模式下会双重结算）。
- 症状识别：机制「静默不生效」，而引擎自带的状态机行为（啃食、走路）一切正常
  —— 因为那些不走你的回调。

### A8-11 ★★★ 「会移动的剪辑」必须自带 `_ground` 位移通道，**否则该剪辑里原地冻结**

- 位移**只**来自 `_ground` 伪层（`GroundMoveComponent.cs:305-370 TryGetGroundLayerDirectPosition`
  → `TryGetLayerIdForRender` 查 **layerDictionary** + `TryGetManagedLayerPositionForRender` 查 **slice 数组**）；
  引擎**没有 `_ground` 特判**，它就是普通层（层 id 0、媒体是 1×1 `Ground.png`），
  位移 = `groundPosSave - vector`，**每帧一元素 ⇒ 每帧一增量**。
- 融合版官方惯例：**只在会移动的剪辑里有切片**。
  实证：`ZombieFootball` Walk 30 片 1.034 px/帧、Swim 11 片 1.600；`ZombieSwanRider` Walk 47／Swim 33；
  **Idle / Death / Eat / Jump 一律 0 片**。
- ⇒ 自建/移植动画时，若给某剪辑换成了「专用冲刺剪辑」而那段**没有 `_ground` 切片**，
  角色会**原地踏步**（切到该剪辑的瞬间 `groundChanged=false` ⇒ 位移 0）。
  **修法**：给该帧段注入 `_ground` 切片，步幅 `step_run = step_walk × mult × n/(n-1)`
  （`n` = 该剪辑帧数，`n/(n-1)` 补偿循环回卷丢掉的那一帧），**`.tres` 与 `.dat` 双侧同步**。
- ⇒ 闸门：**`Walk/Run/Swim/Dash` 每个剪辑都要有 ≥2 个 `_ground` 切片**。
- ⚠️ 「有专用冲刺剪辑时 `sprite.timeScale` 要保持基准」—— 否则 `2.6×2.6 = 6.8` 倍速。

### A8-12 ★★★ 弹体 `.tscn` **引裸 `.png` 会打不出子弹**（★ 第 30 轮定案）

- mod 包**没有 `.import` 元数据** ⇒ `ResourceLoader` 里 `.png` **没有 loader**：
  ```
  ERROR: No loader found for resource: …/ProjectileXxx.png (expected type: Texture2D)
  ERROR: …/ProjectileXxx.tscn:6 - Parse Error: [ext_resource] referenced non-existent resource
  ```
  ⇒ `projectileScene` 实例化失败 ⇒ 僵尸打不出子弹（**日志会同时刷这两条**）。
- 官方 `ProjectilePea.tscn` 用的**也是** `Texture2D` + 裸 png，但它旁边有官方 `.import`。
- **正确范式**（照抄已上线的《究极樱桃战神》）：
  ```
  Resources/Projectiles/<Key>.tscn
    → script = AdobeAnimateSpriteBase
    → flashAnimeData = ../Animations/<Key>Anime.tres
       Animation/Clip = "Idle"
       Animation/LayerVisible/AnimeClips = true
       Animation/LayerVisible/AnimeEvents = true
       Animation/LayerVisible/<层名> = true
       Animation/MediaReplace/<媒体名>.png = null
  Resources/Animations/<Key>Anime.tres → animeFile = "./<Key>Anime.dat"
  Resources/Animations/<Key>Anime.dat  → 内嵌 RGBA8 图集像素（无独立 PNG）
  ```
- 极简单帧 `.dat` 的最小结构：`f32 frameRate(12)` + `u16 frameMax(1)` + `u16 w` + `u16 h` +
  `i64 像素字节数` + RGBA8 像素；然后 **u32 长度**的 PascalString 媒体名 + 4×f32 rect；
  1 层（1 帧 × 1 元素：`u16 mediaId` + `6×f32` + `u32 alpha=0xFF`）；1 剪辑；0 事件。

### A8-13 ★★★ 同一部位常是「两层叠加」——「谁盖谁」看 `layerId`，可见性只管「画不画」

- 融合版把「有防具／无防具／轻损／重损」做成**独立层**，并且**每一帧都带全套**。
  实证（`BlackHorseAnime`）：`head`(#40) = **裸**绿马头（绿脸／绿嘴／红冠／尖角，单层绿像素 1471 px）、
  `Armor`(#11) = **黑橄榄头盔**（只覆盖马头上半的骷髅盔＋面罩）、
  `2_2` / `3_2` = 同族·轻损／重损档（默认关）。
- ★★★ **官方基准 = 两层都可见，且头盔后画**（两层叠出「戴盔的马头」）。
  ⇒ 判据**不是**「档位家族恰 1 个 true」，而是 **`layerId(Armor) > layerId(head)`**。
  反例：02 骑兵 = `head` 40 / `Armor` 11 ⇒ 绿马头把头盔整个盖住（游戏里表现为「马没有头盔」）；
  01 团长 = `head` 22 / `Armor` 23 ⇒ 恰好正确。
- ★★★ **绘制主序 = `layerId`**：GPU 快路径按 slice 数组顺序发射（`AdobeAnimateDrawItemBuilder.cs:353-381`）
  ＝ `layerId` 升序（`AdobeAnimateData.cs:1467-1496` 的双循环）；CPU 排序路径用
  `AdobeAnimateSortPath(rootZIndex, treeOrderPath, LayerId, DrawOrder, …)`（`:416 / :446`）
  ⇒ **只重排 slice 数组没用，必须改 `layerId`**。
- ★ **修法**：把 `Armor` 的 `layerId` 提到 `max(所有层 id)+1`，同步 `layerDictionary` /
  `sliceLayerIds` / `sliceKeys`（高 16 位 = layerId）＋ **数组内次序**（双保险）。
  本项目实现：`build_boc.py::promote_layer_after_text()`（token 级重排、幂等）。
- ⚠️⚠️ **别用 `LayerVisible` 关「裸态层」** —— 本项目第一版把 `head` 关掉，结果
  **连绿嘴一起关掉了**（马头只剩黑盔），与官方基准不符。教训：
  **「可见性」只能控制画不画，「`layerId`」才能控制谁在上。**
- **开关** = Sprite `.tscn` 的 `Animation/LayerVisible/<层名> = true|false`，
  运行时**逐片**门控（`AdobeAnimateDrawItemBuilder.cs:379/395/428 → IsLayerVisible`，`:947-962`）；
  **没写的层 = 默认 true，`layerId` 越界也 true**（`:957-961`）
  ⇒ 把层 id 提到 `max+1` **不会**让它隐形。它适合关「真正互斥的档位」（如 `2_2` / `3_2`）。
- ⇒ 自查渲染工具**必须带可见性**、且**多图共用坐标系**（本项目
  `k3_tres_render.py --tscn <Sprite.tscn> [bbox=…]`）；
  用 `.dat` 的 layer 表渲染会看到「多套变体全堆在一起」的**假象**；
  定位「某块颜色属于哪一层」用**逐层单独渲染**（`k9_layer_probe.py`）。
- 详见 `pvz-hybrid-mod-authoring/references/pitfalls.md` **§I**。
