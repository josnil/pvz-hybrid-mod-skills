using System;
using System.Collections.Generic;
using System.Reflection;
using Godot;
using PVZHE.ModEditor.ModSystem;

/// <summary>
/// 「超级机枪读报僵尸」僵尸 Mod 的托管运行时入口。
///
/// 用户需求（2026-09-19）：
///   1. 名称 = 超级机枪读报僵尸
///   2. 贴图暂用读报僵尸的贴图
///   3. 每 1.5 秒向前方直线发射 7 颗豌豆，**仅 7 颗**（形态：约 0.1s 一颗的连发链）
///   4. 每次攻击有 10% 概率触发大招：5 秒内向 ±15° 范围内散射 300 颗豌豆
///   5. 血量 500（二类防具）+ 1250（本体），移速 = 普通僵尸，伤害 800，伤害类型 = 啃食
///   6. 二类防具掉落后移速 ×3
///
/// 追加需求（2026-09-22，用户原话「你这头为什么这么不协调，而且我要你用的头部贴图是
/// 「超级机枪射手」的头部贴图，而不是「机枪射手」的头部贴图，而且植物僵尸的攻击判定
/// 你也没有加（没有植物不攻击，进场内才攻击）」）：
///   7. 头换成「超级机枪射手」的头部贴图（自制 `SuperGatlingPea.{tres,dat}`，见第七节）
///   8. 修掉换头对位（头悬空、原头透出）—— 数据侧为主（`offset` 反解 + 关掉身体上 7 层原头，
///      见 `build_zombie_super_gatling_paper.py`）+ **运行期幂等兜底**（`TryEnforceHeadSwap`，
///      因为这两件事各有一条静默失败路径，见第七节末）
///   9. **补上植物僵尸共用的射击判定**：没有植物不攻击、进场内才攻击（见第六节）
///
/// ────────────────────────────────────────────────────────────────────────
/// 〇、前置条件：角色场景必须显式声明 `ComponentSet`（否则本插件什么都做不了）
/// ────────────────────────────────────────────────────────────────────────
///
/// 基场景 `Prefab/TowerDefense/Character/TowerDefenseZombie.tscn:10` 自带
/// `ComponentSet = ExtResource("2")` → `TowerDefenseZombieComponentSet.tres`，
/// **那份里没有 FireComponent**。子场景不覆盖 ⇒ 发射组件根本不会被创建：
///   · `TowerDefenseCharacter.cs:703-704` `[Export] public CharacterComponentSet ComponentSet`；
///   · `EnsureComponentManagerResource()`（:1911-1930）—— 有效就用它，否则回落基场景那份；
///   · `ComponentManager.InitializeResourceComponents()`（`ComponentManager.cs:318-346`）
///     按 `ComponentSet.GetCreationPlan()` 逐条 `CreateRuntime()`。
/// ⇒ 症状：一颗豌豆都不出，且**日志里一条 warning 都没有**（`GetRuntime` 只是返回 null）。
///   修法：场景根节点加 `ComponentSet = ExtResource("…")` 指向本包含 FireComponent 的组件集。
///   本插件现在会在「认出僵尸却拿不到 character.fire」时报一次警告，不再静默。
///
/// ────────────────────────────────────────────────────────────────────────
/// 一、为什么「发射」必须走插件（纯数据做不到，证据都在解包源码里）
/// ────────────────────────────────────────────────────────────────────────
///
/// `FireComponentFireProjectileConfig` 只有 8 个字段
/// （Script/Component/TowerDefense/Character/FireComponent/Resource/FireComponentFireProjectileConfig.cs）：
/// `checkProjectileId / firePosId / speed / dir / offsetLine / fireNumSkip / fireEventNeed / projectileFlip`
/// —— **没有概率、没有时窗、没有逐发随机角**。所以：
///   · 需求 4（10% 概率 + 5 秒 + ±15° 随机角）纯数据不可能；
///   · 需求 3（**每 1.5 秒**整点连发 7 颗）也做不到：`FireComponent` 的自发发射是
///     「有目标就发」（`IdleProcessing` 里的 idle fire check → `SetFireState(Attack)` → 动画事件
///     `fire` → `AnimeEvent` → `FireConfiguredVolley`），节拍由动画长度决定，不是固定 1.5s，
///     而且**无目标时一枪不发**。
///
/// 更关键的一条：读报僵尸的精灵**没有可用的开火动画**。
///   内置机枪豌豆僵尸用的是 `ZombieNormalPeaShooterSingle.tscn`，它的 `Head` 子精灵带
///   `HeadFire` / `HeadIdle` 两个 clip（`TowerDefenseZombieNormalGatlingPeaFireComponentDefinition.tres`
///   的 `spritePath` + `fireAnimeClips = "HeadFire"` + `isSpliceSprite = true`）。
///   而 `ZombiePaper.tscn`（读报僵尸精灵）只有头部插槽，**没有 Head 子精灵、没有 HeadFire**。
///   ⚠️ 2026-09-22 更新：本包的 Sprite 场景现在**自带**换头三节点（见第七节），
///      可见头的数据里**确实**有 `HeadFire`（50..86 帧）。
///      开火动画由本插件自己接上：`FirePea()` 每打出一颗豌豆就把可见头切到 `HeadFire`
///      并续开火窗口（`HeadFireWindowMsec`），窗口过后自动切回 `HeadIdle`
///      —— 见第七节末「开火动画」。这**不影响**上面那句结论（引擎自己的动画驱动发射
///      链路依旧是断的），豌豆仍然全部由 `Fire()` 直发。
///   ⇒ `FireComponent.AttackEntered()`（源码 3224-3234 行）第一步就是
///     `if (!CanPlayFireAnimation(fireAnimeClips)) { SetFireState(Idle); return; }`，
///     `CanPlayFireAnimation("")` 恒为 false（源码 1011-1014 行）⇒ 动画驱动的发射链路整条失效。
///   这是**设计好的降级路径**（数据层没有开火动画时打不出去），不是 bug ⇒ 本 Mod 就顺着它走：
///     FireComponent 老老实实待在 Idle（`spliceIdleAnimeClips = ""` 时它连 `sprite.timeScale`
///     都不碰，见源码 1645 行），豌豆全部由插件调 **`FireComponent.Fire()`** 打出去。
///
/// `Fire()` 是 public（源码 3429 行）且**不受状态机约束**：
///   只检查 `CanExecuteGameplay && alive && parent 有效 && parent.instance 有效`（3436 行），
///   然后按 `fireProjectileList` 逐条创建子弹（3449-3502 行）。
///   `CanExecuteGameplay => IsInsideComponentBattlefield`（CharacterComponentRuntime.cs:86）
///   —— 只要僵尸在战斗场内就能打，与它当前是走、是吃、有没有目标**无关**。
///   ⇒ 正是需求 3/4 要的「无条件、按固定节拍」。
///
/// ⚠️ 那句「无条件」在 2026-09-22 被用户按回去了：`Fire()` 只查 `CanExecuteGameplay`，
///   于是「没植物也开火、还没进场也开火」，数据侧的 `checkRayResources` **形同虚设**
///   （它只在引擎状态机的 idle fire check 路径里被读，而本插件绕开了那条路径）。
///   现在**每一轮普攻开始前**先过 `HasFireTarget()` ⇒ 见第六节。
///
/// ────────────────────────────────────────────────────────────────────────
/// 二、逐发改方向：为什么改 `fire.fireProjectileList[i].dir` 就一定生效
/// ────────────────────────────────────────────────────────────────────────
///
/// `Fire()` 内层循环读的是**私有** `_fireProjectiles`（3449 行），看起来改不到；
/// 但 `RefreshExportedArrayCaches()`（源码 964-965 行）是
///     `CopyGodotArray(fireCheckList, _fireChecks); CopyGodotArray(fireProjectileList, _fireProjectiles);`
/// —— **按引用拷贝**，两个列表里放的是**同一批 Resource 对象**。
/// `DuplicateRuntimeResources()`（1259 行）虽然会 `Duplicate(deep:true)`，但被
/// `_runtimeResourcesIsolated` 守卫，只在组件装配期跑一次；之后
/// `RefreshExportedArrayCaches()` 重新拷贝也只是把同一批对象再指一遍。
/// ⇒ 运行期写 `fireProjectileList[i].dir = 角度` 后 `Fire()` 立刻按新角度发射。
///   本插件每次都**重新取一遍** `fire.fireProjectileList`，不缓存列表/元素，彻底规避这个细节。
///
/// ────────────────────────────────────────────────────────────────────────
/// 三、节拍、去抖与「精确 300 颗」
/// ────────────────────────────────────────────────────────────────────────
///
/// · 普攻：每 1.5s 一个周期，周期起点打第 1 颗，之后每 0.1s 一颗 ⇒ 恰好 7 颗（0.0~0.6s）。
/// · 大招：由普攻周期起点掷 10% 骰子；命中后 5 秒内发 **300 颗**，
///   第 k 颗的时刻 = 大招起点 + k × (5000/300) ms ⇒ 精确 300 颗、精确 5 秒，
///   角度 = 每颗独立 `RandfRange(-15, +15)`。
///   ⚠️ 刻意**不用**「7 颗一轮 × 43 轮 = 301 颗」那一套（上一版植物 Mod 的做法）：
///      那次是因为「一轮 7 颗」是原子行为、无法只发半轮；本合同没有这个约束
///      （逐颗发射），所以能做到**恰好 300 颗**。
/// · 大招期间**暂停普攻**（用户 2026-09-19 明确选择），大招结束后重新计时 1.5s。
/// · 计时一律用 `Time.GetTicksMsec()`（毫秒墙钟），与帧率、攻速加成无关。
///
/// ⚠️ 暂停/长卡顿保护：`SceneTree.process_frame` 在游戏暂停时**照常发信号**，
///   若不管就攒下几百毫秒的「欠账」，恢复时会一口气喷出来。
///   对策：当两帧间隔 > 250ms 时，把该僵尸的三条时间轴整体后移同样的间隔
///   （`StallShiftMsec`），欠账直接抹平，不补发。
///   另外每帧最多补 `MaxPeasPerFrame = 12` 颗，避免掉帧时雪崩式创建子弹对象。
///
/// ────────────────────────────────────────────────────────────────────────
/// 四、顺带这件事：把卡补进共享卡库（「可选中」的唯一开关）
/// ────────────────────────────────────────────────────────────────────────
///
/// `Almanac.cs:220` 是 `zombiePacketBank = TowerDefenseManager.GetPacketBankData("GeneralZombie")`
/// —— **同一个实例**（不像植物页的 `WithPlants()` 那样深拷贝）。
/// 「选卡界面 / 关卡编辑器 / 图鉴的 `Zombie` 分类」读的都是它，
/// 所以往 `GeneralZombie.category["Zombie"]` 追加本卡 key **一处生效三处**。
/// 再按 `Include` 闭包补派生库（`ResourceManager.BuildExpandedPacketBank` 递归合并语义），
/// 否则切到 `Total`（`debugPacketOpenAll`）时又看不到。
/// 派生集合在运行期按 `PacketBankResource.json` 的 `Include` 闭包算，不写死。
///
/// ✅ 图鉴重复已在**运行时**消除（2026-09-22）。`Almanac.InitZombie()`（411-431 行）有
///    **两条独立来源**且**都不去重** —— 先遍历共享卡库的 `Zombie` 分类（本插件补的那条）、
///    再无条件遍历 `XWModContentCatalog.GetPackets(plants:false)`（引擎把包内
///    `Resources/Cards/` 注册为 `Packet` 类别后**自动收录**）⇒ 本卡在图鉴僵尸页出现**两条**。
///    两条都**删不得**：卡库那条喂 `CategoryChooseAsync`（`TowerDefenseBattleFeaturePacketBank.cs:509-514`
///    只读 `packetBankData.category[分类]`，且 `ResourceManager.BuildExpandedPacketBanks:638-647`
///    **不合并** Mod 注册）⇒ 删了选卡界面就选不到；`Resources/Cards/` 那条是 `TOWERDEFENSE_PACKETS`
///    （`ResourceManager.cs:529` ← `roots.PacketPathByName`）里 config 的来源 ⇒ 删了连 config 都加载不出来。
///    ⇒ 改为**只在图鉴侧**去重：反射 `Almanac._zombieLogicalConfigs` 删重复项，再用公开的
///    `QueueZombieVirtualRefresh()` 重建虚拟列表。见 `TryDedupeAlmanacZombie`。
///
/// ────────────────────────────────────────────────────────────────────────
/// 五、铁律：入口三回调一律不许抛
/// ────────────────────────────────────────────────────────────────────────
///
/// `ModLoader.TryInitializeRuntimeEntry` 失败 → `ModLoader.cs:667-671` **无条件整包回滚**
/// （不受 `runtimeAssemblyPolicy` 保护）；`NotifyAllModsLoaded` 失败 → State = Failed。
/// 所以 Initialize / OnAllModsLoaded / Shutdown 全部 try/catch 吞异常，
/// 连 `Info/Warn` 内部也再套一层 try(catch) —— 日志本身绝不能成为异常源。
///
/// ────────────────────────────────────────────────────────────────────────
/// 六、目标判定：没有植物不攻击、进场内才攻击（2026-09-22，追需求 9）
/// ────────────────────────────────────────────────────────────────────────
///
/// 引擎早就把这两条做好了，只是**它在状态机的 idle fire check 路径上**，
/// 而本插件绕开状态机自建节拍（第一节末），所以一直没吃到。
/// 修法 = 在**每一轮普攻开始前**调一次 `FireComponent.CanFireCheckOnce*`：
///
/// | 用户要的 | 引擎里的那一行 |
/// |---|---|
/// | 进场内才攻击 | `FireComponent.cs:1766` `parent.GetLogicalGlobalPosition().X > groundRight ⇒ false` |
/// | 没有植物不攻击 | `:1820` `HasOpposingFireCandidates(...)`（同队列无对立阵营候选 ⇒ false）+ `:1836` 逐条 `CheckRayHit`（数据侧 `checkRayResources`） |
///
/// 数据侧**本来就配好了**射线（`…FireComponentDefinition.tres` 的
/// `checkRayResources = [AabbRay2DResource_backward]`、`TargetPosition = (-2000, 0)`），
/// 之前只是没人读它。所以这次**不需要改任何数据**，只补这一次调用。
///
/// 三条刻意的取舍（都写进 `HasFireTarget` 的注释，避免以后被当成 bug 改掉）：
///   ① 判定不通过 ⇒ 这一轮**作废**（不掷大招骰、不开连发链），节拍推到 `now + interval`
///      （用 `=` 不用 `+=`：站着不动不攒欠账，否则植物一进场会一次砸出十几轮）。
///   ② **只挡「开始一轮」**。已经开出去的连发链（7 颗连发）与大招（300 颗散射）**跑完**：
///      7 颗是「一次攻击」的形态；300 颗若在中途因目标死亡而中止，会退化成十几颗 ⇒ 大招概念失效。
///   ③ 判定函数自身抛异常 ⇒ **放行**（宁可多打一颗，也不要把僵尸变成站着不还手的靶子），
///      异常只报一次日志。
///
/// ────────────────────────────────────────────────────────────────────────
/// 七、换头：自制「超级机枪射手」头部 + 它带来的动画修复 + 开火动画
/// ────────────────────────────────────────────────────────────────────────
///
/// ★★★ 2026-09-22 定稿：换头是**三个节点**，不是「一个 `Head` 子节点」。
///
/// 事故：头的区域画出一团**别的角色的图集碎片**
///       （冰系蓝白菱形 / 向日葵黄橙块 / 紫块 / 青蓝小方块 / 白豌豆 / 橙点…）。
/// 根因（源码链条，逐条实锤）：
///   1. `CollectOwnedChildBindings`（`AdobeAnimateSprite.cs:5365`，判定 `:5385`）
///      **只按 Godot 节点类型**收集子精灵，**完全不看 `parentSprite`**；
///      对「非精灵但有子节点」的中间节点会递归（`:5397`），但那一刻把
///      `collectSpriteChildren` 传成 `ownerSlot != null` ⇒ **普通容器下面不再收精灵**。
///   2. ⇒ 只要头是身体的（直接）子精灵，就进身体的 `_spriteChildren`/`_insertedSprites`
///      ⇒ `OwnsSpriteChildForRender`（`:7774`）true
///      ⇒ `IsRenderedByParentSpriteForRender`（`:9559`）true
///      ⇒ `_Draw()`（`:9534`）**第一行就 return**
///      ⇒ 头自己的 `forceLocalRender` **永远走不到**
///        （`_Draw` 只在 `:9549`/`:9551` 读它 —— 这就是「插件明明打了 forceLocalRender、
///         画面还是乱」的原因，也是下面那条「完全静止」的修法**单独用不管用**的原因）。
///   3. ⇒ 头的切片由**身体的渲染批次代画**（`AppendChildSprites` `:833`：rect 用头自己的
///      definition，但整批共用**身体那一张纹理数组**）⇒ 自制皮肤不在全局图集清单里
///      （`AdobeAnimateGlobalAtlasCache.RefreshAtlas` `:3489` 是**构建期**才写
///        `res://…/GeneratedAtlas/AdobeAnimateGlobalAtlasManifest.tres`，运行期无补救 API）
///      ⇒ `MediaAtlasPages` 解析不到 ⇒ 落 `BaseAtlasPage = 0`
///        （`AdobeAnimateDrawItemBuilder.ResolveMediaRect` `:921`）
///      ⇒ 采样 `AdobeAnimateVisualTextureArray.png`（**把全部角色拼在一张的大图**）
///      ⇒ **各种角色碎片拼贴**，与实机截图逐像素吻合。
///   · 植物包为什么没这病：它的 root 与 Head **共用同一份 `.tres`** ⇒ 同 definition
///     ⇒ 同 `MediaAtlasPages` ⇒ 身体代画也是对的。
///
/// ⇒ 修法（在引擎语义下唯一可行）＝ **让可见头脱离身体的子树**，姿势另找来源：
///   · `HeadShadow`：身体的子精灵，`visible = false` + 29 层全 `false`。
///     只为吃 `UpdateChild()`（`:5208-5286`）每帧写的
///     `Position = 被跟随层 pose.Origin + 父精灵 offset`、
///     `Rotation = pose.Rotation + child.offsetRotate`。
///     ⚠️ 那段循环**没有可见性判断**（定位在 `:5259-5281`）⇒ `visible = false` 不影响被定位；
///        层全 false 还保证它**零切片**，不污染身体的批次。
///   · `HeadHolder`：普通 `Node2D`（identity）—— **打断「父代画」**的那层容器
///     （身体扫到它时 `collectSpriteChildren` 已是 `false` ⇒ 里面的精灵不会被收集）。
///   · `Head`：`HeadHolder` 的子节点 = **给人看的那个头**，**独立渲染**
///     （`GetSpriteChildrenForRender()` `:7486` 只返回收集表 ⇒ 身体批次里没有它）
///     ⇒ 用**它自己那张纹理数组**（standalone ⇒ page 0 就是皮肤图集）⇒ 贴图正确。
///   ⇒ 但 ② 断了引擎的定位，所以**本插件每帧**把 ① 的 `Position`/`Rotation` 抄给 ③
///     （`HeadPair` + `SyncHeadPairs()`）。两者的 `scale`/`offset`/`offsetRotate`
///     在场景里逐字相同 ⇒ 画面与「影子若可见」完全一致。
///   ⚠️ `insertLayerId = -1` **不等于**「不插入」：`ResolveSpriteChildInsertLayer`（`:8039`）
///      会回落到顶层 ⇒ 照样被代画。所以**不能**靠「把 insertLayerId 写 -1」躲开这件事。
///   ⚠️ 同步必然有 **1 帧延迟**（`process_frame` 早于节点的 `_process`，那一刻身体的
///      `UpdateChild()` 还没跑）。低速动画下远小于 1px，可以接受；要归零得改挂
///      `RenderingServer.frame_pre_draw`（本次未采纳，少一个不确定点）。
///   ⚠️ 该同步是**插件依赖项**：DLL 没加载时可见头会停在身体原点。
///      `runtimeAssemblyPolicy = "optional"`（加载失败不连坐角色），但本 Mod 的发射本来
///      也全靠插件 ⇒ 可接受；`logs/godot.log` 里 `[ModLoader] package applied` 能一眼看出。
///
/// 头的美术来自本工坊**植物包的同名数据**：`SuperGatlingPea.tres` / `.dat`
/// （经典版 `SuperGatling.reanim.compiled` 27 轨 × 87 帧直转，clip =
/// `BodyIdle(0,24)` / `HeadIdle(25,49)` / `HeadFire(50,86)`）。
/// 因为 `.pmod` 之间**不能互相引用资源**，本包自带一份副本
/// （`Resources/Animations/SuperGatlingPea.{tres,dat}`），Sprite 场景用**相对路径**指过去。
/// 头节点取 `Animation/Clip = "HeadIdle"` + `followParentSpriteLayerId = 16`（读报僵尸的
/// `anim_head1`），于是**影子**自动落在原头所在的位置，不需要我们算世界坐标。
/// ⚠️ 必须是 `Animation/Clip` 这个**官方键名**：裸的 `clip` 不是 `AdobeAnimateSprite`
///    的属性，会被 Godot **静默丢弃**（`.tscn` 里的错键名连一行错误都不报）⇒ `_clip` 留空 ⇒
///    `ApplyFlashAnimeDataChange()`（`:10222-10230`）把它兜成 `clips.Keys[0]` = `BodyIdle`
///    （茎叶段）⇒ 头上长叶子而不是脸。同样的坑还有 `mediaReplaceAtlasPaths` /
///    `mediaReplaceUse` / `name_ignore`（后三个连字段都不存在）。
///
/// ⚠️ 对位只由 `offset`（+可选 `offsetRotate`）决定，**场景里的 `position` 是无效值**：
///    `AdobeAnimateSprite.UpdateChild()`（`:5259-5281`）每帧覆盖
///        `child.Position  = <被跟随图层的 pose>.Origin + <父精灵的 offset>`
///        `child.Rotation  = <被跟随图层的 pose>.Rotation + child.offsetRotate`
///    （`usePos / useRotate` 默认都是 true ⇒ 两者都被覆盖）。
///    而 `offset` 作用在**子精灵自己的美术坐标系**里：`transform = transform.Translated(offset)`
///    （`:7044 / :7071 / :7362`），再叠上节点自身的 `scale = (-1,1)` 与旋转。
///    ⇒ 标定方法见 `build_zombie_super_gatling_paper.py` 的 `HEAD_OFFSET` 注释。
///
/// ⚠️ **2026-09-23 第三轮：`Rotation` 那条恢复成立**（用户要求「回退到上一版本的僵尸头部动画」）。
///    第二轮的「冻结」是靠场景里写 `useRotate = false` + `rotation = 0.0`（弧度）把
///    `:5258-5276` 的 `Rotation` 赋值跳过去；本轮**三行全部撤掉** ⇒ 两个 `[Export]` 开关
///    回到默认 `true` ⇒ 引擎恢复每帧覆写 `Position`/`Rotation`（= 头跟 `anim_head1` 摆动，
///    Idle 净旋转 −16.03°..+1.01°）。
///    ⇒ 本类的 `SyncHeadPairs()` **不需要任何改动**：它本来就是「每帧把影子的
///      `Position`/`Rotation` 抄给可见头」，与旋转是被引擎算出来还是被场景冻住无关
///      （第二轮的冻结下它是幂等空转，本轮才是真正在搬运摆动）。
///    📌 留档（开关仍保留在生成器里，随时可切回）：冻结时的选角是 **0°** ——
///      该美术的原生朝向（同套美术在植物里的 Head 无任何旋转覆写，其跟随层在 BodyIdle
///      全帧旋转恒为 +0.000°）；官方那个 `offsetRotate = −0.25` 属锚错参照物（另一套美术）。
///    📌 单位提醒：`rotation` / `offsetRotate` 都是**弧度**。
///
/// ⚠️ **头部「起始位置」的微调靠 `offset`，别加在屏幕上**（2026-09-23 第三轮）：
///    用户要求「头部初始位置从偏左向右上微移」⇒ 生成器给了 `HEAD_PLACE_SHIFT = (8, -4)`
///    （**屏幕空间** px，y 向下），再反解成 `offset = (-59.9377, -10.0515)`。
///    ⚠️ 把同一个数**直接加到 `offset`** 上是错的：`offset` 在头局部空间、还要过
///    `A = rot_scale(θ, -1, 1)`（含横翻）⇒ 实测横向**正负完全相反**。插件同样不需要配合。
///
/// ⚠️ **可见头另写 `z_index = 1`**（用户要求「层级调高、不被遮挡/穿插」）：
///    全局绘制排序键第一位是 `ZIndex`（`AdobeAnimateSortPath.cs:37-48`，
///    统一排序处 `AdobeAnimateRenderManager.cs:753`），而 `EffectiveZIndex`
///    就是沿父链累加 Godot 的 `z_index`（`AdobeAnimateSprite.cs:6513-6531`）
///    ⇒ 正数即保证排在身体（含报纸/手臂）之后绘制。插件侧**不需要**任何配合。
///
/// ⚠️ **换成自制 `.dat` 会让头「完全静止」**（只有 ESC 暂停一次跳一帧）：
///    自制 `.dat` 不在引擎的全局图集清单里 ⇒ `GpuPoseTextureRid` 无效 ⇒
///    GPU 位姿时钟不推进。修法 = 运行期把该精灵切到本地 CPU 姿态
///    （`forceLocalRender` + `forceCpuPoseRender`，两个都不是 `[Export]` ⇒ 只能插件设）。
///    实现收在**共用源** `runtime_shared/AnimeSpriteLocalRender.cs`，
///    由 `ScanRecursive` 每 10 帧幂等重扫（覆盖战斗 / 图鉴 / 选卡 / 种植预览的各自实例）。
///    ⚠️⚠️ 这一招**必须配合换头三节点才有效**：头若还是身体的直接子精灵，
///    `_Draw()` 会在读 `_forceLocalRender` **之前**就 `return` ⇒ 设了等于没设。
///    （`HeadShadow` 被显式跳过：它 `visible = false` + 全层 false，一个切片都不产生。）
///
/// ⚠️ 运行期还有一道**换头兜底** `TryEnforceHeadSwap()`（与上一条同在 `ScanRecursive` 里）：
///    ① 可见头若既不在 `HeadIdle` 也不在 `HeadFire` 就纠成 `HeadIdle`
///       （**刻意不踩 `HeadFire`** —— 那是本插件刚设的开火窗口，见下面「开火动画」）；
///    ② 身体上构成原版头的 7 层必须不可见，否则原地把可见性表那 7 位写 false。
///    理由：这两件事分别有「`_clip` 被兑成 `clips.Keys[0]`」与「表长不符时引擎
///    把可见性整表重置为全 true」两条**静默**失败路径（数据侧已写对，但挡不住这两条）。
///    幂等、绝不抛、不抢对：表长不符时直接放手交给引擎。
///    ⚠️ 找身体**不能**再用 `sprite.GetParent() as AdobeAnimateSprite`：可见头挂在
///    `HeadHolder`（普通 Node2D）下 ⇒ 那样拿到 null ⇒ 静默不干活。改用 `ResolveBodyForHead()`。
///
/// ── 开火动画（用户需求：「用超级机枪射手的……**射击动画**」）────────────────
/// 头既然独立渲染，它的 clip 就完全由本插件管：
///   · `FirePea()` 每打出一颗豌豆 → `MarkHeadFire()`：把可见头切到 `HeadFire`
///     并把窗口续到 `now + HeadFireWindowMsec`；
///   · `ExpireHeadFire()`（每帧，在 `AdvanceAll` 里）→ 窗口过后切回 `HeadIdle`。
/// `HeadFireWindowMsec` 取自皮肤自身（`HeadFire` 37 帧 ÷ `trueFrameRate` 180 ≈ 206ms，取 220）。
/// **续窗口**的写法让「7 颗连发」（0/100/…/600ms）与「大招 300 颗 5 秒」都表现为
/// 「整段保持开火姿势」；而 `SetHeadClip()` 只在 clip 真的变了才 `SetClip()`
/// ⇒ 整段只**重头播一次**，不会每颗豌豆都把动画打回第 0 帧。
/// 窗口结束后 `HeadIdle` 与 `HeadFire` 不同 ⇒ 下一轮自然重头播 ✓。
/// </summary>
public sealed class SuperGatlingPaperRuntimeEntry : IXWModRuntimeEntry
{
	private const string LogPrefix = "[SuperGatlingPaper] ";

	/// <summary>识别本 Mod 僵尸：用角色配置资源的 `name` 字段（= 角色包 Key，插件与卡库都靠它认人）。</summary>
	private const string CharacterConfigName = "ZombieSuperGatlingPaper";

	/// <summary>ComponentSet 里 FireComponent 的 InstanceId（ChangeSet 里写死的接线键，不能改）。</summary>
	private const string FireInstanceId = "character.fire";

	// ---------------- 普攻参数（需求 3） ----------------

	/// <summary>普攻周期 = 1.5 秒（需求 3「每 1.5 秒」）。</summary>
	private const double AttackIntervalSeconds = GatlingVolleyParams.AttackIntervalSeconds;

	/// <summary>一个周期打出几颗（需求 3「7 颗，仅 7 颗」）。</summary>
	private const int PeasPerAttack = GatlingVolleyParams.PeasPerAttack;

	/// <summary>连发链的颗间距（秒）—— 用户选择「连发成链」，7 颗排成一条直线向前飞。</summary>
	private const double PeaSpacingSeconds = GatlingVolleyParams.PeaSpacingSeconds;

	// ---------------- 大招参数（需求 4） ----------------

	/// <summary>每次攻击触发大招的概率（需求 4「10%」）。</summary>
	private const double UltimateChance = GatlingVolleyParams.UltimateChance;

	/// <summary>大招持续时间（需求 4「5 秒内」）。</summary>
	private const double UltimateSeconds = GatlingVolleyParams.UltimateSeconds;

	/// <summary>大招总颗数（需求 4「300 颗」）。逐颗发射 ⇒ 能做到**恰好** 300。</summary>
	private const int UltimatePeas = GatlingVolleyParams.UltimatePeas;

	/// <summary>散射半角（需求 4「±15°」）。</summary>
	private const double ScatterHalfAngleDeg = GatlingVolleyParams.ScatterHalfAngleDeg;

	// ---------------- 调度参数 ----------------

	/// <summary>扫场景找僵尸的间隔（帧）。大招/普攻节拍每帧推进，不受这里影响。</summary>
	private const int ScanIntervalFrames = 10;

	/// <summary>单帧最多发射几颗：防掉帧时一次性创建几百个子弹对象。</summary>
	private const int MaxPeasPerFrame = GatlingVolleyParams.MaxPeasPerFrame;

	/// <summary>两帧间隔超过它就认为「暂停 / 长卡顿」，把时间轴整体后移，不补发欠账。</summary>
	private const ulong StallThresholdMsec = GatlingVolleyParams.StallThresholdMsec;

	/// <summary>普攻时恢复的 vanilla 开火音效名（fireAudioName 的默认值）。</summary>
	private const string FireAudioName = "ProjectileThrow";

	// ---------------- 卡库参数（第四节） ----------------

	/// <summary>`Almanac.cs:220` 取的就是这个卡库的实例 ⇒ 补它 = 选卡界面/关卡编辑器/图鉴同时生效。</summary>
	private const string RootZombieBankKey = "GeneralZombie";

	/// <summary>僵尸卡的分类键（`Almanac.InitZombie()` 读的就是 `GetCategory("Zombie")`）。</summary>
	private const string ZombieCategory = "Zombie";

	private const string PacketBankResourcePath = "res://Asset/Config/PacketBank/PacketBankResource.json";

	/// <summary>读不到上面的 json 时的兜底（离线按 V0.28 资源算出的 Include 闭包真实值）。</summary>
	private static readonly string[] FallbackDerivedBankKeys =
		new string[] { "GeneralZombie", "TotalZombie", "Total" };

	/// <summary>一个已挂上的僵尸发射组件。</summary>
	private sealed class ZombieHook
	{
		public FireComponent Component;

		/// <summary>下一次「普攻周期起点」的时刻（ms 墙钟）。</summary>
		public ulong NextAttackMsec;

		/// <summary>本轮连发链还剩几颗没打。</summary>
		public int ChainLeft;

		/// <summary>连发链下一颗的时刻（ms 墙钟）。</summary>
		public ulong NextChainMsec;

		/// <summary>是否正在放「散射 300 颗」的大招。</summary>
		public bool BurstActive;

		/// <summary>大招起点（第 k 颗的时刻 = 起点 + k × 5000/300 ms）。</summary>
		public ulong BurstStartMsec;

		/// <summary>大招已经打出去几颗。</summary>
		public int BurstEmitted;

		/// <summary>
		/// 本僵尸的**可见头**（换头三节点的 ③，名字恰好 `Head` 的那一个）。
		/// 懒解析：组件可能比 `Head` 先 ready ⇒ 第一次要放 `HeadFire` 时才去找，找不到就下一颗再试。
		/// </summary>
		public AdobeAnimateSprite Head;

		/// <summary>开火动画窗口的截止时刻（ms 墙钟）；0 = 不在开火窗口内。</summary>
		public ulong HeadFireUntilMsec;
	}

	private XWModRuntimeContext _context;
	private SceneTree _tree;
	private Callable _tickCallable;
	private RandomNumberGenerator _rng;
	private readonly List<ZombieHook> _hooks = new List<ZombieHook>();
	private bool _hooked;
	private bool _connected;
	private int _frameCounter;
	private ulong _lastFrameMsec;

	// 每条出错路径**各用一个**「已报告」标志：共用会「先报的把后报的静音掉」。
	private bool _tickFaultReported;
	private bool _bankFaultReported;
	private bool _hookFaultReported;
	private bool _fireFaultReported;
	private bool _fireMissingReported;

	/// <summary>「开火前目标判定」自身抛异常时的已报告标志（判定失败本身是正常路径，不打日志）。</summary>
	private bool _targetCheckFaultReported;

	private string[] _bankKeys;
	private int _bankPatchCount;

	/// <summary>
	/// `Almanac._zombieLogicalConfigs`（private readonly `List&lt;TowerDefensePacketConfig&gt;`）。
	/// 反射拿到的是**列表引用**，可以原地删元素（readonly 只约束字段赋值，不约束列表内容）。
	/// 探不到就退化成「不去重」：最坏回到「图鉴僵尸页显示两条」，不影响任何其它功能。
	/// </summary>
	private static FieldInfo _zombieLogicalField;
	private static bool _zombieLogicalFieldProbed;
	private int _almanacDedupeCount;
	private bool _dedupeFaultReported;
	private int _ultimateCount;
	private int _attackCount;
	private bool _shapeMismatchReported;

	/// <summary>已切到本地 CPU 位姿渲染的自制皮肤精灵个数（只用于日志）。</summary>
	private int _skinPatchCount;

	/// <summary>
	/// 位姿影子：身体（Sprite 场景根）的直接子精灵，`visible = false` + 29 层全 false。
	/// 只为吃 `UpdateChild()` 的每帧定位（见类注释第七节）。
	/// </summary>
	private const string HeadShadowNodeName = "HeadShadow";

	/// <summary>打断「父代画」的普通容器（identity `Node2D`），可见头挂在它下面。</summary>
	private const string HeadHolderNodeName = "HeadHolder";

	/// <summary>可见头：`HeadHolder` 的子精灵，**独立渲染**（给人看的那个）。</summary>
	private const string HeadNodeName = "Head";

	/// <summary>
	/// 子弹生成点（`FireComponentDefinition.firePosMarkerPaths` 指向的 `Marker2D`）
	/// 在**身体精灵下**的相对路径。
	///
	/// 结构：`身体 / HeadSlot（原版护具用的静态插槽）/ FireMarker（Marker2D）`。
	/// ⚠️ `HeadSlot` **不跟头部美术**（它是原版给护具/DamagePoint 用的静态插槽，
	///    护具之所以看着贴在头上是**护具自己的 offset 补掉了差**）⇒ 生成点必须由本插件
	///    每帧覆写，否则会停在「头顶上方」（实测偏上 80.77px）。
	/// </summary>
	private const string FireMarkerNodePath = "HeadSlot/FireMarker";

	/// <summary>
	/// 炮口在**可见头节点局部**空间的位置 = 生成器的 `MUZZLE_POSE + HEAD_OFFSET`
	/// （= `HEAD_MUZZLE_LOCAL`，由 `.cache/_fire_marker_solve.py` 反解）。
	///
	/// ⇒ 运行期 `head.GlobalTransform * HeadMuzzleLocal` 就是**炮口的世界坐标**
	///   （头节点的绘制变换是 `transform.Translated(offset)` 再画 pose 点 ⇒ 局部点 = pose + offset）。
	///
	/// ⚠️ 它随 `HEAD_OFFSET` 走：生成器那边一改 `HEAD_OFFSET`，这里必须同步重算
	///   （`check_gates_super_gatling_paper.cs` 会逐字比对，别手改）。
	/// </summary>
	private static readonly Vector2 HeadMuzzleLocal = new Vector2(28.6143f, 20.1485f);

	/// <summary>头静止时的 clip（皮肤数据里的头段 25..49）。</summary>
	private const string HeadClipName = "HeadIdle";

	/// <summary>开火时的 clip（皮肤数据里的开火段 50..86）。</summary>
	private const string HeadFireClipName = "HeadFire";

	/// <summary>
	/// 开火窗口：切到 `HeadFire` 后保持多久（ms）。
	///
	/// 取自皮肤自身：`HeadFire` = 第 50..86 帧共 37 帧，`trueFrameRate = 180`
	/// ⇒ 37/180 ≈ 206ms ⇒ 取 220ms 留一点余量，让最后一帧画得出来。
	/// ⚠️ 每打出一颗豌豆就**续**一次窗口（不是重设成固定值），所以：
	///    · 普攻 7 颗 × 100ms 间距 ⇒ 开火姿态保持约 600 + 220 = 820ms；
	///    · 大招 300 颗 / 5 秒 ⇒ 整段 5 秒都在开火姿态。
	/// 而 `SetHeadClip()` 只在 clip 真的变化时才 `SetClip()` ⇒ 整段只重头播一次。
	/// </summary>
	private const ulong HeadFireWindowMsec = 220;

	/// <summary>
	/// 换头兜底：原版僵尸的「头」= 7 个图层，必须全部不可见（否则从盔下透出来）。
	/// 名字取自内置 `ZombiePaper.tres` 的 `layerDictionary`；内置 `ZombiePaper.tscn`
	/// 把这 7 层**显式写 true**，所以不覆写就是看得见的。
	/// </summary>
	private static readonly string[] BodyHiddenHeadLayers = new string[]
	{
		"anim_hair",
		"anim_head1",
		"anim_head_look",
		"anim_head_pupils",
		"anim_hairpiece",
		"anim_head_jaw",
		"anim_head_glasses"
	};

	/// <summary>换头兜底已修正的个数（只用于日志，证明幂等）。</summary>
	private int _headClipFixCount;
	private int _bodyHeadHideCount;

	/// <summary>
	/// 「影子 → 可见头」配对表（换头三节点的运行期纽带，见类注释第七节）。
	/// 由 `ScanRecursive`（每 `ScanIntervalFrames` 帧）幂等登记，
	/// 由 `SyncHeadPairs()`（**每帧**）抄位姿 —— 10 帧一档对头来说太粗，会抖。
	/// </summary>
	private sealed class HeadPair
	{
		public AdobeAnimateSprite Shadow;
		public AdobeAnimateSprite Visible;

		/// <summary>
		/// 本角色的子弹生成点（`HeadSlot/FireMarker`）。可为 null（数据侧缺节点 ⇒ 只是生成点
		/// 退回静态兜底值，不影响换头本身）。
		/// </summary>
		public Marker2D Marker;
	}

	private readonly List<HeadPair> _headPairs = new List<HeadPair>();

	/// <summary>「找到了可见头却没有影子」的一次性告警标志（数据侧漏节点时极难自查）。</summary>
	private bool _headShadowMissingReported;

	/// <summary>「找到了身体却没有子弹生成点」的一次性告警标志。</summary>
	private bool _fireMarkerMissingReported;

	/// <summary>「皮肤数据里没有 HeadFire」的一次性告警标志（否则每颗豌豆刷一行）。</summary>
	private bool _headFireMissingReported;

	public void Initialize(XWModRuntimeContext context)
	{
		try
		{
			_context = context;
			_hooked = false;
			_connected = false;
			_frameCounter = 0;
			_lastFrameMsec = 0UL;
			_tickFaultReported = false;
			_bankFaultReported = false;
			_hookFaultReported = false;
			_fireFaultReported = false;
			_fireMissingReported = false;
			_targetCheckFaultReported = false;
			_skinPatchCount = 0;
			_headClipFixCount = 0;
			_bodyHeadHideCount = 0;
			_headPairs.Clear();
			_headShadowMissingReported = false;
			_fireMarkerMissingReported = false;
			_headFireMissingReported = false;
			_ultimateCount = 0;
			_attackCount = 0;
			_shapeMismatchReported = false;
			_bankKeys = null;
			_bankPatchCount = 0;
			_almanacDedupeCount = 0;
			_dedupeFaultReported = false;
			_hooks.Clear();

			_rng = new RandomNumberGenerator();
			// 用引擎随机源播种（真随机）—— 单机体验优先；
			// 联机会与主机不同步，这是**刻意接受**的代价（需求 4 要求真随机 10%）。
			_rng.Randomize();

			string root = (context == null) ? "<null>" : context.PackageRoot;
			Info("运行入口已初始化；PackageRoot=" + root
				+ "；普攻 " + AttackIntervalSeconds.ToString("0.#") + "s/" + PeasPerAttack + " 颗"
				+ "（连发间距 " + (PeaSpacingSeconds * 1000.0).ToString("0.#") + "ms）"
				+ "；大招概率 " + Pct(UltimateChance) + "%，"
				+ UltimateSeconds.ToString("0.#") + "s 内散射 " + UltimatePeas + " 颗 ±"
				+ ScatterHalfAngleDeg.ToString("0.#") + "°。");
		}
		catch (Exception ex)
		{
			Warn("Initialize 异常（已吞掉，避免整包被拒）：" + ex.Message);
		}
	}

	public void OnAllModsLoaded()
	{
		try
		{
			if (_hooked)
			{
				return;
			}
			_tree = Engine.GetMainLoop() as SceneTree;
			if (_tree == null)
			{
				Warn("拿不到 SceneTree；豌豆不会发射（僵尸本身仍可正常行走/啃食）。");
				return;
			}
			_tickCallable = Callable.From(new Action(OnProcessFrame));
			_tree.Connect("process_frame", _tickCallable);
			_connected = true;
			_hooked = true;
			_lastFrameMsec = Time.GetTicksMsec();
			Info("已挂载 process_frame；并发把「" + CharacterConfigName + "」补进卡库「"
				+ RootZombieBankKey + "」的「" + ZombieCategory + "」分类（⇒ 选卡界面可选）。");
		}
		catch (Exception ex)
		{
			Warn("OnAllModsLoaded 异常（已吞掉）：" + ex.Message);
		}
	}

	public void Shutdown()
	{
		try
		{
			if (_connected && _tree != null && GodotObject.IsInstanceValid(_tree))
			{
				_tree.Disconnect("process_frame", _tickCallable);
			}
		}
		catch (Exception ex)
		{
			Warn("Shutdown 取消失效：process_frame 断开异常（已吞掉）：" + ex.Message);
		}
		finally
		{
			_connected = false;
			_hooked = false;
			_tree = null;
			_hooks.Clear();
		}
	}

	// ---------------------------------------------------------------- 每帧

	private void OnProcessFrame()
	{
		try
		{
			_frameCounter++;
			ulong now = Time.GetTicksMsec();
			ulong gap = now - _lastFrameMsec;
			_lastFrameMsec = now;
			bool stalled = gap > StallThresholdMsec;

			AdvanceAll(now, stalled, gap);

			// ★ 换头三节点的纽带：**每帧**把影子的位姿抄给可见头。
			//   必须在 ScanIntervalFrames 的早退**之前** —— 10 帧一档对头来说太粗，会抖。
			SyncHeadPairs();

			if ((_frameCounter % ScanIntervalFrames) != 0)
			{
				return;
			}
			ScanScene();
		}
		catch (Exception ex)
		{
			if (!_tickFaultReported)
			{
				_tickFaultReported = true;
				Warn("发射节拍推进异常（本条只报一次，仍会继续尝试）：" + ex.Message);
			}
		}
	}

	private void ScanScene()
	{
		TryPatchCardBanks();

		if (_tree == null || !GodotObject.IsInstanceValid(_tree))
		{
			return;
		}
		Node root = _tree.Root;
		if (root == null || !GodotObject.IsInstanceValid(root))
		{
			return;
		}
		ScanRecursive(root);
	}

	private void ScanRecursive(Node node)
	{
		if (node == null || !GodotObject.IsInstanceValid(node))
		{
			return;
		}
		if (node is TowerDefenseCharacter character)
		{
			TryHookCharacter(character);
		}
		else if (node is Almanac almanac)
		{
			TryDedupeAlmanacZombie(almanac);
		}
		else if (node is AdobeAnimateSprite animeSprite)
		{
			TryPatchSkinRender(animeSprite);
			TryEnforceHeadSwap(animeSprite);
			TryRegisterHeadPair(animeSprite);
		}
		Godot.Collections.Array<Node> children = node.GetChildren();
		for (int i = 0; i < children.Count; i++)
		{
			ScanRecursive(children[i]);
		}
	}

	// ---------------------------------------------------------------- 动画修复

	/// <summary>
	/// 把「本工坊自制皮肤」的精灵切到本地 CPU 位姿渲染 ⇒ 动画恢复逐帧播放。
	///
	/// 为什么需要（本包从 #47 起头也换成了自制 `.dat`）：
	///   僵尸身体仍是内置 `ZombiePaper`（在引擎的全局图集清单里，不受影响），
	///   但**头**用的是本工坊自制的 `SuperGatlingPea.{tres,dat}`（standalone）⇒
	///   不在图集清单里 ⇒ 引擎的 GPU 位姿时钟失效 ⇒ 头会「完全静止，只有 ESC 暂停一次跳一帧」。
	///
	/// 判定与实现收在**共用源** `runtime_shared/AnimeSpriteLocalRender.cs`（植物/僵尸同源）：
	///   幂等（已设过就返回 `AlreadyLocal`）、未 ready 的节点留到下一轮、**绝不抛**。
	/// 因为本方法跑在 `ScanRecursive` 里（每 `ScanIntervalFrames` 帧扫一遍整棵树），
	/// 所以「引擎自己把 `forceCpuPoseRender` 放掉」以及「图鉴 / 选卡 / 种植预览各自独立实例」
	/// 两种情况都会被下一轮扫描自动覆盖。
	///
	/// ⚠️⚠️ 这一招**只在头脱离身体子树之后才有效**（换头三节点，见类注释第七节）：
	///   头若还是身体的直接子精灵 ⇒ `_Draw()`（`:9534`）在读 `_forceLocalRender`
	///   **之前**就 `return` ⇒ 设了等于没设（旧版就是这样：日志打了「已切到本地 CPU 位姿渲染」，
	///   画面依旧是碎片拼贴）。
	/// ⚠️ 影子（`HeadShadow`）显式跳过：它 `visible = false` + 全层 false ⇒ 零切片，
	///   切不切本地渲染对画面毫无影响，只会把日志刷成两倍。
	/// </summary>
	private void TryPatchSkinRender(AdobeAnimateSprite sprite)
	{
		if (sprite.Name == HeadShadowNodeName)
		{
			return;
		}
		if (AnimeSpriteLocalRender.Patch(sprite) != AnimeSpriteLocalRender.Patched)
		{
			return;
		}
		_skinPatchCount++;
		Info("已把第 " + _skinPatchCount + " 个自制皮肤精灵切到本地 CPU 位姿渲染"
			+ "（forceLocalRender + forceCpuPoseRender）⇒ 动画恢复逐帧播放。节点="
			+ sprite.Name + "，data=" + AnimeSpriteLocalRender.Describe(sprite.flashAnimeData));
	}

	// ---------------------------------------------------------------- 换头兜底

	/// <summary>
	/// 「换上超级机枪射手的头」的运行期兜底（需求 1/2）。
	///
	/// 数据侧已经把两件事都写对了（Sprite 场景里可见头 `Head` 的
	/// `Animation/Clip = "HeadIdle"`、身体的 7 层原头发 `Animation/LayerVisible/<名> = false`），
	/// 运行期还要再兜一次，因为这两件事各自都有一条**静默失败**路径：
	///
	///   · **clip**：`Head` 是本包场景里**新增**的节点，它的 `_clip` 只靠 `.tscn` 属性落下。
	///     一旦这行没生效（写了不存在的键名 / 实例化顺序），`_clip` 留空，
	///     `ApplyFlashAnimeDataChange()`（`AdobeAnimateSprite.cs:10222-10230`）会把它
	///     兜成 `clips.Keys[0]` —— 本皮肤是 `BodyIdle`，那是**茎叶段**，
	///     头上会长出一丛叶子（而不是脸 + 头盔 + 机枪）。
	///   · **可见性**：`_layerVisible.Count != 图层数` 时引擎把整表**重置为全 true**
	///     （`:10190-10205` / `:10267-10275`）⇒ 原头立刻透出来。
	///
	/// 只认名字恰好为 `Head` 的节点（`HeadSlot` / `HeadHolder` / `HeadShadow` 都不算），
	/// 所以不会误伤身体 / 别的精灵。
	///
	/// ⚠️ 本方法**刻意不碰 `HeadFire`**：那是 `MarkHeadFire()` 刚设的开火窗口，
	///    本方法每 10 帧才跑一次，若按「不等于 HeadIdle 就纠正」写就会把开火动画腰斩。
	///    只在「既不是 `HeadIdle` 也不是 `HeadFire`」（= 兑成了 `BodyIdle` 之类）时才纠正。
	/// ⚠️ 找身体**不能**再用 `GetParent() as AdobeAnimateSprite`：可见头挂在 `HeadHolder`
	///    （普通 `Node2D`）下 ⇒ 那样永远拿到 null ⇒ `EnforceBodyHeadLayersHidden` 变成空操作。
	/// 幂等：已经对了就什么都不写、不打日志。绝不抛。
	/// </summary>
	private void TryEnforceHeadSwap(AdobeAnimateSprite sprite)
	{
		try
		{
			if (sprite.Name != HeadNodeName || !sprite.IsInsideTree() || !sprite.IsNodeReady())
			{
				return;
			}

			// (1) 可见头必须有个**有效**的 clip（HeadIdle 或开火窗口里的 HeadFire）。
			AdobeAnimateData data = sprite.flashAnimeData;
			if (data != null && GodotObject.IsInstanceValid(data)
				&& data.clips != null && data.clips.ContainsKey(HeadClipName))
			{
				string current = sprite.Get("Animation/Clip").AsString();
				if (current != HeadClipName && current != HeadFireClipName)
				{
					sprite.SetClip(HeadClipName);
					_headClipFixCount++;
					Info("换头兜底：把头的 clip 从「" + current + "」纠正为「" + HeadClipName
						+ "」（第 " + _headClipFixCount + " 个）。");
				}
			}

			// (2) 身体那 7 层原头必须关掉。
			EnforceBodyHeadLayersHidden(ResolveBodyForHead(sprite));
		}
		catch
		{
			// 视觉兜底失败不该影响战斗逻辑：静默放弃，下一轮扫描还会再来。
		}
	}

	// ---------------------------------------------------------------- 换头三节点的纽带

	/// <summary>
	/// 可见头 → 它所属的**身体精灵**。
	///
	/// 结构是 `身体 / HeadHolder(普通 Node2D) / Head`（见类注释第七节），所以：
	///   ① 先按约定取「`HeadHolder` 的父」—— 快路径；
	///   ② 名字对不上（有人改了嵌套）就沿祖先链找最近的上层精灵 —— 兜底路径。
	/// 两条都失败返回 null（调用方全部按「拿不到就什么都不做」处理）。
	/// 绝不抛。
	/// </summary>
	private static AdobeAnimateSprite ResolveBodyForHead(AdobeAnimateSprite head)
	{
		try
		{
			Node holder = head.GetParent();
			if (holder != null && holder.Name == HeadHolderNodeName)
			{
				AdobeAnimateSprite direct = holder.GetParent() as AdobeAnimateSprite;
				if (direct != null)
				{
					return direct;
				}
			}
			Node node = head.GetParent();
			int guard = 0;
			while (node != null && guard++ < 64)
			{
				if (node is AdobeAnimateSprite body)
				{
					return body;
				}
				node = node.GetParent();
			}
		}
		catch
		{
		}
		return null;
	}

	/// <summary>
	/// 登记「影子 → 可见头」这一对（换头三节点的运行期纽带）。
	///
	/// 只在遇到名为 `Head` 的精灵时登记 —— `HeadShadow` / `HeadHolder` 名字都不同，
	/// 不会误触（`Name` 比较是全等的，不是前缀匹配）。
	/// 幂等：同一对只登记一次；任一端失效时由 `SyncHeadPairs()` 剔除，下一轮扫描重新登记。
	/// 找不到影子只报**一次**日志（数据侧漏节点时画面表现为「头停在身体原点」，
	/// 没有日志的话极难自查）。绝不抛。
	/// </summary>
	private void TryRegisterHeadPair(AdobeAnimateSprite visible)
	{
		try
		{
			if (visible.Name != HeadNodeName)
			{
				return;
			}
			AdobeAnimateSprite body = ResolveBodyForHead(visible);
			if (body == null)
			{
				return;
			}
			AdobeAnimateSprite shadow = body.GetNodeOrNull<AdobeAnimateSprite>(HeadShadowNodeName);
			if (shadow == null || ReferenceEquals(shadow, visible))
			{
				if (!_headShadowMissingReported)
				{
					_headShadowMissingReported = true;
					Warn("找到换头可见头 `" + HeadNodeName + "`，但身体 `" + body.Name
						+ "` 下没有 `" + HeadShadowNodeName + "` ⇒ 头不会跟随身体位移，"
						+ "会停在身体原点。请重跑 build_zombie_super_gatling_paper.py"
						+ "（换头必须是「影子 + 容器 + 可见头」三节点结构）。");
				}
				return;
			}
			for (int i = 0; i < _headPairs.Count; i++)
			{
				if (ReferenceEquals(_headPairs[i].Visible, visible))
				{
					return;
				}
			}
			Marker2D marker = body.GetNodeOrNull<Marker2D>(FireMarkerNodePath);
			if (marker == null && !_fireMarkerMissingReported)
			{
				_fireMarkerMissingReported = true;
				Warn("身体 `" + body.Name + "` 下找不到子弹生成点 `" + FireMarkerNodePath
					+ "` ⇒ 生成点只能靠场景里的静态兜底值（头一摆动就离线，Idle 段最坏 10.9px、"
					+ "Walk/Eat 更大）。请重跑 build_zombie_super_gatling_paper.py。");
			}
			HeadPair pair = new HeadPair();
			pair.Shadow = shadow;
			pair.Visible = visible;
			pair.Marker = marker;
			_headPairs.Add(pair);
		}
		catch
		{
			// 登记失败只影响外观：静默放弃，下一轮扫描还会再来。
		}
	}

	/// <summary>
	/// **每帧**把影子的位姿抄给可见头 —— 换头三节点被打断的那条「引擎定位」链路的替身。
	///
	/// 为什么必须每帧：影子的 `Position`/`Rotation` 是 `UpdateChild()`
	/// （`AdobeAnimateSprite.cs:5259-5281`）在身体的 `_process` 里逐帧改写的，
	/// 10 帧一档的 `ScanRecursive` 太粗 ⇒ 头会抖。
	/// 为什么只抄 `Position`/`Rotation`：两者 `scale`/`offset`/`offsetRotate` 在场景里
	/// 已经逐字相同 ⇒ 节点变换一致则渲染结果与「影子若可见」完全一致
	/// （`offset` 只影响本精灵自己的美术，见 `:7044`/`:7071`/`:7362`）。
	/// ⚠️ `process_frame` 早于节点的 `_process` ⇒ 这里读到的是**上一帧**的影子位姿
	///    （1 帧延迟，低速动画下远小于 1px）。要归零得改挂 `RenderingServer.frame_pre_draw`。
	/// 幂等、绝不抛；失效的对会被剔除（`ScanRecursive` 下一轮重新登记）。
	///
	/// 【第四轮补充】同一循环里还负责把**子弹生成点**（`HeadSlot/FireMarker`）摆到当帧真炮口：
	///     `marker.GlobalPosition = head.GlobalTransform * HeadMuzzleLocal`
	/// 理由见 `HeadMuzzleLocal` 与 `FireMarkerNodePath` 的注释 —— 场景里的静态值只是
	/// 参考帧（bf=0）的兜底，头摆动后每帧都要重算。
	/// </summary>
	private void SyncHeadPairs()
	{
		if (_headPairs.Count == 0)
		{
			return;
		}
		for (int i = _headPairs.Count - 1; i >= 0; i--)
		{
			HeadPair pair = _headPairs[i];
			if (!IsLiveSprite(pair.Shadow) || !IsLiveSprite(pair.Visible))
			{
				_headPairs.RemoveAt(i);
				continue;
			}
			try
			{
				if (pair.Visible.Position != pair.Shadow.Position)
				{
					pair.Visible.Position = pair.Shadow.Position;
				}
				if (!Mathf.IsEqualApprox(pair.Visible.Rotation, pair.Shadow.Rotation))
				{
					pair.Visible.Rotation = pair.Shadow.Rotation;
				}
				// 顺带把**子弹生成点**摆到当帧真炮口上（用户：「让子弹生成位置靠左一点，
				// 对齐子弹发射口」）。头是跟 anim_head1 逐帧摆的 ⇒ 炮口每帧都在动，
				// 场景里那个静态 `FireMarker.position` 只能对上参考帧 bf=0（Idle 段就
				// 已经飘到 10.9px、Walk/Eat 更大）⇒ 必须每帧覆写。
				// `head.GlobalTransform * HeadMuzzleLocal` = 炮口的**世界坐标**
				//（头绘制时是 `transform.Translated(offset)` 再画 pose 点 ⇒ 局部点 = pose + offset）。
				// ⚠️ 必须放在抄完 Position/Rotation **之后**：GlobalTransform 跟着这两个量变。
				if (pair.Marker != null && GodotObject.IsInstanceValid(pair.Marker))
				{
					Vector2 muzzle = pair.Visible.GlobalTransform * HeadMuzzleLocal;
					if (!pair.Marker.GlobalPosition.IsEqualApprox(muzzle))
					{
						pair.Marker.GlobalPosition = muzzle;
					}
				}
			}
			catch
			{
				_headPairs.RemoveAt(i);
			}
		}
	}

	/// <summary>精灵是否还能安全读写（节点有效 + 在树内）。绝不抛。</summary>
	private static bool IsLiveSprite(AdobeAnimateSprite sprite)
	{
		try
		{
			return sprite != null && GodotObject.IsInstanceValid(sprite) && sprite.IsInsideTree();
		}
		catch
		{
			return false;
		}
	}

	// ---------------------------------------------------------------- 开火动画

	/// <summary>
	/// 打出一颗豌豆时让**可见头**播 `HeadFire`（用户需求：「用超级机枪射手的……射击动画」）。
	///
	/// 做法 = 续窗口 + 只在 clip 真的变化时才 `SetClip()`：
	///   · `hook.HeadFireUntilMsec = now + HeadFireWindowMsec`（**续**，不是取 max）
	///     ⇒ 7 颗连发（0/100/…/600ms）与 300 颗/5s 的大招都表现为「整段保持开火姿态」；
	///   · `SetHeadClip()` 内部比 clip，`HeadIdle → HeadFire` 才真重头播
	///     ⇒ 一轮只重头播一次，不会被每颗豌豆打回第 0 帧。
	/// 窗口结束后由 `ExpireHeadFire()` 切回 `HeadIdle`（clip 变了 ⇒ 下一轮自然重头播）。
	///
	/// ⚠️ `hook.Head` 懒解析：组件可能比 `Head` 先 ready，拿不到就下一颗再试
	///    （一次发 7 颗 ⇒ 同一轮里后面的豌豆就会补上）。
	/// 幂等、绝不抛 —— 纯外观，失败绝不影响发射。
	/// </summary>
	private void MarkHeadFire(ZombieHook hook, ulong now)
	{
		try
		{
			AdobeAnimateSprite head = hook.Head;
			if (!IsLiveSprite(head))
			{
				head = ResolveHeadForFire(hook);
				hook.Head = head;
				if (!IsLiveSprite(head))
				{
					return;
				}
			}
			hook.HeadFireUntilMsec = now + HeadFireWindowMsec;
			SetHeadClip(hook, HeadFireClipName);
		}
		catch
		{
			// 开火动画纯属外观：任何异常都吞掉，绝不连坐发射。
		}
	}

	/// <summary>
	/// 开火窗口过期 ⇒ 把可见头切回 `HeadIdle`。
	///
	/// 头是**独立渲染**的（换头三节点），它的 clip 完全由本插件管，
	/// 所以这里必须自己收尾 —— 否则头会永远停在开火姿势。
	/// 幂等、绝不抛；`HeadFireUntilMsec == 0`（不在窗口内）时直接返回。
	/// </summary>
	private void ExpireHeadFire(ZombieHook hook, ulong now)
	{
		if (hook.HeadFireUntilMsec == 0UL || now < hook.HeadFireUntilMsec)
		{
			return;
		}
		hook.HeadFireUntilMsec = 0UL;
		SetHeadClip(hook, HeadClipName);
	}

	/// <summary>
	/// 组件 → 本僵尸的可见头（名字恰好为 `Head` 的那一个）。
	///
	/// 走 `FireComponent.Owner`（= 该僵尸的 `TowerDefenseCharacter`）往下 `FindChild`。
	/// ⚠️ `owned: false` 是必须的：本包在 `Sprite` 场景里新增的节点**没有 owner**
	///    （`owned = true` 会把它们全部过滤掉 ⇒ 永远找不到）。
	/// 找不到返回 null。绝不抛。
	/// </summary>
	private static AdobeAnimateSprite ResolveHeadForFire(ZombieHook hook)
	{
		try
		{
			FireComponent fire = hook.Component;
			if (fire == null || fire.IsReleased)
			{
				return null;
			}
			Node owner = fire.Owner as Node;
			if (owner == null || !GodotObject.IsInstanceValid(owner))
			{
				return null;
			}
			return owner.FindChild(HeadNodeName, recursive: true, owned: false) as AdobeAnimateSprite;
		}
		catch
		{
			return null;
		}
	}

	/// <summary>
	/// 给可见头切 clip（带一次性的「皮肤数据里没有 HeadFire」告警）。
	///
	/// ⚠️ **只在 clip 真的变化时才 `SetClip()`** —— 这是本文件唯一的「不重启动画」保证：
	///    `FirePea()` 每颗豌豆都会调到这里，若每次都 `SetClip("HeadFire")`，
	///    7 颗连发会把动画反复打回第 0 帧，看起来永远停在第一帧。
	/// ⚠️ 数据里没有目标 clip 时只报**一次**日志（否则每颗豌豆刷一行）。
	/// 幂等、绝不抛。
	/// </summary>
	private void SetHeadClip(ZombieHook hook, string clipName)
	{
		AdobeAnimateSprite head = hook.Head;
		if (!IsLiveSprite(head))
		{
			return;
		}
		try
		{
			AdobeAnimateData data = head.flashAnimeData;
			if (data == null || !GodotObject.IsInstanceValid(data)
				|| data.clips == null || !data.clips.ContainsKey(clipName))
			{
				if (clipName == HeadFireClipName && !_headFireMissingReported)
				{
					_headFireMissingReported = true;
					Warn("皮肤数据里没有 clip「" + HeadFireClipName
						+ "」⇒ 开火时头不会换姿势（豌豆照常发射，纯外观损失）。data="
						+ AnimeSpriteLocalRender.Describe(data));
				}
				return;
			}
			if (head.Get("Animation/Clip").AsString() != clipName)
			{
				head.SetClip(clipName);
			}
		}
		catch
		{
			// 外观失败静默放弃：下一颗豌豆还会来。
		}
	}

	/// <summary>
	/// 把僵尸身体（内置 `ZombiePaper`）上构成「原版头」的 7 层关掉。
	///
	/// ⚠️ 只在**表长正好等于图层数**时才动：表长不符时引擎自己会重置成「全 true」，
	/// 我们抢先写会被它盖掉，还会把脏表写回去 —— 那种情况交给引擎，不做无用的对抗。
	/// 幂等：已经全关就直接返回（不打日志）。
	/// </summary>
	private void EnforceBodyHeadLayersHidden(AdobeAnimateSprite body)
	{
		if (body == null || !GodotObject.IsInstanceValid(body))
		{
			return;
		}
		AdobeAnimateData data = body.flashAnimeData;
		if (data == null || !GodotObject.IsInstanceValid(data) || data.layerDictionary == null)
		{
			return;
		}
		Godot.Collections.Array<bool> visible = body.layerVisible;
		if (visible == null || visible.Count != data.layerDictionary.Count)
		{
			return;
		}
		int changed = 0;
		for (int i = 0; i < BodyHiddenHeadLayers.Length; i++)
		{
			string layerName = BodyHiddenHeadLayers[i];
			if (!data.layerDictionary.ContainsKey(layerName))
			{
				continue;
			}
			int layerId = (int)data.layerDictionary[layerName].AsInt64();
			if (layerId >= 0 && layerId < visible.Count && visible[layerId])
			{
				visible[layerId] = false;
				changed++;
			}
		}
		if (changed > 0)
		{
			// 走属性 setter ⇒ 内部会 MarkLayerStateChanged()，把渲染快照缓存失效掉。
			body.layerVisible = visible;
			_bodyHeadHideCount++;
			Info("换头兜底：关掉身体上 " + changed + " 层原版头（第 " + _bodyHeadHideCount
				+ " 个精灵）。节点=" + body.Name + "，data="
				+ AnimeSpriteLocalRender.Describe(data));
		}
	}

	// ---------------------------------------------------------------- 发射节拍

	private void AdvanceAll(ulong now, bool stalled, ulong gap)
	{
		for (int i = _hooks.Count - 1; i >= 0; i--)
		{
			ZombieHook hook = _hooks[i];
			if (!IsUsable(hook.Component))
			{
				_hooks.RemoveAt(i);
				continue;
			}
			if (stalled)
			{
				// 暂停 / 长卡顿：三条时间轴整体后移，欠账作废（不补发）。
				// 判定收在共用核心 runtime_shared/GatlingVolleyCore.cs（植物/僵尸同源）。
				GatlingVolleyJudge.ShiftTimeline(ref hook.NextAttackMsec, ref hook.NextChainMsec,
					ref hook.BurstStartMsec, gap);
			}
			if (hook.BurstActive)
			{
				AdvanceBurst(hook, now);
			}
			else
			{
				AdvanceNormalAttack(hook, now);
			}
			// 开火动画窗口收尾：窗口一过就把可见头切回 HeadIdle。
			// 放在推进之后 ⇒ 同一帧里刚打出的豌豆（会把窗口续到 now + 220ms）不会被立刻收掉。
			ExpireHeadFire(hook, now);
		}
	}

	/// <summary>普攻：先补完上一轮的连发链，再考虑开启新的一轮。</summary>
	private void AdvanceNormalAttack(ZombieHook hook, ulong now)
	{
		int guard = 0;
		while (guard < MaxPeasPerFrame)
		{
			if (hook.ChainLeft > 0)
			{
				if (now < hook.NextChainMsec)
				{
					return;
				}
				FirePea(hook, 0f);
				hook.ChainLeft--;
				hook.NextChainMsec += GatlingVolleyParams.PeaSpacingMsec;
				guard++;
				continue;
			}
			if (now < hook.NextAttackMsec)
			{
				return;
			}
			// ★ 需求「植物僵尸共用的射击判定」：没有植物不开火、还没进场不开火。
			//   判定不通过时**这一轮直接作废**（不掷大招骰、不开连发链），
			//   并把节拍推到 now + interval。用 `=` 而不是 `+=`：站着不动时不会攒下一串
			//   欠账（否则一旦有植物进场，会立刻把攒下的十几轮一次性砸出去）。
			if (!HasFireTarget(hook.Component))
			{
				hook.NextAttackMsec = now + GatlingVolleyParams.AttackIntervalMsec;
				return;
			}
			hook.NextAttackMsec += GatlingVolleyParams.AttackIntervalMsec;
			BeginAttackCycle(hook, now);
			if (hook.BurstActive)
			{
				// 本轮变成了大招，交给 AdvanceBurst（下一帧起）
				return;
			}
		}
	}

	/// <summary>
	/// 开火前的「目标判定」—— 与**植物僵尸共用同一套引擎判定**
	/// （`FireComponent.CanFireCheckOnce*`，`FireComponent.cs:1756`）。用户要的两条都在里面：
	///
	///   ① **还没进场不攻击**：`:1766` `parent.GetLogicalGlobalPosition().X > groundRight ⇒ false`。
	///      `groundRight = GetMapGroundRight() + gridSize.X × offscreenTargetMarginColumns`
	///      （`:1471`，余量默认 1 列）⇒ 僵尸从屏幕右侧外出生、还没走进场地时，它的 X 大于这个边界，
	///      判定直接失败 ⇒ **进场内才攻击**。（顺带也管「走出场」那一侧。）
	///   ② **没有植物不攻击**：`CheckTarget(...)`（`:1808`）先 `HasOpposingFireCandidates`（`:1862`，
	///      同队列里没有对立阵营候选 ⇒ false），再过数据侧的 `checkRayResources` 逐条 `CheckRayHit`
	///      （`:1836`）。本包的射线 = `AabbRay2DResource_backward`、`TargetPosition = (-2000,0)`
	///      （见 `…FireComponentDefinition.tres`）⇒ **只打正前方同一行、2000px 内的植物**。
	///
	/// ⚠️ 用 `CanFireCheckOnce` 而**不是** `CanFire`：后者多一道 `timer > 0f`（`:1738`），
	///    那是引擎状态机自己的冷却；本插件**绕开了状态机**（自建毫秒节拍，见类注释第二节），
	///    `timer` 归不归零不可控 ⇒ 用 `CanFireCheckOnce` 才是「只问有没有目标」。
	/// ⚠️ 只判 `collectionFlag == -1`（默认）⇒ `CheckTarget` 会取 `parent.instance.collisionFlags`，
	///    与数据侧 `useParentCollision = true`（默认）时的行为逐字一致。
	///
	/// 判定本身**出错时放行**（返回 true）：宁可多打一颗，也不要因为一次异常把僵尸变成
	/// 「站着不还手的靶子」；异常只报一次日志（真出问题日志里看得见）。
	/// </summary>
	private bool HasFireTarget(FireComponent fire)
	{
		try
		{
			TowerDefenseProjectileCreateData data = null;
			Godot.Collections.Array<FireComponentCheckConfig> checks = fire.fireCheckList;
			if (checks != null && checks.Count > 0 && checks[0] != null
				&& GodotObject.IsInstanceValid(checks[0]))
			{
				// `GetProjectile()` 在 projectile 无效时自己返回 null（FireComponentCheckConfig.cs:43）
				data = checks[0].GetProjectile();
			}
			return fire.CanFireCheckOnceByData(data);
		}
		catch (Exception ex)
		{
			if (!_targetCheckFaultReported)
			{
				_targetCheckFaultReported = true;
				Warn("开火前目标判定异常（本条只报一次；已放行，僵尸仍会照常开火）：" + ex.Message);
			}
			return true;
		}
	}

	/// <summary>普攻周期起点：掷 10% 骰子；命中则开大招，否则开一条 7 颗的连发链。</summary>
	private void BeginAttackCycle(ZombieHook hook, ulong now)
	{
			if (GatlingVolleyJudge.RollUltimate(_rng))
		{
			hook.BurstActive = true;
			hook.BurstStartMsec = now;
			hook.BurstEmitted = 0;
			hook.ChainLeft = 0;
			SetSoundEnabled(hook, false);
			_ultimateCount++;
			Info("触发大招（第 " + _ultimateCount + " 次）："
				+ UltimateSeconds.ToString("0.#") + "s 内散射 " + UltimatePeas + " 颗 ±"
				+ ScatterHalfAngleDeg.ToString("0.#") + "°，节拍 "
				+ (UltimateSeconds * 1000.0 / UltimatePeas).ToString("0.0") + "ms/颗。");
			return;
		}
		hook.ChainLeft = PeasPerAttack;
		hook.NextChainMsec = now;
		SetSoundEnabled(hook, true);
		_attackCount++;
	}

	/// <summary>
	/// 大招：第 k 颗的计划时刻 = 起点 + k × (5000/300) ms（k 从 1 数）。
	/// 用「按颗数算时刻」而不是「每次 += 间隔」，可以完全避免浮点累加漂移，
	/// 保证**恰好 300 颗**、**恰好 5 秒**。
	/// </summary>
	private void AdvanceBurst(ZombieHook hook, ulong now)
	{
		int guard = 0;
		while (hook.BurstEmitted < UltimatePeas && guard < MaxPeasPerFrame)
		{
			ulong dueMsec = GatlingVolleyJudge.BurstDueMsec(hook.BurstStartMsec, hook.BurstEmitted);
			if (now < dueMsec)
			{
				return;
			}
			float angle = GatlingVolleyJudge.ScatterAngleDeg(_rng);
			FirePea(hook, angle);
			hook.BurstEmitted++;
			guard++;
		}

		if (hook.BurstEmitted >= UltimatePeas)
		{
			hook.BurstActive = false;
			hook.ChainLeft = 0;
			// 大招结束后重新起算普攻周期（用户选择：大招期间暂停普攻）
			hook.NextAttackMsec = now + GatlingVolleyParams.AttackIntervalMsec;
			SetSoundEnabled(hook, true);
			Info("大招结束：共散射 " + hook.BurstEmitted + " 颗，用时 "
				+ ((now - hook.BurstStartMsec) / 1000.0).ToString("0.0") + "s。");
		}
	}

	/// <summary>
	/// 打出一颗豌豆：把 `fireProjectileList` 里所有发射配置的 `dir` 写成目标角度，
	/// 再走**游戏自己的** `FireComponent.Fire()`（同一段代码 ⇒ 命中/伤害/碰撞旗标必然一致）。
	/// 每次重新取列表与元素，不缓存（见类注释第二节）。
	/// </summary>
	private void FirePea(ZombieHook hook, float angleDeg)
	{
		try
		{
			FireComponent fire = hook.Component;
			Godot.Collections.Array<FireComponentFireProjectileConfig> list = fire.fireProjectileList;
			if (list == null || list.Count == 0)
			{
				return;
			}
			if (list.Count != 1 && !_shapeMismatchReported)
			{
				_shapeMismatchReported = true;
				Warn("fireProjectileList 有 " + list.Count + " 条配置（预期恰好 1 条）；"
					+ "本插件会把它们的 dir 全部写成同一角度，请核对 ComponentSet。");
			}
			int written = 0;
			for (int i = 0; i < list.Count; i++)
			{
				FireComponentFireProjectileConfig cfg = list[i];
				if (cfg == null || !GodotObject.IsInstanceValid(cfg))
				{
					continue;
				}
				cfg.dir = angleDeg;
				written++;
			}
			if (written == 0)
			{
				return;
			}
			fire.Fire();

			// ★ 打出去了 ⇒ 让头播「超级机枪射手」的射击动画（见类注释第七节「开火动画」）。
			//   纯外观：内部自己有 try/catch + 懒解析，失败绝不影响上面这次发射。
			MarkHeadFire(hook, Time.GetTicksMsec());
		}
		catch (Exception ex)
		{
			// 发射失败不能把「整帧节拍」炸掉（否则同一帧里后续僵尸全被跳过）。
			if (!_fireFaultReported)
			{
				_fireFaultReported = true;
				Warn("调用 FireComponent.Fire() 失败（本条只报一次；僵尸仍会行走/啃食）：" + ex.Message);
			}
		}
	}

	/// <summary>普攻时打开 vanilla 开火音效；大招期间静音（300 颗会在 5 秒内砸出 180 次/秒的音效）。</summary>
	private void SetSoundEnabled(ZombieHook hook, bool enabled)
	{
		FireComponent fire = hook.Component;
		if (fire == null || fire.IsReleased)
		{
			return;
		}
		string want = enabled ? FireAudioName : "";
		if (!string.Equals(fire.fireAudioName, want, StringComparison.Ordinal))
		{
			fire.fireAudioName = want;
		}
	}

	// ---------------------------------------------------------------- 挂载

	private void TryHookCharacter(TowerDefenseCharacter character)
	{
		try
		{
			TowerDefenseCharacterConfig config = character.config;
			if (config == null || !GodotObject.IsInstanceValid(config))
			{
				return;
			}
			if (!string.Equals(config.name, CharacterConfigName, StringComparison.Ordinal))
			{
				return;
			}
			ComponentManager components = character.componentManager;
			if (components == null)
			{
				return;
			}
			FireComponent fire = components.GetRuntime<FireComponent>(FireInstanceId);
			if (!IsUsable(fire))
			{
				// ⚠️ 这条以前是**静默** return 的，结果是「一颗豌豆都不出、日志里什么都看不到」。
				// 真实踩过的坑：角色场景没声明 ComponentSet ⇒ 发射组件根本没被创建
				//（基场景那份 TowerDefenseZombieComponentSet.tres 里没有 FireComponent）。
				if (!_fireMissingReported)
				{
					_fireMissingReported = true;
					Warn("找到了「" + CharacterConfigName + "」但拿不到组件 \"" + FireInstanceId
						+ "\"（豌豆不会发射；僵尸仍会正常行走/啃食）。"
						+ "最常见原因：角色场景根节点漏了 `ComponentSet = ExtResource(…)`，"
						+ "于是基场景那份不含 FireComponent 的组件集生效。");
				}
				return;
			}
			AddHook(fire);
		}
		catch (Exception ex)
		{
			if (!_hookFaultReported)
			{
				_hookFaultReported = true;
				Warn("读取僵尸发射组件失败（本条只报一次；不影响僵尸正常行走/啃食）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 组件是否仍可用。
	/// ⚠️ CharacterComponentRuntime **不是 GodotObject**（AppendTo 里是纯 C# 抽象类），
	/// 所以既没有 `GodotObject.IsInstanceValid` 也没有 `GetInstanceId()`；
	/// 只能看 `IsReleased` + `Owner`（Owner 是 TowerDefenseCharacter，是 Node）。
	/// </summary>
	private static bool IsUsable(FireComponent fire)
	{
		try
		{
			return fire != null && !fire.IsReleased && fire.Owner != null
				&& GodotObject.IsInstanceValid(fire.Owner);
		}
		catch
		{
			return false;
		}
	}

	private void AddHook(FireComponent fire)
	{
		// 引用相等即「同一个组件」：CharacterComponentRuntime 不是 GodotObject，没有 GetInstanceId。
		for (int i = 0; i < _hooks.Count; i++)
		{
			if (ReferenceEquals(_hooks[i].Component, fire))
			{
				return;
			}
		}

		ZombieHook hook = new ZombieHook();
		hook.Component = fire;
		hook.NextAttackMsec = Time.GetTicksMsec() + GatlingVolleyParams.AttackIntervalMsec;
		hook.ChainLeft = 0;
		hook.NextChainMsec = 0UL;
		hook.BurstActive = false;
		hook.BurstStartMsec = 0UL;
		hook.BurstEmitted = 0;
		hook.Head = null;
		hook.HeadFireUntilMsec = 0UL;
		_hooks.Add(hook);
		SetSoundEnabled(hook, true);
		Info("已挂上第 " + _hooks.Count + " 只「" + CharacterConfigName + "」的发射组件。");
	}

	// ---------------------------------------------------------------- 卡库

	/// <summary>
	/// 把本卡补进**共享卡库** `GeneralZombie` 的 `Zombie` 分类 —— 这一步决定
	/// 「**选卡界面 / 关卡编辑器里能不能选到它**」。
	///
	/// 依据（源码位置）：
	///   · `Almanac.cs:220` `zombiePacketBank = GetPacketBankData("GeneralZombie")` —— **同一实例**；
	///   · `Almanac.InitZombie()`（418 行）读 `zombiePacketBank.GetCategory("Zombie")`；
	///   · `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync` 也按
	///     `packetBankData.category[分类]` 列卡（`packetBankType` 默认为 `GeneralZombie` 系）。
	///   ⇒ 补一处 = 三处同时生效。
	///
	/// 幂等且可恢复：每次扫描都检查一遍（几十条字符串比较，开销可忽略），缺了再补，补上才打日志。
	/// </summary>
	private void TryPatchCardBanks()
	{
		try
		{
			ResourceManager manager = ResourceManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;   // 资源管理器还没起来，下次扫描再说
			}
			System.Collections.Generic.Dictionary<string, TowerDefensePacketBankData> banks =
				manager.TOWERDEFENSE_PACKETBANKS;
			if (banks == null || banks.Count == 0)
			{
				return;   // 全量资源还在加载
			}

			string[] keys = _bankKeys ?? (_bankKeys = ResolveDerivedBankKeys());
			for (int i = 0; i < keys.Length; i++)
			{
				TowerDefensePacketBankData bank;
				if (!banks.TryGetValue(keys[i], out bank) || bank == null
					|| !GodotObject.IsInstanceValid(bank))
				{
					continue;
				}
				if (EnsureCategoryContains(bank, keys[i]))
				{
					_bankPatchCount++;
				}
			}
		}
		catch (Exception ex)
		{
			if (!_bankFaultReported)
			{
				_bankFaultReported = true;
				Warn("补共享卡库「" + ZombieCategory + "」分类失败（本条只报一次；"
					+ "不影响僵尸本体与豌豆发射）：" + ex.Message);
			}
		}
	}

	private bool EnsureCategoryContains(TowerDefensePacketBankData bank, string bankKey)
	{
		Godot.Collections.Dictionary categories = bank.category;
		if (categories == null || !categories.ContainsKey(ZombieCategory))
		{
			return false;
		}
		Godot.Collections.Array list = categories[ZombieCategory].AsGodotArray();
		if (list == null)
		{
			return false;
		}
		for (int i = 0; i < list.Count; i++)
		{
			if (string.Equals(list[i].AsString(), CharacterConfigName, StringComparison.Ordinal))
			{
				return false;   // 已经在里面（幂等）
			}
		}
		list.Add(CharacterConfigName);
		categories[ZombieCategory] = list;   // 显式回写（Array 是引用语义，写回最稳）
		Info("已把「" + CharacterConfigName + "」补进卡库「" + bankKey + "」的「"
			+ ZombieCategory + "」分类 ⇒ 选卡界面/关卡编辑器里可以选到它了。");
		return true;
	}

	/// <summary>
	/// 图鉴僵尸页**运行时去重**（需求 2026-09-22）。
	///
	/// 根因（`Prefab/GUI/DialogBox/Almanac/Almanac.cs`）：
	///   `InitZombie()`（411-431 行）有**两条独立来源**，且**都不去重** ——
	///     · 418 行：遍历共享卡库的 `Zombie` 分类（= 本插件补进去的那条）；
	///     · 427 行：无条件遍历 `XWModContentCatalog.GetPackets(plants: false)`
	///       （引擎把包内 `Resources/Cards/` 注册成 `Packet` 类别后会**自动收录**）
	///   ⇒ 本卡在图鉴僵尸页出现**两条**。
	///
	/// 为什么不能「删掉其中一条」：
	///   · 卡库那条（`TryPatchCardBanks`）删不得 —— 选卡界面
	///     `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync:509-514` 是
	///     `packetBankData.category[分类]` **直读**，而 `ResourceManager.BuildExpandedPacketBanks:638-647`
	///     只从内置 `PacketBankResource.json` 构建、**不合并** Mod 注册 ⇒ 不补就选不到；
	///   · `Resources/Cards/` 那条也删不得 —— 它是 `TOWERDEFENSE_PACKETS`
	///     （`ResourceManager.cs:529` ← `roots.PacketPathByName`）里 config 的来源，
	///     删了 `TowerDefenseManager.GetPacketConfigReadOnly(key)` 直接返回 null。
	///   ⇒ 只剩「在图鉴侧就地去掉重复项」这一条路。
	///
	/// 做法：反射取 `Almanac._zombieLogicalConfigs` 的**列表引用**，把 `saveKey` 等于
	///   本卡的重复项（保留最靠前的一条）原地 `RemoveAt`，再用**公开**的
	///   `Almanac.QueueZombieVirtualRefresh()` 重建虚拟列表。
	///   共享卡库 / `_packetPaths` / 解锁状态**一个字节都不动**。
	///
	/// 幂等且安全：
	///   · 列表 ≤1 条（未建列表 / 只补了一半）时直接返回，不动它；
	///   · 去重在「从后往前」遍历时保留最先遇到的命中项，**顺序不变**；
	///   · 每帧扫描一次（10 帧间隔），`InitZombie()` 每次重建列表后都会被重新收敛；
	///   · `QueueZombieVirtualRefresh()` 自带 `_zombieInitialized` 守卫，不会提前初始化。
	/// </summary>
	private void TryDedupeAlmanacZombie(Almanac almanac)
	{
		try
		{
			if (almanac == null || !GodotObject.IsInstanceValid(almanac))
			{
				return;
			}
			if (almanac.ZombieLogicalEntryCount <= 1)
			{
				return;   // 僵尸页还没建过列表，或本来就只有一条
			}
			List<TowerDefensePacketConfig> list = GetZombieLogicalConfigs(almanac);
			if (list == null || list.Count <= 1)
			{
				return;
			}

			int kept = 0;
			int removed = 0;
			for (int i = list.Count - 1; i >= 0; i--)
			{
				TowerDefensePacketConfig config = list[i];
				if (config == null || !GodotObject.IsInstanceValid(config))
				{
					continue;
				}
				if (!string.Equals(config.saveKey, CharacterConfigName, StringComparison.Ordinal))
				{
					continue;
				}
				kept++;
				if (kept == 1)
				{
					continue;   // 从后往前，第一个命中的就是原本最靠前的那条 ⇒ 保留、顺序不变
				}
				list.RemoveAt(i);
				removed++;
			}
			if (removed == 0)
			{
				return;
			}

			_almanacDedupeCount += removed;
			almanac.QueueZombieVirtualRefresh();   // public，不必反射
			Info("图鉴僵尸页去重：抹掉 " + removed + " 条重复的「" + CharacterConfigName
				+ "」（共享卡库 + 引擎 Mod 内容目录各列了一次；累计 " + _almanacDedupeCount
				+ " 条）。选卡界面 / 关卡编辑器不受影响。");
		}
		catch (Exception ex)
		{
			if (!_dedupeFaultReported)
			{
				_dedupeFaultReported = true;
				Warn("图鉴僵尸页去重失败（本条只报一次；不影响僵尸本体、豌豆发射与选卡）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 反射拿 `Almanac._zombieLogicalConfigs` 的列表引用。字段名对不上（换版本）就返回 null，
	/// 调用方按「不去重」处理 —— 绝不抛、绝不影响其它功能。
	/// </summary>
	private static List<TowerDefensePacketConfig> GetZombieLogicalConfigs(Almanac almanac)
	{
		if (!_zombieLogicalFieldProbed)
		{
			_zombieLogicalFieldProbed = true;
			try
			{
				_zombieLogicalField = typeof(Almanac).GetField(
					"_zombieLogicalConfigs",
					BindingFlags.Instance | BindingFlags.NonPublic);
			}
			catch
			{
				_zombieLogicalField = null;
			}
		}
		if (_zombieLogicalField == null)
		{
			return null;
		}
		try
		{
			return _zombieLogicalField.GetValue(almanac) as List<TowerDefensePacketConfig>;
		}
		catch
		{
			return null;
		}
	}

	/// <summary>
	/// `GeneralZombie` 自身 + 所有通过 `Include` **间接包含**它的卡库
	/// （`ResourceManager.BuildExpandedPacketBank` 是递归合并语义）。
	/// json 读不到就回落 `FallbackDerivedBankKeys`（离线算好的真实值）。
	/// </summary>
	private string[] ResolveDerivedBankKeys()
	{
		try
		{
			Json json = GD.Load<Json>(PacketBankResourcePath);
			if (json == null || json.Data.VariantType != Variant.Type.Dictionary)
			{
				return FallbackDerivedBankKeys;
			}
			Godot.Collections.Dictionary raw = json.Data.AsGodotDictionary();
			List<string> result = new List<string>();
			foreach (Variant bankKey in raw.Keys)
			{
				string name = bankKey.AsString();
				if (string.Equals(name, RootZombieBankKey, StringComparison.OrdinalIgnoreCase)
					|| IncludesTransitively(raw, name, RootZombieBankKey,
						new HashSet<string>(StringComparer.OrdinalIgnoreCase)))
				{
					result.Add(name);
				}
			}
			if (result.Count == 0)
			{
				return FallbackDerivedBankKeys;
			}
			return result.ToArray();
		}
		catch (Exception ex)
		{
			Warn("读 PacketBankResource.json 失败，改用兜底卡库列表：" + ex.Message);
			return FallbackDerivedBankKeys;
		}
	}

	private static bool IncludesTransitively(
		Godot.Collections.Dictionary raw, string fromBank, string target, HashSet<string> visited)
	{
		if (!raw.ContainsKey(fromBank))
		{
			return false;
		}
		Godot.Collections.Dictionary bank = raw[fromBank].AsGodotDictionary();
		if (bank == null || !bank.ContainsKey("Include"))
		{
			return false;
		}
		Godot.Collections.Array includes = bank["Include"].AsGodotArray();
		if (includes == null)
		{
			return false;
		}
		for (int i = 0; i < includes.Count; i++)
		{
			string name = includes[i].AsString();
			if (string.IsNullOrEmpty(name) || !visited.Add(name))
			{
				continue;
			}
			if (string.Equals(name, target, StringComparison.OrdinalIgnoreCase)
				|| IncludesTransitively(raw, name, target, visited))
			{
				return true;
			}
		}
		return false;
	}

	// ---------------------------------------------------------------- 日志

	private static string Pct(double v)
	{
		return (v * 100.0).ToString("0.#");
	}

	private void Info(string message)
	{
		try
		{
			if (_context != null)
			{
				_context.Log(message);
				return;
			}
		}
		catch
		{
			// 落到 GD.Print
		}
		try
		{
			GD.Print(LogPrefix + message);
		}
		catch
		{
			// 日志本身绝不能成为异常源：入口三回调抛异常 = 无条件整包回滚。
		}
	}

	private void Warn(string message)
	{
		try
		{
			if (_context != null)
			{
				_context.Warn(message);
				return;
			}
		}
		catch
		{
			// 落到 GD.PushWarning
		}
		try
		{
			GD.PushWarning(LogPrefix + message);
		}
		catch
		{
			// 同上：日志不许抛。
		}
	}
}
