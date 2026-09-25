---
name: pvz-hybrid-zombie-authoring
description: 为《植物大战僵尸杂交版》(Godot 4 + C#) 从零制作或改造一个「僵尸」Mod 的端到端流程——选基底僵尸、建包（13 个文件）、本体配置（血量/濒死/啃食伤害）、护具 Armor 三件套、换头「三节点」结构、换外观（经典 reanim 官方素材直转）、给僵尸加发射（自建 Fire 组件 + 托管插件驱动节拍）、植物僵尸共用的攻击判定（没植物不开火、进场才开火）、子弹生成点对齐炮口（FireMarker）、图鉴去重，以及闸门/负向测试/幂等全套离线验证。当用户要求「做个僵尸 Mod」「把僵尸换成 XX」「给僵尸换头/换贴图/换动画」「让僵尸会开枪/会发射」「僵尸加护具」「植物僵尸的攻击判定」，或提到 .pmod / Zombie / 僵尸 / 护具 / Armor / FireMarker / 子弹生成点 / ModAssembly.dll / 图鉴僵尸页 时使用。
agent_created: true
---

# 制作 PvZ 杂交版「僵尸」Mod —— 端到端流程

> 姊妹技能：`pvz-hybrid-mod-authoring`（全量/通用，含包格式与编辑器）、`pvz-hybrid-plant-authoring`（植物端到端）。
> 本技能只讲**僵尸**这条路，以及它与植物的**每一个差异**。

## 0. 权威来源与边界（务必先看）

| 用途 | 路径 |
|---|---|
| **源码真相（唯一有 `.cs` 的那棵树）** | `D:\zzz\pvzHE\解包\植物大战僵尸杂交版V0.28\` |
| 基底僵尸（读报/普通/路障…） | `Asset\Anime\Character\Zombie\Chapter1\<Name>\` |
| 内置僵尸基场景 | `Prefab\TowerDefense\Character\TowerDefenseZombie.tscn` |
| 内置僵尸组件集 | `Prefab\TowerDefense\Character\ComponentSets\TowerDefenseZombieComponentSet.tres` |
| 护具体系 | `Registry\Armor\`、`Script\Component\TowerDefense\Character\Armor\` |
| 发射体系 | `Script\Component\TowerDefense\Character\FireComponent\FireComponent.cs` |
| 图鉴 | `Prefab\GUI\DialogBox\Almanac\Almanac.cs` |
| 用户 Mod 目录 | `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\` |
| 实况日志 | 同上目录 `PVZHE_Logs\` |

**边界**：游戏内「PVZ Mod 编辑器」（F3）**AI 无法驱动**；但 `.pmod` 只是「zip + 根 `mod.json`」，
纯脚本可写。**动手前先确认用户已有可复制的生成器**（本仓 `build_zombie_super_gatling_paper.py` 为样板，
160KB，含全部自检与金标）。

---

## 1. 先做四个决定（决定后面 80% 的工作量）

### 决定 A：复用什么基底僵尸？

| 基底 | 特点 | 什么时候选 |
|---|---|---|
| `Chapter1\Paper\`（读报僵尸） | **自带护具 + 状态机 + 暴走**（`ArmorHitpointsEmpty("Paper")` → `ToGasp` → 3 倍速） | 要护具 / 要「血量掉光后暴走」的机制 |
| `Chapter1\Normal\`（普通僵尸） | 最干净：只有身体 + 头 | 只换外观、不加机制 |
| 其它（路障/铁桶/舞王…） | 各自带护具或特殊动画 | 想白拿它的护具/动画 |

⚠️ **基底僵尸的「脚本」不能复制进包**（包内禁 `.cs`）—— 见 Step 4 的剥离手法。

### 决定 B：要僵尸「发射」吗？

**僵尸默认没有 `FireComponent`**（`TowerDefenseZombieComponentSet.tres` 里没有 Fire，只有 Armor/Attack 等）。
「啃食」是 `AttackComponent` 默认的 `attackType = "Eat"`，**不是发射**。
⇒ 只要想做「会开枪的僵尸」，就必须：

1. 数据侧：新建 `…ComponentSet.tres`，**基于内置僵尸组件集再加 1 个 FireComponent**；
2. 代码侧：写托管插件（僵尸没有植物那种「内置发射动画链」，节拍要自己驱动）。

### 决定 C：外观走哪条路？

* **官方素材直转**（首选）：经典未重置版 reanim → 重置版 `.dat`/`.tres`/图集（见 `references/zombie-skin-and-head.md`）。
* **只换头**：走「三节点换头」（`HeadShadow` + `HeadHolder` + `Head`）—— 见 Step 5 与 references。
* **自制逐帧**：能走，但要处理「自制 `.dat` 皮肤静止」⇒ 运行期 `forceLocalRender` + `forceCpuPoseRender`。

### 决定 D：要不要图鉴 / 卡库？

僵尸的卡库是 `GeneralZombie`，**补一处 = 选卡界面 / 关卡编辑器 / 图鉴僵尸页同时生效**
（`Almanac.cs:220` 取的是**同一个实例**，不像植物页那样深拷贝）。
但副作用是**图鉴僵尸页会多出第二条** ⇒ 见 Step 9。

---

## 2. 关键路径（按需查证）

```
<包>/
  mod.json
  Resources/Cards/<Key>.tres                                  ① 卡片（类型 ZOMBIE）
  Resources/Characters/Zombies/<Key>/Config/TowerDefense<Key>.tres       ② 本体配置
  Resources/Characters/Zombies/<Key>/Packet/<Key>.tres                 ③ 卡包条目
  Resources/Characters/Zombies/<Key>/Scene/<Key>.tscn                  ④ 场景
  Resources/Characters/Zombies/<Key>/Scene/<Key>ComponentSet.tres      ⑤ 组件集
  Resources/Characters/Zombies/<Key>/Scene/<Key>FireComponentDefinition.tres  ⑥ 发射定义（要发射才需要）
  Resources/Characters/Zombies/<Key>/Sprite/<Key>.tscn                 ⑦ 精灵场景
  Resources/Characters/Zombies/<Key>/Armor/Zombie<Key>ArmorData.tres   ⑧ 护具数据
  Resources/Characters/Zombies/<Key>/Armor/Config/Zombie<Key>Armor<X>.tres   ⑨ 护具槽配置
  Resources/Animations/<Skin>.{dat,tres,Atlas.png}                     ⑩ 外观三件套（换贴图时）
  Runtime/ModAssembly.dll                                             ⑪ 托管插件
  <中文名>.pvzmodeproject                                              ⑫ 工程标记（**不进包**）
```

**路径硬约束**：`Resources/Characters/Zombies/<Key>/{Scene,Sprite}/<Key>.tscn` —— 恰 **6 段**；
类别目录必须是 `Zombies`；文件名必须等于 `<Key>`。违反 = `ModLoader.InferRuntimeEntry` 推不出类别。

---

## 3. 标准流程（12 步）

### Step 0 — 把需求问全

必须问清：① 基底僵尸？② 要不要护具、护具多少血？③ 要不要发射、射速/弹数/散射？
④ 头部贴图换不换、用哪个角色的？⑤ 要不要「没植物不开火、进场才开火」？
⑥ 血量/啃食伤害/卡片价格冷却？⑦ 大招之类的特殊机制？
**缺一项后面就得返工**（尤其④⑤，它们决定要不要写插件）。

### Step 1 — 复制生成器，别从零写

```bash
cp build_zombie_super_gatling_paper.py build_zombie_<新Key>.py
```

生成器要包含：`self_check()`（含 `*_GOLDEN` 金标）、场景/配置渲染函数、`Build` 落盘、
`dotnet build` 调用（或独立 `build_runtime.py`）、打包 `.pmod`、安装到 `Mods/`、镜像到 `%APPDATA%`。
**改常量永远只改一个文件**。

### Step 2 — 定 Key 与中文名

* `<Key>`：ASCII，如 `ZombieSuperGatlingPaper`（**进图鉴的键、也是插件识别角色的锚**）。
* 中文名：`translate` 里**直接写中文**（不需要 `translations.csv`；写了反而要多维护一份）。
* 每个 `.tres` 的 `script_class` / `metadata/_custom_type_script` 要与内置基底对齐。

### Step 3 — 包内 13 个文件

逐个从基底改。最容易漏的是 **③ Packet**（没它卡在包里但选不到）与 **⑨ 护具槽**。

### Step 4 — ★★ 场景必须**显式声明** `ComponentSet`（在 `script` **之前**）

基场景 `TowerDefenseZombie.tscn:10` 自带 `ComponentSet = ExtResource(...)`
⇒ **子场景不写就继承它**。而它指向的 `TowerDefenseZombieComponentSet.tres` 里**没有 FireComponent**
⇒ 「僵尸不会开枪」而且是**零日志**（组件根本没被创建）。

```gdscript
[node name="Zombie<Key>" instance=ExtResource("1")]
ComponentSet = ExtResource("<你的组件集 id>")     # ← 必须在 script 之前
script = ExtResource("<内置僵尸脚本 id>")
```

**继承内置脚本时**：包内**禁止** `.cs` / `.scn` / `.res` ⇒ 只能引用**内置**的 `res://` 路径，
且要**剥掉**基底场景里指向包内的 `ExtResource` 行（否则 ModLoader 会拒整包）。

### Step 5 — 精灵场景：换头走「三节点」

**为什么不能直接换子精灵的贴图**（我踩过）：`CollectOwnedChildBindings`（`:5385`）只看节点类型，
`_Draw`（`:9534`）首行就 `return` ⇒ **子精灵的切片一定被父批次代画、采样父那一张图集**
⇒ 跨 `.tres` / 自制皮肤的子精灵 = **别的角色碎片拼贴**。

**修法（唯一可行）**：身体下留三个节点：

| 节点 | 类型 | 作用 |
|---|---|---|
| `HeadShadow` | 与身体同类精灵 | `visible = false` + **全层 false** ⇒ 零切片；只为吃 `UpdateChild()` 的每帧定位 |
| `HeadHolder` | 普通 `Node2D`（identity） | 打断「父代画」的容器 |
| `Head` | 独立渲染的精灵 | 给人看的那个；写 `z_index = 1` 压住身体 |

> **⚠️ 反过来「要让子精灵排在父后面」怎么办？**（贴图光环、脚底特效等）
> 这时 `z_index = -1` **完全无效** —— 被父代画的子精灵，它的 `ZIndex` 排序位取的是**父精灵**的
> `EffectiveZIndex`。**唯一**有效手段是显式写 `insertLayerId = <id>`（按**父精灵**的
> `layerDictionary` 解释；一般 `id = 0` 是内建隐藏背景板，可见层从 `1` 起 ⇒ 取 `0` 就画在父**后面**）。
> 详见 `references/zombie-skin-and-head.md` **§9**。

两头（`HeadShadow` 与 `Head`）的 `scale` / `offset` / `offsetRotate` **逐字相同**，
位姿由插件每帧从影子抄给可见头（见 Step 8）。
**原版头部的 7 个图层必须在身体上显式关掉**（`Animation/LayerVisible/<原头层> = false`），
否则原头会从头盔底下透出来。

> **⚠️⚠️ 写 `Animation/LayerVisible/…` 时，引号必须包住「整条」属性名**（2026-09-25 用一天换来的教训）：
> 层名含**空格或非 ASCII**（`图层_1` / `skin2_2 ` / `cloak1 复制` …）时：
> ```
> 正确： "Animation/LayerVisible/图层_1" = false     ← 官方写法（全库 6941 个文件零例外）
> 错误： Animation/LayerVisible/"图层_1" = false     ← 只包末段 ⇒ 这一行**完全无效**
> ```
> 坏写法**不报错、不留日志**：`_Set()` 里 `layerDictionary.ContainsKey()` 拿到带引号的名字 ⇒ 为假 ⇒
> 直接 `return true` ⇒ 该层保持**初值 `true`**（`:9049-9069` 没写进 `_layerVisible` 的下标一律按可见算）
> ⇒ **永远可见**。后果实测：`HeadShadow` 的「全层 false」白写 6 层（含**另一张脸 `skin2_2`**、皇冠、
> 花瓣、火圈、光环、披风）⇒ 身体上**多长出一个完整的头**，且光环/披风怎么关都关不掉。
> ⇒ 生成器统一走 `_prop(key)`（判据作用在**整条 key** 上）+ 常驻自检 `_bad_prop_keys()`；
> 全库对照扫描 `.cache/_sq_quotefix_scan.py`。**ASCII/纯数字层名裸写是对的**（`Animation/LayerVisible/1 = true`）。

### Step 6 — 外观三件套

见 `references/zombie-skin-and-head.md`（含经典 reanim 直转、`.dat` 二进制规格、头对位反解）。
**关键：僵尸朝左**（`scale = (-1, 1)` 横翻）⇒ 所有屏幕坐标都要过横翻矩阵，别直接加。

### Step 7 — 发射：数据侧只做两件事

1. **组件集**：基于内置僵尸组件集 + 加 1 个 FireComponent（`InstanceId` 用固定的接线键）。
2. **发射定义** `.tres`：
   * `firePosMarkerPaths = [NodePath("…/HeadSlot/FireMarker")]` —— 指向 Marker2D（**子弹生成点**，见 references）；
   * `fireProjectileList` 只留 **1 条** config（`Fire()` 一次遍历全部弹 ⇒ 逐颗发射必须在插件里循环）；
   * `speed` 为**负**（僵尸朝左，负值才是向前）；
   * 僵尸的场景里要有真实 `Marker2D` 节点（`firePosMarkerPaths` 必须是真 Marker2D）。

⚠️ **数据侧做不到的事**（只能插件）：概率 / 延时改模式 / 真随机 / 改投掷单位 / 逐颗发射 / 特殊大招。

### Step 8 — 托管插件（僵尸的真正工作量在这里）

入口类放在**无命名空间**下（`runtimeEntryType` 是类名），实现 `IXWModRuntimeEntry`，
三个回调（`Initialize` / `OnAllModsLoaded` / `Shutdown`）**一律不许抛**（抛了 = 无条件整包回滚）。

插件的几件典型职责（照抄本仓 `SuperGatlingPaperRuntimeEntry.cs`）：

| 职责 | 要点 |
|---|---|
| 自建节拍 | 挂 `SceneTree.process_frame` 自己推进毫秒时间轴（**不要**去骗内置状态机） |
| 射击判定 | 必须用 `FireComponent.CanFireCheckOnceByData()`（**不是** `CanFire` —— 后者多一道 `timer > 0` 会把节奏拖一轮）；「没植物不开火、进场才开火」都在这里 |
| 开火动画 | 头独立渲染后，头 clip 完全归插件管：`MarkHeadFire()` 切 `HeadFire` 并**续**窗口；`SetHeadClip()` 只在 clip 真变了才 `SetClip()`（否则每颗豌豆都把动画打回第 0 帧） |
| 换头位姿 | 每帧把影子 `Position`/`Rotation` 抄给可见头（10 帧一档的扫描会抖） |
| **子弹生成点** | 每帧 `marker.GlobalPosition = head.GlobalTransform * HeadMuzzleLocal`（见 references/zombie-fire-and-marker.md） |
| 卡库入库 | 把角色补进 `GeneralZombie` 的派生库（按 `Include` 闭包**运行期**算，别写死） |
| 图鉴去重 | 反射去 `_zombieLogicalConfigs` 的重复项 + 公开的 `QueueZombieVirtualRefresh()` |

**编译**：`python runtime_src_zombie_super_gatling/build_runtime.py --check`（两次编译比 sha256）。
⚠️ **生成器不会自动重编 DLL** —— 改了 `.cs` 必须单独跑一次构建，否则打进包的还是旧 DLL（踩过：DLL 停在两天前）。

### Step 9 — 让它「能被选到」+ 图鉴

* 补进**僵尸根卡库** `GeneralZombie` 的 `Zombie` 分类，以及 `Include` 闭包算出的派生库
  （实测 `['GeneralZombie','TotalZombie','Total']`）——只补根库的话，`debugPacketOpenAll` 切到 `Total` 又看不到。
* **图鉴僵尸页会多一条**（`Almanac.cs:411-435` 两条来源都不去重）⇒ 运行期反射去重（Step 8 表末行）。

### Step 10 — 写/跑闸门（**不能省**）

见 §5 与 `references/zombie-package-and-gates.md`。**离线能抓的错绝不留给实机**。

### Step 11 — 装机

生成器负责：写 `dist/<中文名>.pmod` → 复制到 `Mods/` → 解到 `Mods/<中文名>/`（**72 个标准目录**）→
登记 `enabled_mods.json`（**保留别人的条目**）→ 登记 `mod_editor_recent_projects.cfg`。
**改完包重启游戏即可**，别手删 `ModsCache`。

### Step 12 — 实机验收

离线验不了的（并且**必须如实告诉用户**）：
「头真的画对了 / 动画在动 / 子弹真的从炮口出来 / 没被遮挡 / 图鉴只有一条」。
先看 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\PVZHE_Logs\` 的加载日志。

---

## 4. 坑 Top 10（僵尸专属，每条都能白忙半天）

1. **★★ 场景没显式写 `ComponentSet` ⇒ 发射组件根本不创建，且零日志**（Step 4）。
2. **★★ 子精灵必被父代画** ⇒ 换头必须「三节点」（Step 5），直接换贴图只会得到别的角色碎片。
   **同一条规则的第二个面**：既然被父代画，子精灵自己的 **`z_index` 也失效** ⇒ 想让它排在父**后面**
   只能写 `insertLayerId = <id>`（`-1` = 默认 ⇒ 回落顶层 = 画在最前）。
   详见 references/zombie-skin-and-head.md §9。
3. **★★ 子弹生成点 = `firePosMarkerPaths` 指向的 `Marker2D.GlobalPosition`**，
   不是角色原点、也不是炮口；而 `HeadSlot` **是原版护具用的静态插槽、不跟头部美术**
   （「挂在 HeadSlot 下就跟着头」是错的）⇒ 见 references/zombie-fire-and-marker.md。
4. **★ 头在摆 ⇒ 静态值只能对上参考帧**：只要头跟 `anim_head1` 逐帧摆，炮口每帧都在动
   （Idle 段就跨 20px）⇒ 必须插件每帧覆写。
5. **★ `CanFire` vs `CanFireCheckOnceByData`**：自建节拍必须用后者。
6. **★ 僵尸朝左**（`scale=(-1,1)`）⇒ 「屏幕向右上微移」**不能直接加到 `offset` 上**（横向会反向）；
   必须加在**锚点**上再反解（本仓 `HEAD_PLACE_SHIFT`）。
7. **★ 改完 `.cs` 生成器不会重编 DLL** ⇒ 包里的还是旧 DLL（对比 mtime 立刻能看出来）。
8. **★ 图鉴僵尸页两条** ⇒ 运行期去重。
9. **★★ Godot 对 `.tscn` 的坏写法「静默容忍」**——两类都已实证，都不报错、零日志：
   * **节点头收尾必须是 `]`**：写成 `>` ⇒ **静默吞行**（节点不建）；断言别写成不带闭合括号的前缀匹配
     （**断言与实现同错 = 假绿**）。
   * **属性名引号要包「整条」**：`Animation/LayerVisible/"图层_1" = false`（只包末段）⇒ 该行**完全无效**，
     层保持默认 `true`（详见 Step 5 的警示框）⇒ 会凭空多出一个头。
   ⇒ 规程：**只认官方同源文件的写法**（拿同一份 `.tres` 的官方 `.tscn` 逐字对照），
     再配「复刻负向」（把实现改回坏写法，断言必须打红）。
10. **★ 「断言与实现同错 = 假绿」**：① 恒真比较（拿常量比由同一常量渲染的文本）⇒ 加 `*_GOLDEN` 金标；
    ② 门控共用 ⇒ 硬需求写成无开关不变量；③ 前缀匹配漏字节；④ 目标行在当前口径下不生成 ⇒ **打桩注入**。
    **写完/改完断言必须逐条篡改常量确认报警。**
11. **★★ 尺寸 / 位置类需求（「头调大调小一点」「头往上挪一点」）都别目测猜** —— 目测必被下一张图推翻。
    **尺寸**（用户给目标截图）走三步：**① 泛洪分割**量参考图轮廓（从四边泛洪，黑框/草坪判据）→
    **② 离线合成渲染**扫候选倍率（共享图集 + `Manifest` + `PIL.AFFINE` 逆矩阵，量真实像素 bbox）→
    **③ 同高度归一并排**目视复核。至少两个独立判据，取落在参考图两侧最近的一档。
    ⚠️ 归一化要**剔掉尺寸恒定的装饰**（固定像素的光环会稀释倍率差异）。
    ⚠️ 改完 `head_scale` **必须重解 `head_offset`**（`A = rot_scale(θ, −s, +s)` 含节点 scale）。
    **位置**（「跟那张图一样高」）拿**两张真实图直接比**，**别经过离线渲染**（帧/姿势未必一致），四个坑：
    ① 画幅不同 ⇒ 绝对 y 不可比，先找「与头无关」的身体标尺；
    ② 标尺**不能选会被遮挡的量**（裤子常被脚底光环截断 ⇒ 改用**头宽**，且只能比**宽**）；
    ③ 头块取「**最靠上的橙色大块**」（脚底光环常比头大好几倍）；
    ④ 头的锚点**必须"刚性"** —— 头 bbox 含**火焰花瓣**且火焰**逐帧变**，
       顶/底/中心都会被帧差污染（实测「头块中心」少算 **20%**）；只用**脸 / 王冠**这种刚性子块。
    ⇒ 位移**加在锚点上**反解，别直接加到 `offset` 上（`A` 含横翻 + 交叉项）。
    ★★ **「改为现在的 N 倍」= 相对放大**（在上次定标结果上再乘 N，不是「N 倍于原素材」），三条口径：
    ⑴ `head_scale = 旧值 × N`；⑵ 解 `offset` 时**沿用当前 `shift`**（否则上移量会被一起解掉、头掉回原位）；
    ⑶ **旧 `offset` 不许复用**，必须重解。✅「原地放大」的判据 = **头块落点中心逐字不变**。
    ⚠️ 别用启发式取块量放大前后的尺寸（火焰花瓣逐帧变 ⇒ 两倍率下不是同一块，实测给出 `1.19` 假比值）；
    尺寸比报**解析值**。⭐ 对照图最干净画法：同 `box`、`k`、`shift` 渲两张，画**解析锚点十字**；
    且离线渲染落盘是 **RGBA** ⇒ 「旧轮廓叠新图」**直接取 alpha 通道**（`MinFilter(3)` 腐蚀相减），零启发式。
    ★★ **没给参考图**时（「再往右上方移一点」）：铁律 30 仍**禁止目测猜** ⇒ **先问量级**，
    问不到就**按口径定**（查本项目历史同义先例、取保守值；实测先例 18px / 20.16px ⇒ 取 **12px**），
    并写明「**这是默认值、一句话可改**」；**多角色同一句话 ⇒ 同一增量**；位移用**累计 `shift`** 重解。
    ⚠️ **隐藏基准坑**：离线渲染器 `--mult` 实为 `S = 0.45 × mult`，`0.45` 是**女王包历史口径** ⇒
    给**别的角色**渲图必须用 **`--head-scale`**（直接给绝对 `S`），否则头会被渲小 2.2 倍。
    详见 references/zombie-skin-and-head.md §10 / §10b / §10c / §10d。

---

## 5. 闸门总览（离线全套，缺一层就可能白跑实机）

| 门 | 命令 | 验什么 |
|---|---|---|
| 生成器自检 | `python build_zombie_<Key>.py --self-check` | 常量/结构/金标/跨语言一致性（`fails = 0`） |
| 负向测试 | `python .cache/_neg_test_head.py` | 逐条篡改常量，断言**必须响**（含注入式用例） |
| 几何门 | `python .cache/check_head_fit.py` | 头对位反解 + 换头落点 + **炮口/生成点**（两个独立来源） |
| 字节核对 | `python .cache/_byte_check_head.py` | 落盘产物**按字节**核对（含工作区 == 安装镜像） |
| 插件入口 | `python .cache/run_entry_sgp.py` | 入口类型 public/非嵌套/有无参构造/实现接口 |
| ModLoader 闸门 | `python .cache/run_gates_sgp.py` | **两份构建**各跑一遍 `check_gates_*.cs`（反射读 DLL + 真产物文本） |
| 幂等 | `python .cache/check_sgp_idempotent.py` | 3 连跑同 sha256 + 只读产物断言 |

**两份构建都要跑**：remake `…\0.28.1\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64`；
console `D:\zzz\植物大战僵尸重制版\data_PlantsVsZombies_windows_x86_64`。

**交付文档与产物必须事实一致**：改完代码顺手刷指纹（大小 / sha256 / 条目数 / 场景字节数 / 闸门条数）。

---

## 6. references 索引

| 文件 | 内容 |
|---|---|
| `references/zombie-package-and-gates.md` | 包结构逐字段、护具体系、卡库/图鉴、闸门与幂等脚本写法 |
| `references/zombie-fire-and-marker.md` | 发射体系（僵尸侧）、真源链路、**子弹生成点对齐炮口**（两层实现 + 判据写法） |
| `references/zombie-skin-and-head.md` | 换外观：经典 reanim 直转、`.dat` 二进制规格、换头三节点与头对位反解、**§9 子精灵排序（`insertLayerId`）**、**§10 尺寸类需求的量化流程**、**§11 换「被跟随层」修抬头段头/身接缝（1D+2D 判据）**、**§11b 位姿必须同帧（`process_frame` 早于 `_process` ⇒ 头落后 1 帧，用 `CallDeferred` 覆盖）** |
