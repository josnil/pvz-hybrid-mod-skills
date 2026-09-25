# 托管 C# 插件（只做纯数据做不到的事）

## 0. 什么时候非它不可

| 需求 | 为什么纯数据不行 |
|---|---|
| 概率触发（如 10% 大招） | `FireComponentFireProjectileConfig` 无 probability 字段 |
| 延时/持续改发射模式（5 秒内连发 300 颗） | `FireComponentDefinition` 无字段，状态机只有 `idle/attack/restore`，`GuardDefinition = null` |
| 真随机 | 唯一随机源 `OnFireVolley(ulong randomSeed)` 的种子是**确定性**的（`NetworkDeterministicSeed.ForCharacterEvent`，为联机同步刻意禁掉真随机） |
| **逐颗**发射（每颗单独角度/节奏） | 一次 `Fire()` 会**遍历全部 config** ⇒ 数据侧拆不开 |
| 让卡「能被选到」/ 进图鉴内置分类 | 见 §3.5 |
| 换自定义战斗背景图 | `mapTexturePath` 只喂 `GetMapTexture()`（裸 `ResourceLoader.Load`，**不查 Mod 贴图表**）；Mod 图片进不了 `ResourceLoader`；`provides.Texture` 只是塞一个 key，**运行时无代码消费** |
| 投掷单位替换（僵尸投石车） | `TowerDefenseZombieImppult.ImpSpawn()` **硬编码** `GetPacketConfig("ZombieImp")` |
| 修「自定义皮肤动画静止」 | `forceLocalRender` 是 **public 非 `[Export]`**，数据侧写不进去，见 §3.4 |

> `overrides` 覆盖原版 `FireComponent` **污染面太大**（波及所有植物），**不建议**。

## 1. 四条硬约束（写错 = 整包被拒 / 回滚）

1. `runtimeAssembly` **必须恰好是字面量** `"Runtime/ModAssembly.dll"`
   （`ModLoader.cs:329-333` + `ResolveDeclaredRuntimeAssembly:918`）—— 写别的路径**硬拒**，`policy` 救不了。
2. `runtimeApiVersion` **必须恰好 `1`**，否则入口 init 返回 false → **无条件整包回滚**；
   `TryInitializeRuntimeEntry` 失败（`ModLoader.cs:667-671`）同样是**不设防硬拒**，
   连 `policy="optional"` 都保不住 ⇒ **三个回调必须 try/catch**。
3. `provides`/`overrides` **只要有任何非空条目**，包内**每个**被 `InferRuntimeEntry` 识别的文件
   都必须在里面声明（`ModLoader.cs:526/578/673`）—— 否则该文件被静默跳过 +
   `ValidateManifestRegistrations` 判**整包失败**。所以自定义贴图**必须**写 `provides.Texture`。
4. `resources` 必须 == `XWModManifestSyncService.SyncProject` 的规范序：**所有**非忽略文件、
   `OrdinalIgnoreCase` 升序 —— 否则**编辑器一打开工程就重写 `mod.json`**。
   含 `Runtime/ModAssembly.dll`。

`runtimeAssemblyPolicy: "optional"` ⇒ `IsRuntimeAssemblyRequired() == false`
⇒ 程序集加载失败**不连坐**整包（**新 Mod 建议先 optional**）。

## 2. `Runtime/` 目录只许有一个文件

`ModLoader.IsExecutablePackageFile` 认 `.dll/.exe/.bat/.cmd/.ps1/.cs/.gd`；
`ValidateDeclaredPackageExecutables`（`ModLoader.cs:343-346`）对**除声明程序集外**的任何一个
抛 `undeclared executable package file` **直接拒收整包**。

⇒ `Runtime/` 下**只能有 `ModAssembly.dll`**。`.pdb` 不在该名单里（会被 `IsDeclaredRuntimeSymbols`
静默跳过），但既然没用就别放。**构建脚本结尾加一条"只允许 ModAssembly.dll"的硬护栏**。

## 3. 配方

### 3.1 概率大招 + 逐颗连射（本项目的标准样板）

样板：`.workbuddy/ModWorkspace/runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs`

```
扫场景找自己的角色（按 config.name，❌ 别按类名 —— 内置 GatlingPea 会误伤）
  → character.componentManager.GetRuntime<FireComponent>("character.fire")
  → ★ 订阅 fire.OnFireReady（delegate，AttackEntered() 里只发一次；FireComponent.cs:255/3258）
      · 或 fire.OnFireVolley（每条 config 各发一次，须 200ms 时间窗去抖；FireComponent.cs:673）
  → 每次命中则用 Time.GetTicksMsec() 做节拍器，逐颗调 FireComponent.Fire()
      · 逐颗 = 每发前改写 fireProjectileList[i].dir 再 Fire()
      · ★ 数据侧只留 1 条 config（否则 N² 颗重叠）
      · 想让原版不再自动开火 ⇒ fire.fireEventName = "modfire"
```

**为什么用 `OnFireReady`**：它在 `AttackEntered()`（`:3258`）里**只发一次**
⇒ 天然「本轮攻击开始」信号，**无需去抖**。
`OnFireVolley` 是**每条 config 各发一次** ⇒ 一次齐射会掷 N 次骰子。

**节奏仍由引擎状态机给**：`IdleEntered(:3089)` → `Refresh(:2377)` 设
`timer = fireInterval ± offset`（≈1.3~1.5s）→ 每物理帧递减 → 归零且有目标 ⇒ `AttackEntered` ⇒ `OnFireReady`。
⇒ **不要自己造「每 1.5 秒一轮」的节拍器**，跟着 `OnFireReady` 走就与游戏一致。

**`FireComponent.Fire()`（`:3429`）是 public 且不受状态机约束**：只检查
battlefield / alive / parent 有效 + 每条配置的 `fireEventNeed` / `fireNumSkip`，
然后**逐条执行 N 条发射配置**。**它与常规攻击走的是同一段代码** ⇒ 命中盒/伤害/行号行为必然一致，
不用担心"插件子弹打不中僵尸"。这是插件连射**最安全的入口**。

**逐发控制（每颗不同角度）—— 改 `fireProjectileList[i].dir`，一定生效**：

```csharp
// FireComponent.cs:443
public Array<FireComponentFireProjectileConfig> fireProjectileList = new Array<…>();
// FireComponent.cs:447
private readonly List<FireComponentFireProjectileConfig> _fireProjectiles = new List<…>();
// FireComponent.cs:919-929  CopyGodotArray —— ★ 逐元素同引用拷贝
target.Clear(); for (…) target.Add(source[i]);
// FireComponent.cs:965（在 :931 RefreshExportedArrayCaches() 里）
CopyGodotArray(fireProjectileList, _fireProjectiles);
// FireComponent.cs:3462 —— 每一发都现场读 dir，不是缓存
Vector2 velocity = cfg.speed * Vector2.FromAngle(Mathf.DegToRad(cfg.dir));
```

| 操作 | 生效？ |
|---|---|
| 改元素（`cfg.dir = 角度`） | ✅ 两个容器同时可见 |
| 往 `fireProjectileList` 增删元素 | ❌ `_fireProjectiles` 不跟 |

⇒ **只改不增删**；每发前**重新取一遍** `fire.fireProjectileList`（不缓存列表/元素）。

**要「恰好 N 颗 / 恰好 T 秒」⇒ 按颗数算时刻**：第 k 颗的计划时刻 = 起点 + k×(T/N) ms。
**别**用「每次 `next += 间隔`」（浮点累加漂移）。

**单帧上限**：加 `MaxPeasPerFrame`（如 6~8）防掉帧时雪崩式创建几百个子弹对象。

### 3.2 掐掉原版开火链（避免"一次攻击 = 原版一发 + 插件 N 发"）

```csharp
fire.fireEventName = "modfire";     // public 字段，默认 "fire"，FireComponent.cs:343
```

`AnimeEvent()`（`:3365`）拿 `fireEventName.Split("&")` 当白名单 ⇒ 名字不存在则**整块跳过**；
**`fireAnimeClips` 不动 ⇒ 开火动画照播**。

⚠️ 这样一来 `.dat`/`.tres` 里那条 `fire` 事件就**打不出弹了** ⇒ 与
「`events` 必须有 `fire` 条目」那条铁律**不能同时用**，**二选一**。

### 3.3 真随机

`RandomNumberGenerator.Randomize()`。
**代价**：联机会与主机不同步（框架的 `NetworkDeterministicSeed` 刻意禁真随机），
**交付时如实标注这是取舍**。

### 3.4 ★★ 修「自定义皮肤动画完全静止、按 ESC 暂停一次只跳一帧」

```csharp
// AdobeAnimateSprite.cs —— 两个都是 public 的普通属性（非 [Export]）⇒ 只有运行时插件能改
public bool forceLocalRender { … }       // :1141
public bool forceCpuPoseRender { … }     // :1166
// :8415 ShouldUseGlobalRuntimeManager() ⇒ _forceLocalRender 为真时返回 false ⇒ 绕开全局姿态图集
```

**真因链**：自定义 Mod 的 `AdobeAnimateData`（`.tres` + standalone `.dat`）**不在全局图集清单**里
⇒ `GpuPoseTextureRid` 无效 ⇒ `_runtimeGpuClockInterpolationActive == false` ⇒ 姿态定格，
只有 `RequestNodeRedraw`（**按 ESC 暂停菜单→恢复会触发**）才前进一帧。

**做法**：对**所有用自己皮肤数据的 `AdobeAnimateSprite`** 同时设
`forceLocalRender = true` + `forceCpuPoseRender = true`。

* 读法：`mod 内所有用自己皮肤数据的` 都要打标 ⇒ **每 N 帧（如 10）递归全树扫描 + 幂等**
  （战斗 / 图鉴 / 选卡 / 种植预览的实例是**各自独立创建**的，不打标就有一处静止）。
* 识别自己的皮肤：查 `sprite.flashAnimeData` 的 `animeFile` / `ResourcePath` 是否含自己的 `CHAR_KEY`。
* **引擎先例**：`PacketPickControl.cs:401-402`（卡片预览精灵，两开关一起设）；
  另 `TowerDefenseCharacter.cs` 有 `forceLocalRenderDuringZMotion`。
* ⚠️ 这是**绕开**缺失的全局姿态图集，**不是补一张**（后者无法随 mod 包分发）。

### 3.5 让卡进「选卡界面」和「图鉴」

因果链、共享卡库追加法、派生库、`GetPlantList()` 只认 6 个键、副作用告知
→ `plant-data-fields.md` §4。要点：**往
`TOWERDEFENSE_PACKETBANKS["GeneralPlant"].category["<分类>"]` check-then-add（幂等）**，
一次喂两边。

⚠️ 改游戏侧 UI/列表状态时**别破坏它的懒初始化**：图鉴的植物页是
`PlantButtonPressed` → `if (!_plantInitialized) InitPlant()` 才建列表，
自带测试还专门断言「不得提前初始化隐藏分类/预览节点」⇒ 补完分类**只在
`_plantInitialized` 已为 true 时才主动刷新**：读私有字段用**缓存一次的 `FieldInfo`**
（`BindingFlags.Instance | NonPublic`），拿不到就退化成「不刷新」（最坏：用户翻一次分类），
**绝不硬调 `InitPlant()`**。

## 4. 入口实现纪律

* 三个回调 `Initialize(XWModRuntimeContext)` / `OnAllModsLoaded()` / `Shutdown()`
  **一律 try/catch、绝不抛**（抛 = 无条件回滚）。
* **别每帧硬干**：`Initialize` 只存 context；`OnAllModsLoaded` 挂 `process_frame` 并**自己节流**
  （如每 10 帧一次）；`Shutdown` 摘掉。取用前先判空
  （`TowerDefenseManager.Instance` / `GetMapFeature()` / `config` / 目标节点）。
* 只在自己生效的范围动手。
* ⚠️ **每条出错路径各用一个「已报告」标志，不要共用一个**
  （如 `_tickFaultReported` / `_almanacFaultReported` / `_hookFaultReported`）。
  共用时「先报的那条会把后报的静音掉」：图鉴归类失败（只是难看）会把「大招推进失败」
  （= 玩法真没生效）的日志吃掉，排查时只看到一个不相干的警告。
  同理，**日志措辞要和实际行为一致** —— 只做去重就别写「已停止重试」（其实每帧还在试）。
* ⚠️ **`CharacterComponentRuntime` 不是 GodotObject**（纯 C# 抽象类）
  ⇒ 它**没有** `GetInstanceId()`、**不能**传给 `GodotObject.IsInstanceValid()`。
  判活只能 `fire != null && !fire.IsReleased && fire.Owner != null && GodotObject.IsInstanceValid(fire.Owner)`；
  去重只能 `ReferenceEquals`。（编译期就会报 CS1503/CS1061，别以为是 API 找错了。）
* ⚠️ **暂停/长卡顿保护**：`SceneTree.process_frame` 在游戏暂停时**照常发信号** ⇒
  不管就会攒下几百毫秒的「欠账」，恢复时一口气喷出来。对策：两帧间隔 > 阈值（如 400 ms）时，
  把该角色的**所有时间轴整体后移同样间隔**（欠账作废、不补发）。

## 5. 编译

```bash
# 样板：runtime_src_plant/build_runtime.py
python build_runtime.py --godot-ref-dir "<游戏目录>\data_PlantsVsZombies_windows_x86_64"
```

* `dotnet build <Xxx>Runtime.csproj -c Release`；GodotSharp 引用目录优先取 `--godot-ref-dir`，否则回落内置候选。
* ⚠️ **csproj 必须 `<Compile Remove="check_*.cs" />`** —— 否则探针脚本（顶级语句）会被编进库 → **CS8805**。
* 装机**只放 `ModAssembly.dll`**，别带 `.pdb` / `.deps.json`。
* ⚠️ 本机有**两份构建** ⇒ 引用目录/闸门**各跑一遍**。

## 6. 不开游戏怎么验（本机可行）

用 `dotnet run --file x.cs` 跑探针，**反射直调游戏程序集里的真函数**（不启动 Godot）：

* `ModLoader.InferRuntimeEntry` 逐条核对包内路径推出的 `(category,key)` == 我们写的 `provides`；
  ⚠️ 也要核**不该推导**的那些：角色包依赖（`Resources/Characters/<Cat>/…`）与
  `Runtime/ModAssembly.dll` 都必须返回 `false`（靠 `IsCharacterPackageDependency` /
  `IsDeclaredRuntimeAssembly` 放行），**返回 `true` 反而是错**。
* `XWModManifest.Load` 读回 `mod.json`，核 4 个 runtime 字段 + `IsRuntimeAssemblyRequired()`；
* `ModLoader.ValidateDeclaredPackageExecutables`（**private static，用 `BindingFlags.NonPublic` 反射调**）
  传**真实 pmod 的 namelist**（`ZipFile.OpenRead` 取）**必须不抛**；
  再塞一条假 `Runtime/Evil.dll` **必须抛** —— 这是唯一能证明该闸门真在生效的负向对照。
  参数是 `IReadOnlyList<string>`，传 `List<string>` 可行。
* `XWModRuntimeCompatibility.ValidatePackage`（若类型存在）；
* `XWModManifestSyncService.SyncProject` 在**工程副本**上跑，断言返回 `false` 且 `mod.json` **字节不变**。

**探针写法的坑**：

* ⚠️ **C# 没有相邻字符串字面量拼接**（`CS1003`）—— 写长 SQL/正则要显式 `+`。
* ⚠️ `dotnet run --file` 编译期**没有 GodotSharp** ⇒ 类型关系（`is` / 强转）走**反射**，
  不要直接引用游戏类型。
* ⚠️ Godot 资源字段名对**字段**和**属性**都成立 ⇒ 断言要写「**或**」（如
  `obj.GetType().GetField(n) ?? obj.GetType().GetProperty(n)`）。
* ⚠️ **判「DLL 里到底有没有某个东西」要按字符串搜**（`strings` 式），别靠反编译语义。
* ⚠️ **反射访问的接缝要单独加闸门**：每次用反射跨进程边界拿东西，都写一条"拿得到 + 拿对了"的断言。

## 7. ★ 与「僵尸版同名 Mod」共用同一套判定逻辑（2026-09-22）

需求常是「植物版和僵尸版共用同一套判定」。**共享程序集做不到**（每个 `.pmod` 必须自带
`Runtime/ModAssembly.dll`，且两版 `runtimeEntryType` 不同）⇒ 用**共享源文件**：

```
ModWorkspace/
├── runtime_shared/GatlingVolleyCore.cs     ← 判定核心（参数 + 判定函数），两版共用
├── runtime_src_plant/SuperGatlingPeaRuntime.csproj
└── runtime_src_zombie_super_gatling/SuperGatlingPaperRuntime.csproj
```

两个 csproj **各自**挂同一份源：

```xml
<ItemGroup>
  <Compile Include="..\runtime_shared\GatlingVolleyCore.cs" Link="GatlingVolleyCore.cs" />
</ItemGroup>
```

⇒ 编译进两个 DLL，判定只有一份实现。要点：

* 入口里的常量改成**转发**（仍是编译期常量，取值处零开销）：
  `private const double UltimateChance = GatlingVolleyParams.UltimateChance;`
* **别强行统一「节拍外壳」**：植物由 `FireComponent.OnFireReady` 触发，僵尸自建毫秒计时器。
  外壳不同、判定相同 ⇒ 只共享判定函数，不抽状态机基类（零收益纯重构 + 会搅乱已验证产物）。
* 共享源**不引用任何游戏类型**（只用 Godot 的 `RandomNumberGenerator` + `System.Math`），
  否则两个工程都得配齐引用。

**两种「漂移」会立刻现形**：植物单帧上限 `8` vs 僵尸 `12`、卡顿阈值 `400ms` vs `250ms` ——
「各写一份」必然漂，抽出共享核心时一并收敛。

### ⚠️⚠️ 把它搬进共享源后，所有「断言源码里有字面量」的检查都会假红

生成器的 `self_check()` 与 `check_plant_super_gatling.py` 原本直查
`UltimateChance = 0.10` 这样的字面量 ⇒ 改完一次红 7 条，生成器直接**拒绝写盘（exit 3）**。
**要改的是断言，不是绕过它。** 把它拆成**两问**：

```python
# (a) 入口必须转发（谁把值写回字面量 / 改了转发名 ⇒ 立刻红）
fwd = re.compile(r"const\s+\w+\s+" + local_name
                 + r"\s*=\s*GatlingVolleyParams\." + shared_name + r"\s*;")
# (b) 字面量只在共用核心里出现一次，且等于生成器侧记录的期望值
lit = re.compile(r"const\s+\w+\s+" + shared_name + r"\s*=\s*([0-9.]+)\s*;")
```

再加两条：**两个 csproj 都真的 `Include` 了同一份源**（只挂一边 = 另版本质还是各抄一份）、
**入口真的在调用共用判定函数**。植物侧编号是 `K15*`（8 组 × 2 问 = 16 条）/ `K16`（1）/ `K18`（2）/ `K19`（4），
**合计 23 条**，但脚本里只有 **6 个 `chk(` 调用点**（条数是循环展开出来的）⇒ 数断言要看**脚本末尾自带的分组统计行**，
别数 `chk(` 出现次数，也别在文档里手抄数字。

> 通用教训：任何「源码里必须含某个字面量」的断言都是**重构陷阱** ——
> 一旦把值搬到别处（共享源、常量表、配置），它必然假红。搬家时顺手把断言升级成
> 「转发在不在 + 唯一真源在不在 + 值对不对」，**不要**删断言或跳过校验。
