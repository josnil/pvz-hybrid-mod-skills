# 踩坑总表（通用 / 跨角色）—— 现象 · 触发场景 · 原因 · 正确做法

> **本文件定位**：把《植物大战僵尸杂交版》Mod 工坊开发中**实际踩过**的坑，统一成四段式速查表。
> 每条都回答四件事：**看到什么**（现象）→ **什么时候会撞上**（触发场景）→ **为什么**（原因，带源码位置）→ **怎么办**（正确做法）。
>
> **与其它文档的分工**（别重复维护）：
> - `SKILL.md` = 流程与规范正文；`references/*.md` = 各专项展开。
> - **本文件 = 坑的索引与速查**：条短、要点全、**详细推导指向上面那些文档**。
> - 角色特有的坑分别在 `pvz-hybrid-plant-authoring/references/plant-pitfalls.md`
>   与 `pvz-hybrid-zombie-authoring/references/zombie-pitfalls.md`。
>
> 用法：出问题时先在本文件 Ctrl-F **现象**里的一句话（如"零日志""假绿""整包被拒"）。

---

## A. 打包与清单（撞上就整包被拒 / 静默失效）

### A-01 整包被拒：`invalid declared runtime assembly path`
- **现象**：Mod 完全不加载，日志一句 `invalid declared runtime assembly path: xxx`。
- **触发场景**：为了让程序集名字好看，去改 `mod.json` 的 `runtimeAssembly`。
- **原因**：`ModLoader.cs:330`（另一处 `:918`，还额外禁 `..`/根路径/`:`）把它当成**字面量硬校验**。
- **正确做法**：`mod.json` 里**永远**写 `"Runtime/ModAssembly.dll"`，一个字都不改。
  想让程序集名字唯一，改的是 **`.csproj` 的 `<AssemblyName>`**（见 E-01）——**变的是程序集身份，不是包内文件路径**。

### A-02 整包被拒：`undeclared executable package file`
- **现象**：包里多放一个文件就整包拒收。
- **触发场景**：手工往 `Runtime/` 里塞 `.pdb` / `.deps.json`，或把 `.cs` 打进包。
- **原因**：`ValidateDeclaredPackageExecutables` + `IsExecutablePackageFile` 会认这些扩展名。
- **正确做法**：**`Runtime/` 下只允许 `ModAssembly.dll` 一个文件**。构建脚本结尾加一条硬护栏：
  `extra = [f for f in os.listdir(runtime_dir) if f != "ModAssembly.dll"]` → 非空就报错。
  ⚠️ **备份文件也别放在 `Runtime/` 里**（`ModAssembly.dll.bak-xxx` 同样会被判违规）——备份放**包目录上一层**。

### A-03 编辑器一打开工程就重写 `mod.json`
- **现象**：`mod.json` 的 `resources` 顺序不断被改，git diff 一直脏。
- **触发场景**：手写 `resources` 列表时顺序随意。
- **原因**：必须等于 `XWModManifestSyncService.SyncProject` 的规范序：**所有**非忽略文件、`OrdinalIgnoreCase` 升序。
- **正确做法**：让脚本按该规则生成 `resources`；`Runtime/ModAssembly.dll` 也要在列表里。

### A-04 包内自引用写成 `res://` ⇒ 配置加载失败、角色被拒
- **现象**：包内 `.tres`/`.tscn` 互相引用时报找不到资源。
- **触发场景**：套用游戏本体的写法，把包内引用也写成 `res://Resources/...`。
- **原因**：包解到 `user://ModsCache/<包名>/`（`ModLoader.cs:373/388`）⇒ `res://Resources/…` 在游戏本体里**根本不存在**。
- **正确做法**：包内自引用**必须相对**（`./X.tres`、`../Config/X.tres`；`Sprite/`、`Scene/` 在 5 段目录 ⇒ 5 个 `../`）；
  只有引游戏自带资源才写 `res://Prefab|Asset|Script|Resource|Registry|Extends`。
  ⚠️ **例外**：`type="Script"` 的 `ext_resource` **必须**写 `res://`，否则被 `ModLoader.SanitizeCharacterTextResource:1418-1463` 剥掉。

### A-05 手删 `ModsCache` 是白费力气
- **现象**：改完包不生效，上网搜到"删缓存"，删了也没用（或删完出现别的问题）。
- **触发场景**：以为游戏会缓存解包结果。
- **原因**：`LoadMod` 每次先 `Directory.Delete(extractDir, recursive:true)` 再解压（`ModLoader.cs:392-396`）。
- **正确做法**：**重启游戏**即可。别去动 `ModsCache`。（本机删除还很贵，见 F-05。）

### A-06 工程目录骨架凭印象写 ⇒ 编辑器打不开
- **现象**：游戏能加载，但游戏内编辑器（F3）看不到/打不开工程。
- **触发场景**：手工维护 `STANDARD_DIRS`。
- **原因**：必须照抄 `XWModProjectLayout.StandardDirectories` 的**72 项**（顺序也一致）。
  历史事故：臆造出 120 项清单，混进不存在的目录、同时漏掉 39 项。
- **正确做法**：**正则解析那个 `.cs` 再比对**，绝不维护第二份手抄名单。
  ⚠️ 「游戏能加载」≠「编辑器能打开」，是两套东西（`.pmod` 给游戏；`.pvzmodeproject` + 72 目录给编辑器）。

### A-07 「最近工程」缓存被写坏，两个生成器互相清空
- **现象**：编辑器里最近工程列表只剩一条（或全没了）。
- **触发场景**：用 `^path_\d+="(.*)"$` 直接匹配那个 CRLF 的 cfg 文件。
- **原因**：CRLF 下正则一条都匹配不到 ⇒ 读到空列表 ⇒ 把整个列表重写成"只剩自己一条"。
- **正确做法**：写回前**先归一化 CRLF**；统一正斜杠 + 大小写不敏感去重 + **保留既有条目**。
  `.pvzmodeproject` 的 `ExportDirectory` 写**正斜杠 + 结尾斜杠**的 Mods 目录。

---

## B. 断言与闸门（"假绿"重灾区）

> **总纲**：**只跑一遍正向自检说明不了任何事**。每加/改一条断言，必须做**负向测试**（篡改 → 确认报警 → 改回）。

### B-01 恒真比较（拿常量比由同一常量渲染出的文本）
- **现象**：自检全绿，但产物其实是错的。
- **触发场景**：`if f"offset = Vector2({HEAD_OFFSET[0]}, …)" not in rendered: fail` 这类写法。
- **原因**：拿**活常量**比**由它渲染出的文本** ⇒ 恒成立，改错了也全绿。
- **正确做法**：加**金标锚点**（`*_GOLDEN`，**独立记录**的字面量），自检拿「活常量」比「金标」；
  几何真值交给真正会重解几何的脚本。

### B-02 门控共用（实现与断言同在 `if <开关>` 里）
- **现象**：把开关关掉后，两边一起消失 ⇒ 断言的保护作用归零。
- **触发场景**：把输出行与断言包在同一个条件里。
- **原因**：**关掉开关，被测物和断言同时不存在**。
- **正确做法**：把硬需求写成**无开关的不变量**（如「`z_index` 必须是正整数」）。

### B-03 前缀匹配漏掉关键字节
- **现象**：把值从 `1.5` 改成 `1.575`，断言照样过。
- **触发场景**：对**数值**做纯子串断言，如 `f"HEAD_EXTRA_SCALE = {sc_}"` 的 `in` 比较。
- **原因**：`"HEAD_EXTRA_SCALE = 1.5"` 是 `"…= 1.575"` 的**前缀** ⇒ 恒真。负向用例首跑**不报警 = 假绿**。
- **正确做法**：数值子串断言**一律带右边界** `re.search(re.escape(txt) + r'(?![\d.])', doc)`，或改用精确取值比对。

### B-04 注入式用例：有些断言的目标行在当前口径下根本不生成
- **现象**：想用「改常量」造负例，但目标行压根不在产物里。
- **触发场景**：断言针对的是某个可选分支的输出。
- **原因**：改常量造不出场景。
- **正确做法**：**打桩**（猴子补丁替换生成器函数体，强行塞进目标行）再跑断言。

### B-05 反例被同名值稀释（只改一处 ⇒ 一条 FAIL 都不报）
- **现象**：负向测试首跑 1/3，看起来"大部分都过"。
- **触发场景**：篡改用 `replace(old, new, 1)`，而目标值在文档/产物里出现**多处**。
- **原因**：其余处仍满足断言。
- **正确做法**：负向一律**全量替换**，并断言「**被测的那一条**」出现在 FAIL 列表里
  （只看「fails 非空」不够，可能被别的断言碰巧掩盖）。

### B-06 子串断言被注释/死分支骗过
- **现象**：把语句注释掉或改成 `if (false && cond)`，子串级断言照样绿。
- **触发场景**：对 **C# 源码**做子串断言。
- **原因**：注释里、字符串里、死分支里都还留着那个子串。
- **正确做法**：断言前先 `_strip_cs_comments()`（跳过 `//` 与 `/*…*/`，**字符串字面量原样保留**），
  口径从「子串级」升级为「**整条活语句**」，并**同时**断言关键**条件表达式**存在。

### B-07 生成器自检比对「刚生成的内存文本」= 假绿
- **现象**：把错值直接写进磁盘 `.tscn`，自检照样打印「自检通过」。
- **触发场景**：`self_check()` 里重新调用渲染函数拿内存文本再做正则。
- **原因**：它只能证明「生成器常量 == 生成结果」，证明不了**磁盘上的文件**是对的。
- **正确做法**：凡生成器自检都要配一条 **on-disk 断言**（读文件 + 比对值），
  并用「故意写坏磁盘文件 → 必须报错」验证这条断言真的会响。

### B-08 「源码里必须含某个字面量」的断言是重构陷阱
- **现象**：把值抽到共享源/常量表后，生成器 + 校验脚本一次红 7 条，生成器直接拒绝写盘。
- **触发场景**：抽出共享判定核心、或把字面量搬进配置。
- **原因**：断言锚的是**出现位置**，不是**语义**。
- **正确做法**：升级成两问 —— (a) 入口有没有**转发**；(b) 唯一真源里值**对不对**。
  **绝不删断言、绝不跳过校验**。

### B-09 验证只做一层「结构」⇒ 漏掉「拼起来全错」
- **现象**：每个字段都对，但画面上头压在身体上。
- **触发场景**：外观类只跑了字节布局/字段值的校验。
- **原因**：缺「**拼合**」这一层。
- **正确做法**：外观至少**四层独立 + 负向测试**：
  ① 源↔产物（对**全部 (层,帧)** 逐值反查）② `.dat`（解析终点==文件长 + 像素区逐字节==自写 PNG 解码）
  ③ `.tres`（f32 位级一致）④ 场景 + 结构性不变量（图层不跨 body/head 边界）。
  **四层都不许复用生成器代码。**

---

## C. 交付链（"看起来成功了"）

### C-01 编译失败后打包 ⇒ 拿到一个「假产物」
- **现象**：包做出来了、也能装，但行为是旧的。
- **触发场景**：构建脚本没检查 `dotnet build` 的退出码就继续打包。
- **原因**：编译失败时输出目录里可能残留**上一次**的 dll；打包照样成功。
- **正确做法**：编译必须**断言退出码 == 0**；打包前对 dll 做**新鲜度/指纹**校验
  （如编译两次比 sha256，或断言产物 mtime 晚于源码）。

### C-02 DLL 根本没进包
- **现象**：插件不起作用，包看着正常。
- **触发场景**：改了源码但忘了重跑构建脚本，或改了产物名却没改打包逻辑。
- **原因**：交付链缺一环。
- **正确做法**：装机后**从 `.pmod` 里把 dll 抽出来**核对（内部 sha256 == 工作区那份），
  而不是只看工作区文件在不在。本项目已固化为「抽包 → 读身份 → 比 sha」三步。

### C-03 csproj 的 XML 注释里写了两个连续减号
- **现象**：`dotnet build` 报 XML 解析错误。
- **触发场景**：在 `<!-- -->` 里画分隔线 `-----------`。
- **原因**：XML 规范禁止注释内出现 `--`。
- **正确做法**：注释里用 `=` 或 `~` 画线。

---

## D. 玩法机制（"纯数据做不到"的那些）

### D-01 概率 / 延时改模式 / 真随机 / 改投掷单位 ⇒ 只能写插件
- **现象**：翻遍 `.tres` 字段也找不到「10% 概率」「5 秒后变招」这种配置位。
- **触发场景**：想纯数据实现随机玩法。
- **原因**：`FireComponentFireProjectileConfig` 只有 8 个字段，**没有任何概率或时窗字段**；
  `FireComponent.AttackProcessing` 只按 `fireInterval` 调 `sprite.timeScale`，最高约 4 倍速。
  且 `OnFireVolley(ulong randomSeed)` 的种子是**确定性**的（为联机同步刻意禁掉真随机）。
- **正确做法**：写托管插件（`Runtime/ModAssembly.dll`）实现。

### D-02 动画 `events` 表没有 `fire` 条目 ⇒ 只有动画没有子弹（零报错）
- **现象**：角色会摆手，但一颗弹都不出，加载期**零日志**。
- **触发场景**：自制/直转 `.dat` 时漏了事件表。
- **原因**：链路是 `AdobeAnimateSprite.events[f]` → `OnAnimeEvent:5327` → `FireComponent.AnimeEvent`
  → `cmd ∈ fireEventName.Split("&")`（默认 `"fire"`，`:343`）→ `FireConfiguredVolley()` → `Fire()`。
  没有事件 ⇒ 链路起点就不存在。
- **正确做法**：`.dat` 的 `events` 里必须有 `{"Command":"fire","Argument":""}`；
  **发射帧 = `HeadFire.start + 12`**（内置单发族 7 例全为 HeadFire(50,74)+1 event@f62）。

### D-03 掐掉原版开火链 / 让插件自己发
- **现象**：需要插件接管发射，但原版也在发 ⇒ 打两遍。
- **触发场景**：插件要自定义发射节拍或逐颗发射。
- **原因**：原版链由动画事件 `fire` 驱动。
- **正确做法**：把 `fire.fireEventName` 改成**动画事件表里不存在的名字**（如 `"modfire"`；public 字段默认 `"fire"`，`:343`）
  ⇒ `AnimeEvent():3365` 白名单跳过，而 `fireAnimeClips` 未动 ⇒ 动画照播。
  ⚠️ **触发点用 `FireComponent.OnFireReady`**（`AttackEntered():3258`，只发一次），**别用 `OnFireVolley`**（每条配置发一次）。
  ⚠️ **屏蔽与接管必须一起做**：只屏蔽不接管 ⇒ 完全不发；只接管不屏蔽 ⇒ 打两遍。

### D-04 插件自建节拍时用 `CanFire` 判定 ⇒ 刷屏报错
- **现象**：没战场也硬开火，日志刷 `E_MAP_BOUNDS_UNAVAILABLE` + `E_FIELD_UNAVAILABLE`。
- **触发场景**：插件自己维护开火计时器。
- **原因**：`CanFire` 多一道 `timer > 0f`（`:1738` 状态机冷却），而插件自建节拍时 `timer` 归不归零不可控。
- **正确做法**：用 **`CanFireCheckOnceByData(...)`** —— 它含「进场内才攻击」(`:1766`) 与「没有植物不攻击」(`:1808`→`:1862`→`:1836`) 两条。

### D-05 托管入口里定义 Node/Control 子类
- **现象**：莫名其妙的运行时错误 / 类型加载失败。
- **触发场景**：在插件里顺手写了个 helper 类继承 `Node`。
- **原因**：托管入口程序集不走 Godot 的脚本类注册通道。
- **正确做法**：**不要在托管入口里定义 Node/Control 子类**。

### D-06 Mod 的 `Localization/translations.csv` 运行时根本不加载
- **现象**：`name` / `describe` 显示成 key 本身（如 `TOWERDEFENSE_PLANT_X_NAME`）。
- **触发场景**：按"正规做法"把文本放进 csv、字段里写 key。
- **原因**：三条证据齐备 ——
  ① 全库 `TranslationServer.AddTranslation` **零调用**；② `project.godot` 只挂内置 `res://Asset/Translate/Translate.{en,es,zh}.translation`；
  ③ `.csv` **不在** `ModLoader.cs:1006 TryResolveDeclaredResourceCandidate` 的扩展名白名单里。
- **正确做法**：`name` / `describe` / `handbookDescribe` / `handbookStory` **直接写中文字面量**。
  csv 只留「两列留底」（键 = 内联中文原文本身），别放多行块与故事（会破坏 CSV 行结构）。
  ⚠️ **改 `name` 不破坏注册**：身份标识是 `saveKey`（== 注册键 == 卡片文件名去扩展），`name` 只是显示名。

### D-07 图鉴里同一张卡出现两次
- **现象**：植物页/僵尸页有重复条目。
- **触发场景**：Mod 内容被游戏硬塞进额外分类。
- **原因**：
  - **植物**：`XWModContentCatalog.WithPlants():107-123` 把 `GeneralPlant` 卡库深拷贝后，
    把所有 Mod 植物塞进**新建**的 `category["ModPlants"]`；`Almanac.cs:219` 是全库唯一调用点，
    图鉴按 `category.Keys` 枚举顺序翻页 ⇒ 同卡在 `ModPlants` 与 `Gold` 各出现一次。
  - **僵尸**：`Almanac.InitZombie():411-435` 两条来源都不去重（共享卡库 `Zombie` 分类 + 无条件 `XWModContentCatalog.GetPackets(plants:false)`）。
- **正确做法**：**只能图鉴侧运行时去重**（纯数据改不动）。
  - 植物：**摘条目不整类删**（`ModPlants` 是所有 Mod 植物共用的）→ **摘空了才删键** → 回落 `plantCategoryId` → 只在 `_plantInitialized` 为真时刷新。
  - 僵尸：反射 `Almanac._zombieLogicalConfigs` 从后往前删重复，再调 public `QueueZombieVirtualRefresh()`。
  ⚠️ 别往场景加 `%Almanac`、别提前 `Instantiate()`（官方 `AlmanacVirtualizedResidencyRuntimeTest` 断言「不得提前初始化隐藏分类 / 不得提前实例化预览节点」）。
- **★☆ V0.30 起必须改成「周期性自愈」**（V0.29 的老写法在 V0.30 **会失效**）：
  - 老写法是「把 `XWModRuntimeRegistry.GetRegistrations()` 里 `kv.Key == 卡名` 的条目标 `OverridesBuiltIn = true`」。
  - **V0.30 回归点**：新增的 `RefreshAliases()`（`XWModRuntimeRegistry.cs:365-414`）在**每一次** `RegisterCore()` 之后都会用**裸键**重建 `Registrations[cat][裸键] = new Registration{…}`，只拷 9 个字段，**没拷 `OverridesBuiltIn`** ⇒ 标记归零；只要之后**还有任何一次注册**（例：另一个 Mod 注册 Feature / 商店 / 钻卡），所有旧 Mod 的抑制标记就**一起被抹掉** ⇒ 图鉴每条 ×2。
  - **正确做法（V0.30 口径，已落地为 `runtime_shared/ModV30Compat.cs`）**：`Install(id, tag, cards)` + **每 10 帧**自愈一次（`HealIntervalFrames = 10`），幂等（**只补被清零的**），匹配口径**同时**覆盖 `kv.Key == 卡名` **与** `kv.Value.ContentId.Key == 卡名`；兜底还要反射 `_zombieLogicalConfigs` 去重（**正向记首命中、倒序 `RemoveAt` 保序**，再 `QueueZombieVirtualRefresh()`）。
  - ⚠️ **`GetRegistrationStack(category, key)` 在 V0.30 语义变了**：查不到裸键时会走 `Aliases` 分支展开，返回的是**命名空间 layer**（`IsLegacyContent = true`），**不是**图鉴收录的那条别名副本 ⇒ 老补丁「用 `GetRegistrationStack` 取对象再设 `OverridesBuiltIn`」**完全无效**（`alpha_squad` 就是踩这个）。

### D-08 选卡界面同一张卡出现两遍（V0.30 起）
- **现象**：选卡界面 / 卡库筛选 / 关卡编辑器 / 沙盒里，同一张 Mod 卡出现两次。
- **触发场景**：包是 `schemaVersion: 2`（**没有 `contentEntries`**）⇒ 走 legacy `Register()` 路径。
- **原因**：V0.30 给旧式 Mod 内容做了**命名空间键 + 兼容别名双登记**：
  | 写入点 | 键 |
  |---|---|
  | `RegisterCore()`（`XWModRuntimeRegistry.cs:319`） | `"mod/<id>/<Card>"`（命名空间键） |
  | `RefreshAliases()`（`:395`） | `"<Card>"`（裸键 = 兼容别名） |
  而选卡链路是**按字典键**枚举整张表的，**不按卡身份去重**：
  `TowerDefenseManager.CollectPacketConfigsByCost()`（`:2468-2490`，`GetPacketConfigCostLower/Upper(+WithTypeList)` 全走它）／`SandboxScreen.cs:87`／`XWPacketSpawnEntryPacketSelectorWindow.cs:111`／`ResourceManager.GetPacketNames()`（`:1267` 直接返回 `TOWERDEFENSE_PACKETS.Keys`）。
  V0.29 只有裸键一处 ⇒ 无重复。
  植物侧另有辅助通道：`XWModContentCatalog.WithPlants()` 把 Mod 植物再塞进 **`ModPlants`** 分类，而选卡用的是**每次调用新建的深拷贝**（`TowerDefenseBattleFeaturePacketBank.cs:248`）⇒ 只摘图鉴那份 `ModPlants` **管不到选卡**。
- **正确做法**（不要指望引擎别写命名空间键 —— 那是 V0.30 的**本意**，防撞名）：
  1. 临时从枚举面**移出命名空间键**：遍历 `ResourceManager.Instance.TOWERDEFENSE_PACKETS`，删掉 `mod/<id>/<Card>` 这类键（★ **硬守卫**：裸键必须已在表内才删，否则会把卡删没）；
  2. 对 `TOWERDEFENSE_PACKETBANKS` 每库每分类做**保序去重**（同名只留第一条）；`catName == "ModPlants"` 时把**本包卡**一并摘掉；
  3. 改成**每 60 帧**（`BankDedupIntervalFrames`，比抑制自愈贵）周期性执行一遍。
  判定逻辑**抽成共用源**（`runtime_shared/*.cs`，各包 `<Compile Include><Link>`）—— 但 **绝不共享程序集**（G-03：两个 `.pmod` 必须各带自己的 `ModAssembly.dll`）。

### D-09 覆盖卡池的包（`overrides.PacketBank`）在引擎更新后「缺卡」
- **现象**：游戏更新后，覆盖卡池的 Mod 包里**新版本的卡全都不见了**（不是重复，是**缺**）。
- **原因**：`overrides.PacketBank` 是**整体替换**；`TowerDefenseManager.GetPacketBankData()` 只做 `TOWERDEFENSE_PACKETBANKS[name]` **直读**，**不做** Include 展开、**不合并**引擎新增 ⇒ 快照一旦是「老版本展开基线 + 自己一张」，引擎每次加卡池/加卡都会丢。
  （本机实测：V0.30 相比 V0.29 在 `GeneralZombie/Zombie` **+11**、`ExtendZombie` +1、`GeneralPlant` +10；展开基线 `183/290/691` → `194/302/716`。覆盖包实测只有 184 / 291 / 692 ⇒ **Total 共缺 24 张**。）
- **正确做法**：
  1. **每次引擎大版本更新后，用「离线复刻 `BuildExpandedPacketBank()`」重出快照**（递归 Include 展开；注意 `MergePacketBankCategories` 是 `Array.AddRange`，**不去重**，要逐字复刻）；重出后**回读断言**「逐分类逐元素有序等于 · 引擎展开基线 + 自己那一张」，并落 `.bak-before-*`；
  2. 「兜底合并其它 Mod 卡」的列表**必须动态解析**：`GD.Load<Json>("res://Asset/Config/PacketBank/PacketBankResource.json")` → 反向闭包求出「包含某分类的所有卡池名」，别硬编码卡池名；合并时**跳过命名空间键**（含 `/`）并按 `saveKey` 去重。
- **闸门要加**（防止下次再犯）：
  - 「每个卡库的每个分类内**同名卡计数 == 1**」；
  - 「快照**精确等于**（含顺序）引擎展开基线 + 自己一张，自己那张恰好 1 次且在末尾」；
  - 「`Resources/Cards/*.tres` 文件名集合 == `provides.Packet` 集合」；
  - 「包内 `Resources/**` 与装机 `.pmod` 内同路径条目**逐字节零漂移**」。本机口径：221 条断言。

---

## E. 程序集身份与版本号

### E-01 所有 Mod 的程序集都叫 `ModAssembly` ⇒ 安卓上互相顶掉
- **现象**：Windows 上一切正常；**安卓上第二个 Mod 直接加载失败**。
- **触发场景**：`.csproj` 没写 `<AssemblyName>`（默认取包内文件名 `ModAssembly`）。
- **原因**：
  - **PC**：`XWModAssemblyLoader:195-197` 每个 Mod 一个**独立可回收 ALC** ⇒ 同名互不干扰，**所以本地永远测不出来**。
  - **安卓**：`:191-193 LoadAndroidAssembly` 全 Mod 共享**一个非可回收上下文**，按**简单程序集名**记账
    （`:151`/`:299-315`），撞上就 `throw BuildAndroidAssemblyConflict`（`:314`，原文要求 *main assembly names must be unique*）。
  - 第二条闸（`:316-324`）：与当前 AppDomain 里**任何**已加载程序集同名也抛 ⇒ 别撞 `PlantsVsZombies`/`GodotSharp`。
- **正确做法**：每个 Mod 的 `.csproj` 写 `<AssemblyName>` = **该 Mod `mod.json` 的 `id`**（小写无分隔，如 `supergatlingpea`），
  **不是 `name`**（可能是驼峰甚至中文）。`mod.json` 的 `runtimeAssembly` 不动（见 A-01）。
  - `build_runtime.py` 从 `<id>.dll` 读产物、装机时改名成 `ModAssembly.dll`，
    并在 `install()` 里**断言程序集身份 == id**（本项目工具 `tools/asmname.py`，零依赖读 CLR 元数据）。
  - ⚠️ **别把备份 `ModAssembly.dll.bak-*` 留在 `Runtime/`**（会触发 A-02 的护栏）；备份放包目录上一层。
  - ⚠️ **无源码的第三方 `.pmod`**：`#Strings` 堆里的程序集名可**等长原地覆写**
    （`asmname.find_assembly_name_slot` / `rewrite_assembly_name`；要求槽位独立且新名 ≤ 槽位容量），
    改完必须用 `System.Reflection.Metadata` 的 `PEReader` 全表遍历复核「除 name 外与改前完全一致」。

### E-02 版本号怎么抬（修 bug vs 加功能）
- **现象**：`mod.json` 写着 `1.0.0+1`，dll 里还是 `1.0.0.0`；或同一 tag 对应好几个构建。
- **触发场景**：改完直接重新打包，忘了抬版本 / 只改了一处。
- **原因**：版本号散在**多处**，且 `AssemblyVersion` 变了 ⇒ dll 字节变。
- **正确做法**：**按 SemVer 2.0.0 定档**（全文见 `SKILL.md` §「★★ 版本号规范（semver 2.0.0）」）：
  - 修 bug / 调数值 ⇒ **`PATCH` +1**：`1.0.5` → **`1.0.6`**
  - 加功能 / 加角色 ⇒ **`MINOR` +1，`PATCH` 归零**：`1.0.5` → **`1.1.0`**
  - 破坏性变更（改 id / key / 删内容）⇒ **`MAJOR` +1，其余归零**：`1.1.0` → **`2.0.0`**
  - ⚠️ **四段口径 `+0.0.1.0` / `+0.1.0.0` 已作废**；`.csproj` 的 `<AssemblyVersion>` 仍需四段数字，
    映射为 `MAJOR.MINOR.PATCH.REV`（`+BUILD` 的数字，缺省 `0`）。
  - 三处**一起改**：`mod.json` 的 `version` + `.csproj` 的 `<Version>/<AssemblyVersion>/<FileVersion>` + **重编译并重新打包**。
  - ⚠️ 一次改动里**没动过的 mod 别顺手抬版本**。
  - ⚠️ 版本号变 ⇒ 产物 sha256/大小、站点 `mods.js` 的 `fileSize`、Release 附件都要重刷。
  - ⚠️ `.pvzmodeproject` 的 `LastModifiedDate` **每次都要刷新**（别"沿用旧值"）；幂等校验要对时间戳归一化。
    *（注：`.pvzmodeproject` 属**编辑器工程**形态，上游模板已不使用，见基线文档 §7.2。）*

---

## F. 本机环境（会白耗时间的那些）

### F-01 bash 工具缺 coreutils
- **现象**：`dirname` / `cut` / `tail` / `mkdir` / `rm`，以及 `cp` / `ls` / `head` / `wc` 时有时无；
  `rm` 被 `safe-bin` shim 接管后直接失败。
- **触发场景**：用 bash 管道做文件统计/清理/复制。
- **原因**：WorkBuddy 的 Git Bash 环境 coreutils 不可靠。
- **正确做法**：文件统计/清理/复制**一律走 managed Python 或 managed Node**
  （Python `C:\Users\yanxulin002\.workbuddy\binaries\python\versions\3.13.12\python.exe`；
  Node `C:\Users\yanxulin002\.workbuddy\binaries\node\versions\22.22.2-3\node.exe`）。
  诊断脚本用 **Node 写 JS + `execFileSync` 直接调 `bash.exe -c`**，可精确控制 `env`/`cwd` 做 A/B。

### F-02 `node <脚本文件>` 返回 `rc=127` 且 stdout/stderr 全空
- **现象**：运行 node 脚本"什么都没发生"。
- **触发场景**：`node script.js`。
- **原因**：本机 bash 下的已知怪象（`node --version`、`node -e "..."` 却正常）。
- **正确做法**：逻辑改用 **`node -e "..."` 内联**。内联两禁忌：
  **禁用反引号模板串**（bash 双引号内会被当命令替换）；**`\\` 会被吞一层转义**（正则走 `new RegExp('...')` 或 `String.fromCharCode(92)`）。

### F-03 `fs.cpSync` 会把 node 进程直接杀掉
- **现象**：递归复制"什么都没发生"，`rc=127`、零输出、零 stderr。
- **触发场景**：`fs.cpSync(src, dst, {recursive:true})`。
- **原因**：同上进程级怪象（同进程的 `readdirSync`/`writeFileSync`/`copyFileSync`/`rmSync` 全正常）。
- **正确做法**：**递归复制手写**：`readdirSync({withFileTypes:true})` 递归 + `mkdirSync` + `copyFileSync`。

### F-04 Windows 批处理必须纯 ASCII（三项机械校验）
- **现象**：`.bat` 里一有中文，cmd 报一堆「不是内部或外部命令」+ 乱码，**连 `set "VAR=…"` 整行都被吃掉**。
- **触发场景**：`.bat`/`.cmd` 里写中文路径或中文文案。
- **原因**：cmd 按**当前代码页逐字节**读脚本，多字节序列被截断成"看起来像命令的碎片"。
- **正确做法**：中文一律放**外部配置文件（JSON，用 Node/Python 按 UTF-8 读）**，脚本里只做纯 ASCII 转发。三项机械校验缺一不可：
  1. **非 ASCII 字节 = 0**（逐字节 `>0x7F` 断言）
  2. **行尾必须 CRLF**（Write 工具产出的是 LF-only，cmd 对 LF-only 的 `goto`/`for` 块会解析出错 ⇒ 必须显式转 CRLF）
  3. **括号平衡**（校验时**排除 `echo` 与 `REM` 行**）
  另：**cmd 嵌套括号块超过两层就该重构成子过程**（`for %%T in (...) do call :do_one "%%T"`）。

### F-05 文件删除又贵又会被劫持
- **现象**：脚本里"清空重建"卡很久，或直接抛 `SHFileOperationW 0x2`。
- **触发场景**：`shutil.rmtree` / 批量 `os.remove`。
- **原因**：本机删除钩子把 `rmtree` 变成 SHFileOperation 且失败；逐文件 `os.remove` 单次约 0.6 s。
- **正确做法**：任何"清空重建"式脚本改成**增量**（只覆盖/新增，不删目录）；备份用 copy 而不是 move+delete。

### F-06 PowerShell 工具输出长期不回传
- **现象**：跑 PowerShell 命令拿不到输出。
- **触发场景**：用 PowerShell 做诊断。
- **原因**：本机环境已知问题。
- **正确做法**：诊断走 **bash（或 Node 调 bash）**，别指望 PowerShell。

### F-07 `BASH_ENV` 注入脚本不能依赖外部命令
- **现象**：启动期报 `dirname: command not found` 之类。
- **触发场景**：在 `BASH_ENV` 指向的脚本里用 `dirname`/`readlink`/`realpath`。
- **原因**：`BASH_ENV` 在 shell 启动**最早期**被 source，**早于 MSYS 挂载 PATH**。
- **正确做法**：注入脚本里只用 **shell 内建**（参数展开、`case`、`[[ ]]`）。

### F-08 诊断脚本里 `sys.argv` 被别人改写 ⇒ 自己的命令行参数被吞掉
- **现象**：给脚本传 `--json out.json`，脚本跑完**只打印结果、不生成报告文件**，且**零报错**。
- **触发场景**：脚本 A 用 `importlib` 加载脚本 B 的共享函数，而 B 里有 `sys.argv = ["<B 的名字>"]` 这类"给 B 造参数"的语句（或 B 在导入期读 `sys.argv`）。
- **原因**：`sys.argv` 是**进程级全局**；B 一执行就把 A 的参数列表换掉了，A 后面再遍历 `sys.argv` 自然读不到 `--json`。
- **正确做法**：A 在**加载 B 之前**先 `ARGV = list(sys.argv)` 留底，之后一律用 `ARGV`；同时把 B 里那段改成
  `saved = sys.argv; sys.argv = [...]; try: … finally: sys.argv = saved`。**任何"改 `sys.argv`"的库代码都必须 try/finally 还原**。

### F-09 `os.path.relpath` 跨盘符直接抛异常
- **现象**：诊断脚本输出到一半抛 `ValueError: path is on mount 'C:', start on mount 'D:'`。
- **触发场景**：`print(os.path.relpath(p))`，而 `p` 在 `C:`（例：`%APPDATA%` 的装机 `Mods\`），cwd 在 `D:`。
- **正确做法**：日志/表格里改用 `os.path.basename(p)`，或显式打 `Mods` / `dist` 标签；真要相对路径就先 `os.path.splitdrive` 比盘符。

### F-10 bash 里「长输出 + 管道」会被 SIGTERM 打断
- **现象**：`python build_all.py | grep -E "OK"` 返回 `rc=1` 且**stdout/stderr 全空**；同一条命令**不加管道**却正常。
- **触发场景**：多包编译 / 长日志脚本。
- **正确做法**：不要直接管道长输出。改 `python build_all.py > _build.log 2>&1; echo "rc=$?"; grep -E "…" _build.log`，并给命令设足够 `timeout`（9 包冷编译首轮可达 ~25 s/包）。

---

## G. 工程与构建脚本

### G-01 覆盖已被外部改动的文件前必须先 Read
- **现象**：Write 报 `File has been modified since read`。
- **触发场景**：别的会话/进程刚改过那个文件。
- **正确做法**：先 `Read` 再 `Write`；或先写到临时名，再用脚本读临时候处理落盘 + 删临时。

### G-02 生成器包目录里放工具脚本会被当产物打包
- **现象**：包体莫名变大 / 多出奇怪文件。
- **触发场景**：把临时脚本丢进 mod 包目录。
- **原因**：生成器常有 `sweep_stale_files` 之类的清理，或直接把目录全部打包。
- **正确做法**：工具脚本一律放 `.cache/`，**别放包目录**。

### G-03 派生生成器时把共享源当"要一起复制"的东西
- **现象**：两个 mod 的判定逻辑开始漂移。
- **触发场景**：复制一份插件源码再各自改。
- **原因**：判定逻辑一旦有两份就会分叉。
- **正确做法**：**共享源文件**（`runtime_shared/*.cs`，两个 csproj 各 `<Compile Include>`），
  入口常量写成 `= X.Y;` **转发**。**禁用共享程序集**（两个 `.pmod` 必须各带自己的 `ModAssembly.dll`）。

### G-04 同一份成品有多处副本，而某一份是「远古代」产物 ⇒ 逐条替换会拼出缝合怪
- **现象**：给 `dist/` 和装机 `Mods/` 两份 `.pmod` 做「只替换已存在条目」的同步，结果 dist 那份变成一个**既含远古多余条目、又含新资源**的怪包（条目数对不上、体积异常）。
- **触发场景**：同一包名在两处，但其中一处很久没更新（本机实测：`dist/阿尔法小队.pmod` 停在 **v5.0.0 / 22 条目**，而 `Mods/` 那份是 **9.2.x / 13 条目**）。
- **原因**：「只替换已存在条目、绝不新增/删除」的策略，前提是**两份同代**；跨代时旧包的私有条目会被"保留"下来。
- **正确做法**：同步前**先判代**（比对 `mod.json.version` / 条目数 / 包内 dll sha256）。不同代时**以权威副本整体覆盖**（本机口径：以**装机 `Mods/` 那份**为权威 —— 它是游戏真正加载的），覆盖前落 `.bak-*`、覆盖后**逐字节断言一致**；同代时再用"只替换已存在条目"的外科手术式同步（保留 `ZipInfo` 的 `date_time/compress_type/external_attr/internal_attr/create_system`，写完断言"未替换条目字节完全不变"）。

### G-05 版本号批量改写：`<AssemblyVersion>` 旧值是 4 段 ⇒ 按 3 段模板替换匹配不上
- **现象**：批量抬版本后，`mod.json` 版本对了，但 dll 的 `AssemblyVersion` / 文件属性还是旧的，**没有任何报错**。
- **原因**：`str.replace("<AssemblyVersion>1.0.0</AssemblyVersion>", …)` 遇到旧值 `1.0.0.0`（4 段）**匹配不上**。
- **正确做法**：以 `<Version>` 为**唯一真源**，用 `re.subn(r"<AssemblyVersion>[^<]*</AssemblyVersion>", …)` **全量重写**并补齐 4 段（`pad4()`），写成**幂等**脚本（跑第二遍零改动）。改完必须**回读 dll 身份**（`tools/asmname.py` 的 `read_assembly_identity(path)["version"]`）验证，别只看 csproj。⚠️ `GenerateAssemblyInfo=false` 的工程（无 `<AssemblyName>`/自管 AssemblyInfo）本来就是 `0.0.0.0`，**别去改**。

---

## H. 资源引用接缝：写错 = 角色隐形 / 整包回滚（★ 2026-10-13 黑橄榄骑兵团 v1.0.0 定案）

> **背景**：把自烘的 `.dat`/`.tres` 动画 + 自建弹体贴图打进 `.pmod` 后，包能装上、闸门也全绿，
> 但角色**只剩骨骼、没有像素（隐形）**。排查后才明白：Mod 包里有两套**完全不同**的引用机制，
> 各自有各自的合法取值范围，且**都没有任何报错提示**。本节是逐行读 V0.30 源码 + 拿 4 个已交付包交叉验证的结论。

### H-01 ★★★ `animeFile` 必须写 `"./<与 .tres 同名的>.dat"` —— `res://ModAssets/` 这个前缀**根本不存在**

- **现象**：角色隐形（图集加载不到）；包能装、日志未必报错、闸门也查不出。
- **根因链（5 条证据，逐行）**：

  1. `addons/AdobeAnimateEditor/Resource/AdobeAnimateData.cs` 的
     `ResolveAnimeFilePath` / `ResolveCompanionDatPath`：
     **`res://` / `uid://` / 绝对路径 ⇒ 直接取用**；**否则按 `.tres` 自身所在目录拼接**。
  2. `addons/ModEditor/ModSystem/ModLoader.cs:2628-2658 TryGetGodotResourcePath`：
     包内资源被映射为 **`user://ModsCache/<id>/<sha>/<guid>/…`** —— **不是** `res://ModAssets/`。
  3. ★ **全解包树 `grep -rl "ModAssets" .`（任意文件类型）= 空** ⇒ 该前缀在 V0.30 里**根本不存在**。
  4. `addons/ModEditor/FileSystem/XWFileSystemCompanionResourcePolicy.cs` 是**唯一**读 `animeFile` 的类，
     而它**只被编辑器 GUI 调用**（`XWFileSystemTree/List/Panel`、`TresExtensionMethod`），**不在运行时链路上**。
  5. ★ **拿已交付包交叉验证**（最有力）：
     `YetiGargAssault`（已装机验收）/ `AlphaSquad` / `SuperGatlingPaper` 全部是 **`"./同名.dat"`**；
     而「舞王/舞装战车」系列 5 个包用了 `"res://ModAssets/…"` ⇒ **可疑，需实机核查是否隐形**。
- **正确做法**：`animeFile = "./GatlingBlackFootballAnime.dat"`（**与 `.tres` 同目录、同名**）。
- **另外两条必须同时满足**：
  - `.tres` 与 `.dat` **同目录同名**（companion 约定，`XWFileSystemCompanionResourcePolicy.IsAdobeAnimateDatCompanion`
    就是按 `ownerPath.GetBaseDir().PathJoin(basename + ".dat")` 找的）；
  - `.tres` 里要**内嵌完整帧数据**（`frameCounts` / `sliceKeys` / `sliceMediaIds` / `sliceLayerIds` /
    `sliceDrawOrders` / `sliceTransforms` / `sliceAlpha` / `sliceFlags` / `mediaRects` / `mediaDictionary` /
    `layerDictionary` / `clips` / `events`）。
- ★★ **关键认知：像素不在 `.tres` 里**。`mediaDictionary` 只存「媒体名 → 索引」（如 `"head.png": 27`），
  **真正的图集像素全在 `.dat` 里** —— `AdobeAnimateData.HasEmbeddedAtlasSource()` 的实现就是
  `FileAccess.FileExists(ResolveAnimeFilePath())`。⇒ **`.dat` 路径写错 = 一点像素都没有。**
- **闸门建议**（加一条就能永久防住）：
  ```python
  exp = "./" + os.path.basename(tres_name)[:-5] + ".dat"
  tgt = normpath(dirname(tres_name) + "/" + val)
  assert val == exp and tgt in zip_names, (tres_name, val)
  ```

### H-02 ★★★ `[ext_resource]` 的 `path` 只有两种合法值，其余 ⇒ **整包回滚**

- **源码**：`ModLoader.cs:612-676 PreparePackageResourceReferences` 遍历包内每个 `.tscn`/`.tres`，
  **只处理 `[ext_resource ...]` 行**（`:636-639` 对其他行 `continue`）。逐行判据：

  ```
  path = ExtractAttribute(line,"path"); type = ExtractAttribute(line,"type")
  :644  path 为空（UID-only）      ⇒ throw "UID-only resource reference has no portable path"
  :647  isPacked = (type != "Script") && TryResolvePackagedResource(...)   ← ★ Script 永不按包内相对路径解析
  :649  isPacked ⇒ TryGetGodotResourcePath(...) → 回写成 user://ModsCache/…
  :657  else if (!path.StartsWith("res://") || !ResourceLoader.Exists(path))
  :659      if (!(type == "Script") || !(ext == ".tscn") || !IsCharacterPackageDependency(自身))
  :661          ⇒ throw "missing or nonportable resource reference: <自身>: <path>"   ⇒ 整包被拒
  :663      else continue                                       ← 唯一豁免分支
  ```

- ★★★ **豁免成立需要三条件同时满足**（`:659`）：
  1. `type == "Script"`；
  2. **当前文件是 `.tscn`**（`ext` 是**本文件**扩展名，与 `path` 指向的文件无关）；
  3. **本文件路径** = `Resources/Characters/<类别>/…`，类别 ∈ `Plants|Zombies|Props|Vases|Mowers|Items|Graves|Craters`
     且**总段数 ≥ 5**（`IsCharacterPackageDependency` `:2248-2256` + `IsKnownCharacterCategory` `:2239-2246`）。
- ★★★ ⇒ **`.tres` 里的 `type="Script"` 完全不豁免，路径必须真实存在**。
  **踩坑实录（2026-10-13）**：三份 `*ComponentSet.tres` 把 `CharacterComponentSet.cs` 写成
  `res://Script/Component/TowerDefense/Character/CharacterComponentSet.cs`（**不存在**）⇒ 整包被拒；
  真路径是 `res://Script/Component/Runtime/CharacterComponentSet.cs`。对照：工作区其余 8 份
  `*ComponentSet.tres`（含已成功加载的 `SuperGatlingPaper`）**全部**写 `Runtime/…`。
- ★★ **相对路径的 Script（`./X.cs` / `../Script/X.cs`）= `:657` 为真 + `:659` 为假 ⇒ 直接抛**
  （`:647` 的 `type != "Script"` 保证 Script 不会被当包内资源解析）。
  这就是「伴生脚本**不放** `.cs`、改走 `.tscn` metadata `mod_character_script_path`」的原因（见 H-05）。
- ★★ **豁免 ≠ 可以乱写**：豁免只是「不抛异常」；若该 `res://` 脚本不存在，Godot 加载场景时根节点会
  **丢掉脚本** ⇒ 伴生脚本的前提（`authoredRoot.GetType()` 必须是官方 `TowerDefenseCharacter` 子类）破产
  ⇒ **角色静默失效（不报错、只是行为全无）**。⇒ 闸门里被豁免的那部分**也必须单独校验存在性**。
- **正确写法**：
  - 包内贴图/场景：`./ProjectileBlackOliveIronPea.png`、`../Config/TowerDefenseXxx.tres`、
    `../../../../Animations/YetiGargAnime.tres`；
  - 官方资源：`res://Prefab/TowerDefense/Character/TowerDefenseZombie.tscn`、
    `res://Resource/TowerDefense/Collision/CharacterHitBoxes/Rect_44x70_At_4_n2.tres`、
    `res://Script/Component/Runtime/CharacterComponentSet.cs`（**这些要真存在**）。
- **闸门建议**（★ 照抄这个形状，见 `build_boc_runtime.py::audit` 的 G-A~G-F）：
  - ★★ **绝不可对 `type="Script"` 一刀切 `continue`** —— 那正是漏报根因（旧闸门只报了 22 处，
    69 处里的 Script 全没查，于是漏掉 3 处必死引用）。
  - G-C：相对路径必须解析到包内已存在条目（`os.path.normpath(os.path.join(dirname, val))`，**别用字符串拼 `+ "/"`**，`val` 已带 `./` 时会拼出多余段）。
  - G-D：`res://` 引用按 H-02 的三条件判定豁免；**不豁免的**必须 `os.path.exists(TREE/相对路径)`。
  - G-E：每个 `[ext_resource` 行必须有非空 `path=`（对应 `:644`）。
  - G-F：**被豁免的** `res://…*.cs` 同样必须存在（防「静默失去脚本」）。
  - ★ 反向验证：把闸门跑在**修复前**的 `.pmod` 上，确认它真能报出违规（本例：旧包 `必存 62/豁免 9/违规 5` → 新包 `57/9/0`）。

### H-03 ★★ ModLoader 会**剥掉所有 `uid="…"`** ⇒ 别依赖 uid

- `PreparePackageResourceReferences` 对 `[gd_resource]` / `[gd_scene]` 头行与 `[ext_resource]` 行都做
  `Regex.Replace(line, "\\s+uid=\"[^\"]*\"", "")`。
- ⇒ 从编辑器导出的 `.tscn`/`.tres`（带 `uid://…`）打进 mod 后，**uid 全没了**，
  一切退化为**按 path 解析**。⇒ 所以 H-02 的 path 正确性是**唯一**保障。
- ⇒ 另一个推论：U**ID-only 引用**（只有 `uid` 没有 `path`）会**直接抛错**
  （`"UID-only resource reference has no portable path"`）⇒ 导出时必须保证每个 `[ext_resource]` 都有 `path`。

### H-04 ★★ 包内资源类别是按**目录前缀**自动注册的 —— `Resources/Animations/` 是特例

- `ModLoader.cs:1711-1725` 的映射表：
  `Resources/LevelCatalogs/→Level`｜`Resources/Maps/→Map`｜`Resources/Cards/→Packet`｜
  `Resources/PacketBank/→PacketBank`｜`Resources/Projectiles/→Projectile`｜`Resources/Collectables/→Collectable`｜
  `Resources/Mowers/→Mower`｜`Resources/Shovels/→Shovel`｜`Resources/Survivals/→Survival`｜
  `Resources/Tutorials/→Tutorial`｜`Resources/NpcTalks/→NpcTalk`｜`Resources/Shops/→Shop`｜
  `Resources/BGMConfigs/→BGM`。
- ★ **`Resources/Animations/` 不在映射表里** —— 它是合法目录（`XWModProjectLayout.cs:38` 白名单 +
  `:108` DropRule `tres/res/dat` + `AdobeAnimateData`），但**不做独立注册**，
  只作为「被场景按相对路径引用」的资源存在。⇒ **别指望它进任何 Registry。**
- ⇒ 同理 `Resources/Projectiles/Sprite/<Key>/Projectile<Key>.tscn`（PackedScene）不会
  （也不应）被当成 `Projectile` 类别去注册 —— 该类别的注册对象是 `.tres` 形态的
  `TowerDefenseProjectileData`。

### H-05 ★★★ 伴生脚本为什么**不能**放包内 `.cs`（H-02 的直接推论）

- `:647` 的 `type != "Script"` 使 **Script 类引用永不按包内相对路径解析**；而 H-02 的豁免只覆盖
  「`.tscn` + 角色包」⇒ 包内 `.cs` 若用 `res://` 写会因不存在而抛，用相对路径写**也会抛**。
- ⇒ 唯一可行路线：`.tscn` 根绑**官方**脚本 + metadata：
  `mod_character_script_path = "../Script/<类名>.cs"`（**运行时只取文件名**）、
  `mod_character_script_binding = "CompanionOnly"`；真逻辑放本包 DLL，类名 == 文件名，
  且 `类型.IsAssignableFrom(场景根.GetType())`（见 `XWModCharacterCompanionRuntime.cs:210-261`）。
- ⇒ 因此 `.tscn` 里那句 `[ext_resource type="Script" path="res://Prefab/…/TowerDefenseZombie.cs"]`
  **是必需且必须真存在**的（它被豁免，但路径错 = 角色静默失效）—— 见 H-02 的 G-F 闸门。

### H-06 ★★ `overrides.PacketBank` 是**撞车高发区** ⇒ 卡池优先走运行时注入

- 卡池库名（`GeneralZombie` / `TotalZombie` / `Total`）是**全局固定**的 ⇒ 任何两个声明
  `overrides.PacketBank` 的包**必然** `OverrideConflict`，加载顺序在后者 wins、前者被顶掉
  （`XWModLoadPlan.cs:406-443` 打 `legacy/<category>/<key>` 冲突键；面板会显示
  `覆盖顺序：A → B；生效者：B`）。
- 实证（2026-10-13 全量扫描 23 个已装包）：只有 3 个包声明它，库名**完全相同** ⇒ 冲突；
  而 `向日葵女王僵尸` / `奶龙僵尸` / `tour_dance_commander` 等僵尸包**一律不声明**，
  它们的 DLL 里都带 `TOWERDEFENSE_PACKETBANKS` 字符串 ⇒ 走**运行时直改**。
- ★★ **推荐做法**：在 DLL 里直接改
  `ResourceManager.Instance.TOWERDEFENSE_PACKETBANKS[key].category["Zombie"]`（`Godot.Collections.Array`），
  并在 `SceneTree.process_frame` 里**每 N 帧自愈**（重读字典 → 缺则补 / 重复则去重）
  ⇒ **与别人的静态覆盖顺序无关**，且**不必声明 `overrides`**。
- ★ `TOWERDEFENSE_PACKETBANKS` 本身由 `ResourceManager.cs:638-660 BuildExpandedPacketBanks()`
  从 `PacketBankResource.json` 展开（`Include` 递归 + `MergePacketBankCategories` **不去重**）
  ⇒ 引擎基线上**没有**自动吸收 mod 的 Packet 到任何卡池，必须自己注入。
- ★ `ModsCache` 按**包 SHA256** 分目录（`ModsCache/<mod id>/<sha256>/<hash>/content/`）
  ⇒ 改了包内容就是新目录，**旧失败缓存不会拖累复验**。

---

## I. 动画数据的「真几何」「叠加层」与绘制主序（★ 2026-10-13 黑橄榄骑兵团 第 30 轮定案）

### I-01 ★★★ `.dat` 的 layer 表**不是**运行时几何 —— 拿它拼图会得到假象

`AdobeAnimateData` 里有**两条**数据通路，别搞混：

| 通路 | 谁在用 | 内容 |
|---|---|---|
| `.dat` 头 18 字节 + 像素块 | **运行时** | `TryReadEmbeddedAtlasImage:1690-1712` → `ReadEmbeddedImageAtlasFromDat:1629-1646`（`file.GetBuffer(len)` → `Image.CreateFromData(…, Rgba8)`） |
| `.dat` 的 media/layer/clip/event 表 | **ModEditor 预览** | `ParseEditorDatHydration:809-900`；运行时**不读** |
| `.tres` 的 `frameOffsets/frameCounts/sliceKeys/sliceMediaIds/sliceLayerIds/sliceDrawOrders/sliceFlags/sliceTransforms/sliceAlpha/mediaRects` | **运行时几何 100%** | `BuildPackedRuntimeData:1446-1505` |

⇒ 写渲染/比对工具时**必须**走 `.tres` 的 slice 数组；用 `.dat` 的 layer 表渲染会把
**同一位置的多套互斥变体全堆在一起**，看着像「贴图严重错乱」，其实几何是对的。

**运行时几何语义**（逐字对应 `BuildPackedRuntimeData:1466-1495`）：
- 第 f 帧的切片 = slice 数组的 `[frameOffsets[f], frameOffsets[f] + frameCounts[f])`；
- 循环是 `for 帧 → for 层 → for 元素` ⇒ **帧内数组顺序 == 绘制顺序**（`list7.Add(num3)` 单调递增）；
- 四角 = `M·(cx,cy) + O`，`(cx,cy) ∈ {(0,0),(w,0),(0,h),(w,h)}`，`(w,h) = mediaRects[mediaId].size`；
- 不变量：`Off[0]==0`、`Off[i+1]==Off[i]+Cnt[i]`、`Off[-1]+Cnt[-1] == len(sliceLayerIds) == len(sliceTransforms)/6 == len(sliceAlpha)`。
- **`sliceFlags` 恒 0**（`:1506 list8.Add(0)`），没有镜像/翻转位。

### I-02 ★★★ 同一部位常是「两层叠加」——判「谁盖谁」看 `layerId`，可见性只管「画不画」

融合版把「有防具／无防具」「完整／轻损／重损」做成**独立层**，并且**每一帧都带全套**。
典型例子（`BlackHorseAnime`，166 帧里逐帧都在）：

| 层 | 01 团长 id | 02 骑兵 id | 内容 |
|---|---|---|---|
| `head` | 22 | 40 | **裸**绿马头（绿脸／绿嘴／红冠／尖角；单层绿像素 1471 px） |
| `Armor` | 23 | **11** | **黑橄榄头盔**（只覆盖马头上半的骷髅盔＋面罩） |
| `2_2` / `3_2` | 1 / 38 | 2 / 42 | 同族·轻损 / 重损（默认关） |

⇒ **官方基准 = `head` 与 `Armor` 都可见，且头盔后画**（两层叠出「戴盔的马头」）。

- ★★★ **绘制主序 = `layerId`**，两条路径都是：
  · GPU 快路径按 slice 数组顺序发射（`AdobeAnimateDrawItemBuilder.cs:353-381`），
    而数组序恒等于 `layerId` 升序（`AdobeAnimateData.cs:1467-1496` 的双循环 `for 帧 → for 层 k → for 元素`）；
  · CPU 排序路径显式构造 `AdobeAnimateSortPath(rootZIndex, treeOrderPath, LayerId, DrawOrder, …)`
    （`:416 / :446`）⇒ **第一主键就是 `LayerId`**。
  ⇒ **只重排 slice 数组没用，必须改 `layerId`。**
- ★★★ **判据**：`layerId(Armor) > layerId(head)`。反例：02 = `head` 40 / `Armor` 11
  ⇒ 绿马头把头盔整个盖住（游戏里表现为「马没有头盔，只有一圈盔边露出来」）。
- ★ **修法**：把 `Armor` 的 `layerId` 提到 `max(所有层 id)+1`，同步
  `layerDictionary` / `sliceLayerIds` / `sliceKeys`（高 16 位 = layerId）＋ **数组内次序**（双保险）。
  文本级实现见本项目 `build_boc.py::promote_layer_after_text()` —— 对 `.tres` 的
  `PackedInt32Array` 做 **token 级**重排再回填（零精度损失）、幂等（已在 `anchor` 之后则原样返回）。
- ⚠️⚠️ **别用 `LayerVisible` 关「裸态层」** —— 本项目第一版把 `head` 关掉，结果
  **连绿嘴一起关掉了**（马头只剩黑盔），与官方基准不符。教训：
  **「可见性」只能控制画不画，「`layerId`」才能控制谁在上。**
- **可见性开关** = Sprite `.tscn` 的 `Animation/LayerVisible/<层名> = true|false`，
  运行时**逐片**门控：`AdobeAnimateDrawItemBuilder.cs:379/395/428 → IsLayerVisible`；
  `:947-962`：`AllLayersVisible` ⇒ 全画；`CanUseLayerMask` ⇒ 查 `layerMask` 位图；
  否则查 `LayerVisibleValues[layerId]`。**没写的层 = 默认 true；`layerId` 越界也 true**（`:957-961`）
  ⇒ 把某层 id 提到 `max+1` **不会**让它变隐形。
  它真正适合的用途：关掉「同位置真正互斥的档位」（如 `2_2` / `3_2`）。
- **闸门写法**：① 家族正则圈（`^(Armor|2_2|3_2)$`、`^GatlingPea_helmet ?[23]?$`）断言「可见数 == 1」；
  ② 解析 `.tres` 的 `layerDictionary`，断言 `layerId(Armor) > layerId(head)`。
- **修法落点**：改生成器**并且**同步交付源 `.tscn`（双副本先判代再同步），旧版留底 `*.tscn.bak-…`。

### I-03 ★★ 自查工具要「带可见性」＋「能定位颜色归属层」＋「多图共用坐标系」

自造渲染器若只做几何、不读 `.tscn` 的 `LayerVisible`，等价于「全部层都可见」，
结论**会反过来**。渲染入口必须显式传可见性集合；多图并排比对时还要能**共用同一坐标系**
（否则各图各自算 bbox，位置对不上）。

一套好用的排查工具（本项目 `_blackolive/tools/`）：

| 工具 | 作用 |
|---|---|
| `k3_tres_render.py` | 真几何 + `--tscn` 可见性；`bbox=` 参数让多图共用坐标系 |
| `k6_fix_contrast.py` | 四列对照（修复前／上一版错解／本版／官方基准） |
| `k7_baseline_ab.py` | 整身对照 + 前景 IoU（全剪辑全帧搜索最佳姿态） |
| `k9_layer_probe.py` | **逐层单独渲染**，按颜色统计定位「某块颜色属于哪一层」 |
| `k10_order_test.py` | 顺序实验：把某层移到帧末，看是否等于官方基准 |
| `k11_probe_order.py` | 打印帧内 `sliceLayerIds` 序列，检验「数组序 == layerId 升序」 |

另外：`.dat` 的 PascalString 位宽用 **u32**（`ReadManagedPascalString:1004` 是 `reader.ReadInt32()`），
两种位宽线上都能跑（运行时**不读字符串表**），但 u32 才是引擎口径、ModEditor 预览才正确。
