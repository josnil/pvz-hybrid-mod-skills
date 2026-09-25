# 僵尸包结构 / 护具 / 卡库 / 闸门

> 本文件是 `pvz-hybrid-zombie-authoring` 的 reference。

## 1. 包内 13 个文件（缺一个就少一块功能）

| # | 路径 | 作用 | 漏了会怎样 |
|---|---|---|---|
| 1 | `mod.json` | 清单 | 整包不进 |
| 2 | `Resources/Cards/<Key>.tres` | 卡片 | 选卡界面没有它 |
| 3 | `Resources/Characters/Zombies/<Key>/Config/TowerDefense<Key>.tres` | 本体配置 | 角色不存在 |
| 4 | `Resources/Characters/Zombies/<Key>/Packet/<Key>.tres` | 卡包条目 | 卡在包里但选不到 |
| 5 | `Resources/Characters/Zombies/<Key>/Scene/<Key>.tscn` | 场景 | — |
| 6 | `Resources/Characters/Zombies/<Key>/Scene/<Key>ComponentSet.tres` | 组件集 | **发射组件不创建（零日志）** |
| 7 | `Resources/Characters/Zombies/<Key>/Scene/<Key>FireComponentDefinition.tres` | 发射定义 | 不会开枪 |
| 8 | `Resources/Characters/Zombies/<Key>/Sprite/<Key>.tscn` | 精灵场景 | 画不出来 |
| 9 | `Resources/Characters/Zombies/<Key>/Armor/Zombie<Key>ArmorData.tres` | 护具数据 | 没护具 |
| 10 | `Resources/Characters/Zombies/<Key>/Armor/Config/Zombie<Key>Armor<X>.tres` | 护具槽 | 护具没血/秒不掉 |
| 11 | `Resources/Animations/<Skin>.{dat,tres,Atlas.png}` | 外观三件套 | 换外观时才有 |
| 12 | `Runtime/ModAssembly.dll` | 托管插件 | 机制全无 |
| 13 | `<中文名>.pvzmodeproject` | 工程标记 | **不进包**（zip 里出现 = 被拒/污染） |

包内**禁止**：`.cs` / `.scn` / `.res` / `.uid` / dotfile。

## 2. 本体配置的字段（`TowerDefenseZombieConfig`）

| 字段 | 示例 | 含义 |
|---|---|---|
| `hitpoints` | `1180.0` | 本体血 |
| `hitpointsNearDeath` | `70.0` | 濒死血（总血 = 两者相加） |
| `attack` | `800.0` | 啃食伤害（吃掉植物的速率） |
| `walkAnimeClip` / `attackAnimeClip` | `Walk` / `Eat` | 走路 / 啃食 clip |
| `characterConfig.name` | `Zombie<Key>` | **必须已注册进 `TOWERDEFENSE_CHARCATERS`** |

**不吃碾压**：不加 `smashAttack` 即可（碾压是另一套）。

## 3. 护具体系（僵尸独有，也是「暴走」机制的钥匙）

```
<Key>ArmorData.tres        （CharacterArmorData：armorLists 列出本角色有哪些护具槽）
   └─ Config/Zombie<Key>Armor<X>.tres   （SlotConfig：damagePoint = 血量、flags）
场景里：currentArmor = ["Paper"]        （出生即戴）
```

* `damagePoint` 就是「这层护具多少血」（示例 `500.0`）。
* `flags`：本仓实测 `68 = SHIELD | DAMAGEABLE`（二类防具）。
* **防具槽沿用内置媒体名**（如 `Paper`）⇒ 图鉴/掉落等内置逻辑不用改。
* ★ **白送的机制**：内置读报僵尸脚本自带 `ArmorHitpointsEmpty("Paper")` → `SendStateEvent("ToGasp")`
  ⇒ 护具打光后进 `Gasp` 状态 → 3 倍速暴走（`timeScaleInit = 3.0`）。
  想用就在本体/状态机里对齐，别自己写一套。

⚠️ `Config` 里指向护具的路径必须是**包内相对路径**（包内自引用禁 `res://`）。

## 4. 卡库与图鉴

| 目标 | 做法 |
|---|---|
| 选卡界面 / 关卡编辑器 | 补进僵尸根卡库 `GeneralZombie` 的 `Zombie` 分类 |
| `debugPacketOpenAll`（切 `Total`）下也能看到 | 还要补 `Include` 闭包算出的派生库（实测 `['GeneralZombie','TotalZombie','Total']`）—— **运行期**按 `PacketBankResource.json` 算，读不到才回落到离线算好的表 |
| 图鉴僵尸页 | 只需上面两步（`Almanac.cs:220` 取的是**同一个实例**，不像植物页深拷贝） |

**副作用（必然发生）**：图鉴僵尸页会显示**两条**（`Almanac.InitZombie()`，`Almanac.cs:411-435`，
两条来源都不去重）⇒ 运行期反射去重：

1. 扫到 `Almanac` 节点时反射取 `_zombieLogicalConfigs`，抹掉本角的重复项（**保留最靠前那条、顺序不变**）；
2. 调**公开**的 `QueueZombieVirtualRefresh()` 重建虚拟列表；
3. 共享卡库 / `_packetPaths` / 解锁状态**一个字节都不动**。

## 5. mod.json 硬字段（违反 = 整包被拒，不是「不生效」）

| 约束 | 值 |
|---|---|
| `runtimeAssembly` | 只能是**字面量** `"Runtime/ModAssembly.dll"`（字符串相等判定） |
| `runtimeApiVersion` | 必须**恰好** `1` |
| `runtimeAssemblyPolicy` | `"optional"`（DLL 挂了不连坐角色） |
| `runtimeEntryType` | 入口类 `FullName`（**真名是这个**，不是 `runtimeEntry`）；无命名空间 ⇒ 纯类名 |
| `schemaVersion` | `2` |
| 入口类要求 | `public` + 公开无参构造 + **非嵌套** + 实现 `IXWModRuntimeEntry` |
| 三回调 | `Initialize` / `OnAllModsLoaded` / `Shutdown` **一律不许抛**（抛了 = **无条件整包回滚**，不受 `optional` 保护） |

⚠️ `Runtime/ModAssembly.dll` 必须**同时**出现在 `manifest.resources` 里，且遵守 `SyncProject` 的
规范序（`OrdinalIgnoreCase` 升序 ⇒ `Resources/…` 在前、`Runtime/…` 在后），
否则编辑器一打开工程就会重写 `mod.json`。

## 6. 闸门体系（离线全套）

| 门 | 脚本 | 关键写法 |
|---|---|---|
| 生成器自检 | `build_zombie_<Key>.py --self-check` | 常量形状 + 派生式恒等 + 场景文本 + **金标**（`*_GOLDEN` 独立记录）+ **跨语言**（读 C# 源码字面量） |
| 负向测试 | `.cache/_neg_test_head.py` | 逐条篡改常量；**注入式**用例（打桩替换生成器函数体，硬塞不该出现的行） |
| 几何门 | `.cache/check_head_fit.py` | 数据侧反解 vs 生成器常量；换头落点；炮口/生成点（两来源独立） |
| 字节核对 | `.cache/_byte_check_head.py` | 读 `rb`，含 BOM/行尾/节点头闭合括号/工作区 == 安装镜像 |
| 入口 | `.cache/run_entry_sgp.py` | 反射验入口类型 |
| ModLoader 闸门 | `.cache/run_gates_sgp.py` + `check_gates_*.cs` | 加载真 DLL/真产物，逐条 `Check()`；**两份构建各跑一遍** |
| 幂等 | `.cache/check_sgp_idempotent.py` | 3 连跑同 sha256 + 只读产物断言 |

> ⚠️ **负向用例自身的坑**（写断言的人最容易骗自己，四型「假绿」）：
> * 篡改必须**全量替换**（`replace(old, new)`），**不能**只改一处 —— 同一个值（数字/路径）在文档与产物里
>   常有**多处**，只改一处 ⇒ 其余处仍满足断言 ⇒ **0 条 FAIL = 假绿**。实测：文档对账脚本 `--neg` 首跑
>   只有 1/3 报警，改全量后 3/3。
> * 不能只看「fails 非空」：必须断言**被测的那一条**出现在 FAIL 列表里，否则可能被别的断言碰巧掩盖。
> * 目标行在**当前口径下根本不生成**时，改常量造不出反例 ⇒ 必须**注入**（打桩替换生成器函数体，
>   硬塞进不该出现的行再跑）。
> * 生成器 `self_check()` 比「刚生成的内存文本」= **恒真** ⇒ 必须配 **on-disk 断言**（读 `rb`）。

### 6.1 写闸门（C# 反射）时必踩的坑

* **本闸门是 `dotnet run --file` 编译的独立程序** ⇒ 源码里**绝不能**出现 `GodotObject` / `Node` /
  `Vector2` 这类 Godot 类型字面量；需要判断类型关系时拿 `Type` 对象做反射。
* **Godot `Vector2` 的 `X`/`Y` 是「字段」不是「属性」** ⇒ 读分量要 `GetField` 优先、`GetProperty` 兜底
  （只写 `GetProperty("X")` 会拿到 null ⇒ 断言假红）。
* `Type.GetMethod(name, flags)` 有重载时会抛 `AmbiguousMatchException` ⇒ 统一「按名字取全部成员再筛参数个数」；
  查 private 成员要额外带 `BindingFlags.NonPublic`。
* 反射探针不能只用 `GetField`：源码里很多是 `public X { get; set; }` **属性**
  （但也有**字段**，如 `FireComponent.fireProjectileList`、`fireAudioName`）
  ⇒ 断言一律写成「public 字段**或**属性存在」并回报形态。

### 6.2 两份构建

```
remake  : D:\zzz\植物大战僵尸杂交版0.28.1\植物大战僵尸杂交重制版\data_PlantsVsZombies_windows_x86_64
console : D:\zzz\植物大战僵尸重制版\data_PlantsVsZombies_windows_x86_64
```

每次跑完都**如实报两份的 PASS/FAIL**（不一致就说明有构建分支或路径硬编码）。

### 6.3 幂等脚本断言的四组事实

| 组 | 断言 |
|---|---|
| `.pmod` 两份位置 | `dist/` 与 `Mods/` 大小 + sha256 **逐字节一致** |
| zip 结构 | 条目数、`mod.json` 排第 0、**不含** `.cs`/`.pvzmodeproject`/`.uid`/dotfile、条目集 == 构建目录（去掉工程标记） |
| `mod.json` 字段 | §5 的全部硬字段 + `resources` == zip 去 `mod.json`（规范序）+ `provides` 三键 |
| `Runtime/` | 只有 `ModAssembly.dll`，**包内 DLL 与构建目录一致** |
| Mods 镜像 | 恰 **72** 个标准目录、镜像文件集 == 构建目录 |
| 装订 | `enabled_mods.json` 含本 mod、**没丢别人的条目**、最近工程记录无 CR |

> ⚠️ zip 条目顺序 ≠ 文件系统字母序（`mod.json` 被强制排第 0）⇒ 比条目时比**集合**，顺序另立断言。
> ⚠️ 「构建目录文件数」≠「zip 内条目数」（前者多一个 `.pvzmodeproject`）。
