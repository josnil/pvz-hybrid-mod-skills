#! -*- coding: utf-8 -*-
r"""build_zombie_sunflower_queen.py —— 生成《向日葵女王僵尸 + 火焰向日葵舞者僵尸》双角色 .pmod。

═══════════════════════════════════════════════════════════════════════════════
需求（用户口径，2026-09-25 确认；与经典版原文冲突处一律以用户口径为准）
═══════════════════════════════════════════════════════════════════════════════
向日葵女王僵尸 ZombieSunFlowerQueen
  1) 拥有火焰迪斯科僵尸的全部特点（滑步 / 点燃子弹 / 召唤伴舞）
  2) 伤害 300，攻击类型 = 啃食（Eat），总血量 3500
  3) 每 10 秒生产 250 脑光（机制同向日葵僵尸）
  4) 每 1.5 秒发射 6 颗追踪火球（效果同向日葵女王植物）
     周围 3×3 友方（含自身）免疫减速+冻结；每 0.5 秒对 3×3 内敌方 25 点灼烧
  5) 能召唤火焰向日葵舞者僵尸
火焰向日葵舞者僵尸 ZombieFireSunFlowerBackup
  1) 免疫减速与冻结，总血量 800
  2) 点燃子弹
  3) 每 15 秒生产 150 脑光

贴图：身体复用重置版内置「火焰迪斯科 / 火焰舞者」转好的美术（经典版同名 reanim
已由官方直转，无需再转）；头复用内置「向日葵女王 / 向日葵（僵尸）头」。
⚠️ 经典版解包（`D:\zzz\extract_1789988101`）里**没有**这两只僵尸的头美术
（只有 `Zombie_discoFire_head_full.png` / `Zombie_backupFire_head_full.png` 两张
「戴假发墨镜的僵尸头」整图，不是向日葵头）⇒ 头只能合成，这是唯一可行路线。

═══════════════════════════════════════════════════════════════════════════════
一、为什么「一个包放两个角色」
═══════════════════════════════════════════════════════════════════════════════
`ModLoader.ApplyRuntimeResources` 的候选是**逐文件**的 `RuntimeCandidate`，按
`(NormalizeCategory(Category), InferredKey)` 分组（`ModLoader.cs:566-597`）
⇒ 同一个包里放两个 `Resources/Characters/Zombies/<Key>/…` 是**被支持**的。
好处：两份角色共用**一个** `Runtime/ModAssembly.dll` 与**一个**入口实例，
不会出现「同名 DLL 被两个包各加载一次 ⇒ 两条光环 / 两倍火球」的重复执行。

═══════════════════════════════════════════════════════════════════════════════
二、每个角色的组件集（ParentSet = 内置同名僵尸的组件集）
═══════════════════════════════════════════════════════════════════════════════
· 女王：ParentSet = 内置 `TowerDefenseZombieDiscoFireComponentSet.tres`
        （已含 `ChangeProjectile/FireOffset3Definition` = 点燃子弹 + FogArea）
        追加 `Fire`（追踪火球）+ `Produce`（脑光）
· 舞者：ParentSet = 内置 `TowerDefenseZombieDancerFireComponentSet.tres`
        （已含点燃）
        追加 `Produce`（脑光）

「3×3 灼烧」与「3×3 友方免疫」**不放在数据侧**：`PeriodicAreaEventComponent` 与
`TowerDefenseExplode.CreateExplode` 都会 `FillCharactersIntersectingRectListExcludingCamp`
（排除**自己阵营**，见 `TowerDefenseBattleCharacterRegistry.cs:3279`）⇒ 「给友方加免疫」
根本做不到；而「3×3」的像素尺寸要现读 `TowerDefenseManager.GetMapGridSize()`，
硬编码 `checkShape` 会在不同地图上偏。⇒ 两者统一交给插件，每帧按真实格宽算。

═══════════════════════════════════════════════════════════════════════════════
三、头对位（★ 全部由几何反解得出，见 .cache/_sq_final.py）
═══════════════════════════════════════════════════════════════════════════════
引擎真实变换（`AdobeAnimateSprite.UpdateChild()`）：
    child.Position = <被跟随图层 L 的 pose>.Origin + <父精灵的 offset>
    child.Rotation = <被跟随图层 L 的 pose>.Rotation + child.offsetRotate
   绘制自己时 transform = transform.Translated(child.offset)
⇒ 头节点局部点 P = A·(pose + child.offset) + node，A = rot_scale(θ, −s, +s)。

被跟随层 = 身体片里的 **`anim_hair1`**（女王 **L28** / 舞者 **L22**）
—— ★ 第十四轮从「原版 `HeadSlot` 跟的那一层 `anim_head2`」换过来的，理由见 §三-d。
（旧口径：女王 L19 / 舞者 L15，对应 `ZombieDiscoFire.tscn` 的 `HeadSlot.followSlotId=19`、
`ZombieDancerFire.tscn` 的 `HeadSlot.followSlotId=15` —— 那个值现在只留在 `HeadSlot` 上。）

  · 女王：HEAD_OFFSET = (-83.7633, 27.496)  回代残差 0.00000000
          HEAD_EXTRA_SCALE = 0.9（= 0.45 × **2.0 倍**）
          ← 用户 2026-09-25 四档收敛：
              「头部需移除披风，并将其放大**至少 3 倍**」⇒ 先取 **3.5 倍**
               → 看图后「把头部模型**调小一些**」⇒ **3.0 倍**
               → 再看图「头部**再调小一点**」⇒ **2.5 倍**
               → 最后给出一张**目标图**「头部像这样大就行了」⇒ **2.0 倍**（倍率基准 0.45）
            ⚠️ `A` 矩阵含节点 scale（`rot_scale(θ, −s, +s)`）⇒ **改 scale 必须重解 offset**，
               否则头会横竖都跑偏（实测旧 offset 直接配新 scale ⇒ 残差 50.06 / 40.05 / 30.04 / 20.03px）。
            ★ 2.0 倍是**量出来的**，不是猜的（`.cache/_sq_preview.py --sweep` 离线合成渲染 +
              泛洪分割量参考图，见 §三-b）：参考图「头高/全身高」= 0.4925、
              「头高/可见身体高」= 1.0000；本包在 **2.0 倍** 时为 0.4793 / 0.9206，
              2.25 倍为 0.5280 / 1.1186 ⇒ 取两者之间的 **2.0 倍**（另两个宽度判据也落在 1.8~2.0）。
            ★★ 2026-09-25 第十一轮「头的位置**往上一点**，与刚才示例图的位置相同」
               ⇒ 头整体**上移 20.16 显示px**，`offset.y` 由 −27.7745 → **−50.1706**
               （= 第十一轮落地值；第十二轮放大 1.2 倍时又重解为 **−46.9935**，见下）
               （x 不动；量法 = 拿**刚性**锚点「脸 / 王冠」在两图间比，见 §三-c）。
               ⚠️ **位移加在锚点上、不能直接加到 `offset` 上**（见 `head_place.py` 头注 ★★ 第三轮 ②）。
            ★★ 2026-09-25 第十二轮「头的模型改为**现在的 1.2 倍**」
               ⇒ 2.0 倍 × 1.2 = **2.4 倍**；`head_scale 0.9 →` **`1.08`**，offset **重解**：
                 `(-64.8744, -50.1706)` → **`(-61.2078, -46.9935)`**（回代残差 0.00000000）。
               ⇒ 语义 = **以头块中心为轴原地放大**（`_sq_head_place.py --queen-scale=1.08
                 --queen-shift=0,-20.1565`）：头块落点中心仍是 `(-10.20, -55.26)`
                 —— 与 2.0 倍时**逐字相同** ⇒ 「位置不动、只放大 1.2 倍」，
                 `screen_delta` 仍 `(0, -20.1565)`（第十一轮的上移量原样保留）。
               ⚠️ 第三次印证 **改 scale 必须重解 offset**：旧 offset 配 1.08 ⇒ 残差 **5.2397px**
                 （头块中心偏 `(Δx +3.96, Δy −3.43)`）。
                 （前几轮同款残差：3.5 倍 50.06 / 3.0 倍 40.05 / 2.5 倍 30.04 / 2.0 倍 20.03）
            ★★ 2026-09-25 第十三轮「向日葵女王僵尸和火焰向日葵舞者僵尸的头部**往右上方移一点**」
               【⛔ 已回滚】⇒ 曾两个角色用**同一个增量**：再**右上各 12px**。女王 `shift` `(0, -20.1565)` →
                 `(12, -32.1565)`；offset `(-61.2078, -46.9935)` → `(-72.3189, -58.1046)`
                 （`_sq_head_place.py --queen-scale=1.08 --queen-shift=12,-32.1565`，残差 0）。
               ⚠️ 「移一点」**没有参考图** ⇒ 量级由口径定（见 §三-c 的 ⚠️）：当时取**右上各 12px**
                 —— 介于「一点」（小步）与第七轮舞者「右上各 18px」之间，且比第十一轮
                 「往上一点」实测出的 20.16px 保守。要改只需换 `--queen-shift` 的数值。
               ⛔ 2026-09-25 用户「**回调到上一版**」⇒ 本轮改动**已撤销**：女王 `shift` 回到
                 **`(0, -20.1565)`**、offset 回到 **`(-61.2078, -46.9935)`**（= 第十二轮口径）。
            ★★ 2026-09-25 **第十四轮**（「抬头段头/身衔接不自然」）⇒ 跟随层 L19 → **L28**
               （`anim_hair1`），offset **重解** `(-61.2078, -46.9935)` → **`(-76.9485, 17.7287)`**。
               ⇒ 参考帧（`MoonWalk f0`，θ=0）**整头落点逐像素不变**（实测差异 0.00000000px），
                 只把「转轴跟随的身体层」换掉。证据 / 数值见 §三-d。
            ★★ 2026-09-25 **第十五轮** ①「女王的头部整体向上移动一点」
               ⇒ 头整体**上移 8 显示px**（**无参考图** ⇒ 量级按口径定，见 §三-c 的 ⚠️：
                 本仓先例 = 第十一轮「往上一点」**实测 20.16px**、第十三轮同义取 12px；
                 本轮取 **8px** 保守值 —— 要改只换 `.cache/_j15_shift.py --dy`）。
               offset **重解** `(-76.9485, 17.7287)` → **`(-76.9485, 10.3213)`**
               （`.cache/_j15_shift.py --char queen --dy 8`）：回代位移逐字 `(0, -8.000000)`、
                 整头「形状差」`0.00e+00` ⇒ **纯刚性平移、不变形**；x 不动 ⇒ 纯上移。
               ⚠️ 位移仍然加在**锚点**上再反解（`solve_for`），**别**直接改 `offset.y`。
  · 舞者：HEAD_OFFSET = (-48.6837, -37.1999)  回代残差 0.00000000
          HEAD_EXTRA_SCALE = 1.0（原生头/身 = 0.361，本来就是对的）
          ← 用户 2026-09-25 追加：「头部需整体向**右上方**偏移」
            ⇒ 屏幕空间 `shift = (+18, −18)`（右上各 18px）；`screen_delta` 逐字 = `(18, −18)`。
            ★★ 第十三轮同批「**往右上方移一点**」【⛔ 已回滚】⇒ 曾再右上各 12px，`shift` 累计
               `(30, -30)`；offset `(-67.2827, -46.4485)` → `(-74.3657, -61.8703)`
               （`--dancer-shift=30,-30`，残差 0、`screen_delta` 逐字 = `(30, -30)`）。
            ⛔ 用户「**回调到上一版**」⇒ 已撤销：舞者 `shift` 回到 **`(18, -18)`**、
               offset 回到 **`(-67.2827, -46.4485)`**（= 第七轮口径）。
            ★★ 2026-09-25 **第十四轮** ⇒ 跟随层 L15 → **L22**（`anim_hair1`），offset **重解**
               `(-67.2827, -46.4485)` → **`(-48.6837, -37.1999)`**。
               ⇒ 参考帧（`Walk f0`，θ=20.3316°）**两层的旋转角相同** ⇒ 整头落点逐像素不变
                 （实测差异 1e-7px）。证据 / 数值见 §三-d。
  ⚙️ 两个角色的新参数都由 `.cache/_sq_head_place.py` 重解（残差 0、可复跑、带 `--shift`）。

姿态口径：**三行开关一个都不写**（`usePos`/`useRotate`/`rotation`）⇒ 引擎每帧覆写
Position+Rotation，头跟着身体层摆（= 本仓《超级机枪读报僵尸》当前口径）。
`offsetRotate = 0.0`：女王站姿层旋转恒 0°，舞者战斗时的 `ArmRise` 段旋转 0..5°，
不补偿最自然。

★★ 2026-09-25 **第十四轮**（用户：「跳舞动画在**抬头动作阶段**，头部与身体出现
   **衔接不自然**」）：**两个头都写 `timeScale = 0.0`** ⇒ 冻结头自播的 `Idle`
   （头自己那 24/25 帧里**整颗头会横滑 13.2 局部单位**，×1.08 = 显示 14.3px；
   身体在抬头段 f33 起定住 15° 而头还在滑 ⇒ 脖子处随头开合）。
   位置 / 旋转 / 缩放**一律不动**（仍由身体下颌层带着走）；`Aura` **不冻结**（火圈该转）。
   完整证据链见 `HEAD_TIME_SCALE` 上方长注释；判据脚本
   `.cache/_j14_headframes.py` / `_j14_headanim.py` / `_j14_rigid.py` / `_j14_probe.py`。
   ⇒ 漂移（「头并集底边 − 脖子层顶边」）女王 12.176 → **7.637px**、舞者 8.177 → **4.897px**。
   ⛔ **2026-09-25 第十五轮：本冻结已【取消】**（用户「取消头自播的 Idle 冻结」⇒ 见下 ③）。

★★ 2026-09-25 **第十五轮**（用户：①「**女王的头部整体向上移动一点**」②「修复女王和舞者在
   **抬头后收头**时头部与身体**分离**的问题，确保动画过程中头部始终与身体正确连接」
   ③「**取消头自播的 Idle 冻结**」）：
   · ① **数据侧**：女王 `head_offset` `(-76.9485, 17.7287)` → **`(-76.9485, 10.3213)`**
     （上移 **8 显示px**；纯刚性平移 ⇒ 形状逐像素不变）。详见上面女王段的 ★★ 第十五轮。
   · ② **数据侧零改动** —— 真凶在**插件层**：可见头的位姿由 `SyncHeadPairs()` 每帧从
     影子抄，而它挂在 `SceneTree.process_frame`（**早于所有节点的 `_process`**）
     ⇒ 读到的永远是影子**上一帧**的位姿 ⇒ **头永远落后身体 1 帧**。
     正常帧位移 < 1px 察觉不到，但**抬头 / 收头交界**一帧位移可达 **20~33px**
     （女王 `PointDown` f45 → `Walk` f46：L28 的 node `(-49,-109) → (-18,-120)` ≈ **33px**；
       L19 亦 ≈ **28px**）⇒ 头与身体**错位** = 用户看到的「分离」。
     ★ 修法：`OnProcessFrame` 里再排一个 `Callable.CallDeferred()` ⇒ 同一帧的**帧末**
       （所有 `_process` 之后、绘制之前）用**当帧**位姿覆盖 ⇒ **零延迟**；即便它落到下一帧
       初，此刻影子仍是当帧值 ⇒ 同样正确。`CallDeferred` 抛错则退化为旧行为（不更差）。
     ⚠️ 这解释了「为什么离线几何判据（1D 接缝 / 2D 偏差 / 缺帧扫描）全都测不到它」——
        离线渲染**没有时序**，必须读插件与引擎的**调用顺序**才看得见。
   · ③ **取消第十四轮的 `timeScale` 冻结**：`HEAD_TIME_SCALE = 0.0` → **`None`**
     ⇒ 两个头节点**都不再写** `timeScale`（引擎用 `[Export]` 默认 `1.0`）
     ⇒ 头重新播放自己的 `Idle`（眨眼 / 花瓣摆动等）。
     ⚠️ `self_check` 的断言方向随之**翻转**为「**不得出现** `timeScale`」；
        `GOLD_HEAD_TIME_SCALE` 已删除；负向 N36/N37 改成「注入 `timeScale`（可见头 / 影子）」、
        N38 改成「注入 `pause`」。     ⚠️ 当初冻结的收益只有 2.2~4.5px（见上）⇒ 取消的代价同样很小。

  ★★ 2026-09-25 **第十六轮**（用户：「将女王的头部**位置回调至之前的状态**，并将头部的
     **缩放比例调整为原有的 2.0 倍**，确保两项调整**同时生效且相互不冲突**」）：
     · 两项**一次解**：`head_scale 1.08 →` **`0.9`**（2.4 倍 → **2.0 倍**，基准 0.45），
       `head_offset` `(-76.9485, 10.3213)` → **`(-83.7633, 27.496)`**；跟随层仍 L28。
     · 「位置回调至之前的状态」= **撤销第十五轮的 8px 上移** ⇒ 头块中心回到
       `(-10.2002, -55.2566)`（= 第十四轮末的值；实测与上一版**逐字相同**，偏差 `0.00000000`）。
       第十一轮「往上一点」的 **20.16px 上移保留**（那是一次显式的用户要求，从未被撤销）。
     · ★ 为什么「同时生效且不冲突」：`A = rot_scale(θ, −s, +s)` **含节点 scale** ⇒ 光改 scale
       会让头跑偏（实测旧 offset 配 `0.9` ⇒ 偏差 **16.63px**，铁律 27）；本轮的解法 = 在
       **新 scale** 下把「头块中心」重新钉到**上一版的位置**上 ⇒ **位置不动、尺寸变小**。
       尺寸比实测 `0.8333`（= 2.0 / 2.4，宽高一致）。工具：`.cache/_j16_resize.py`。
     · ⚠️ 另一档「之前」= 连第十一轮的 20.16px 也撤销（回到最初 2.0 倍那版的原位）
       ⇒ `head_offset=(-83.7633, 49.8921)`；要换只需 `_j16_resize.py --pos-src zero`。
     · ⚠️⚠️ **别再照 `_sq_head_place.py` 解 offset**：它写死 `follow=19`（**第十四轮前**的口径），
       换成 L28 后 `screen_delta` 相对新锚点**已不等于历史 `shift`**（实测 `(-3.7002, 30.2434)`
       vs 期望 `(0,-20.1565)`）⇒ 拿它解会把头解跑。一律用 `_j16_resize.py` /
       `_j14_final.solve_for` 的**头块中心绝对坐标**口径（同 `_j15_shift.py`）。

═══════════════════════════════════════════════════════════════════════════════
三-d、第十四轮：**换「跟随层」** —— 抬头段接缝的主因与修法（★ 数值全部量出来的）
═══════════════════════════════════════════════════════════════════════════════
结论先行：把 `followParentSpriteLayerId` 从「原版 `HeadSlot` 跟的 `anim_head2`」
换成 **`anim_hair1`**（女王 L19→**L28** / 舞者 L15→**L22**），`head_offset` 按
「参考帧整头落点不变」重解。**参考帧外观逐像素不变**，而**抬头段的接缝跳变大幅缩小**。

为什么原来会「不自然」（因果链，全部可复算）：
  1. 引擎每帧把头的 `Position/Rotation` 写成**被跟随那一层的 pose**
     （`AdobeAnimationSprite.cs:5259-5281`：`Position = transform3.Origin + <父精灵 offset>`、
     `Rotation = transform3.Rotation + offsetRotate`；★ 用的是**父精灵**的 `offset` ⇒
     `HeadShadow.offset` 其实**不参与定位**，只是与 `Head.offset` 保持逐字一致）。
  2. 我们的头是**刚体**、且比原头大 2.4 倍 ⇒ 头美术离枢轴很远；
     `Rotation` 一变，头底缘就被甩出 `∝ R·sinΔθ` 的位移。
  3. **最凶的是 `PointDown`(f45) → `Walk`(f46) 的交界**：`θ(L19)` 一帧内 `0° → 20.332°`，
     `node` 从 `(-30.000, -38.100)` 跳到 `(-8.887, -56.758)`。
     女王换头版头底缘 **−0.29 → +2.40**（+2.69px），而脖子（`Zombie_disco_upperbody`）顶缘
      **−47.45 → −61.01**（−13.56px）⇒ **gap 一跳 +16.26px**；原版原头只跳 **+3.79px**。
     该交界实机**必然播放**：`DancingComponent.AnimeCompleted("PointDown")` ⇒ `parent.Walk()`。
  4. 原版原头组**不是刚体**（各层相对下颌层逐帧漂 4~26 局部单位、含头发摆动，
     舞者还有 `sy 0.80→0.945` 的缩放变化）⇒ 刚体头**先天无法**逐像素复刻原头组，
     只能把「相对脖子的漂移」压到最小。
  5. `anim_hair1` 这一层的特点：**女王的 θ ≡ 0.000°（全 clip）、舞者的 θ 与 `anim_head2`
     同步**（`Walk 20.33°` / `ArmRise 0..5.04°`）⇒ 枢轴落点更贴近脖子，
     且女王那侧干脆**不再跟着下颌转** ⇒ 边界处几乎不动。

判据（显示空间，y 向下为正；脚本 `.cache/_j14_follow.py` / `_j14_pivot2.py`）：
  ① `gap(f) = 头并集 bbox 底边 y − 脖子层（`Zombie_disco_upperbody`）bbox 顶边 y`，
     指标 `max_f |Δ(f)|`（逐帧跳变 = 用户看到的「一顿」）。
  ② 2D 判据：`dev(f) = 换头版头并集中心 − 原版原头并集中心`，指标 `max_f |dev(f) − dev(f_ref)|`
     （= 头相对身体「脱离原轨迹」的程度）。

                 ① 1D max|Δgap|        ② 2D 偏差
  原版基线        3.79 / 2.95 px        0（定义）
  女王 现状 L19   16.26 px              6.68 px
  女王 换 L28     **3.96 px**           **3.22 px**
  舞者 现状 L15    6.19 px              4.56 px
  舞者 换 L22     **2.58 px**           **3.09 px**
  （逐层全扫见 `.cache/_j14_follow.py --layers all`；二维枢轴扫描证明「只挪枢轴」
   在 1D 上也能到 2.67px，但 2D 会劣化到 16.0px ⇒ **换层**才是对的方向。）

⚠️ 换层**必须重解 `head_offset`**（否则头整体跑掉 40+ px）：终值由
   `.cache/_j14_final.py` 反解并核对「参考帧整头落点差异 = 0.00000000px」：
     女王 L28 → `(-76.9485, 17.7287)`；舞者 L22 → `(-48.6837, -37.1999)`。
   之所以「只改 offset 就能保持外观」：参考帧上 `θ` 逐字相同（女王 0.0000°、舞者 20.3316°）
   + `scale` 不变 ⇒ 刚体 + 同旋转 + 同缩放 + 头块中心钉住 ⇒ 整头全等。
⚠️ **别**改成「平移 + 冻结旋转」：`useRotate = false` 只冻结旋转、位置仍跟下颌层跑，
   1D 只降到 ~8.3px、2D 也更差；`pause` 更是不能用（`ApplyRuntimeParentState` 会覆写）。

★ 2026-09-25 追加两条**贴图**改动（定位手段：`layerDictionary`(名→id) 与
   `mediaDictionary`(名→id) 对齐 `sliceLayerIds`/`sliceMediaIds` ⇒ 逐层反查「这层用的是哪张图」）：
   ① **移除披风** —— 女王头层 `"1"` 用的图是 **`cloak00.png`（深红圆顶块）**，就是披风。
      披风实际由 `1` + `cloak1` + `cloak1 复制` **三层**组成，后两层上一轮已关，
      只剩 `"1"` 漏着 ⇒ 本轮从 `QUEEN_HEAD_ON` 去掉。
      交叉印证：官方 `QueenSunFlowerCoustomData.tres` 的 `fliterCloseAll` 把这三层
      列在**同一组**（原版外观层）。
   ② **头部尺寸 2.0 → 2.4 倍**（女王；四轮收敛 3.5 → 3.0 → 2.5 → **2.0**，末轮按用户目标图标定）
      / **右上各 18px**（舞者）—— 见上面 §三 与 §三-b。
   ②-b **女王头再上移 20.16px**（第十一轮「头的位置往上一点，与刚才示例图的位置相同」）
      —— 见上面 §三-c；`offset.y −27.7745 → −50.1706`（第十一轮落地值；第十二轮重解后 −46.9935）。
   ②-c **女王头再 ×1.2（2.0 → 2.4 倍）、原地放大**（第十二轮「头的模型改为现在的 1.2 倍」）
      —— 见上面 §三；`head_scale 0.9 → 1.08`、`offset → (-61.2078, -46.9935)`（残差 0）。
   ②-d 【⛔ 已回滚】**两个头一起再往右上方 12px**（第十三轮「女王和舞者的头往右上方移一点」）
      —— 见上面 §三-c 末尾 ⚠️；当时女王 `offset → (-72.3189, -58.1046)`、
      舞者 `offset → (-74.3657, -61.8703)`（`shift` 曾累计到 `(12,-32.1565)` / `(30,-30)`）。
      ⛔ 用户「**回调到上一版**」⇒ 已撤销，回到第十二轮口径：女王 `(-61.2078, -46.9935)`、
      舞者 `(-67.2827, -46.4485)`。
   ③ **「3×3 光环」贴图改挂身体底部** —— 头层 `图层_3` 用的图是
      **`6-0001.png`..`6-0012.png`（火焰漩涡，12 帧）** = 用户说的那道环。
      用户口径（推荐方案）：**不跟着头，改贴到脚底** ⇒ 见 §七。
   ④ **光环必须画在身体后面** —— 靠 `insertLayerId = 0`，**不是** `z_index`
      （被父代画的子精灵自己的 `z_index` 无效）⇒ 见 §七 与 `AURA_INSERT_LAYER`。

───────────────────────────────────────────────────────────────────────────────
三-b、头部尺寸**不再靠猜**：离线合成渲染 + 参考图泛洪分割（2026-09-25 新增能力）
───────────────────────────────────────────────────────────────────────────────
前四轮「3.5 / 3.0 / 2.5 倍」全是**目测猜**，每次都被下一张图推翻。末轮用户直接给
**目标图**（`QQ_1790301323306.png`）⇒ 改成「**量出来**」三步闭环（工具都留在 `.cache/`）：

  ① **量参考图轮廓** —— `.cache/_sq_refmeasure.py`
     · 截图四周是**纯黑框 + 草坪**，简单阈值会把黑框当背景 ⇒ 必须**从四边泛洪填充**：
       `lawnish(p) = g − max(r, b) > 8`（草坪偏绿）或 `darkish(p) = max(r,g,b) < 45`（黑框），
       从四条边 BFS 扩散，填不到的**最大连通块**才是角色。
     · 实测目标图（202×180）：角色占 `y 38..171`（高 **134**）、`x 60..123`（宽 64）。
  ② **真实渲染候选倍数** —— `.cache/_sq_preview.py --sweep 3.0,2.75,…,1.25`
     · 自写**离线合成渲染器**：读共享图集
       `addons/AdobeAnimateEditor/GeneratedAtlas/AdobeAnimateVisualTextureArray.png`
       （40960×2048 = 20 页 × 2048² 横排）+ `Manifest` 的每 media 页号/页内 rect，
       按 `body/head/aura` 三条变换链把切片喂给 `PIL` 的 `AFFINE` 做**逆矩阵**贴图。
     · 绘制顺序即排序结果：**光环 → 身体 → 头**（光环 `insertLayerId = 0` 先行 ⇒ 在身体后）。
     · 量**真实渲染像素**的 bbox ⇒ 得下表（`S` = `head_scale`，倍率 = `S / 0.45`）：

        参考图：头/全身 = **0.4925**   头/可见身体 = **1.0000**
         倍率      S       头高   头宽  身体rc  全身rc  可见身  头/全身  头/可见身
         3.00   1.3500    87     93    102    136     49    0.6397   1.7755
         2.50   1.1250    73     77    102    129     56    0.5659   1.3036
         2.40   1.0800    70     74    102    127     57    0.5512   1.2281   ← 第十二~十五轮值（第十六轮已退回 2.0）
         2.25   1.0125    66     70    102    125     59    0.5280   1.1186
         2.10   0.9450    62     66    102    124     62    0.5000   1.0000   ← 正中
         2.00   0.9000    58     63    102    121     63    0.4793   0.9206   ★ 当前终值（第十六轮）
         1.75   0.7875    51     55    102    117     66    0.4359   0.7727

       ⇒ **2.10 倍正中**参考图；另两个宽度判据（头宽/可见身体宽）落在 1.8~2.1。
         取**整档 2.0 倍**（= `head_scale 0.9`）——宁可略小一点，避免又一轮「再调小」。
     ⚠️ 2026-09-25 第十二轮用户又要求「头的模型改为**现在的 1.2 倍**」⇒ 2.4 倍
        （`head_scale 1.08`，上表已于 2.40 行补测：头/全身 **0.5512**、头/可见身 **1.2281**）。
        ⇒ 该表在「2.0 倍」这一档仍是**标定依据**（那一档对齐的是用户的**目标图**）；
        2.4 倍比目标图**明显更大**，这是用户**显式要求**的（2.0 × 1.2），不是标定漂了。
     ★★ 2026-09-25 **第十六轮**：用户「缩放调整为**原有的 2.0 倍**」⇒ **退回上表 2.00 档**
        （`head_scale 0.9`；头/全身 **0.4793**、头/可见身 **0.9206**）—— 与「2.10 倍正中」
        只差半档，即当初用户**目标图**的标定值。同轮「位置回调」见 §三-a 顶部第十六轮块。
       ⚠️ 全渲染高度比 ≠ 分割掩码高度比：渲染含火圈/花瓣/发光细节，掩码被草坪混色吃掉边缘
       ⇒ 掩码在 2.5 倍时也只到 0.545。**判定以全渲染比为准**，掩码只作交叉印证。
  ③ **目视复核** —— `.cache/_sq_sbs.py`（参考图 + 候选倍数图按同一高度归一，并排拼一张）。
     · 放大细看用 `.cache/_sq_zoom.py <in> <out> <x0,y0,x1,y1> <倍率>`。

  ⚙️ 涉及 `PIL` 的脚本必须用
     `C:/Users/yanxulin002/.workbuddy/binaries/python/envs/default/Scripts/python.exe`（PIL 12.3.0）；
     纯数学脚本（`.cache/_sq_head_place.py` / 本生成器）用
     `versions/3.13.12/python.exe`（**没有** PIL）。

───────────────────────────────────────────────────────────────────────────────
三-c、头的位置（**纵向**）怎么量出来：只用两张真实截图，靠**刚性锚点**（2026-09-25 第十一轮）
───────────────────────────────────────────────────────────────────────────────
需求「头的位置往上一点，与刚才示例图的位置相同」= 拿**上一轮的示例图**当目标、
拿**新的实机截图**当现状，量出「头要上移多少」。工具：`.cache/_sq_overlay2.py`。

  ⚠️ **先看三个坑**（都实际踩过）：
   1. **两张图的画幅与角色占比都不同**（示例 202×180、实机 160×195）⇒ 绝对 y 不可比，
      必须先找一个**两图都有、且与头无关**的身体标尺做归一。
   2. **不能用裤高当标尺**：实机截图的裤子被**脚底光环**截断（白块只到 y=123，真腿到 ~150）
      ⇒ 裤高跨图不可比。本包改用**头宽**（两图都是同一素材同一 2.0 倍 ⇒ 头宽 = 共同比例尺，
      实测 64 vs 62，差 3.2%）。⚠️ 头**高**受火焰帧影响，只能用**宽**。
   3. **头的锚点必须"刚性"**：头的 bbox 含**火焰花瓣**，而火焰是**逐帧动画**的
      （实机截图里火焰向上张扬、示例图里花瓣向下延伸）⇒ 用「头顶 / 头底 / 头块中心」
      都会被帧差污染：实测头块中心判据给 **+15.90** 显示px，而刚性判据给 **+20.2**，
      **差 4.3px（≈ 20% 误差）** —— 这就是第十一轮第一次算错的原因。
      ✅ 正解 = 头块 bbox **内的黄色块**，按面积降序取前两块：
         · 第 1 大 = **脸**（宽:高 ≈ 2:1）
         · 第 2 大 = **王冠**金色环（≈13×15）
         两者随整个头平移、**不随火焰变形** ⇒ 刚性。
         （实测两图都稳定给出这两块；黄上衣同色但被「限定在头块 bbox 内」排除。）

  ✅ 量法（`.cache/_sq_overlay2.py <out.png>` 一次跑完并出红/青叠加图）：
    ① 各图取「画面里**最靠上的橙色大块**」= 头块
       ⚠️ 不能用「最大橙块」——实机截图的**脚底光环** n=6701 > 花瓣 n=1575，最大块会选到光环。
    ② 各图取「白块中**最靠下**的大块」= 裤子，其 bbox 顶 = **裤腰**
       ⚠️ 不能用「最大白块」——离线渲染图里**白手套与白裤连通成一块**。
    ③ 尺度 `s = 头宽(实机) / 头宽(示例)`；把示例图缩放 `s`，再平移使**裤腰**重合。
    ④ 在统一坐标系里比「脸中心」「王冠中心」的 y 差 ⇒ 取**平均**为采用值。
    ⑤ 截图px → 显示px：`头宽(截图) / 头宽(显示)`，后者由离线渲染量得（2.0 倍 / k=2 ⇒ 60.50px）。

  ✅ 第十一轮实测量（Δy > 0 = 实机头更低）：
      判据                      目标(示例)        现状(实机)       Δy(截图)   Δy(显示)
      头块中心(含火焰·仅参考)   ( 83.0, 29.7)   ( 85.0, 46.5)    +16.82    +15.90
      **脸中心(刚性★)**         ( 85.5, 20.9)   ( 85.0, 42.5)    +21.60    **+20.42**
      **王冠中心(刚性★)**       ( 72.1,  6.5)   ( 76.0, 27.5)    +21.05    **+19.90**
      ⇒ 采用 = 刚性判据均值 **+20.16 显示px**（两个刚性判据只差 0.5px，互为交叉印证）。
      ⇒ `_sq_head_place.py --queen-shift=0,-20.1565` ⇒ `offset.y = -50.1706`，残差 0。
        ⚠️ 该值是**第十一轮**落地值；第十二轮把 scale 改到 1.08 后**必须重解** ⇒ **`-46.9935`**。

  🔎 顺带查清的一件事：MoonWalk 各帧的**头跟随层 L19** `node.y` 在 **−44.10 ~ −38.10**
     之间摆动（跨度仅 6px），`rot` 恒 0 ⇒ 头的纵向摆动幅度远小于本轮位移，
     不需要「匹配实机截图是哪一帧」。
     命令：直接 `Placement(...).node(f)` 扫 f=0..26（见 `.cache/_sq_head_place.py` 的构造方式）。

  ⚠️ **「移一点」但没有参考图时怎么办**（第十三轮遇到）：本节的量法**必须有第二张图**才有得量。
     用户只说「往右上方移一点」时，**量级只能由「口径」定**，不许目测糊一个数就当结论 ——
     本仓已定的量级先例：第七轮舞者「向右上方偏移」= **右上各 18px**；第十一轮「往上一点」
     = 实测 **20.16px**。⇒ 第十三轮取 **右上各 12px**（比两者都保守，符合「一点」），
     并在交付说明里**点名这是口径默认值、一句话可改**（改法 = 换 `--queen-shift` / `--dancer-shift`）。
     ⇒ 两个角色**用同一增量**（用户是同时提的），舞者的 18px 是**累计**上去的：`(18,-18) → (30,-30)`。


═══════════════════════════════════════════════════════════════════════════════
四、文案（照抄经典版 `NewZombieStrings.txt`，只把冲突数值改成用户口径）
═══════════════════════════════════════════════════════════════════════════════
占位符按本仓已验收的《图鉴/卡片文案》口径落地（`mod交接文档.md`）：
  `{KEYWORD}` / `{FLAVOR}` / `{SHORTLINE}` → 去掉（头词与正文都是裸文本）
  `{STAT}` → `[color=cc241d]…[/color]`（#CC241D 红，面板自己把 describe 包成 #2f375e）
  `describe` 里**不再自带外层颜色**；`花费`/`冷却速度` 由面板拼，不写进字段。
  多行用**真实换行**（`.tres` 里不写 `\\n` 转义）。
数值修正：女王 3000→3500、150脑光/15秒→250脑光/10秒、40/2s→25/0.5s；
         舞者 500→800、25脑光→150脑光。
⚠️ `Localization/translations.csv` 游戏运行时**不加载**（`ModLoader` 从不调
`TranslationServer.AddTranslation`，`.csv` 也不在扩展名白名单）⇒ 中文直接内联。

═══════════════════════════════════════════════════════════════════════════════
五、路径硬约束（违反 = 整包被拒）
═══════════════════════════════════════════════════════════════════════════════
· `Resources/Characters/Zombies/<Key>/{Scene,Sprite}/<Key>.tscn` **恰 6 段**，
  类别目录必须是 `Zombies`，文件名 == 目录名 == `<Key>`（`ModLoader.cs:1279`）。
· 包内自引用一律**相对** `./` `../`；只有指向游戏自带资源才用 `res://`
  （白名单：`res://Prefab|Asset|Script|Resource|Registry|Extends|addons`）。
· `.tres` 里的 `Script` 引用必须是 `res://`。
· 禁 `.cs/.scn/.res/.uid`、禁 `unique_id` / `parent_id_path`、禁 `CompanionOnly`。
· `Resources/Cards/<Key>.tres` 是**注册**位置，包内 `Packet/<Key>.tres` 是镜像。
· 场景必须**显式写 `ComponentSet` 且在 `script` 之前**（否则继承基场景那份没有
  FireComponent / ProduceComponent 的集 ⇒ 组件根本不创建，**零日志**）。

═══════════════════════════════════════════════════════════════════════════════
六、托管运行时（`.pmod` 硬字段）
═══════════════════════════════════════════════════════════════════════════════
`runtimeAssembly` 只能是字面量 `"Runtime/ModAssembly.dll"`；`runtimeApiVersion` 恰好 1；
`runtimeAssemblyPolicy = "optional"`；入口 `Initialize/OnAllModsLoaded/Shutdown`
**一律不许抛**（抛了 = 无条件整包回滚）。改了 `.cs` 必须**单独**跑一次
`python runtime_src_zombie_sunflower_queen/build_runtime.py --check` —— 本生成器不重编 DLL。

═══════════════════════════════════════════════════════════════════════════════
七、「3×3 光环」贴图：从**头**挪到**身体底部**（仅女王，2026-09-25 用户口径）
═══════════════════════════════════════════════════════════════════════════════
灼烧/免疫**逻辑不动**（仍由插件按 `GetMapGridSize()` 每帧算 3×3），本轮只挪**贴图**：
· 复用**同一份**内置 `.tres`（`res://Asset/Anime/Character/Plant/Gold/QueenSunFlower/
  QueenSunFlower.tres`，跨包引用免费）⇒ **不新增 `ext_resource`**（`headscript`/`headdata`
  与头共用）⇒ `Sprite/<Key>.tscn` 的 `load_steps` 仍是 **4**。
· 该 `.tres` 只有**一个 clip**：`"Idle" = Vector2i(0, 23)`（已核）⇒ 直接用 `HEAD_CLIP`。
· `AdobeAnimateSprite : Node2D`（`addons/AdobeAnimateEditor/Node/AdobeAnimateSprite.cs:11`）
  ⇒ 节点类型写 `type="Node2D"` + `script = ExtResource("headscript")`（与 `Head` 同款）。
· 结构（**必须**，否则又是铁律 16 的「父批次代画」）：
      `AuraHolder`  普通 `Node2D`，`position = Vector2(1.4, 54.6)`（贴地点）
      └ `Aura`      `AdobeAnimateSpriteBase`，只开 `图层_3`，
                    `insertLayerId = 0`（＝压在**身体后面**）、`z_index = -1`（非托管路径兜底）
  直接挂身体精灵下 ⇒ 被**身体批次代画** ⇒ 采样身体图集 ⇒ 变成别的角色碎片。

· ★★★ **「画在身体后面」只能靠 `insertLayerId`，`z_index` 无效**（2026-09-25 用户口径④实证）：
  `CollectOwnedChildBindings`（`:5365-5402`）**递归**收集任意深度的 `AdobeAnimateSprite`
  （第 `5397-5400` 行专门穿过非精灵中间节点）⇒ 子精灵走
  `IsRenderedByParentSpriteForRender()==true`（`:9559-9567`）⇒ 由**父精灵的批次**绘制
  ⇒ 排序键 `AdobeAnimateSortPath` 的 `ZIndex` 那一位取的是**父精灵**的
  `snapshot.EffectiveZIndex`（`AppendChildSprites:833-856` 把 `rootZIndex` 原样往下传）
  ⇒ **子精灵自己的 `z_index` 整条被忽略**。
  真正生效的是父精灵给它的 `layerId` ⇒ 写成 `LayerOrder`（`sortLayerOverride = layerId`）。
  取值链 `TryGetChildRenderLayerForRender:7986-8003` →
  `ResolveSpriteChildInsertLayer:8039-8050` =
  `child.insertLayerId >= 0 ? insertLayerId : ResolveTopInsertLayerId()`；
  ⚠️ `insertLayerId` 默认 **−1** ⇒ 回落**顶层** ⇒ 画在最前。
  本包取 **0**：身体 `layerDictionary` 的 id=0 是隐藏的 `'_ground'`，可见层是 **1..29**
  ⇒ `LayerOrder 0` 严格小于每一片身体 ⇒ **完全在身体后面**。
  官方同款：`ZombieDiscoFire.tscn` 的 `ZombieDuckytube` 子精灵写 `Layer/insertLayerId/
  followParentSpriteLayerId = 15`（插到父的第 15 层）。
· 位置标定（`.cache/_sq_aura.py` / `.cache/_sq_ground.py`）：
  根锚点 `offset = Vector2(-40, -80)`（`ZombieDiscoFire.tscn` 根节点）；
  `图层_3` 全帧(0..23) bbox 宽高 **125.00**、中心 `(39.5, 71.5)`
  ⇒ `Aura.offset = (-39.5, -71.5)`（把漩涡中心挪到挂点上）；
  `AURA_SCALE = 1.6` ⇒ 125px → **200px** ≈ 2.6 格宽（3×3 的视觉指示）。
  ⚠️ **挂点 y 的坑**：显示空间 = 美术空间 + 身体 `offset`。`discoFire` 的**全体图层并集**
     底边是 **80.00**，但那是美术工程里那块**隐藏背景板 `_ground`**（宽 188.80、
     y −40..80，内建场景 `Animation/LayerVisible/_ground = false`）的底边，**不是脚**。
     按**脚部图层并集**（`*foot*`）重标 ⇒ 中心 `(1.37, 28.74)`、底边 **54.60**
     ⇒ 挂点取「中心 x + 底边 y」= `Vector2(1.4, 54.6)`（差 25.4px，不修就悬空）。
· `offset` 的坐标语义（**必须记牢**，`AdobeAnimateSprite.cs:3835`）：
  `LocalBounds.Position + offset` **整体**再乘 `GetCachedGlobalTransformForRender()`
  ⇒ **`offset` 活在节点自身基内**（会被节点 `scale`/`rotation` 缩放旋转）
  ⇒ 子精灵美术点 `t` 的落点 = `node + A·(t + offset)`，`A = rot_scale(θ, −s, +s)`。
  这也是换头 `Placement` 模型的依据；`offset` **不能**当作「屏幕平移」直接加。
"""

from __future__ import annotations

import io
import json
import os
import re
import shutil
import stat
import sys
import zipfile
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------- 顶层常量

HERE = os.path.dirname(os.path.abspath(__file__))
WS = HERE
MODS_DIR = r"C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods"
USER_DATA_DIR = os.path.dirname(MODS_DIR)

BUILD_DIR = "SunFlowerQueen"                     # 工作区构建目录（ASCII）
MOD_NAME = "向日葵女王僵尸"                        # Mods 下的工程目录 / .pmod 文件名
MOD_ID = "sunflowerqueenzombie"
PKG_CAT = "Zombies"
MOD_ROOT = os.path.join(WS, BUILD_DIR)
DIST_DIR = os.path.join(WS, "dist")

QUEEN_KEY = "ZombieSunFlowerQueen"
DANCER_KEY = "ZombieFireSunFlowerBackup"

# ---- 内置真源（只读引用；不复制进包） ----
GAME_Z = "res://Asset/Anime/Character/Zombie"
BASE_ZOMBIE_SCENE = "res://Prefab/TowerDefense/Character/TowerDefenseZombie.tscn"
BASE_ASH_SCENE = f"{GAME_Z}/Ash/General/ZombieGeneralAsh.tscn"
BASE_WATER_LINE_SCENE = f"{GAME_Z}/WaterLine/ZombieWaterLine.tscn"
BASE_ZOMBIE_CONFIG_SCRIPT = "res://Resource/TowerDefense/Character/Config/TowerDefenseZombieConfig.cs"
BASE_PACKET_SCRIPT = "res://Registry/Battle/Feature/PacketBank/Resource/Packet/TowerDefensePacketConfig.cs"
BASE_COMPONENT_SET_SCRIPT = "res://Script/Component/Runtime/CharacterComponentSet.cs"
BASE_FIRE_DEF_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentDefinition.cs"
BASE_FIRE_STATE_MACHINE = "res://Script/Component/TowerDefense/Character/FireComponent/FireComponentStateMachine.tres"
BASE_RAY_SCRIPT = "res://Resource/TowerDefense/Collision/AabbRay2DResource.cs"
BASE_CREATEDATA_SCRIPT = "res://Registry/Projectile/Resource/TowerDefenseProjectileCreateData.cs"
BASE_PROJ_SINGLE_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/Projectile/FireComponentProjectileSingle.cs"
BASE_CHECK_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentCheckConfig.cs"
BASE_FIRE_CONFIG_SCRIPT = "res://Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentFireProjectileConfig.cs"
BASE_PRODUCE_DEF_SCRIPT = "res://Script/Component/TowerDefense/Character/ProduceComponent/ProduceComponentDefinition.cs"
ADOBE_SPRITE_BASE_SCRIPT = "res://Extends/AdobeAnimateSprite/AdobeAnimateSpriteBase.cs"
HITBOX = "res://Resource/TowerDefense/Collision/CharacterHitBoxes/Rect_44x70_At_4_n2.tres"

DISC = f"{GAME_Z}/Challenge/DiscoFire"
DANC = f"{GAME_Z}/Challenge/DancerFire"
HEAD_QUEEN = "res://Asset/Anime/Character/Plant/Gold/QueenSunFlower/QueenSunFlower.tres"
HEAD_DANCER = f"{GAME_Z}/Chapter1/Normal/Sprite/Sunflower/SunFlowerHead.tres"

# ================================================================ 角色表
#
# `hide_head_layers` = 身体精灵上要显式关掉的原头图层（不关就从新头底下透出来）
# `head_layers`      = 头 `.tres` 的全部图层名（用于生成 LayerVisible 全表，保持确定性）
# `head_on`          = 其中**保留可见**的层（其余一律 false）
#   女王：砍掉 `stalk_*`(茎) / `*leaf*`(叶) / `cloak*`(斗篷) / `skin*`(替换皮肤，原生默认也关)
#         —— 那些是「一整株植物」的身体部分，不是头
#   舞者：`SunFlowerHead` 全部 20 层都是花瓣/花盘 ⇒ 全开

_Q_STALK_LEAF_CLOAK = [
    "backleaf", "backleaf_left_tip", "backleaf_right_tip",
    "frontleaf", "frontleaf_left_tip", "frontleaf_right_tip",
    "cloak1", "cloak1 复制", "stalk_bottom", "stalk_top",
]
_Q_SKINS = [
    "skin1_1", "skin1_2", "skin1_3", "skin2_1", "skin2_2 ", "skin3_1", "skin3_2",
    "skin3_3", "skin3_4", "skin3_5", "skin4_1", "skin4_2", "skin4_3", "skin4_4",
    "skin4_5", "skin5_1", "skin5_2", "skin5_3", "skin5_4", "skin6_1", "skin6_2",
    "skin6_3", "skin7_1", "skin7_1_2", "skin7_2", "skin7_2_2",
]
QUEEN_HEAD_LAYERS = (
    ["AnimeClips", "1", "anim_idle", "blink", "图层_1", "图层_3", "图层_67 复制", "图层_69"]
    + _Q_STALK_LEAF_CLOAK + _Q_SKINS
)
# ★★ 2026-09-25 用户口径（两条贴图改动，均由 `layerDictionary` → `mediaDictionary` 逐层反查定案）：
#   ① **去掉 `"1"`** —— 该层用的图是 **`cloak00.png`（披风：深红圆顶块）**
#      ⇒ 用户：「头部需移除披风」。披风实际由 `1` + `cloak1` + `cloak1 复制` 三层组成，
#        后两层上一轮已经关掉，只剩 `"1"` 漏着；
#        `QueenSunFlowerCoustomData.tres` 的 `fliterCloseAll` 也把这三层列成同一组 ⇒ 互相印证。
#   ② **去掉 `"图层_3"`** —— 该层用的图是 **`6-0001.png`..`6-0012.png`（火焰漩涡，12 帧）**，
#      就是用户说的「3×3 光环的贴图」。用户口径：**不跟着头，改挂到身体底部**（见 `AURA_*`）。
#   保留：`图层_1`=`hat.png`(皇冠) / `图层_67 复制`=`SunFlower_fire1..3`(火焰花瓣) /
#        `图层_69`=`SunFlower_double_petals_fire`(双层花瓣) / `anim_idle`=`SunFlower_head_fire`(火焰脸)
QUEEN_HEAD_ON = ["AnimeClips", "anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69"]

# ---- 「3×3 光环」贴图：从**头**挪到**身体底部**（用户 2026-09-25 的推荐方案） ----
# 复用同一份内置 `.tres`（`QueenSunFlower.tres`，跨包引用免费）⇒ 只开 `图层_3`，其余全关。
# ⚠️ 结构铁律（同铁律 16 / `HeadHolder`+`Head`）：`Aura` 必须挂在**普通 `Node2D`（`AuraHolder`）**
#    下面；直接挂在身体精灵下会被**身体批次代画** ⇒ 采样身体那张图集 ⇒ 变成别的角色碎片。
# 位置（`.cache/_sq_aura.py` + `.cache/_sq_ground.py` 标定）：
#    · 挂点 = **脚部图层并集**的中心 x + 底边 y（sprite 显示空间 = 美术空间 + 身体 `offset`）
#      = `Vector2(1.4, 54.6)`。
#      ⚠️ 2026-09-25 踩坑记录：`.cache/_sq_ground.py` 首版算的是**全体图层并集**，把美术工程里
#         那块**隐藏背景板 `_ground`**（宽 188.80、y −40..80，内建场景里 `= false`）算了进去
#         ⇒ 得到假的「底边 y = 80.00」（真值是 **54.60**，差 25.4px）。已按脚部图层重标。
#    · `Aura.offset` = −(`图层_3` 全帧 bbox 中心 (39.5, 71.5)) ⇒ 漩涡中心正好落在挂点上。
AURA_HOLDER_NAME = "AuraHolder"
AURA_NODE_NAME = "Aura"
AURA_LAYER = "图层_3"
AURA_ON = ["AnimeClips", AURA_LAYER]
AURA_HOLDER_POS = "Vector2(1.4, 54.6)"    # 脚部并集中心 x=1.37 / 底边 y=54.60（sprite 显示空间）
AURA_SCALE = 1.6                          # `图层_3` 原生 125px → 200px ≈ 2.6 格宽 = 3×3 的视觉指示
AURA_OFFSET = (-39.5, -71.5)              # = −(图层_3 bbox 中心 (39.5, 71.5))
AURA_Z_INDEX = -1                         # 只在**非托管渲染**路径当兜底（见下）
# ★★★ 2026-09-25 用户口径②：「光环的图层应该在**身体的后面**而不是前面」。
#   ⚠️ 踩坑：原来写 `z_index = -1` **完全无效** ——
#     `Aura` 是**被父精灵代画**的子精灵（`AuraHolder` 只是普通 Node2D；
#     `CollectOwnedChildBindings:5365-5402` 会**递归**收集任意深度的 `AdobeAnimateSprite`，
#     第 5397-5400 行专门钻过非精灵中间节点）⇒ 它走 `IsRenderedByParentSpriteForRender()==true`
#     ⇒ 自己的 `z_index` **根本不进排序键**。
#   · 真正决定顺序的是**父精灵**给子精灵算出的 `layerId`：
#     `AdobeAnimateDrawItemBuilder.AppendChildSprites:833-856` 把
#     `sortLayerOverride = TryGetChildRenderLayerForRender(child)` 一路透传给子树的每个 slice
#     ⇒ `AdobeAnimateSortPath.LayerOrder`。而 `ZIndex` 那一位取的是**父精灵的**
#     `snapshot.EffectiveZIndex`（`BuildSpriteTree(snapshot2, …, rootZIndex=snapshot.EffectiveZIndex)`）
#     ⇒ 子精灵自己的 `z_index` 被**整条忽略**。
#   · `TryGetChildRenderLayerForRender`（`:7986-8003`）三级回落：
#     ① `_insertedSprites`（只对**直接子节点**自动插入，`AutoInsertChildSprites:5547-5577`
#        要求 `child.GetParent() == this` ⇒ 本包 `Aura` 挂 `AuraHolder` 下，**不命中**）
#     ② `_spriteChildren` 下标 ⇒ `ResolveSpriteChildInsertLayer`（`:8039-8050`）
#     ③ `child.insertLayerId >= 0 ? 它 : ResolveTopInsertLayerId()`
#     ⚠️ **`insertLayerId` 默认 −1 ⇒ 回落到「顶层」`GetLayerVisibleCountForRender()`** ⇒ 画在最前。
#        这就是「光环跑到身体前面」的真凶（`Head` 也是靠这条顶层回落才压住身体的）。
#   · 官方同款写法（照着抄）：`ZombieDiscoFire.tscn` 的 `ZombieDuckytube` 子精灵写
#     `Layer = 15` / `insertLayerId = 15` / `followParentSpriteLayerId = 15`
#     ——「插到父傀儡的第 15 层」。
#   · 本包取 **0**：`ZombieDiscoFire.tres` 的 `layerDictionary` 里
#     id=0 = `'_ground'`（内建场景 `Animation/LayerVisible/_ground = false`，不画），
#     可见身体层是 **1..29**（id=1 `Zombie_disco_innerarm_lowercuff` … id=29 `anim_hair`）
#     ⇒ `LayerOrder = 0 < 1` ⇒ 光环**严格在每一片身体之前**绘出 = 完全在身体后面。
#   · `z_index = -1` **保留**：万一走了非托管渲染路径（编辑器 / 管理器未就绪），
#     自己的 `z_index` 才生效 ⇒ 双保险，改注释即可，值不动。
AURA_INSERT_LAYER = 0                     # ⇒ LayerOrder 0 < 身体可见层 1..29 ⇒ 压在**身体后面**

DANCER_HEAD_LAYERS = (
    ["AnimeClips", "anim_idle", "SunFlower_bottompetals", "SunFlower_toppetals"]
    + [f"SunFlower_leftpetal{i}" for i in range(1, 9)]
    + [f"SunFlower_rightpetal{i}" for i in range(1, 10)]
)
DANCER_HEAD_ON = list(DANCER_HEAD_LAYERS)


# ---------------------------------------------------------------- 卡片文案
#
# 口径（沿用本仓已验收的植物《超级机枪射手》那套，见该生成器 :339-344）：
#   · 头词（韧性 / 速度 / 伤害 / 特点）→ **裸文本**，吃面板 default_color #8F431B（棕）
#   · 数值 / 短语                        → `[color=cc241d]`（#CC241D 红）
#   · `describe`（首句）                  → 面板自己包 `[color=2f375e]`，**不要再自己包色**
#   · `handbookStory`（FLAVOR 段）        → 裸文本
#   · `.tres` 多行用**真实换行**（Python 里的 `\n` 渲染到文件即真换行，不写 `\\n` 转义）
#   · `{KEYWORD}` / `{SHORTLINE}` / `{FLAVOR}` 占位符**去掉**（只留文本）
#   · 「花费：x」/「冷却速度：x 秒」两行由面板自己拼，**不写进这些字段**
#
# 原文出处：经典版 `properties/NewZombieStrings.txt`
#   · `[ZOMBIE_SUNFLOWERQUEEN_DESCRIPTION]`        :1920-1930
#   · `[ZOMBIE_FIRESUNFLOWERBACKUP_DESCRIPTION]`   :1938-1949
# 用户口径（2026 本轮澄清）：「照抄经典版原文，数值按我这次指定的修正」——
#   女王 韧性 3000→**3500**、灼烧 `40/2s`→**25/0.5s**、脑光 `每15秒150`→**每10秒250**、
#   追加原文没有的 **伤害 300（啃食）**；
#   舞者 韧性 500→**800**、脑光 `每15秒25`→**每15秒150**、②补注「（点燃僵尸方子弹）」。
QUEEN_DESC = "女王驾到，一起燃起来吧！"
QUEEN_HANDBOOK_DESC = (
    "韧性：[color=cc241d]3500[/color]\n"
    "速度：[color=cc241d]慢[/color]\n"
    "伤害：[color=cc241d]300（啃食）[/color]\n"
    "特点：[color=cc241d]①自身和周围3×3僵尸免疫减速与冻结[/color]\n"
    "[color=cc241d]②提供僵尸方火炬效果（点燃僵尸方子弹），灼烧3×3范围植物"
    "（伤害25/0.5s），每1.5秒发射6枚追踪火球[/color]\n"
    "[color=cc241d]③每10秒生产250脑光[/color]\n"
    "[color=cc241d]④召唤4只火焰向日葵舞者僵尸[/color]"
)
QUEEN_HANDBOOK_STORY = "向日葵女王僵尸的最新MV“向日葵僵尸炫舞秀”正在火热售卖中。"

DANCER_DESC = "燃起来的女王小跟班！"
DANCER_HANDBOOK_DESC = (
    "韧性：[color=cc241d]800[/color]\n"
    "速度：[color=cc241d]慢[/color]\n"
    "特点：[color=cc241d]①免疫减速与冻结[/color]\n"
    "[color=cc241d]②提供僵尸方火炬效果（点燃僵尸方子弹）[/color]\n"
    "[color=cc241d]③每15秒生产150脑光[/color]"
)
DANCER_HANDBOOK_STORY = (
    "为什么这帮舞者的头发是绿的？“叶绿体、焰色反应、铜绿…额，"
    "你随便选一个吧。”她扶了扶假胡子，极力掩盖自己理科不及格的事实。"
)

CHARS = [
    dict(
        tag="queen",
        key=QUEEN_KEY,
        display="向日葵女王僵尸",
        body_sprite=f"{DISC}/ZombieDiscoFire.tscn",
        body_script=f"{DISC}/Scene/TowerDefenseZombieDiscoFire.cs",
        parent_set=f"{DISC}/Scene/TowerDefenseZombieDiscoFireComponentSet.tres",
        state_machine=f"{DISC}/Scene/TowerDefenseZombieDiscoFireStateMachine.tres",
        damage_arm=f"{DISC}/DamagePoint/Config/ZombieDiscoFireDamagePointArm.tres",
        damage_head=f"{DISC}/DamagePoint/Config/ZombieDiscoFireDamagePointHead.tres",
        damage_point_data=f"{DISC}/DamagePoint/ZombieDiscoFireDamagePointData.tres",
        body_clip="MoonWalk",
        idle_clip="MoonWalk",
        sleep_clip="MoonWalk",
        garlic_replace="Zombie_jackson_head.png",
        body_pos="Vector2(-12, -33)",
        transform_pos="Vector2(12, 33)",
        water_line_pos="Vector2(-6, -44)",
        head_slot_pos="Vector2(-16.300331, -43.600334)",
        head_slot_extra="Layer = 19",
        arm_slot_pos="Vector2(-16.809021, -14.777953)",
        arm_slot_rot="1.0471977",
        arm_slot_scale="0.6399807",
        ground_slot_pos="Vector2(-50, -40)",
        use_spotlight=True,
        dancer_packet=DANCER_KEY,
        wardrobe="DamagePartSlot",
        hide_head_layers=["anim_hair", "anim_hair1", "anim_hair2", "anim_hair3",
                          "anim_hair4", "anim_head1", "anim_head2"],
        head_tres=HEAD_QUEEN,
        head_layers=QUEEN_HEAD_LAYERS,
        head_on=QUEEN_HEAD_ON,
        # ★★ 2026-09-25 用户口径①（四档收敛）：「头部…放大至少 3 倍」→ 3.5 倍
        #    → 「把头部模型调小一些」→ **3.0 倍** → 「头部再调小一点」→ **2.5 倍**
        #    → 给出一张**目标图**「头部像这样大就行了」→ **2.0 倍**（终值，图文比对标定）
        #    ⇒ 倍率基准 0.45（旧口径 HEAD_EXTRA_SCALE=1.575 即 3.5 倍）⇒ 0.45 × 2.0 = **0.9**。
        # ⚠️ 头对位矩阵 A = rot_scale(θ, −s, +s) **含节点 scale** ⇒ 改 scale 必须重解 offset：
        #    直接把旧 offset 配上新 scale ⇒ 残差 50.06(3.5) / 40.05(3.0) / 30.04(2.5) / 20.03(2.0) px。
        #    新值由 `.cache/_sq_head_place.py --queen-scale=0.9` 反解，回代残差 0.00000000。
        # ★ 2.0 倍是**量出来的**（不是再猜一轮）：`.cache/_sq_preview.py --sweep` 离线合成渲染 +
        #    `.cache/_sq_refmeasure.py` 泛洪分割量用户目标图 ⇒ 参考图「头高/全身高」= 0.4925、
        #    「头高/可见身体高」= 1.0000；本包 2.25 倍为 0.5280/1.1186、2.00 倍为 0.4793/0.9206
        #    （2.10 倍正中 0.5000/1.0000）⇒ 取整档 **2.0 倍**（两个宽度判据同样落在 1.8~2.1）。
        # ★★ 2026-09-25 第十一轮：「头的位置**往上一点**，与刚才示例图的位置相同」
        #    ⇒ **上移 20.16 显示px**，offset.y −27.7745 → **−50.1706**（x 不动）
        #      （第十一轮落地值；第十二轮放大到 1.08 后重解 ⇒ **−46.9935**，见下）。
        #    量法（`.cache/_sq_overlay2.py`，见 docstring §三-c）：
        #      · 标尺 = **头宽**（两图同素材同 2.0 倍 ⇒ 可比；不能用裤高，实机裤子被脚底光环截断）
        #      · 锚点 = 头块内的**黄色块**：第 1 大 = 脸、第 2 大 = 王冠 ⇒ **刚性**，不随火焰帧变形
        #      · 两刚性判据只差 0.5px：脸 +20.42 / 王冠 +19.90 ⇒ 均值 **+20.16**
        #    ⚠️ 用「头块中心」(含火焰) 只会得到 **+15.90**（差 4.3px）——火焰逐帧变，会污染中心。
        #    ⚠️ 位移**加在锚点上**、不能直接加到 offset 上（A 含 sx=−1 横翻 + 交叉项 ⇒ 横竖都会变）。
        # ★★ 2026-09-25 第十二轮：「头的模型改为**现在的 1.2 倍**」
        #    ⇒ 2.0 倍 × 1.2 = **2.4 倍**，`head_scale 0.9 → 1.08`；offset **必须重解**：
        #      (-64.8744, -50.1706) → **(-61.2078, -46.9935)**
        #      （`.cache/_sq_head_place.py --queen-scale=1.08 --queen-shift=0,-20.1565`，残差 0）。
        #    ⇒ 语义 = **以头块中心为轴原地放大**：头块落点中心仍 = (-10.20, -55.26)
        #      （与 2.0 倍时**逐字相同**），`screen_delta` 仍 (0, -20.1565)
        #      ⇒ 第十一轮「上移 20.16px」原样保留、头的位置不动，只变大。
        #    ⚠️ 第三次印证：旧 offset 配 1.08 ⇒ 残差 **5.2397px**（头块中心偏 (Δx +3.96, Δy −3.43)）。
        # ★★ 2026-09-25 第十三轮：「女王和舞者的头**往右上方移一点**」⇒【⛔ 已回滚】。
        #    当时：女王 `shift` (0, -20.1565) → (12, -32.1565)，offset → (-72.3189, -58.1046)
        #    （`.cache/_sq_head_place.py --queen-scale=1.08 --queen-shift=12,-32.1565`，残差 0）。
        #    ⚠️ 「移一点」**无参考图** ⇒ 量级由**口径**定（本仓先例：舞者 18px / 第十一轮实测 20.16px）。
        #    ⛔ 用户「回调到上一版」⇒ 已执行 `--queen-shift=0,-20.1565` 重解回第十二轮：
        #      `head_scale=1.08`、`head_offset=(-61.2078, -46.9935)`（残差 0）。
        # ★★ 2026-09-25 第十四轮：「抬头段头/身衔接不自然」⇒ 跟随层 **L19 → L28**（`anim_hair1`），
        #    offset 重解为 **(-76.9485, 17.7287)**（`.cache/_j14_final.py`，参考帧整头落点差 0px）。
        #    完整因果链 + 判据数值见文件头 §三-d。
        # ★★ 2026-09-25 第十五轮 ①：「女王的头部整体向上移动一点」⇒ 上移 8 显示px，
        #    offset (-76.9485, 17.7287) → **(-76.9485, 10.3213)**（`.cache/_j15_shift.py --dy 8`）。
        # ★★ 2026-09-25 第十六轮：「位置回调至之前的状态」+「缩放调整为**原有的 2.0 倍**」
        #    ⇒ **两项一次解**（`.cache/_j16_resize.py`）：
        #      · 撤销第十五轮的 8px 上移（头块中心回到第十四轮末的 (-10.2002, -55.2566)）；
        #      · `head_scale 1.08 → 0.9`（2.4 倍 → **2.0 倍**），offset **必须重解**
        #        ⇒ **(-83.7633, 27.496)**（残差 0、头块中心偏差 0.00000000 = 位置逐字不变）。
        #    ⚠️ 为什么「同时生效且不冲突」：`A` 含节点 scale ⇒ 只改 scale 会跑偏
        #       （旧 offset 配 0.9 ⇒ 偏差 16.63px）；解法 = 在**新 scale** 下重新钉「头块中心」。
        #    ⚠️ 另一档「之前」= 连第十一轮的 20.16px 也撤销 ⇒ `(-83.7633, 49.8921)`（`--pos-src zero`）。
        #    ⚠️ `_sq_head_place.py` 写死 `follow=19`（第十四轮前口径）⇒ **别再拿它解 offset**。
        head_scale=0.9,
        head_offset=(-83.7633, 27.496),
        head_follow_layer=28,
        head_true_frame_rate=None,
        head_use_multi_mesh=True,
        # ---- 卡片文案（照抄经典版原文，数值按用户口径修正） ----
        describe=QUEEN_DESC, handbook_desc=QUEEN_HANDBOOK_DESC,
        handbook_story=QUEEN_HANDBOOK_STORY,
        # ---- 数值（用户口径） ----
        hp_total=3500.0, hp_near_death=350.0, attack=300.0,
        cost=350, packet_cooldown=15.0, weight=3000, wave_point_cost=300,
        # ---- 数据侧组件 ----
        want_fire=True,          # FireComponent：6 颗追踪火球
        produce_type="BrainSun", produce_num=250, produce_interval=10.0,
        fire_num=6, fire_interval=1.5,
    ),
    dict(
        tag="dancer",
        key=DANCER_KEY,
        display="火焰向日葵舞者僵尸",
        body_sprite=f"{DANC}/ZombieDancerFire.tscn",
        body_script=f"{DANC}/Scene/TowerDefenseZombieDancerFire.cs",
        parent_set=f"{DANC}/Scene/TowerDefenseZombieDancerFireComponentSet.tres",
        state_machine=f"{DANC}/Scene/TowerDefenseZombieDancerFireStateMachine.tres",
        damage_arm=f"{DANC}/DamagePoint/Config/ZombieDancerFireDamagePointArm.tres",
        damage_head=f"{DANC}/DamagePoint/Config/ZombieDancerFireDamagePointHead.tres",
        damage_point_data=f"{DANC}/DamagePoint/ZombieDancerFireDamagePointData.tres",
        body_clip="Walk",
        idle_clip="Walk",
        sleep_clip="Walk",
        garlic_replace=None,
        body_pos="Vector2(-12, -33)",
        transform_pos="Vector2(12, 33)",
        water_line_pos="Vector2(3, -46)",
        head_slot_pos="Vector2(4.5863104, -59.792213)",
        head_slot_extra="",
        arm_slot_pos="Vector2(27.530771, -22.619017)",
        arm_slot_rot="-0.15318371",
        arm_slot_scale="0.6367618",
        ground_slot_pos="Vector2(-33.4255, -40)",
        use_spotlight=False,
        dancer_packet=None,
        wardrobe="damagePartSlot",
        hide_head_layers=["anim_hair", "anim_hair1", "anim_hair2", "anim_hair3",
                          "anim_head1", "anim_head2"],
        head_tres=HEAD_DANCER,
        head_layers=DANCER_HEAD_LAYERS,
        head_on=DANCER_HEAD_ON,
        # ★★ 2026-09-25 用户口径②：「头部…整体向**右上方**偏移」。屏幕空间 shift = (+18, −18)（右上各 18px）。
        # scale 不动（原生头/身 = 0.361，本来就对）；只重解 offset —— 由 `.cache/_sq_head_place.py`
        # 的 `solve(shift=(18,-18))` 给出，`screen_delta()` 逐字回代 = (18.0000, -18.0000)。
        # ★★ 2026-09-25 第十三轮同批「**往右上方移一点**」⇒【⛔ 已回滚】当时再**右上各 12px**
        #    （累计 `shift = (30, -30)`），offset → (-74.3657, -61.8703)（残差 0、
        #    `screen_delta()` 逐字回代 = (30.0000, -30.0000)）。两个角色用**同一增量**。
        #    ⛔ 用户「回调到上一版」⇒ 已执行 `--dancer-shift=18,-18` 重解回第七轮：
        #      `head_scale=1.0`、`head_offset=(-67.2827, -46.4485)`（残差 0）。
        # ★★ 2026-09-25 第十四轮：「抬头段头/身衔接不自然」⇒ 跟随层 **L15 → L22**（`anim_hair1`），
        #    offset 重解为 **(-48.6837, -37.1999)**（`.cache/_j14_final.py`，参考帧整头落点差 1e-7px）。
        #    完整因果链 + 判据数值见文件头 §三-d。
        head_scale=1.0,
        head_offset=(-48.6837, -37.1999),
        head_follow_layer=22,
        head_true_frame_rate=180.0,
        head_use_multi_mesh=False,
        # ---- 卡片文案（照抄经典版原文，数值按用户口径修正） ----
        describe=DANCER_DESC, handbook_desc=DANCER_HANDBOOK_DESC,
        handbook_story=DANCER_HANDBOOK_STORY,
        hp_total=800.0, hp_near_death=80.0, attack=300.0,
        cost=75, packet_cooldown=5.0, weight=1500, wave_point_cost=150,
        want_fire=False,
        produce_type="BrainSun", produce_num=150, produce_interval=15.0,
        fire_num=0, fire_interval=0.0,
    ),
]

BY_TAG = {c["tag"]: c for c in CHARS}

# 两个角色共用的僵尸通用数值
ATTACK_TYPE = "Eat"
MASK_FLAGS = 9
UNUSE_BUFF_FLAGS = 19          # bit0 减速 + bit1 冻结 + bit4 RedHeat（= 内置 DiscoFire/DancerFire）
ELEMENT_FLAGS = 2              # 火
PACKET_TYPE = 6                # PACKET_TYPE.ZOMBIE
HOME_WORLD = 1
PACKET_ANIME_SCALE = "Vector2(0.75, 0.75)"
PACKET_ANIME_OFFSET = "Vector2(25, 60)"
PACKET_ANIME_CLIP_QUEEN = "MoonWalk"
PACKET_ANIME_CLIP_DANCER = "Walk"
# 头自己播哪段动画：两个头 `.tres` 都只有 `Idle` 一个 clip
# （`QueenSunFlower.tres` / `SunFlowerHead.tres` 的 AnimeClips 里只有 `Idle`）
# ⇒ 影子与可见头**必须用同一个 clip**，否则影子的 `pose` 与头自播的动画不同源。
HEAD_CLIP = "Idle"

# ★★ 2026-09-25 **第十四轮**：用户口径「跳舞动画在**抬头动作阶段**，头部与身体出现
#    **衔接不自然**」⇒ 定位到**头自播的 `Idle` 动画**，修法 = **冻结它**（`timeScale = 0.0`）。
#
# 证据链（全部离线复算，脚本在 `.cache/`）：
#   ① 引擎事实：`ElapsedTimer += delta·|timeScale|·frameRate`（`AdobeAnimateSprite.cs:9782`）
#      ⇒ `timeScale = 0` 时 `frameIndex` **永不推进** ⇒ 头恒停在第 0 帧。
#      `timeScale` 是 `[Export]`（`:1229`），**只在运行期被写、永不回存场景** ⇒ 纯场景旋钮。
#      ⚠️ 别改走 `pause`（`:1270` 也是 `[Export]`）：`ApplyRuntimeParentState`（`:5475-5478`）
#         会把 `pause = parent._pause` **覆写掉** ⇒ 影子（父 = 身体精灵）与可见头
#         （父 = 普通 `Node2D` `HeadHolder`）**行为不一致**。`timeScale` 没有这种传播。
#      ⚠️ 冻结**不会**断跟随：`UpdateChild()` 是**父节点**的职责（`:5155`，由根精灵在
#         `:9898/:9939/:9985` 调用），与子节点自己的 `IsPlaybackStopped` 无关
#         （`:9728` 的早退只跳过**该节点自己**的动画推进）。
#   ② 量出来（`.cache/_j14_headframes.py`，判据 = 逐帧并集 bbox + **刚性核心层**中心）：
#      · 女王头 `Idle` 0..23 @12fps：**整颗头（并集与核心层位移逐帧一致 ⇒ 是纯平移，
#        不是原地呼吸）**在头局部空间横滑 **13.20**（x 40.00→53.20）、上下摆 **6.85**
#        ⇒ ×`head_scale 1.08` = **显示空间横滑 14.3px / 上下 7.4px**。
#      · 舞者头 `Idle` 0..24 @12fps：核心层 y 34.49→28.85（**−2.86 局部 ≈ −2.86px**），
#        并集 y 漂 **5.23**（花瓣另有形变）。
#      ⚠️ 身体与头**都是 12fps**，但头的 `Idle` 是常驻循环、身体在 clip 之间切换
#         ⇒ 两者相位**随机**。抬头段身体在 f33 起**定住 15°**，头却还在滑
#         ⇒ 脖子处随「头自己」开合 = 用户看到的「衔接不自然」。
#   ③ 判据「头并集底边 − 脖子层顶边」的漂移（`.cache/_j14_headanim.py`，扫遍相位）：
#      女王 最坏 **12.176 → 7.637px（−37%）**；舞者 最坏 **8.177 → 4.897px（−40%）**。
#   ④ 代价：**零**。位置 / 旋转 / 缩放一律不动，只是让头不动自己的独立动画
#      ⇒ 仍由身体下颌层（女王 L19 / 舞者 L15）带着走，与**原版头**一样是「刚体挂在身上」。
#      （原版原头组本身**不是刚体** —— 各层相对下颌逐帧漂 4~26 单位、含头发摆动，
#        见 `.cache/_j14_rigid.py`；所以刚体头无法逐像素复刻，只能取「不叠加额外漂移」。）
#   ⇒ 第 0 帧与第 23 帧姿态几乎重合（并集中心 (40.00,37.50) vs (40.00,37.00)）⇒ 停在第 0 帧无跳变。
#
# ★★ 2026-09-25 **第十五轮**：用户「**取消头自播的 Idle 冻结**」⇒ 上面这套冻结**已撤销**。
#    `HEAD_TIME_SCALE = None` ⇒ 生成器**不再**给两个头节点写 `timeScale`
#    ⇒ 引擎用 `[Export]` 默认 `1.0` ⇒ 头重新播放自己的 `Idle`（眨眼 / 花瓣摆动等）。
#    ⚠️ 上面的因果链与数值**保留为历史**（它解释了当初为什么冻结、以及代价只有 2.2~4.5px）。
#       若将来又要冻结：把它改回 `0.0`，**并同步**把 `self_check` 里
#       「不得写 timeScale」那条断言翻回「必须等于金标」（否则自检会红）。
HEAD_TIME_SCALE = None

# 火球（照抄植物《向日葵女王》的发射口径 + 僵尸朝向取负）
#
# ★★ 齐射的**数据侧正解**（僵尸侧，源码级取证）：
#   `FireComponent.Fire()`（`FireComponent.cs:3429/3434`）**一次遍历 `fireProjectileList` 全部配置**，
#   每条配置各自 `CreateProjectile(cfg.firePosId, …)`，而
#   `CreateProjectile`（`:2684`）里 `posId` 就是 `_firePosMarkerPaths` 解析出的
#   `_firePosMarkers[posId]` 的下标（`:2708-2715`）。
#   ⇒ **N 条配置 + N 个 Marker = 同一次 `Fire()` 同帧打 N 颗**，不需要插件循环。
#   （铁律 22 的植物侧口径「多 Marker + 不写 `fireNumAtOnce`」在僵尸侧等价于：
#     `fireProjectileList` N 条、`firePosId` 0..N-1、**不写** `fireNum`/`fireNumAtOnce`。）
#   ⚠️ 反面教训：只写 1 条配置 ⇒ 一次 `Fire()` 只出 1 颗（写成 6 颗就永远出不来）。
#   ⚠️ 更不能用 `fireNumAtOnce = true` + `fireNum = 6` 配 6 条配置 ⇒
#     `FireConfiguredVolley()`（`:3413`）会循环 6 次 `Fire()` ⇒ **36 颗**。
#
# `fireMethodFlags = 32` = `PROJECTILE_FIRE_METHOD_FLAG.TRACK`：
#   `CreateProjectile:2718` `if ((fireMethodFlags & 0x20) != 0)` → `GetProjectileInitialTrackTarget(...)`
#   ⇒ 「追踪火球」就是引擎自带的这条，不是插件模拟的。
FIRE_PROJECTILE_NAME = "FirePea"
FIRE_BASE_DAMAGE = 40.0
FIRE_COLLISION_FLAGS = 11
FIRE_METHOD_FLAGS = 32
FIRE_AUDIO = "ProjectileThrow"
FIRE_SPEED = -600.0           # 负号 = 向僵尸面朝方向（僵尸基础场景三层 Scale.X 都是 +1）
# 6 条配置各自的初速角（度）：对称扇形散开，追踪会把它们拉向目标
FIRE_DIR_SPREAD = (-22.0, -13.0, -4.5, 4.5, 13.0, 22.0)
# 6 个火球生成点沿 y 铺开（相对炮口，px），避免同帧 6 颗完全重叠成一颗粒子
FIRE_MARKER_Y_STEP = 14.0
# 脑光产出用的静态投掷点（`ProduceComponentDefinition.markerPaths`）
PRODUCE_MARKER_NAME = "ProduceMarker"
PRODUCE_MARKER_PATH_TMPL = "SpriteGroup/TransformPoint/{key}/ProduceMarker"
# 6 个火球生成点（`FireComponentDefinition.firePosMarkerPaths`）
FIRE_MARKER_NAME_TMPL = "FireMarker{idx}"
FIRE_MARKER_PATH_TMPL = "SpriteGroup/TransformPoint/{key}/FireMarker{idx}"

# 插件侧常量（★ 数值只在 runtime_src_zombie_sunflower_queen 里出现一次；
#          这里记录「期望值」，自检会读 .cs 源码比对）
PLUGIN_FIRE_NUM = 6
PLUGIN_FIRE_INTERVAL = 1.5
PLUGIN_BURN_INTERVAL = 0.5
PLUGIN_BURN_DAMAGE = 25.0
PLUGIN_GRID_SPAN = 3.0        # 3×3 格
PLUGIN_IMMUNE_FLAGS = 3       # bit0|bit1

RUNTIME_ASSEMBLY = "Runtime/ModAssembly.dll"
RUNTIME_ENTRY_TYPE = "SunFlowerQueenRuntimeEntry"
RUNTIME_API_VERSION = 1
RUNTIME_POLICY = "optional"
RUNTIME_SRC_DIR = os.path.join(WS, "runtime_src_zombie_sunflower_queen")

# 游戏侧编辑器 72 个标准子目录（原样照抄 XWModProjectLayout.StandardDirectories）
STANDARD_DIRS = [
    "Scenes", "Scripts", "Battle", "Battle/Features", "Battle/Processes", "Battle/Components",
    "Resources", "Resources/Levels", "Resources/LevelCatalogs", "Resources/Maps",
    "Resources/MapCells", "Resources/GameplayLogic", "Resources/GameplayLogic/Waves",
    "Resources/StateMachines", "Resources/StateMachines/Conditions", "Resources/CharacterComponents",
    "Resources/CharacterCombat", "Resources/CharacterCombat/Attacks", "Resources/CharacterCombat/Buffs",
    "Resources/CharacterCombat/Events",
    "Resources/CharacterData", "Resources/CharacterData/Armor", "Resources/CharacterData/Custom",
    "Resources/CharacterData/DamagePoints", "Resources/BuffVisuals", "Resources/CollisionGeometry",
    "Resources/AwardSettlements", "Resources/UnlockConditions", "Resources/PacketEvents",
    "Resources/PacketSpawnEntries",
    "Resources/PacketSpawnEntries/Level", "Resources/PacketSpawnEntries/Conveyor",
    "Resources/PacketSpawnEntries/Rain", "Resources/ConveyorEvents", "Resources/ToolEvents",
    "Resources/Cards", "Resources/CardCostRules", "Resources/CardOverrides", "Resources/PacketBank",
    "Resources/Projectiles",
    "Resources/ProjectileChanges", "Resources/Characters", "Resources/Characters/Plants",
    "Resources/Characters/Zombies", "Resources/Characters/Props", "Resources/Characters/Vases",
    "Resources/Characters/Mowers", "Resources/Characters/Items", "Resources/Characters/Graves",
    "Resources/Characters/Craters",
    "Resources/Collectables", "Resources/DropItems", "Resources/Mowers", "Resources/Shovels",
    "Resources/FallingObjects", "Resources/Animations", "Resources/AnimationAtlasProfiles",
    "Resources/BGMConfigs", "Resources/Survivals", "Resources/Tutorials",
    "Resources/Tutorials/Conditions", "Resources/Tutorials/Steps", "Resources/NpcTalks",
    "Resources/Shops", "Resources/Dialogs", "Assets", "Assets/Images", "Assets/Audio",
    "Assets/Audio/Sfx", "Assets/Audio/BGM",
    "Assets/Fonts", "Localization",
]

MANIFEST_KEYS = [
    "schemaVersion", "id", "name", "version", "author", "description",
    "dependencies", "conflicts", "provides", "overrides", "scripts",
    "runtimeAssembly", "runtimeEntryType", "runtimeApiVersion", "runtimeAssemblyPolicy",
    "blueprints", "translations", "resources",
]
PROJECT_KEYS = [
    "Name", "Version", "Author", "Description", "ExportDirectory", "GameDirectory",
    "CreatedDate", "LastModifiedDate",
]

TZ_CN = timezone(timedelta(hours=8))
FIXED_T = (2026, 1, 1, 0, 0, 0)


# ---------------------------------------------------------------- 包内路径

def pkg_rel(key):
    return f"Resources/Characters/{PKG_CAT}/{key}"


def cfg_file(key):
    return f"TowerDefense{key}.tres"


def card_rel(key):
    return f"Resources/Cards/{key}.tres"


def pkg_cfg_rel(key):
    return f"{pkg_rel(key)}/Config/{cfg_file(key)}"


def pkg_packet_rel(key):
    return f"{pkg_rel(key)}/Packet/{key}.tres"


def pkg_scene_rel(key):
    return f"{pkg_rel(key)}/Scene/{key}.tscn"


def pkg_set_rel(key):
    return f"{pkg_rel(key)}/Scene/{key}ComponentSet.tres"


def pkg_fire_rel(key):
    return f"{pkg_rel(key)}/Scene/{key}FireComponentDefinition.tres"


def pkg_produce_rel(key):
    return f"{pkg_rel(key)}/Scene/{key}ProduceComponentDefinition.tres"


def pkg_sprite_rel(key):
    return f"{pkg_rel(key)}/Sprite/{key}.tscn"


def _abs(rel):
    return os.path.join(MOD_ROOT, rel.replace("/", os.sep))


def _prop(key):
    """Godot `.tscn` 属性名写法：**整条 key** 含空格或非 ASCII 时整体加引号。

    ⚠️⚠️ 血泪史（2026-09-25 当场踩到）——**引号必须包住整条属性名**：
        正确：`"Animation/LayerVisible/图层_1" = true`   ←（官方 `QueenSunFlower.tscn` 逐字如此）
        错误：`Animation/LayerVisible/"图层_1" = true`   ←（只包末段 ⇒ **静默失效**）
      Godot 解析出的属性名里**会带上引号** ⇒ `AdobeAnimateSprite._Set` 里
      `layerDictionary.ContainsKey(name)` 为假 ⇒ 直接 `return true` 什么都不做 ⇒
      该层保持**初值 true** ⇒ **永远可见**（哪怕你写了 `= false`）。
      本包实测后果：`HeadShadow` 的「全层 false」失效 6 层（`图层_1` 皇冠 / `图层_69` 花瓣 /
      `图层_67 复制` 火圈 / `图层_3` 光环 / `cloak1 复制` 披风 / `skin2_2` **脸**）⇒ 身体上
      **多长出一个完整的头**，且皇冠/光环/披风关不掉。
    ⚠️ 判定口径就用「含空格或非 ASCII」——与官方文件逐字一致（`Animation/LayerVisible/1 = true`
      裸写，`"Animation/LayerVisible/Layer 29" = true` 整条加引号）。
    """
    return f'"{key}"' if (" " in key or not key.isascii()) else key


# ---------------------------------------------------------------- 基础工具

def write_bytes(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def write_bytes_if_changed(path, data):
    if os.path.isfile(path):
        with open(path, "rb") as f:
            if f.read() == data:
                return False
    write_bytes(path, data)
    return True


def fmt_f(v):
    """Godot .tres 的 double 风格：至少一位小数。"""
    s = f"{float(v):.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s


def write_text(path, text, newline="\n"):
    write_bytes(path, text.replace("\n", newline).encode("utf-8"))


def read_json(path):
    with io.open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def dump_json(path, obj):
    write_text(path, json.dumps(obj, ensure_ascii=False, indent=2), "\n")


_ESC = re.compile(r"\\u([0-9a-fA-F]{4})")


def godot_json(obj, newline="\r\n"):
    s = json.dumps(obj, ensure_ascii=True, indent=2)
    s = _ESC.sub(lambda m: "\\u" + m.group(1).upper(), s)
    return s.replace("\n", newline)


def net_datetime(dt):
    off = dt.strftime("%z")
    off = off[:3] + ":" + off[3:] if off else "+08:00"
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "0" + off


def safe_rmtree(path):
    """刻意不用 shutil.rmtree（本机被劫持成 fail-closed 的回收站搬运）。"""
    if not os.path.isdir(path):
        return False
    for root, dirs, files in os.walk(path, topdown=False):
        for fn in files:
            fp = os.path.join(root, fn)
            try:
                os.remove(fp)
            except PermissionError:
                os.chmod(fp, stat.S_IWRITE)
                os.remove(fp)
        for dn in dirs:
            os.rmdir(os.path.join(root, dn))
    os.rmdir(path)
    return True


def sweep_stale_files(root, keep):
    removed = []
    for r, dirs, files in os.walk(root):
        for fn in files:
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, root).replace("\\", "/")
            if rel not in keep:
                os.remove(full)
                removed.append(rel)
    return removed


def sync_tree(src, dst, marker):
    """src → dst 增量镜像（只写变化的文件、只删 src 里没有的文件与空目录）。

    返回 (写入数, 删除数)。dst 必须已确认是我方目录（带 marker）。
    """
    keep = set()
    wrote = 0
    for r, dirs, files in os.walk(src):
        rel_dir = os.path.relpath(r, src).replace("\\", "/")
        rel_dir = "" if rel_dir == "." else rel_dir
        target_dir = os.path.join(dst, rel_dir.replace("/", os.sep)) if rel_dir else dst
        os.makedirs(target_dir, exist_ok=True)
        for fn in files:
            keep.add(f"{rel_dir}/{fn}" if rel_dir else fn)
            with open(os.path.join(r, fn), "rb") as f:
                data = f.read()
            if write_bytes_if_changed(os.path.join(target_dir, fn), data):
                wrote += 1
    keep.add(marker)
    removed = 0
    for r, dirs, files in os.walk(dst, topdown=False):
        for fn in files:
            full = os.path.join(r, fn)
            rel = os.path.relpath(full, dst).replace("\\", "/")
            if rel not in keep:
                os.remove(full)
                removed += 1
        rel_dir = os.path.relpath(r, dst).replace("\\", "/")
        if rel_dir != "." and not os.listdir(r):
            if not os.path.isdir(os.path.join(src, rel_dir.replace("/", os.sep))):
                os.rmdir(r)          # src 里没有的空目录 → 历史遗留，清掉
                removed += 1
    return wrote, removed


# ================================================================ 内容生成

def _layer_lines(layers, on_set):
    # ⚠️ 引号包整条属性名（见 `_prop`）—— 只包层名会让这一行**完全无效**
    return "\n".join(f"{_prop('Animation/LayerVisible/' + k)} = "
                     f"{'true' if k in on_set else 'false'}" for k in layers)


def _bad_prop_keys(text):
    """扫出「属性名引号写法错误」的行（判定口径与成因见 `_prop`）。

    只看**属性路径**（名字里含 `/`），跳过 `.tres` 多行字符串的续行
    （那些行也含 `=`，例：`速度：[color=cc241d]慢[/color]` —— 是 `[color=…]` 里的等号）。
    返回 `[(行号, 原文, 原因)]`，两类：
      A 只给末段加引号 `Animation/LayerVisible/"图层_1" = true` ⇒ 名字带引号 ⇒ 静默失效
      B 整条含空格/非 ASCII 却裸写 ⇒ 名字被拆碎 ⇒ 静默失效
    """
    bad = []
    for i, ln in enumerate(text.splitlines(), 1):
        s = ln.strip()
        if not s or s.startswith(("[", "#")) or "=" not in ln:
            continue
        key = ln.split("=", 1)[0].rstrip()
        if not key:
            continue
        whole_q = len(key) > 1 and key.startswith('"') and key.endswith('"')
        name = key[1:-1] if whole_q else key
        if "/" not in name:          # 不是属性路径（含 .tres 文本续行）⇒ 跳过
            continue
        if whole_q:
            continue
        if '"' in key:
            bad.append((i, ln, "A 只给末段加引号 ⇒ 解析后属性名带引号 ⇒ 静默失效"))
        elif " " in name or not name.isascii():
            bad.append((i, ln, "B 含空格/非 ASCII 却裸写 ⇒ 名字被拆碎 ⇒ 静默失效"))
    return bad


def zombie_config_tres(ch):
    """`TowerDefenseZombieConfig`。字段顺序 = 类声明顺序（防编辑器重排）。

    ⚠️ `name` 必须是内部键 `<Key>`（`TowerDefensePacketConfig.Create()` 拿它查
    `ResourceManager.TOWERDEFENSE_CHARCATERS`，插件也靠它认人）—— **不能写中文**。
    ⚠️ `armorData = null`（本包不带护具，照抄内置 DiscoFire/DancerFire）。
    ⚠️ `damagePointData` 指向内置同名资源的 DamagePointData 即可（那只是「打哪算哪」的
    伤害分派表，与外形无关），不复制进包。
    """
    return f"""[gd_resource type="Resource" script_class="TowerDefenseZombieConfig" format=3]

[ext_resource type="PackedScene" path="{BASE_ASH_SCENE}" id="1"]
[ext_resource type="Resource" path="{ch['damage_point_data']}" id="2"]
[ext_resource type="Script" path="{BASE_ZOMBIE_CONFIG_SCRIPT}" id="3"]

[resource]
script = ExtResource("3")
attack = {fmt_f(ch['attack'])}
weight = {ch['weight']}
wavePointCost = {ch['wave_point_cost']}
name = "{ch['key']}"
hitpointsNearDeath = {fmt_f(ch['hp_near_death'])}
hitpoints = {fmt_f(ch['hp_total'] - ch['hp_near_death'])}
damagePointData = ExtResource("2")
armorData = null
customData = null
ashScene = ExtResource("1")
homeWorld = {HOME_WORLD}
cost = {ch['cost']}
packetCooldown = {fmt_f(ch['packet_cooldown'])}
plantGridType = [-1]
maskFlags = {MASK_FLAGS}
unUseBuffFlags = {UNUSE_BUFF_FLAGS}
elementFlags = {ELEMENT_FLAGS}
metadata/_custom_type_script = "{BASE_ZOMBIE_CONFIG_SCRIPT}"
"""


def produce_definition_tres(ch):
    """`ProduceComponentDefinition` —— 脑光产出。

    ★ `produceType = "BrainSun"`：`ProduceComponent.ProduceAuthoritative` 的
      `case "BrainSun"` **无条件**产出脑光（不像 `case "Sun"` 要 `instance.hypnoses`）
      ⇒ 僵尸直接写 BrainSun，不需要靠 `OnHypnosisStateChanged` 切类型。
    ★ `sunOnceMax` 默认只有 **50**！`num`（250/150）大于它会被截断 ⇒ 必须一起提上去。
    ★ `markerPaths` 指向 Sprite 场景里**真实存在**的 `Marker2D`（`ProduceMarker`）。
    """
    path = PRODUCE_MARKER_PATH_TMPL.format(key=ch["key"])
    return f"""[gd_resource type="Resource" script_class="ProduceComponentDefinition" format=3]

[ext_resource type="Script" path="{BASE_PRODUCE_DEF_SCRIPT}" id="1"]

[resource]
script = ExtResource("1")
produceType = "{ch['produce_type']}"
produceInterval = {fmt_f(ch['produce_interval'])}
num = {ch['produce_num']}
sunOnceMax = {ch['produce_num']}
markerPaths = [NodePath("{path}")]
ComponentTypeId = "ProduceComponent"
DefinitionId = "mod.{MOD_ID}.component.produce.{ch['tag']}"
InstanceId = "character.produce"
WireIndex = 0
StateMachineDefinition = null
LegacyNodeNames = [&"ProduceComponent"]
"""


def fire_definition_tres(ch):
    """`FireComponentDefinition` —— 追踪火球（照抄植物《向日葵女王》的发射口径）。

    ★ `fireProjectileList` **6 条**（= 齐射数量），每条 `firePosId` 0..5 各指一个 `FireMarker{i}`；
      **不写** `fireNum` / `fireNumAtOnce` —— 见文件顶部「齐射的数据侧正解」那段注释。
    ★ `fireMethodFlags = 32` = `PROJECTILE_FIRE_METHOD_FLAG.TRACK`（追踪）。
    ★ `speed = -600.0`：僵尸基础场景三层 `Scale.X` 都是 +1 ⇒ 负值才是「向面朝方向」（向左）。
    ★ 不写 `spritePath` / `fireAnimeClips` / `isSpliceSprite`：本包的头是独立渲染的
      向日葵头，没有 `HeadFire` clip，写只会指向空节点；插件走 `Fire()`，与动画解耦。
    """
    key = ch["key"]
    marker_paths = ", ".join(
        'NodePath("%s")' % FIRE_MARKER_PATH_TMPL.format(key=key, idx=i)
        for i in range(ch["fire_num"]))

    subs = []
    for i, ang in enumerate(FIRE_DIR_SPREAD[:ch["fire_num"]]):
        subs.append(f"""[sub_resource type="Resource" id="Resource_fcfpc{i}"]
script = ExtResource("6")
firePosId = {i}
speed = {fmt_f(FIRE_SPEED)}
dir = {fmt_f(ang)}
projectileFlip = true
metadata/_custom_type_script = "{BASE_FIRE_CONFIG_SCRIPT}"
""")
    sub_txt = "\n".join(subs)
    list_txt = ", ".join(f'SubResource("Resource_fcfpc{i}")' for i in range(ch["fire_num"]))

    return f"""[gd_resource type="Resource" script_class="FireComponentDefinition" format=3]

[ext_resource type="Resource" path="{BASE_FIRE_STATE_MACHINE}" id="1"]
[ext_resource type="Script" path="{BASE_RAY_SCRIPT}" id="2"]
[ext_resource type="Script" path="{BASE_CREATEDATA_SCRIPT}" id="3"]
[ext_resource type="Script" path="{BASE_PROJ_SINGLE_SCRIPT}" id="4"]
[ext_resource type="Script" path="{BASE_CHECK_CONFIG_SCRIPT}" id="5"]
[ext_resource type="Script" path="{BASE_FIRE_CONFIG_SCRIPT}" id="6"]
[ext_resource type="Script" path="{BASE_FIRE_DEF_SCRIPT}" id="7"]

[sub_resource type="Resource" id="AabbRay2DResource_backward"]
script = ExtResource("2")
TargetPosition = Vector2(-2000, 0)

[sub_resource type="Resource" id="Resource_firepea"]
script = ExtResource("3")
projectileName = &"{FIRE_PROJECTILE_NAME}"
baseDamage = {fmt_f(FIRE_BASE_DAMAGE)}
collisionFlags = {FIRE_COLLISION_FLAGS}
fireMethodFlags = {FIRE_METHOD_FLAGS}

[sub_resource type="Resource" id="Resource_proj_single"]
script = ExtResource("4")
projectileData = SubResource("Resource_firepea")
metadata/_custom_type_script = "{BASE_PROJ_SINGLE_SCRIPT}"

[sub_resource type="Resource" id="Resource_fcchk"]
script = ExtResource("5")
projectile = SubResource("Resource_proj_single")
metadata/_custom_type_script = "{BASE_CHECK_CONFIG_SCRIPT}"

{sub_txt}
[resource]
script = ExtResource("7")
firePosMarkerPaths = [{marker_paths}]
checkRayResources = [SubResource("AabbRay2DResource_backward")]
fireInterval = {fmt_f(ch['fire_interval'])}
fireAudioName = "{FIRE_AUDIO}"
fireCheckList = [SubResource("Resource_fcchk")]
fireProjectileList = [{list_txt}]
ComponentTypeId = "FireComponent"
DefinitionId = "mod.{MOD_ID}.component.fire.{ch['tag']}"
InstanceId = "character.fire"
WireIndex = 0
StateMachineDefinition = ExtResource("1")
LegacyNodeNames = [&"FireComponent"]
"""


def component_set_tres(ch):
    """`CharacterComponentSet` —— 父集（内置同名僵尸的组件集）+ 追加新组件。

    ★ 父集带来的东西**全部保留**：
        · DiscoFire/DancerFire 组件集已含 `ChangeProjectile/FireOffset3Definition`
          （= 点燃子弹 + 灼烧判定，`InstanceId = "change_projectile"`）与 FogArea
        · 基场景 `TowerDefenseZombie.tscn` 的父集带来 `AttackComponentZombieDefinition`
          （`InstanceId = "character.attack.0"`、`attackType` 默认 `"Eat"` = 啃食）
      ⇒ 「拥有火焰迪斯科僵尸的全部特点」这句话在组件层面是**逐字继承**，不是重写。
    ★ 追加项的 `InstanceId` 用官方固定的接线键，插件按它取运行时组件：
        `character.fire`（插件不用，走数据） / `character.produce`
    """
    comps = []
    exts = []
    if ch["want_fire"]:
        exts.append(f'[ext_resource type="Resource" path="./{ch["key"]}FireComponentDefinition.tres" id="fire"]')
        comps.append('ExtResource("fire")')
    exts.append(f'[ext_resource type="Resource" path="./{ch["key"]}ProduceComponentDefinition.tres" id="produce"]')
    comps.append('ExtResource("produce")')
    comps_txt = ", ".join(comps)
    return ("[gd_resource type=\"Resource\" script_class=\"CharacterComponentSet\" format=3]\n\n"
            + "\n".join(exts) + "\n"
            + f'[ext_resource type="Resource" path="{ch["parent_set"]}" id="parent"]\n'
            + f'[ext_resource type="Script" path="{BASE_COMPONENT_SET_SCRIPT}" id="script"]\n\n'
            + "[resource]\n"
            + 'script = ExtResource("script")\n'
            + 'ParentSet = ExtResource("parent")\n'
            + f"Components = [{comps_txt}]\n")


def zombie_scene_tscn(ch):
    """`Scene/<Key>.tscn`（6 段硬约束）。

    节点树逐字复刻内置 `TowerDefenseZombieDiscoFire.tscn` / `…DancerFire.tscn`，
    只把名字换成本包 `<Key>`、Sprite 指向包内副本、`ComponentSet` 指向包内那份。

    ★★ **必须显式声明 `ComponentSet` 且在 `script` 之前** —— 基场景
      `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn` 自带一个 ComponentSet
      （那份里没有 Fire/Produce），不覆盖 ⇒ 组件根本不会被创建，**零日志**。
    ★ 女王把 `dancerPacketName` 覆写成 `{DANCER_KEY}` ⇒ 召唤出的就是本包的舞者。
    ★ `DamagePartSlot/*`（女王）与 `damagePartSlot = {}`（舞者）是两套**不同**的字段名，
      照抄各自内置场景，别统一。
    """
    hide = "\n".join(f"{_prop('Animation/LayerVisible/' + n)} = false"
                     for n in ch["hide_head_layers"])
    z = ch["key"]
    base = f"SpriteGroup/TransformPoint/{z}"

    if ch["use_spotlight"]:
        exts = f"""[ext_resource type="Texture2D" path="res://Asset/Texture/Character/Effect/Spotlight2.png" id="spot2"]
[ext_resource type="Texture2D" path="res://Asset/Texture/Character/Effect/Spotlight.png" id="spot1"]
[sub_resource type="Gradient" id="Gradient_spot"]
offsets = PackedFloat32Array(0, 0.173077, 0.331731, 0.507212, 0.65625, 0.824519, 1)
colors = PackedColorArray(1, 0, 0, 1, 0.8, 1, 0, 1, 0.15, 1, 0.1925, 1, 0.33, 1, 0.609167, 1, 0.51, 1, 0.665167, 1, 0.69, 1, 0.932833, 1, 1, 1, 1, 1)"""
        extra_head = (f'spotlightGrandient = SubResource("Gradient_spot")\n'
                      f'walkSpeedScale = 2.0\ndancerPacketName = "{ch["dancer_packet"]}"\n'
                      if ch["dancer_packet"] else '')
        garlic = f'garlicReplace = "{ch["garlic_replace"]}"\n' if ch["garlic_replace"] else ''
        damage = f'''damagePart = {{
"Arm": ExtResource("dmgarm"),
"Head": ExtResource("dmghead")
}}
PreviewDamagePointPersontage = 1.0
DamagePartSlot/Arm = NodePath("{base}/ArmSlot")
DamagePartSlot/Head = NodePath("{base}/HeadSlot")'''
        extra_nodes = f"""
[node name="Spotlight2" type="Sprite2D" parent="BackEffectNode" index="0"]
unique_name_in_owner = true
visible = false
position = Vector2(14, 33)
scale = Vector2(3.5, 3.5)
texture = ExtResource("spot2")
"""
        tail_nodes = f"""
[node name="Spotlight" type="Sprite2D" parent="FrontEffectNode" index="0"]
unique_name_in_owner = true
visible = false
position = Vector2(17, -200)
scale = Vector2(3.5, 3.5)
texture = ExtResource("spot1")
"""
    else:
        exts = ""
        extra_head = 'groan = ""\n'
        garlic = ''
        damage = f'''damagePart = {{
"Arm": ExtResource("dmgarm"),
"Head": ExtResource("dmghead")
}}
damagePartSlot = {{
"Arm": NodePath("{base}/ArmSlot"),
"Head": NodePath("{base}/HeadSlot")
}}'''
        extra_nodes = ""
        tail_nodes = ""

    return f"""[gd_scene format=3]

[ext_resource type="PackedScene" path="{BASE_ZOMBIE_SCENE}" id="base"]
[ext_resource type="Script" path="{ch['body_script']}" id="script"]
[ext_resource type="Resource" path="{HITBOX}" id="hitbox"]
[ext_resource type="Resource" path="{ch['state_machine']}" id="sm"]
[ext_resource type="Resource" path="../Config/{cfg_file(ch['key'])}" id="cfg"]
[ext_resource type="Resource" path="{ch['damage_arm']}" id="dmgarm"]
[ext_resource type="Resource" path="{ch['damage_head']}" id="dmghead"]
[ext_resource type="PackedScene" path="../Sprite/{ch['key']}.tscn" id="sprite"]
[ext_resource type="PackedScene" path="{BASE_WATER_LINE_SCENE}" id="water"]
[ext_resource type="Resource" path="./{ch['key']}ComponentSet.tres" id="compset"]
{exts}

[node name="{z}" node_paths=PackedStringArray("duckytobeSprite", "waterLineSprite", "sprite", "headSlot") instance=ExtResource("base")]
ComponentSet = ExtResource("compset")
script = ExtResource("script")
HitBoxDefinition = ExtResource("hitbox")
MainStateMachineDefinition = ExtResource("sm")
{extra_head}waterHeight = 25.0
idleAnimeClip = "{ch['idle_clip']}"
sleepAnimeClip = "{ch['sleep_clip']}"
duckytobeSprite = NodePath("{base}/ZombieDuckytube")
waterLineSprite = NodePath("SpriteGroup/TransformPoint/ZombieWaterLine")
{garlic}config = ExtResource("cfg")
sprite = NodePath("{base}")
headSlot = NodePath("{base}/HeadSlot")
{damage}
metadata/mod_resource_kind = "Character"
metadata/mod_display_name = "{ch['display']}"
metadata/mod_character_category = "Zombie"
metadata/mod_character_config_path = "../Config/{cfg_file(ch['key'])}"
metadata/mod_character_sprite_scene = "../Sprite/{ch['key']}.tscn"
{extra_nodes}
[node name="TransformPoint" parent="SpriteGroup" index="0"]
position = {ch['transform_pos']}

[node name="{z}" parent="SpriteGroup/TransformPoint" index="0" instance=ExtResource("sprite")]
position = {ch['body_pos']}
Animation/Clip = "{ch['body_clip']}"
{hide}

[node name="ZombieDuckytube" parent="{base}" index="0"]

[node name="HeadSlot" parent="{base}" index="1"]
drawLayerId = -2
position = {ch['head_slot_pos']}
{ch['head_slot_extra']}

[node name="ArmSlot" parent="{base}" index="2"]
position = {ch['arm_slot_pos']}
rotation = {ch['arm_slot_rot']}
scale = Vector2({ch['arm_slot_scale']}, {ch['arm_slot_scale']})
skew = 0.0

[node name="GroundSlot" parent="{base}" index="3"]
position = {ch['ground_slot_pos']}

[node name="ZombieWaterLine" parent="SpriteGroup/TransformPoint" index="1" instance=ExtResource("water")]
visible = false
position = {ch['water_line_pos']}
trueFrameRate = 180.0
{tail_nodes}
[editable path="{base}"]
"""


def sprite_scene_tscn(ch):
    """`Sprite/<Key>.tscn` —— 身体（内置同名精灵场景）+ **三节点换头** + 产出 Marker。

    ★★ 为什么必须「三节点」而不是直接给身体加一个头子精灵：
      `AdobeAnimateSprite.CollectOwnedChildBindings`（`:5385`）只看节点类型，
      `_Draw`（`:9534`）首行 `return` ⇒ **子精灵的切片一定被父批次代画、采样父那一张
      图集** ⇒ 跨 `.tres` 的子精灵 = 别的角色碎片拼贴，`forceLocalRender` 也救不了。
      修法（唯一可行）：
        `HeadShadow`  与身体同类精灵、`visible=false` + **全层 false** ⇒ 零切片，
                      只为吃 `UpdateChild()` 的每帧定位（位姿影子）
        `HeadHolder`  普通 `Node2D`（identity）——**打断「父代画」递归**的容器
        `Head`        `HeadHolder` 的子节点 = **给人看的那个头**，独立渲染
      两头 `scale` / `offset` / `offsetRotate` **逐字相同**，由插件每帧从影子抄位姿。
    ★ 层级用 `z_index`（全局排序键第一位是 `EffectiveZIndex`，沿父链累加）⇒
      可见头写正整数即压住身体，**对树序不敏感**。
    ★ 原版头层必须在身体上显式关掉（`hide_head_layers`），否则从新头底下透出来。
    ★ 姿态开关三行（`usePos`/`useRotate`/`rotation`）**一个都不写** ⇒ 默认跟随口径。
    """
    off = ch["head_offset"]
    sc = ch["head_scale"]
    vis_on = _layer_lines(ch["head_layers"], set(ch["head_on"]))
    vis_off = _layer_lines(ch["head_layers"], set())
    hide = "\n".join(f"{_prop('Animation/LayerVisible/' + n)} = false"
                     for n in ch["hide_head_layers"])
    fr = (f'trueFrameRate = {fmt_f(ch["head_true_frame_rate"])}\n'
          if ch["head_true_frame_rate"] else "")
    # ★★ 第十四轮曾**冻结头自身动画**（`timeScale = 0.0`）；**第十五轮用户要求取消**
    #   ⇒ `HEAD_TIME_SCALE is None` 时这里渲染成**空串** ⇒ 两个头节点**都不写** `timeScale`
    #   ⇒ 引擎用默认 `1.0`，头的 `Idle`（眨眼 / 花瓣摆动）正常播放。
    #   ⚠️ `Aura` 从来就不写 —— 它复用同一份 `图层_3`（火焰漩涡 12 帧），本来就该转。
    #   ⚠️ `{ts}` 在模板里**保留**（渲染成空串），这样「要不要冻结」只由这一个常量决定。
    ts = ("" if HEAD_TIME_SCALE is None
          else "timeScale = {}\n".format(fmt_f(HEAD_TIME_SCALE)))
    mm = "useMultiMesh = true\n" if ch["head_use_multi_mesh"] else ""
    z = ch["key"]
    # 6 个火球生成点（`fire_num` 个），沿 y 铺开；插件每帧把每一个都摆到「炮口 + 本行偏移」。
    # ⚠️ 数量必须与 `fireProjectileList` 条数一致 —— `CreateProjectile(firePosId)` 按下标取，
    #    少一个就会有配置取不到 marker ⇒ 那颗退回僵尸原点（而不是炮口）。
    fire_markers = "".join(
        f'\n[node name="{FIRE_MARKER_NAME_TMPL.format(idx=i)}" type="Marker2D" parent="."]'
        f'\nposition = Vector2(0, {(-40.0 + i * FIRE_MARKER_Y_STEP):.1f})'
        for i in range(ch["fire_num"] or 0)
    )
    # ★★ 2026-09-25 用户口径③：「3×3 光环的贴图…改为**身体底部**，而不是头部（推荐）」。
    #   即头 `.tres` 里的 `图层_3`（火焰漩涡 `6-0001..0012.png`，12 帧）不再跟着头摆，
    #   改成**贴在脚底**的独立精灵。
    #   · 复用**同一份**内置 `.tres`（`QueenSunFlower.tres`）⇒ 不新增 `ext_resource`
    #     （`headscript` / `headdata` 与头共用）⇒ `load_steps` 仍是 4。
    #   · 只开 `图层_3`，其余层全 false（`_layer_lines(QUEEN_HEAD_LAYERS, AURA_ON)`）。
    #   · 该 `.tres` 只有 **一个 clip** `"Idle" = Vector2i(0, 23)`（已核）⇒ 直接用 `HEAD_CLIP`。
    #   · `AdobeAnimateSprite : Node2D` ⇒ 节点类型写 `Node2D` 是对的（与 `Head` 同款）。
    # ⚠️ 必须挂**普通 `Node2D`（`AuraHolder`）**下面：直接挂身体精灵下会被**身体批次代画**
    #    ⇒ 采样身体那张图集 ⇒ 变成别的角色碎片（同铁律 16 的 `HeadHolder` 手法）。
    # ⚠️⚠️ **压在身体后面靠 `insertLayerId = 0`，不是靠 `z_index`**（2026-09-25 用户口径②实证）：
    #    `Aura` 是被**父精灵代画**的子精灵 ⇒ 自己的 `z_index` 不进排序键（详见 `AURA_INSERT_LAYER`
    #    上方那大段源码链）。真正生效的是父精灵给它的 `layerId` ⇒ 写进 `AdobeAnimateSortPath.LayerOrder`。
    #    `insertLayerId = 0` ⇒ `LayerOrder 0 < 身体可见层 1..29` ⇒ 严格画在身体之前 = 身体后面。
    #    ⚠️ 别把它写成 `-1`（那会回落**顶层** ⇒ 又跑到身体前面）；也别指望改 `z_index` 更负。
    #    `z_index = -1` 只留作「非托管渲染路径」的兜底。
    aura_block = ""
    if ch["tag"] == "queen":
        aura_vis = _layer_lines(ch["head_layers"], set(AURA_ON))
        aura_block = f"""
[node name="{AURA_HOLDER_NAME}" type="Node2D" parent="."]
position = {AURA_HOLDER_POS}

[node name="{AURA_NODE_NAME}" type="Node2D" parent="{AURA_HOLDER_NAME}"]
unique_name_in_owner = true
z_index = {AURA_Z_INDEX}
insertLayerId = {AURA_INSERT_LAYER}
scale = Vector2({AURA_SCALE:g}, {AURA_SCALE:g})
script = ExtResource("headscript")
flashAnimeData = ExtResource("headdata")
offset = Vector2({AURA_OFFSET[0]}, {AURA_OFFSET[1]})
offsetRotate = 0.0
useTween = false
skipLastFrame = false
Animation/Clip = "{HEAD_CLIP}"
{aura_vis}
"""
    return f"""[gd_scene load_steps=4 format=3]

[ext_resource type="PackedScene" path="{ch['body_sprite']}" id="body"]
[ext_resource type="Script" path="{ADOBE_SPRITE_BASE_SCRIPT}" id="headscript"]
[ext_resource type="Resource" path="{ch['head_tres']}" id="headdata"]

[node name="{z}Sprite" instance=ExtResource("body")]
Animation/Clip = "{ch['body_clip']}"
{hide}
metadata/mod_resource_kind = "CharacterSprite"
metadata/mod_preview_source = "内置{ch['display']}身体（{'火焰迪斯科僵尸' if ch['tag'] == 'queen' else '火焰舞者僵尸'}）+ 内置向日葵头"

[node name="HeadShadow" type="Node2D" parent="." node_paths=PackedStringArray("parentSprite")]
visible = false
scale = Vector2({-sc:g}, {sc:g})
script = ExtResource("headscript")
flashAnimeData = ExtResource("headdata")
{mm}offset = Vector2({off[0]}, {off[1]})
offsetRotate = 0.0
{fr}{ts}useTween = false
skipLastFrame = false
parentSprite = NodePath("..")
Animation/Clip = "{HEAD_CLIP}"
{vis_off}
Layer = {ch['head_follow_layer']}
insertLayerId = {ch['head_follow_layer']}
followParentSpriteLayerId = {ch['head_follow_layer']}

[node name="HeadHolder" type="Node2D" parent="."]

[node name="Head" type="Node2D" parent="HeadHolder"]
unique_name_in_owner = true
z_index = 1
scale = Vector2({-sc:g}, {sc:g})
script = ExtResource("headscript")
flashAnimeData = ExtResource("headdata")
{mm}offset = Vector2({off[0]}, {off[1]})
offsetRotate = 0.0
{fr}{ts}useTween = false
skipLastFrame = false
Animation/Clip = "{HEAD_CLIP}"
{vis_on}
metadata/mod_resource_kind = "CharacterSprite"

[node name="ProduceMarker" type="Marker2D" parent="."]
position = Vector2(0, -40)
{fire_markers}{aura_block}"""


def packet_tres(ch, config_rel):
    """僵尸卡片 `TowerDefensePacketConfig`。

    ⚠️ 硬闸门：`saveKey` == 注册键 == 卡片文件名去扩展 == `<Key>`；
       `characterConfig` 的 `name` 必须已注册；`unlockCheckList` 必须空表；`type = 6`。
    ⚠️ `name`/`describe`/`handbook*` 直接写中文（翻译表进不了运行时）。
    """
    clip = PACKET_ANIME_CLIP_QUEEN if ch["tag"] == "queen" else PACKET_ANIME_CLIP_DANCER
    return f"""[gd_resource type="Resource" script_class="TowerDefensePacketConfig" format=3]

[ext_resource type="Resource" path="{config_rel}" id="1"]
[ext_resource type="Script" path="{BASE_PACKET_SCRIPT}" id="2"]

[resource]
script = ExtResource("2")
saveKey = "{ch['key']}"
unlockCheckList = []
name = "{ch['display']}"
describe = "{ch['describe']}"
handbookDescribe = "{ch['handbook_desc']}"
handbookStory = "{ch['handbook_story']}"
packetAnimeClip = "{clip}"
packetAnimeOffset = {PACKET_ANIME_OFFSET}
packetAnimeScale = {PACKET_ANIME_SCALE}
characterConfig = ExtResource("1")
type = {PACKET_TYPE}
"""


# ---------------------------------------------------------------- mod.json

def build_manifest():
    """manifest 键序必须严格 == `XWModManifestSerializeHandler` 的顺序。

    `resources` 用 `sorted(key=lower)` 生成（= `SyncProject` 规范序），
    否则编辑器一打开工程就重写 `mod.json`。
    `provides` 里的每个 key 都必须真的被注册（Character/CharacterSprite 来自
    `Scene/Sprite/<Key>.tscn`，Packet 来自 `Resources/Cards/<文件名>`）—— 两个角色都要列。
    """
    res = [RUNTIME_ASSEMBLY]
    for ch in CHARS:
        k = ch["key"]
        res += [card_rel(k), pkg_cfg_rel(k), pkg_packet_rel(k),
                pkg_scene_rel(k), pkg_set_rel(k), pkg_produce_rel(k), pkg_sprite_rel(k)]
        if ch["want_fire"]:
            res.append(pkg_fire_rel(k))
    return {
        "schemaVersion": 2,
        "id": MOD_ID,
        "name": MOD_NAME,
        "version": "1.0.0",
        "author": "云漫行",
        "description": (DISPLAY_DESCRIPTION
                        + "（含托管运行时插件 Runtime/ModAssembly.dll）"),
        "dependencies": [],
        "conflicts": [],
        "provides": {
            "Character": sorted(c["key"] for c in CHARS),
            "CharacterSprite": sorted(c["key"] for c in CHARS),
            "Packet": sorted(c["key"] for c in CHARS),
        },
        "overrides": {},
        "scripts": [],
        "runtimeAssembly": RUNTIME_ASSEMBLY,
        "runtimeEntryType": RUNTIME_ENTRY_TYPE,
        "runtimeApiVersion": RUNTIME_API_VERSION,
        "runtimeAssemblyPolicy": RUNTIME_POLICY,
        "blueprints": [],
        "translations": [],
        "resources": sorted(res, key=lambda p: p.lower()),
    }


DISPLAY_DESCRIPTION = (
    "向日葵女王僵尸：3500 血 / 300 啃食；每 1.5 秒发射 6 颗追踪火球，"
    "周围 3×3 友方（含自身）免疫减速与冻结，每 0.5 秒对 3×3 内敌方造成 25 点灼烧；"
    "每 10 秒生产 250 脑光；点燃子弹、滑步，并召唤火焰向日葵舞者僵尸。"
    "火焰向日葵舞者僵尸：800 血，免疫减速与冻结，点燃子弹，每 15 秒生产 150 脑光。"
)


# ================================================================ 组装

PROJECT_FILE = f"{MOD_NAME}.pvzmodeproject"
PROJECT_DESC = f"新增僵尸「向日葵女王僵尸 + 火焰向日葵舞者僵尸」（数据 + 托管运行时插件）"

# `TowerDefenseZombieConfig` 的**类声明顺序**（生成器必须照这个序写出，
# 否则游戏侧编辑器一打开就按自己的序重排整份 `.tres`）。
CFG_KEY_ORDER = [
    "attack", "weight", "wavePointCost", "name", "hitpointsNearDeath", "hitpoints",
    "damagePointData", "armorData", "customData", "ashScene", "homeWorld", "cost",
    "packetCooldown", "plantGridType", "maskFlags", "unUseBuffFlags", "elementFlags",
]

# ================================================================ 金标（GOLD）
#
# ★★★ 铁律 20 ①：**断言必须与「实现用的常量」不同源**。
#   下面这一组是「**写死的字面量**」，只给 `self_check()` 比对用，
#   **绝不允许**在生产代码路径里引用（引用 = 改常量时断言跟着变 = 永远绿 = 假绿）。
#   `.cache/_neg_test_sunflower_queen.py` 就是靠篡改生产常量来验证这组金标真的会打红。
GOLD_QUEEN_HP = 3500.0
GOLD_QUEEN_HP_NEAR_DEATH = 350.0
GOLD_DANCER_HP = 800.0
GOLD_DANCER_HP_NEAR_DEATH = 80.0
GOLD_ATTACK = 300.0
GOLD_MASK_FLAGS = 9
GOLD_UNUSE_BUFF_FLAGS = 19
GOLD_ELEMENT_FLAGS = 2
GOLD_CFG_NAME_QUEEN = "ZombieSunFlowerQueen"
GOLD_CFG_NAME_DANCER = "ZombieFireSunFlowerBackup"
GOLD_PRODUCE_TYPE = "BrainSun"
GOLD_QUEEN_PRODUCE_INTERVAL = 10.0
GOLD_QUEEN_PRODUCE_NUM = 250
GOLD_DANCER_PRODUCE_INTERVAL = 15.0
GOLD_DANCER_PRODUCE_NUM = 150
GOLD_FIRE_INTERVAL = 1.5
GOLD_FIRE_NUM = 6
GOLD_FIRE_SPEED = -600.0
GOLD_FIRE_METHOD_FLAGS = 32
GOLD_FIRE_BASE_DAMAGE = 40.0
GOLD_FIRE_DIR_SPREAD = (-22.0, -13.0, -4.5, 4.5, 13.0, 22.0)
GOLD_PACKET_TYPE = 6
GOLD_ATTACK_TYPE = "Eat"
GOLD_QUEEN_HIDDEN_HEAD_LAYERS = (
    "anim_hair", "anim_hair1", "anim_hair2", "anim_hair3", "anim_hair4",
    "anim_head1", "anim_head2",
)
GOLD_DANCER_HIDDEN_HEAD_LAYERS = (
    "anim_hair", "anim_hair1", "anim_hair2", "anim_hair3", "anim_head1", "anim_head2",
)
GOLD_QUEEN_HEAD_ON = (
    "AnimeClips", "anim_idle", "blink", "图层_1", "图层_67 复制", "图层_69",
)
# ★★ 2026-09-25 换头/光环口径（**四轮追加收敛后的当前值**）：
#   ① 女王头 **×2.0 →（第十二轮再 ×1.2）→ ×2.4**（基准 0.45 → 0.9 → **1.08**）；
#      四轮收敛：3.5 → 3.0 → 2.5 → **2.0**，第十一轮上移 20.16px，第十二轮原地放大 1.2 倍。
#      末轮由用户**目标图**标定（`.cache/_sq_preview.py --sweep` 离线合成渲染量出，
#      参考图「头高/全身高」0.4925 /「头高/可见身体高」1.0000 ⇒ 2.10 倍正中，取整档 2.0）。
#      ⚠️ `A = rot_scale(θ,−s,+s)` 含节点 scale ⇒ 改 scale **必须重解 offset**
#      （旧 offset 配新 scale ⇒ 残差 50.06 / 40.05 / 30.04 / 20.03px）。
#   ①-b 女王头**再上移 20.16px**（第十一轮「头的位置往上一点，与示例图相同」）：
#      offset.y −27.7745 → **−50.1706**（x 不变；第十二轮重解后 **−46.9935**；第十三轮的 −58.1046 已回滚）。
#      量法 = 头块内的**刚性**黄块
#      （脸 / 王冠）跨两图比 y，得 +20.42 / +19.90 ⇒ 均值 +20.16（见生成器 docstring §三-c）。
#      ⚠️ 别用「头块中心」含火焰 ⇒ 只给 +15.90，会少调 4.3px。
#   ①-c 女王头**再放大到 2.4 倍**（第十二轮「头的模型改为**现在的 1.2 倍**」）：
#      scale 0.9 → **1.08**，offset **重解** (-64.8744, -50.1706) → **(-61.2078, -46.9935)**。
#      语义 = **以头块中心为轴原地放大**（落点中心 (-10.20, -55.26) 与 2.0 倍时**逐字相同**），
#      `screen_delta` 仍 (0, -20.1565) ⇒ 第十一轮的上移量原样保留、位置不动。
#      ⚠️ 第 3 次印证「改 scale 必重解 offset」：旧 offset 配 1.08 ⇒ 残差 **5.2397px**
#      （头块中心偏 (Δx +3.96, Δy −3.43)）。
#      第十三轮**再**重解（右移 12px）：offset → (-72.3189, -58.1046) —— ⛔**已回滚**（用户「回调到上一版」）。
#   ② 舞者头**右上各 18px**（屏幕空间 shift = `(+18, −18)`）；只重解 offset，scale 不动（1.0）。
#   ②-b 【⛔ 已回滚】**第十三轮（两个角色同批）**：「女王和舞者的头**往右上方移一点**」⇒ 当时
#      **同一增量、右上各 12px**：女王 shift `(0, -20.1565)` → (12, -32.1565)，
#      offset → (-72.3189, -58.1046)；舞者 shift `(18, -18)` → (30, -30)（累计），
#      offset → (-74.3657, -61.8703)。两者残差 0、`screen_delta` 逐字一致。
#      ⚠️ 「移一点」**没有参考图** ⇒ 量级由**口径**定：本仓先例 = 舞者 18px、第十一轮「往上一点」
#      实测 20.16px ⇒ 当时取 **12px**（偏保守）。详见生成器 docstring §三-c 末尾 ⚠️。
#      ⛔ 用户「**回调到上一版**」⇒ 已撤销：女王 `shift` 回 `(0, -20.1565)`、offset 回
#      **`(-61.2078, -46.9935)`**；舞者 `shift` 回 `(18, -18)`、offset 回 **`(-67.2827, -46.4485)`**。
#   ③ 「3×3 光环」贴图（`图层_3` = 火焰漩涡 `6-0001..0012.png`）从头挪到**脚底**；
#      **必须** `insertLayerId = 0` 才画在**身体后面**（自己的 `z_index` 被父代画吞掉）。
#   ④ 「披风」(`"1"` = `cloak00.png`) 从头移除（与 `cloak1`/`cloak1 复制` 同组）。
#   具体值全部由 `.cache/_sq_head_place.py` / `.cache/_sq_aura.py` 反解，残差 0。
# ★★ 第十四轮（「抬头段头/身衔接不自然」）：**换跟随层** + 重解 offset。
#    见文件头 §三-d。①/② 两栏 = `.cache/_j14_follow.py` / `_j14_pivot2.py` 的
#    `max|Δgap|` 与 2D 偏差（原版基线 3.79 / 2.95px、0）：
#      · 女王 L19 → **L28**（`anim_hair1`，θ≡0）  1D 16.26→**3.96**px  2D 6.68→**3.22**px
#      · 舞者 L15 → **L22**（`anim_hair1`）       1D  6.19→**2.58**px  2D 4.56→**3.09**px
#    offset 由 `.cache/_j14_final.py` 反解，**参考帧整头落点差 0px**（外观不变）。
# ★★ 第十六轮：女王头 **2.4 倍 → 2.0 倍**（`head_scale 1.08 → 0.9`）且**位置回调**到上一版
#    ⇒ offset 重解为 `(-83.7633, 27.496)`（`.cache/_j16_resize.py`，残差 0）。
GOLD_QUEEN_HEAD_SCALE = 0.9
GOLD_QUEEN_HEAD_OFFSET = (-83.7633, 27.496)
GOLD_DANCER_HEAD_SCALE = 1.0
GOLD_DANCER_HEAD_OFFSET = (-48.6837, -37.1999)
# ★★ 第十四轮：**跟随层**的独立金标（三个属性 `Layer`/`insertLayerId`/`followParentSpriteLayerId`
#    都由 `head_follow_layer` 渲染 ⇒ 断言比这里的裸 `int`，防「改实现常量 ⇒ 同源恒真」）。
GOLD_QUEEN_HEAD_FOLLOW_LAYER = 28
GOLD_DANCER_HEAD_FOLLOW_LAYER = 22
# ★★ 第十五轮：`GOLD_HEAD_TIME_SCALE` **已删除** —— 用户取消了「冻结头自播 Idle」，
#    两个头节点**不再写** `timeScale` ⇒ 没有「该写的值」可比 ⇒ 断言改为
#    「**不得出现** `timeScale`」（`_kv(...) is not None` 即打红）。见 `HEAD_TIME_SCALE` 上方。
# 这两层**必须留在** `QUEEN_HEAD_LAYERS` 里（`图层_3` 还要给光环用），但**不得**进 `head_on`。
GOLD_QUEEN_HEAD_ON_DROP = ("1", "图层_3")
# 「3×3 光环」节点（**仅女王**）：`AuraHolder` 普通 Node2D 打断父代画 + `Aura` 独立渲染。
GOLD_AURA_HOLDER_NAME = "AuraHolder"
GOLD_AURA_NODE_NAME = "Aura"
GOLD_AURA_ON = ("AnimeClips", "图层_3")
GOLD_AURA_HOLDER_POS = "Vector2(1.4, 54.6)"
GOLD_AURA_SCALE = 1.6
GOLD_AURA_OFFSET = (-39.5, -71.5)
GOLD_AURA_Z_INDEX = -1
# ★★★ 「光环画在身体后面」的**唯一**有效手段（`z_index` 对父代画的子精灵无效，见 `AURA_INSERT_LAYER`）：
#   0 ⇒ `LayerOrder 0` < 身体可见层 `1..29` ⇒ 严格在每片身体之前绘出 = **身体后面**。
GOLD_AURA_INSERT_LAYER = 0
GOLD_DANCER_HEAD_ON = (
    "AnimeClips", "anim_idle", "SunFlower_bottompetals", "SunFlower_toppetals",
    "SunFlower_leftpetal1", "SunFlower_leftpetal2", "SunFlower_leftpetal3",
    "SunFlower_leftpetal4", "SunFlower_leftpetal5", "SunFlower_leftpetal6",
    "SunFlower_leftpetal7", "SunFlower_leftpetal8",
    "SunFlower_rightpetal1", "SunFlower_rightpetal2", "SunFlower_rightpetal3",
    "SunFlower_rightpetal4", "SunFlower_rightpetal5", "SunFlower_rightpetal6",
    "SunFlower_rightpetal7", "SunFlower_rightpetal8", "SunFlower_rightpetal9",
)
# 端到端常量（生成用的那份，断言一律改用下面的 GOLD_* 或直接字面量）
STANDARD_DIR_COUNT = 72


def ensure_project_layout(project_dir):
    """建出游戏侧编辑器要求的 72 个标准子目录（幂等）。"""
    n = 0
    for d in STANDARD_DIRS:
        os.makedirs(os.path.join(project_dir, d.replace("/", os.sep)), exist_ok=True)
        n += 1
    return n


def build_project_file(existing=None):
    """`.pvzmodeproject`（编辑器工程文件）。

    ⚠️ 幂等要求：`LastModifiedDate` 必须「读回旧值」，不能写 now ——
       否则每次运行都会改字节，与其余生成器的字节幂等约定冲突。
       只有**首次创建**（无旧文件）才写当前时间。
    """
    now = datetime.now(TZ_CN)
    created = (existing or {}).get("CreatedDate") or net_datetime(now)
    modified = (existing or {}).get("LastModifiedDate") or net_datetime(now)
    obj = {
        "Name": MOD_NAME,
        "Version": "1.0.0",
        "Author": "云漫行",
        "Description": PROJECT_DESC,
        # ⚠️ 必须和编辑器自己写出的形态一致：**正斜杠 + 结尾斜杠**
        "ExportDirectory": MODS_DIR.replace("\\", "/") + "/",
        "GameDirectory": "",
        "CreatedDate": created,
        "LastModifiedDate": modified,
    }
    assert list(obj.keys()) == PROJECT_KEYS, "工程文件键序不符"
    return obj


def mirror_is_ours(dst, marker):
    """判断 `Mods/<工程名>/` 镜像目录是不是「我们生成的」（决定能不能动它）。

    · 目录不存在                → 是（这次直接建）
    · 带 marker（= 工程文件）    → 是
    · 空壳（只有目录、零文件）    → 是（上一次构建留下的骨架；无用户数据，可安全接管）
    · 其它                      → **不是**（用户自己的目录，绝不删/改）
    """
    if not os.path.isdir(dst):
        return True
    if os.path.isfile(os.path.join(dst, marker)):
        return True
    for _r, _dirs, files in os.walk(dst):
        if files:
            return False
    return True


def install_project_dir(src, dst, marker):
    """把工程目录增量镜像到 Mods/ 下。dst 里不放 .pmod，所以不污染 ScanMods(*.pmod)。"""
    if not mirror_is_ours(dst, marker):
        return "跳过（%s 已存在且不是本工程，未改动）" % dst
    wrote, removed = sync_tree(src, dst, marker)
    return "已镜像到 %s（写 %d / 删 %d）" % (dst, wrote, removed)


def merge_enabled_mods(mods_dir, mod_id):
    """把本 Mod 的 id 并进 `Mods/enabled_mods.json`，**保留别人的条目**。

    ⚠️ 只把「与本 Mod 的 id 只差大小写」的历史残留清掉（改名残留），
       其它 Mod 的 id 一律不动并原样保留（含前缀包含关系，如
       `sunflowerqueenzombie` 与别人的 id 不能互相误删）。
    """
    p = os.path.join(mods_dir, "enabled_mods.json")
    ids = []
    if os.path.isfile(p):
        try:
            v = read_json(p)
            if isinstance(v, list):
                ids = [x for x in v if isinstance(x, str)]
        except Exception:
            ids = []
    dropped = sorted({x for x in ids if x != mod_id and x.lower() == mod_id.lower()})
    if dropped:
        ids = [x for x in ids if x not in dropped]
    if mod_id not in ids:
        ids.append(mod_id)
    ids = sorted(set(x.strip() for x in ids if x.strip()), key=lambda s: s.lower())
    write_text(p, json.dumps(ids, ensure_ascii=False, indent=2), "\n")
    return ids, dropped


def merge_recent_project(project_file_abs):
    """把工程登记进编辑器「最近工程」缓存（`mod_editor_recent_projects.cfg`，与 `Mods/` 同级）。

    ⚠️ 三个必须守住的点（实测踩过，别改回去）：
      1. **不能丢别人的条目**：解析前必须先把 CRLF 归一化成 LF，
         否则 `^path_\\d+="(.*)"$` 一条都匹配不到，整个列表被重写成「只剩自己一条」。
      2. 路径一律写**正斜杠**；登记的是 **Mods 下**那份工程（编辑器只认那里）。
      3. 保留原文件的换行风格与末尾换行。
    """
    cfg = os.path.join(USER_DATA_DIR, "mod_editor_recent_projects.cfg")
    if not os.path.isfile(cfg):
        return None
    with open(cfg, "rb") as f:
        raw = f.read()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    text = raw.decode("utf-8-sig", "replace").replace("\r\n", "\n").replace("\r", "\n")
    trailing = text.endswith("\n")
    seen, paths = set(), []
    for p in re.findall(r'^path_\d+="(.*)"$', text, re.M):
        p = p.replace("\\", "/")
        if p.lower() not in seen:
            seen.add(p.lower())
            paths.append(p)
    want = os.path.abspath(project_file_abs).replace("\\", "/")
    if want.lower() in seen:
        return len(paths)
    paths.insert(0, want)
    body = "[projects]\n\ncount=%d\n" % len(paths)
    body += "".join('path_%d="%s"\n' % (i, p) for i, p in enumerate(paths))
    if not trailing:
        body = body[:-1]
    write_text(cfg, body, nl)
    return len(paths)


def collect_entries():
    """`.pmod` 的条目清单（`mod.json` 必须排第 0）。"""
    entries = []
    for root, dirs, files in os.walk(MOD_ROOT):
        dirs.sort()
        for f in sorted(files):
            full = os.path.join(root, f)
            rel = os.path.relpath(full, MOD_ROOT).replace("\\", "/")
            if rel.endswith((".uid", ".import")) or rel.endswith(".cs"):
                continue
            if rel.endswith(".pvzmodeproject"):
                continue
            if os.path.basename(rel).startswith("."):
                continue
            entries.append(rel)
    entries.sort(key=lambda r: (r != "mod.json", r))
    return entries


def package_pmod(out_path):
    """打 `.pmod`（zip）。**固定时间戳**保证字节幂等。"""
    entries = collect_entries()
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        for rel in entries:
            zi = zipfile.ZipInfo(rel, FIXED_T)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            full = os.path.join(MOD_ROOT, rel.replace("/", os.sep))
            if not os.path.isfile(full):
                continue
            with open(full, "rb") as f:
                z.writestr(zi, f.read())
    return entries


# ================================================================ 自检
#
# 铁律 20：断言必须「与实现不同源」。下面全部在**渲染出来的文本**上做结构判定，
# 不看生成器自己的中间变量；每一条都能被「篡改常量」的负向测试打红
# （见 .cache/_neg_test_sunflower_queen.py）。

def _num(text, key):
    """`key = <数字>` 的浮点值。"""
    m = re.search(r'^%s = (-?[0-9.]+)\s*$' % re.escape(key), text, re.M)
    return float(m.group(1)) if m else None


def _q(text, key):
    """`key = "…"` 的字符串值（支持值里含真实换行）。"""
    m = re.search(r'^%s = "(.*?)"\n' % re.escape(key), text, re.M | re.S)
    return None if m is None else m.group(1)


def _node_block(text, name):
    m = re.search(r'\[node name="%s"[^\]]*\]\n(.*?)(?=\n\[node |\n\[editable|\Z)'
                  % re.escape(name), text, re.S)
    return m.group(1) if m else ""


def _kv(block, key):
    m = re.search(r'^%s = (.*)$' % re.escape(key), block, re.M)
    return m.group(1).strip() if m else None


# 跨语言常量（C# 源码里的字面量口径；`name` 是 `SunFlowerQueenRuntimeEntry.cs`
# 里的标识符片段，`lit` 是它右边**逐字**的字面量）。
PLUGIN_SRC_EXPECT = [
    ("FireNum", "6"),
    ("FireInterval", "1.5f"),
    ("BurnInterval", "0.5f"),
    ("BurnDamage", "25.0f"),
    ("GridSpan", "3.0f"),
    ("ImmuneFlags", "3"),
]

RES_SCRIPT_RE = re.compile(r'\[ext_resource type="Script" path="([^"]+)"')
PATH_RE = re.compile(r'path="([^"]+)"')
RES_PATH_WHITELIST = ("res://Prefab/", "res://Asset/", "res://Script/", "res://Resource/",
                      "res://Registry/", "res://Extends/", "res://addons/")
BANNED_TOKENS = ['[sub_resource type="GDScript"', '[sub_resource type="CSharpScript"',
                 "unique_id", "parent_id_path", "CompanionOnly", "\nuid="]


def self_check():
    fails = []
    B = {}
    for ch in CHARS:
        k = ch["key"]
        B[ch["tag"]] = {
            "cfg": zombie_config_tres(ch),
            "produce": produce_definition_tres(ch),
            "fire": fire_definition_tres(ch) if ch["want_fire"] else "",
            "comp": component_set_tres(ch),
            "scene": zombie_scene_tscn(ch),
            "sprite": sprite_scene_tscn(ch),
            "card": packet_tres(ch, f"../Characters/{PKG_CAT}/{k}/Config/{cfg_file(k)}"),
            "pkgcard": packet_tres(ch, f"../Config/{cfg_file(k)}"),
        }

    # 1. 路径硬约束：恰 6 段 / 类别必须是 Zombies / 文件名 == 目录名 == <Key>
    for ch in CHARS:
        k = ch["key"]
        for rel in (pkg_scene_rel(k), pkg_sprite_rel(k)):
            segs = rel.split("/")
            if len(segs) != 6:
                fails.append(f"[路径] {rel} 应为 6 段，实为 {len(segs)} 段")
                continue
            if segs[:3] != ["Resources", "Characters", PKG_CAT]:
                fails.append(f"[路径] {rel} 前缀必须 Resources/Characters/{PKG_CAT}")
            if segs[3] != k or segs[4] not in ("Scene", "Sprite") or segs[5] != f"{k}.tscn":
                fails.append(f"[路径] {rel} 的 Key / 子目录 / 文件名不匹配")

    # 2. 包内自引用一律相对：出现 `res://…/Resources/Characters/…` 即违规
    for ch in CHARS:
        for name, body in sorted(B[ch["tag"]].items()):
            for path in PATH_RE.findall(body):
                if path.startswith("res://") and not path.startswith(RES_PATH_WHITELIST):
                    fails.append(f"[自引用] {ch['key']}/{name} 越界 res://：{path}")
                if path.startswith("res://") and "/Resources/Characters/" in path:
                    fails.append(f"[自引用] {ch['key']}/{name} 包内资源写成了 res://：{path}")

    # 3. `.tres` 的 Script 引用必须 res://（唯一允许 res:// 的自引用例外）
    for ch in CHARS:
        for name, body in sorted(B[ch["tag"]].items()):
            for p in RES_SCRIPT_RE.findall(body):
                if not p.startswith("res://"):
                    fails.append(f"[Script] {ch['key']}/{name} 的 Script 必须 res://：{p}")

    # 4. 禁内嵌脚本 / 禁 Godot 4.7 可选字段 / 禁 CompanionOnly / 禁 uid
    for ch in CHARS:
        for name, body in sorted(B[ch["tag"]].items()):
            for bad in BANNED_TOKENS:
                if bad in body:
                    fails.append(f"[禁用项] {ch['key']}/{name} 含 {bad.strip()!r}")

    # 5. 数值（用户口径）—— 总血 = hitpoints + hitpointsNearDeath
    #    ⚠️ 一律比 **GOLD_***（金标字面量），不比生成用的常量（那是「同源 = 恒真」= 假绿）。
    for ch, want_hp, want_nd, want_name in (
            (BY_TAG["queen"], GOLD_QUEEN_HP, GOLD_QUEEN_HP_NEAR_DEATH, GOLD_CFG_NAME_QUEEN),
            (BY_TAG["dancer"], GOLD_DANCER_HP, GOLD_DANCER_HP_NEAR_DEATH, GOLD_CFG_NAME_DANCER)):
        cfg = B[ch["tag"]]["cfg"]
        hp = _num(cfg, "hitpoints") or 0.0
        nd = _num(cfg, "hitpointsNearDeath") or 0.0
        if abs(hp + nd - want_hp) > 1e-6:
            fails.append(f"[数值] {ch['key']} 总血应为 {want_hp:g}，实为 {hp + nd:g}（{hp:g}+{nd:g}）")
        if abs(nd - want_nd) > 1e-6:
            fails.append(f"[数值] {ch['key']} hitpointsNearDeath 应为 {want_nd:g}，实为 {nd:g}")
        if abs((_num(cfg, "attack") or 0.0) - GOLD_ATTACK) > 1e-6:
            fails.append(f"[数值] {ch['key']} 啃食伤害应为 {GOLD_ATTACK:g}，实为 {_num(cfg, 'attack')}")
        if _q(cfg, "name") != want_name:
            fails.append(f"[数值] {ch['key']} 的 config.name 应为 {want_name!r}"
                         f"（== 内部注册键），实为 {_q(cfg, 'name')!r}")
        if "armorData = null" not in cfg:
            fails.append(f"[数值] {ch['key']} armorData 应为 null（本包不带护具）")
        if _num(cfg, "unUseBuffFlags") != GOLD_UNUSE_BUFF_FLAGS:
            fails.append(f"[数值] {ch['key']} unUseBuffFlags 应为 {GOLD_UNUSE_BUFF_FLAGS}"
                         f"（bit0 减速 + bit1 冻结 + bit4 RedHeat），实为 "
                         f"{_num(cfg, 'unUseBuffFlags')}")
        if _num(cfg, "maskFlags") != GOLD_MASK_FLAGS:
            fails.append(f"[数值] {ch['key']} maskFlags 应为 {GOLD_MASK_FLAGS}，实为 "
                         f"{_num(cfg, 'maskFlags')}")
        if _num(cfg, "elementFlags") != GOLD_ELEMENT_FLAGS:
            fails.append(f"[数值] {ch['key']} elementFlags 应为 {GOLD_ELEMENT_FLAGS}（火）")
        # 攻击类型「啃食」：本包不改 attackType ⇒ 逐字继承基组件集的默认值，这里金标复核
        if GOLD_ATTACK_TYPE != "Eat":
            fails.append("[数值] GOLD_ATTACK_TYPE 金标本身应当写 Eat")
        if 'attackType = "Eat"' in cfg:
            fails.append(f"[数值] {ch['key']} config 里不应出现 attackType（那是组件字段，不是 config 字段）")

    # 6. config 字段顺序（防编辑器重排）
    for ch in CHARS:
        body = B[ch["tag"]]["cfg"].split("[resource]\n", 1)[-1]
        keys = re.findall(r'^([A-Za-z_][A-Za-z0-9_]*) = ', body, re.M)
        # `script` 是 `[resource]` 段固定首行，不算配置字段
        keys = [k for k in keys if k != "script" and not k.startswith("metadata")]
        if keys != CFG_KEY_ORDER:
            fails.append(f"[字段序] {ch['key']} config 键序不符：{keys}")

    # 7. 组件：产出 / 发射 / NodePath / InstanceId
    for ch in CHARS:
        k, b = ch["key"], B[ch["tag"]]
        if 'InstanceId = "character.produce"' not in b["produce"]:
            fails.append(f"[组件] {k} Produce 的 InstanceId 必须是 character.produce")
        want_iv, want_num = (GOLD_QUEEN_PRODUCE_INTERVAL, GOLD_QUEEN_PRODUCE_NUM) \
            if ch["tag"] == "queen" else (GOLD_DANCER_PRODUCE_INTERVAL, GOLD_DANCER_PRODUCE_NUM)
        if f'produceType = "{GOLD_PRODUCE_TYPE}"' not in b["produce"]:
            fails.append(f"[组件] {k} produceType 应为 {GOLD_PRODUCE_TYPE}，实为 "
                         f"{_q(b['produce'], 'produceType')!r}")
        if _num(b["produce"], "produceInterval") != want_iv:
            fails.append(f"[组件] {k} produceInterval 应为 {want_iv:g}，实为 "
                         f"{_num(b['produce'], 'produceInterval')}")
        if _num(b["produce"], "num") != want_num:
            fails.append(f"[组件] {k} num 应为 {want_num}，实为 {_num(b['produce'], 'num')}")
        if (_num(b["produce"], "sunOnceMax") or 0) < want_num:
            fails.append(f"[组件] {k} sunOnceMax 必须 >= num（{want_num}），否则脑光被静默截断"
                         f"（实为 {_num(b['produce'], 'sunOnceMax')}）")
        marker = f'NodePath("{PRODUCE_MARKER_PATH_TMPL.format(key=k)}")'
        if marker not in b["produce"]:
            fails.append(f"[组件] {k} Produce.markerPaths 必须指向包内 ProduceMarker")
        if f'[node name="{PRODUCE_MARKER_NAME}" type="Marker2D" parent="."]' not in b["sprite"]:
            fails.append(f"[组件] {k} Sprite 场景里没有 ProduceMarker 节点")
        card_ref = f'../Characters/{PKG_CAT}/{k}/Config/{cfg_file(k)}'
        if f'[ext_resource type="Resource" path="{card_ref}" id="1"]' not in b["card"]:
            fails.append(f"[组件] {k} 注册卡片的 characterConfig 必须指向 {card_ref}")
        if f'[ext_resource type="Resource" path="../Config/{cfg_file(k)}" id="1"]' not in b["pkgcard"]:
            fails.append(f"[组件] {k} 包内卡片的 characterConfig 必须指向 ../Config/")
        if ch["want_fire"]:
            n = GOLD_FIRE_NUM
            if 'InstanceId = "character.fire"' not in b["fire"]:
                fails.append(f"[组件] {k} Fire 的 InstanceId 必须是 character.fire")
            if _num(b["fire"], "fireInterval") != GOLD_FIRE_INTERVAL:
                fails.append(f"[组件] {k} fireInterval 应为 {GOLD_FIRE_INTERVAL:g}，实为 "
                             f"{_num(b['fire'], 'fireInterval')}")
            if _num(b["fire"], "speed") != GOLD_FIRE_SPEED:
                fails.append(f"[组件] {k} 火球 speed 应为 {GOLD_FIRE_SPEED:g}（负 = 向面朝方向），"
                             f"实为 {_num(b['fire'], 'speed')}")
            if _num(b["fire"], "fireMethodFlags") != GOLD_FIRE_METHOD_FLAGS:
                fails.append(f"[组件] {k} fireMethodFlags 应为 {GOLD_FIRE_METHOD_FLAGS}"
                             f"（TRACK 追踪），实为 {_num(b['fire'], 'fireMethodFlags')}")
            if _num(b["fire"], "baseDamage") != GOLD_FIRE_BASE_DAMAGE:
                fails.append(f"[组件] {k} 火球 baseDamage 应为 {GOLD_FIRE_BASE_DAMAGE:g}，实为 "
                             f"{_num(b['fire'], 'baseDamage')}")
            # ★★ 齐射 = N 条配置 + N 个 Marker（`CreateProjectile(firePosId)` 按下标取）
            want_paths = ", ".join(
                'NodePath("%s")' % FIRE_MARKER_PATH_TMPL.format(key=k, idx=i)
                for i in range(n))
            if f"firePosMarkerPaths = [{want_paths}]" not in b["fire"]:
                fails.append(f"[齐射] {k} firePosMarkerPaths 应是 {n} 个 FireMarker0..{n - 1}")
            ids = [int(x) for x in re.findall(r'^firePosId = (\d+)$', b["fire"], re.M)]
            if ids != list(range(n)):
                fails.append(f"[齐射] {k} firePosId 必须恰好是 0..{n - 1}，实为 {ids}")
            if len(re.findall(r'^fireProjectileList = \[', b["fire"], re.M)) != 1:
                fails.append(f"[齐射] {k} 应只有一行 fireProjectileList 声明")
            if b["fire"].count('SubResource("Resource_fcfpc') != n:
                fails.append(f"[齐射] {k} fireProjectileList 应恰好 {n} 条，实为 "
                             f"{b['fire'].count('SubResource(\\"Resource_fcfpc')}")
            for gate in ("fireNum", "fireNumAtOnce"):
                if re.search(r'^%s = ' % gate, b["fire"], re.M):
                    fails.append(f"[齐射] {k} 不得写 {gate}"
                                 f"（配 {n} 条配置会被 FireConfiguredVolley 循环成 {n * n} 颗）")
            for i in range(n):
                if f'[node name="{FIRE_MARKER_NAME_TMPL.format(idx=i)}" type="Marker2D" parent="."]' \
                        not in b["sprite"]:
                    fails.append(f"[齐射] {k} Sprite 场景缺 FireMarker{i}")
            dirs = [float(x) for x in re.findall(r'^dir = (-?[0-9.]+)$', b["fire"], re.M)]
            if dirs != list(GOLD_FIRE_DIR_SPREAD[:n]):
                fails.append(f"[齐射] {k} dir 扇形不符口径：{dirs}（应为 {list(GOLD_FIRE_DIR_SPREAD[:n])}）")
        else:
            # ⚠️ 不能只看 `"FireComponent" in comp` —— 舞者的 ParentSet 路径本身就含
            #    `TowerDefenseZombieDancerFireComponentSet.tres`（会假警报）。
            #    只看**本包追加的**那份 Fire 定义有没有被引到。
            if f"{k}FireComponentDefinition.tres" in b["comp"]:
                fails.append(f"[组件] {k} 不该带 Fire 组件（需求只要求点燃子弹）")
            if b["sprite"].count('name="FireMarker') != 0:
                fails.append(f"[齐射] {k} 没有 Fire 组件，不该有 FireMarker 节点")

    # 8. 卡片闸门 + 文案口径
    for ch in CHARS:
        for which in ("card", "pkgcard"):
            pk = B[ch["tag"]][which]
            tag = f"{ch['key']}/{which}"
            if f"saveKey = \"{ch['key']}\"" not in pk:
                fails.append(f"[卡片] {tag} saveKey 必须 == 注册键")
            if "unlockCheckList = []" not in pk:
                fails.append(f"[卡片] {tag} unlockCheckList 必须为空表")
            if f"type = {GOLD_PACKET_TYPE}" not in pk:
                fails.append(f"[卡片] {tag} type 必须 {GOLD_PACKET_TYPE}（ZOMBIE）")
            if f'name = "{ch["display"]}"' not in pk:
                fails.append(f"[卡片] {tag} name 必须是内联中文「{ch['display']}」")
            if 'describe = "[color=' in pk:
                fails.append(f"[卡片] {tag} describe 不得自带颜色（面板自己包 [color=2f375e]）")
            # 数值块：每行「头词裸文本 + [color=cc241d]…[/color]」且括号成对
            hb = _q(pk, "handbookDescribe") or ""
            lines = hb.split("\n")
            if len(lines) < 3:
                fails.append(f"[卡片] {tag} handbookDescribe 至少 3 行，实为 {len(lines)}")
            for ln in lines:
                if ln.count("[color=cc241d]") < 1 or ln.count("[color=cc241d]") != ln.count("[/color]"):
                    fails.append(f"[卡片] {tag} handbookDescribe 行格式不符：{ln}")
            st = _q(pk, "handbookStory") or ""
            if not st.strip():
                fails.append(f"[卡片] {tag} handbookStory 不能为空")
            elif st.lstrip().startswith("["):
                fails.append(f"[卡片] {tag} handbookStory 不应以颜色标签开头")

    # 9. manifest
    mf = build_manifest()
    if list(mf.keys()) != MANIFEST_KEYS:
        fails.append(f"[manifest] 键序不符：{list(mf.keys())}")
    if mf.get("runtimeAssembly") != RUNTIME_ASSEMBLY:
        fails.append("[manifest] runtimeAssembly 只能是字面量 Runtime/ModAssembly.dll")
    if mf.get("runtimeEntryType") != RUNTIME_ENTRY_TYPE:
        fails.append(f"[manifest] runtimeEntryType 应为 {RUNTIME_ENTRY_TYPE}")
    if mf.get("runtimeApiVersion") != 1:
        fails.append("[manifest] runtimeApiVersion 必须恰好 1")
    if mf.get("translations") != []:
        fails.append("[manifest] translations 必须为空（翻译表进不了运行时，文案已内联）")
    if mf["resources"] != sorted(mf["resources"], key=lambda p: p.lower()):
        fails.append("[manifest] resources 必须按 key=lower 排序（SyncProject 规范序）")
    for key, vs in sorted(mf["provides"].items()):
        if len(vs) != len(CHARS):
            fails.append(f"[manifest] provides[{key}] 应列出 {len(CHARS)} 个角色，实为 {len(vs)}")
        if vs != sorted(vs):
            fails.append(f"[manifest] provides[{key}] 未排序：{vs}")
    want_res = set()
    for ch in CHARS:
        k = ch["key"]
        want_res |= {card_rel(k), pkg_cfg_rel(k), pkg_packet_rel(k), pkg_scene_rel(k),
                     pkg_set_rel(k), pkg_produce_rel(k), pkg_sprite_rel(k)}
        if ch["want_fire"]:
            want_res.add(pkg_fire_rel(k))
    got_res = set(mf["resources"]) - {RUNTIME_ASSEMBLY}
    if got_res != want_res:
        fails.append(f"[manifest] resources 与应产出集合不一致："
                     f"多 {sorted(got_res - want_res)} 缺 {sorted(want_res - got_res)}")
    ids = [c["key"] for c in CHARS]
    for key in ("Character", "CharacterSprite", "Packet"):
        if mf["provides"][key] != sorted(ids):
            fails.append(f"[manifest] provides[{key}] 应为 {sorted(ids)}")

    # 10. 标准目录表
    if len(STANDARD_DIRS) != STANDARD_DIR_COUNT:
        fails.append(f"[目录] STANDARD_DIRS 应为 {STANDARD_DIR_COUNT} 项，实为 {len(STANDARD_DIRS)}")
    if len(set(STANDARD_DIRS)) != len(STANDARD_DIRS):
        dup = sorted({d for d in STANDARD_DIRS if STANDARD_DIRS.count(d) > 1})
        fails.append(f"[目录] STANDARD_DIRS 有重复项：{dup}")

    # 11. 三节点换头（影子与可见头必须逐字同参；姿态开关一个都不许写）
    for ch in CHARS:
        k = ch["key"]
        sp = B[ch["tag"]]["sprite"]
        sc = B[ch["tag"]]["scene"]
        sh = _node_block(sp, "HeadShadow")
        hd = _node_block(sp, "Head")
        if not sh:
            fails.append(f"[换头] {k} Sprite 缺 HeadShadow 节点")
        if not hd:
            fails.append(f"[换头] {k} Sprite 缺 Head 节点")
        if not re.search(r'^\[node name="HeadHolder"[^\]]*\]', sp, re.M):
            fails.append(f"[换头] {k} Sprite 缺 HeadHolder 容器（打断父代画）")
        for field in ("scale", "offset", "offsetRotate"):
            a, b_ = _kv(sh, field), _kv(hd, field)
            if a is None or b_ is None or a != b_:
                fails.append(f"[换头] {k} 影子与头的 {field} 必须逐字相同：{a!r} vs {b_!r}")
        # ⚠️ 用 `_kv` **精确比**，别写子串 `"z_index = 1" in hd`（那是 `z_index = 10` 的前缀）
        if _kv(hd, "z_index") != "1":
            fails.append(f"[换头] {k} 可见头必须写 z_index = 1（压住身体），"
                         f"实为 {_kv(hd, 'z_index')!r}")
        if _kv(sh, "visible") != "false":
            fails.append(f"[换头] {k} 影子必须 visible = false，实为 {_kv(sh, 'visible')!r}")
        for gate in ("usePos", "useRotate"):
            if gate in hd:
                fails.append(f"[换头] {k} 的头不得写 {gate}（回退口径：两开关默认 true）")
        if re.search(r'^rotation = ', hd, re.M):
            fails.append(f"[换头] {k} 的头不得写 rotation")
        # ---- ★★ 第十五轮：用户「**取消头自播的 Idle 冻结**」⇒ 两个头节点**不得**写
        #      `timeScale`（第十四轮曾写 `0.0` 去冻结头自身的 `Idle`，用于修「抬头段衔接」）。
        #      ⇒ 断言方向从「必须等于金标」**翻转**为「**不得出现**」：谁再加回来都会打红。
        #      ⚠️ 用 `_kv(...) is not None` 判「有没有写」（此时没有「该写的值」可比）。
        for nm, blk in (("影子 HeadShadow", sh), ("可见头 Head", hd)):
            got_ts = _kv(blk, "timeScale")
            if got_ts is not None:
                fails.append(f"[换头] {k} {nm} 不得写 timeScale（第十五轮已取消 Idle 冻结，"
                             f"头自播动画应正常播放），实为 {got_ts!r}")
        # ⚠️ 也别改走 `pause`（另一种「冻结」写法）：`ApplyRuntimeParentState`
        #    （`AdobeAnimateSprite.cs:5475-5478`）会把 `pause = parent._pause` 覆写 ⇒
        #    影子（父=身体精灵）与可见头（父=普通 Node2D `HeadHolder`）行为不一致。
        for nm, blk in (("影子 HeadShadow", sh), ("可见头 Head", hd)):
            if re.search(r'^pause = ', blk, re.M):
                fails.append(f"[换头] {k} {nm} 不得写 pause（会被父状态覆写；"
                             f"本轮口径是**不写**任何冻结旋钮）")
        # ---- 可见头的 scale / offset 必须**等于金标**（不比 dict，防「改了 dict 但金标同源」）
        gold_sc = GOLD_QUEEN_HEAD_SCALE if ch["tag"] == "queen" else GOLD_DANCER_HEAD_SCALE
        gold_off = GOLD_QUEEN_HEAD_OFFSET if ch["tag"] == "queen" else GOLD_DANCER_HEAD_OFFSET
        want_scale = "Vector2(%g, %g)" % (-gold_sc, gold_sc)
        want_off = "Vector2(%g, %g)" % gold_off
        if _kv(hd, "scale") != want_scale:
            fails.append(f"[换头] {k} 可见头 scale 应为 {want_scale}（金标），"
                         f"实为 {_kv(hd, 'scale')!r}")
        if _kv(hd, "offset") != want_off:
            fails.append(f"[换头] {k} 可见头 offset 应为 {want_off}（金标），"
                         f"实为 {_kv(hd, 'offset')!r}")
        # ---- ★★ 第十四轮：「跟随层」三个属性必须 = 独立金标（换层修抬头段接缝）----
        gold_follow = (GOLD_QUEEN_HEAD_FOLLOW_LAYER if ch["tag"] == "queen"
                       else GOLD_DANCER_HEAD_FOLLOW_LAYER)
        for prop in ("Layer", "insertLayerId", "followParentSpriteLayerId"):
            got = _kv(sh, prop)
            if got != str(gold_follow):
                fails.append(f"[换头] {k} 影子 HeadShadow 的 {prop} 必须 = {gold_follow}"
                             f"（跟随层金标，修抬头段接缝；见 §三-d），实为 {got!r}")
        # ⚠️ 可见头 `Head` **不得**写这三个属性：它由插件每帧从影子抄位姿
        #    （`SunFlowerQueenRuntimeEntry.SyncHeadPairs`），自己再跟一层会变成两套来源。
        for prop in ("Layer", "insertLayerId", "followParentSpriteLayerId"):
            if _kv(hd, prop) is not None:
                fails.append(f"[换头] {k} 可见头 Head 不得写 {prop}"
                             f"（位姿由插件从影子同步，勿双来源）")
        gold_on = set(GOLD_QUEEN_HEAD_ON if ch["tag"] == "queen" else GOLD_DANCER_HEAD_ON)
        gold_hide = (GOLD_QUEEN_HIDDEN_HEAD_LAYERS if ch["tag"] == "queen"
                     else GOLD_DANCER_HIDDEN_HEAD_LAYERS)
        stray = sorted(gold_on - set(ch["head_layers"]))
        if stray:
            fails.append(f"[换头] {k} 金标 head_on 里有该头不具备的层：{stray}")
        for ln in ch["head_layers"]:
            pat = r'^%s = (\w+)' % re.escape(_prop("Animation/LayerVisible/" + ln))
            m = re.search(pat, sh, re.M)
            if not m or m.group(1) != "false":
                fails.append(f"[换头] {k} 影子层 {ln!r} 必须 false（零切片，只吃定位）")
            want = "true" if ln in gold_on else "false"
            m2 = re.search(pat, hd, re.M)
            if not m2 or m2.group(1) != want:
                fails.append(f"[换头] {k} 可见头层 {ln!r} 应为 {want}（金标）")
        for ln in gold_hide:
            want_ln = r'^%s = false' % re.escape(_prop("Animation/LayerVisible/" + ln))
            if not re.search(want_ln, sc, re.M):
                fails.append(f"[换头] {k} 身体场景的原头层 {ln!r} 未关掉（金标）")
            if not re.search(want_ln, sp, re.M):
                fails.append(f"[换头] {k} 身体精灵场景的原头层 {ln!r} 未关掉（金标）")

        # ---- 11b. 女王专属：「披风层」必须已关 / 「光环层」必须已从头挪走 ----
        #   `1` = cloak00.png（披风）、`图层_3` = 6-0001..0012.png（3×3 火焰漩涡）
        if ch["tag"] == "queen":
            for drop in GOLD_QUEEN_HEAD_ON_DROP:
                if drop not in set(ch["head_layers"]):
                    fails.append(f"[换头] {k} 层清单必须保留 {drop!r}"
                                 f"（{'披风' if drop == '1' else '光环'}层仍需定义）")
                if drop in set(ch["head_on"]):
                    fails.append(f"[换头] {k} head_on 不得含 {drop!r}"
                                 f"（{'披风' if drop == '1' else '光环'}层已从头挪走）")

            # ---- 11c. 「3×3 光环」节点（仅女王）：结构 + 参数全金标 ----
            holder = _node_block(sp, GOLD_AURA_HOLDER_NAME)
            aura = _node_block(sp, GOLD_AURA_NODE_NAME)
            # 缺节点只报**一条**（否则下面的字段/层断言会一起炸出几十条噪声 FAIL）
            if not holder:
                fails.append(f"[光环] {k} Sprite 缺 {GOLD_AURA_HOLDER_NAME} 容器（打断父代画）")
            else:
                pos = _kv(holder, "position")
                if pos != GOLD_AURA_HOLDER_POS:
                    fails.append(f"[光环] {k} {GOLD_AURA_HOLDER_NAME}.position 应为 "
                                 f"{GOLD_AURA_HOLDER_POS}（身体 bbox 底边），实为 {pos!r}")
            if not aura:
                fails.append(f"[光环] {k} Sprite 缺 {GOLD_AURA_NODE_NAME} 节点（3×3 光环贴图）")
            else:
                want_a_scale = "Vector2(%g, %g)" % (GOLD_AURA_SCALE, GOLD_AURA_SCALE)
                a_scale = _kv(aura, "scale")
                if a_scale != want_a_scale:
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME}.scale 应为 {want_a_scale}，"
                                 f"实为 {a_scale!r}")
                want_a_off = "Vector2(%g, %g)" % GOLD_AURA_OFFSET
                a_off = _kv(aura, "offset")
                if a_off != want_a_off:
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME}.offset 应为 {want_a_off}"
                                 f"（= −(图层_3 bbox 中心)），实为 {a_off!r}")
                a_z = _kv(aura, "z_index")
                if a_z != str(GOLD_AURA_Z_INDEX):
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME}.z_index 应为 {GOLD_AURA_Z_INDEX}"
                                 f"（非托管渲染路径兜底），实为 {a_z!r}")
                # ★★★ 「画在身体后面」的**唯一**有效手段 —— `z_index` 对**被父代画**的子精灵无效
                #   （`Aura` 由身体批次代画 ⇒ 自己的 `z_index` 不进排序键；详见 `AURA_INSERT_LAYER`）。
                #   生效的是 `TryGetChildRenderLayerForRender` 给出的 `layerId` ⇒ `LayerOrder`。
                a_ins = _kv(aura, "insertLayerId")
                if a_ins != str(GOLD_AURA_INSERT_LAYER):
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME}.insertLayerId 应为 "
                                 f"{GOLD_AURA_INSERT_LAYER}（= 身体可见层 1..29 之下 ⇒ 画在身体后面），"
                                 f"实为 {a_ins!r}；⚠️ 写 −1 会回落**顶层** ⇒ 又跑到身体前面")
                elif int(a_ins) >= 1:
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME}.insertLayerId 必须 < 1"
                                 f"（身体可见层从 1 起），实为 {a_ins}")
                # 反面金标：`Aura` 节点**不许**出现 `Layer` / `followParentSpriteLayerId`
                #   （那两个是「跟随哪一层的 pose 定位」，本包光环靠 `AuraHolder.position` 静态定位；
                #    写 0 会去跟隐藏的 `_ground` 层，纯噪声）。
                for bad_k in ("Layer", "followParentSpriteLayerId"):
                    if _kv(aura, bad_k):
                        fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME} 不该写 {bad_k}"
                                     f"（光环靠 AuraHolder.position 静态定位）")
                if not _kv(aura, "flashAnimeData"):
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME} 必须有 flashAnimeData")
                if 'Animation/Clip = "%s"' % HEAD_CLIP not in aura:
                    fails.append(f"[光环] {k} {GOLD_AURA_NODE_NAME} 的 Animation/Clip "
                                 f"必须是 {HEAD_CLIP!r}")
                for ln in ch["head_layers"]:
                    pat2 = r'^%s = (\w+)' % re.escape(_prop("Animation/LayerVisible/" + ln))
                    m3 = re.search(pat2, aura, re.M)
                    want3 = "true" if ln in set(GOLD_AURA_ON) else "false"
                    if not m3 or m3.group(1) != want3:
                        fails.append(f"[光环] {k} 光环层 {ln!r} 应为 {want3}（金标）")
        else:
            if _node_block(sp, GOLD_AURA_NODE_NAME) or _node_block(sp, GOLD_AURA_HOLDER_NAME):
                fails.append(f"[光环] {k} 只有女王该有光环节点，"
                             f"{GOLD_AURA_NODE_NAME!r} 不该出现在这里")

    # 11d. 属性名引号写法（**血泪史**，见 `_prop` 与 `_bad_prop_keys`）
    #   只给末段加引号 `Animation/LayerVisible/"图层_1" = true` ⇒ Godot 解析出的属性名
    #   带引号 ⇒ `layerDictionary.ContainsKey()` 假 ⇒ `_Set` 静默 return ⇒ 该层保持初值
    #   **true** ⇒ 永远可见。2026-09-25 实证：`HeadShadow` 的「全层 false」白写 6 层
    #   （皇冠/花瓣/火圈/光环/披风/**脸 `skin2_2`**）⇒ 身体上多长出**一整个头**。
    for ch in CHARS:
        for name, body in sorted(B[ch["tag"]].items()):
            for lno, raw, why in _bad_prop_keys(body):
                fails.append(f"[引号] {ch['key']}/{name}:{lno} {why} —— {raw.strip()!r}")
        # 金标：这 6 个层名必须**整条加引号**出现在产物里（防止有人又把引号挪回末段）
        sp_ = B[ch["tag"]]["sprite"]
        for ln in ch["head_layers"]:
            want = _prop("Animation/LayerVisible/" + ln)
            if want.startswith('"') and f"{want} = " not in sp_:
                fails.append(f"[引号] {ch['key']} Sprite 缺整条加引号的属性名 {want} = …")

    # 12. docstring 与本包常量必须一致（防手改漏改文档）
    # ⚠️ 必须带**右边界** `(?![\d.])`：纯子串比会漏字节 —— 旧口径下
    #    `HEAD_EXTRA_SCALE = 1.5` 是 `HEAD_EXTRA_SCALE = 1.575` 的**前缀** ⇒
    #    把 scale 改成 1.5 时文档断言照样绿（铁律 20 ③，由 N07 负向用例实证）。
    doc = __doc__ or ""
    for ch in CHARS:
        o, sc_ = ch["head_offset"], ch["head_scale"]
        off_txt = f"HEAD_OFFSET = ({o[0]}, {o[1]})"
        sc_txt = f"HEAD_EXTRA_SCALE = {sc_}"
        if not re.search(re.escape(off_txt) + r'(?![\d.])', doc):
            fails.append(f"[文档] docstring 里没有 {off_txt}（{ch['key']}）")
        if not re.search(re.escape(sc_txt) + r'(?![\d.])', doc):
            fails.append(f"[文档] docstring 里没有 {sc_txt}（{ch['key']}）")

    # 13. 跨语言：插件源码必须与本包常量同值
    cs = os.path.join(RUNTIME_SRC_DIR, f"{RUNTIME_ENTRY_TYPE}.cs")
    if not os.path.isfile(cs):
        fails.append(f"[插件] 缺入口源码 {cs}")
    else:
        with io.open(cs, "r", encoding="utf-8") as f:
            src = f.read()
        for name, lit in PLUGIN_SRC_EXPECT:
            if not re.search(r'\b%s\s*=\s*%s' % (re.escape(name), re.escape(lit)), src):
                fails.append(f"[插件] 源码里找不到 `{name} = {lit}`（须与本包口径一字不差）")

    return fails


def main(argv=None):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in argv
    only_check = "--self-check" in argv

    fails = self_check()
    if fails:
        print(f"[FAIL] 自检未通过 {len(fails)} 条：")
        for f in fails:
            print("   -", f)
        if not force:
            return 3
        print("[WARN] --force：忽略上面的失败继续落盘（仅供调试；正式构建必须 fails = 0）")
    else:
        print("自检通过：0 条失败。")
    if only_check:
        return 0 if not fails else 3

    # --- 先取回旧工程文件时间戳（幂等：不能每次写 now）
    proj_path = os.path.join(MOD_ROOT, PROJECT_FILE)
    existing = None
    if os.path.isfile(proj_path):
        try:
            existing = read_json(proj_path)
        except Exception:
            existing = None

    assert os.path.abspath(MOD_ROOT).startswith(os.path.abspath(WS) + os.sep), \
        "MOD_ROOT 必须位于工作区内"

    # --- 工作区：就地增量重建（不做整目录 rmtree —— 本机删除钩子很慢）
    dump_json(os.path.join(MOD_ROOT, "mod.json"), build_manifest())
    for ch in CHARS:
        k = ch["key"]
        write_text(_abs(pkg_cfg_rel(k)), zombie_config_tres(ch), "\n")
        # 同一张卡分发两处：Cards/ 是**注册**位置；包内 Packet/ 是镜像（角色包依赖，不注册）
        write_text(_abs(card_rel(k)),
                   packet_tres(ch, f"../Characters/{PKG_CAT}/{k}/Config/{cfg_file(k)}"), "\n")
        write_text(_abs(pkg_packet_rel(k)),
                   packet_tres(ch, f"../Config/{cfg_file(k)}"), "\n")
        write_text(_abs(pkg_set_rel(k)), component_set_tres(ch), "\n")
        write_text(_abs(pkg_produce_rel(k)), produce_definition_tres(ch), "\n")
        if ch["want_fire"]:
            write_text(_abs(pkg_fire_rel(k)), fire_definition_tres(ch), "\n")
        write_text(_abs(pkg_scene_rel(k)), zombie_scene_tscn(ch), "\n")
        write_text(_abs(pkg_sprite_rel(k)), sprite_scene_tscn(ch), "\n")

    ensure_project_layout(MOD_ROOT)
    write_text(proj_path, godot_json(build_project_file(existing), "\r\n"), "\n")

    # --- 清掉「这次不再产出」的旧文件（含改名前的工程文件名 / 旧卡片名）
    keep = set(build_manifest()["resources"]) | {"mod.json", PROJECT_FILE}
    stale = sweep_stale_files(MOD_ROOT, keep)
    if stale:
        print(f"清理旧产物 {len(stale)} 个：")
        for r in sorted(stale):
            print("   -", r)

    # --- 打包 + 安装
    missing = [r for r in build_manifest()["resources"] if not os.path.isfile(_abs(r))]
    if missing:
        print("[FAIL] manifest.resources 指向的文件缺失：")
        for m in missing:
            print("   -", m)
        return 3
    os.makedirs(DIST_DIR, exist_ok=True)
    out = os.path.join(DIST_DIR, f"{MOD_NAME}.pmod")
    entries = package_pmod(out)
    with open(out, "rb") as f:
        data = f.read()
    os.makedirs(MODS_DIR, exist_ok=True)
    write_bytes_if_changed(os.path.join(MODS_DIR, f"{MOD_NAME}.pmod"), data)
    mirror = install_project_dir(MOD_ROOT, os.path.join(MODS_DIR, MOD_NAME), PROJECT_FILE)
    ids, dropped = merge_enabled_mods(MODS_DIR, MOD_ID)
    if dropped:
        print(f"⚠️ enabled_mods.json 里清掉了本 Mod 的旧 id（只差大小写的改名残留）：{dropped}")
    # ⚠️ 登记 **Mods 下**那份工程（编辑器只从那里打开工程），不是工作区构建目录
    cnt = merge_recent_project(os.path.join(MODS_DIR, MOD_NAME, PROJECT_FILE))

    print(f"包内条目 {len(entries)} 个：")
    for e in entries:
        print("   ", e)
    print(f"dist ：{out}（{len(data)} B）")
    print(mirror)
    print(f"enabled_mods.json = {ids}")
    print(f"最近工程数 = {cnt}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
