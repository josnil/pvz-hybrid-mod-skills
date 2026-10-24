# 官方模板基线（最高优先级）

> **对齐日期**：2026-10-24 ｜ **上游**：<https://github.com/axh-xecoy/pvzhe-mod-template>
> **上游锚点**：`main` 分支、`pushed_at` 2026-10-24T02:05:16Z、仓库体积 1008 KB / 268 个文件
> **上游自述**：以**已发布的 Windows C# 游戏 0.31.0** 为默认基线，保留 0.30.0 输入支持。

## 0. 效力条款（先读这一段）

1. 本仓库三个 `pvz-hybrid-*` 技能里，**凡涉及「流程、字段契约、身份、版本、构建、安装、验证、目录」的规定，一律以上游模板为准**。
2. 本仓库技能与模板**重复**的内容 → 以模板为准，本仓库只保留**模板未覆盖的实测细节**。
   本仓库技能与模板**冲突**的内容 → **以模板为准**；旧口径按 §7 的「废弃表」处理。
3. 本仓库技能的价值边界：**只补充实测细节**（数值、字段类型、动画/图集管线、护具槽、踩坑现象）。
   这些细节**不构成契约**——字段真伪仍须回到已发布 DLL/PCK 与实际运行核验（模板原话：
   「具体游戏字段先作为社区提取线索」）。
4. 模板只把本仓库当作**线索来源**，并已明确删除本仓库若干约定（见 §7.2）。
   **不得**再用本仓库的旧约定去覆盖模板；反之才是允许方向。
5. 上游自述定位：**「本模板是基于发布包实测的社区示例，不是官方 SDK」**。
   因此本文的「官方」= 本组织指定的**上游基线**，不是引擎厂商背书。

## 1. 环境基线

| 项 | 模板规定 |
|---|---|
| 系统 | Windows x64 |
| 游戏输入 | **已发布 C# 发行目录**（EXE + PCK + `data_PlantsVsZombies_windows_x86_64/`），推荐 0.31.0 |
| 游戏源码 | **不需要**，且不得要求玩家提供或把游戏内容纳入模板/产物/版本控制 |
| .NET | **9.0 SDK**，最低 9.0.100；`global.json` = `9.0.100` + `rollForward: latestFeature`；目标框架 `net9.0` |
| Python | **3.11+**（实测 3.12）；核心构建/解包**仅用标准库**；可选素材处理才需 Pillow |
| Godot 编辑器 | **不需要安装**（编译只引用发行包里的 `GodotSharp.dll` 与 `PlantsVsZombies.dll`） |
| 引擎版本 | 本轮发布 PCK 标记 **4.7.0** |
| Shell | PowerShell；命令在**模板根目录**执行 |

## 2. 目录契约

```
<项目根>/
├── mod/mod.json              # 包身份、入口与 API 声明；资源显式允许名单
├── mod/Assets/               # 自有素材（仅需要时创建）
├── src/HelloMod/Entry.cs     # 生命周期入口
├── src/HelloMod/HelloMod.csproj      # 普通 .NET 类库；宿主引用不复制到输出
├── src/HelloMod/{Components,Features,Adapters}/   # 复用组件 / 业务能力 / 版本适配（按需创建）
├── tools/mod.py, tools/pck.py        # prepare / extract / build / check / install / verify
├── tools/HostProbe/                  # 只反射发布程序集，不调用游戏入口
├── tools/runtime_test.py             # 独立发布副本的实机验证
├── .agents/skills/                   # 按任务调用的 Skills（按需读取 references）
├── docs/、docs/wiki/                 # 兼容证据、扩展原则、按版本组织的游戏知识
├── tests/                            # PCK 边界与打包隔离检查
├── .game/{current,old}/              # 本地发行副本（不提交，只留两槽）
├── .work/                            # 本地引用/分析/证据（不提交）
├── dist/                             # 构建与验证产物（不提交）
├── game-compatibility.json           # 支持的发行版摘要（PCK/DLL sha256）
└── template.lock.json                # 上游来源与修订
```

`.gitignore` 必须含：`.work/`、`.game/`、`dist/`、`**/bin/`、`**/obj/`、`**/__pycache__/`、`*.user`。

## 3. `mod.json` 契约（★ 与旧版最大分歧）

```json
{
  "schemaVersion": 3,
  "id": "local.hello-world",
  "name": "Hello World 模板",
  "version": "0.1.0",
  "author": "Mod 开发者",
  "description": "最小托管 Mod：生命周期日志与 UI 挂载文字。",
  "playInstructions": "启用后重启游戏，查看 Hello World 文字及 HELLO_READY 日志。",
  "runtimeAssembly": "Runtime/ModAssembly.dll",
  "runtimeEntryType": "HelloMod.Entry",
  "runtimeApiVersion": 1,
  "runtimeAssemblyPolicy": "required",
  "resources": [],
  "scripts": [],
  "dependencies": []
}
```

| 字段 | 规则（模板校验口径） |
|---|---|
| `schemaVersion` | **3**。宿主接受 1–3；`>3` 直接抛 `unsupported mod schema version`。**新包一律写 3** |
| `id` | **1–32 个 ASCII**，字符集 `[0-9a-z_.-]`；无大写/空格/斜杠；`.`、`..` 不算有效身份。推荐点分命名空间风格（`local.hello-world`、`zombie-kill-counter`） |
| `name` | 必填显示名，可含中文；模板不设 32 字符上限 |
| `author` | 必填，**≤32 个 UTF-16 单元**（emoji 等补充平面字符占 2） |
| `version` | **≤32 字符，SemVer**：`major.minor.patch[-prerelease][+build]`；不加 `v`、不写 `1.0`、数字段禁前导零；默认 `0.1.0` |
| `playInstructions` | 模板新增字段：面向玩家的启用/观察说明 |
| `runtimeAssembly` | 硬校验，**恰好** `"Runtime/ModAssembly.dll"` |
| `runtimeApiVersion` | **宿主当前 API 版本**。0.30 源码实测 `XWModRuntimeApi.CurrentVersion = 3`、`SupportedVersions = [1,2,3]`（0.29 时代为 `1`）。**新包建议写 3**；写不支持的值 ⇒ 入口 init 返回 false ⇒ 无条件整包回滚。⚠️ 模板示例 `mod.json` 写的是 `1`（**兼容但非当前**），与引擎实测并列给出，见 §10 第 7 条 |
| `runtimeAssemblyPolicy` | `"required"` / `"optional"`；新 Mod 建议先 `optional` |
| `resources` | **显式允许名单**，不列不进包 |
| `postId`（可选） | 社区投稿 ID 字符串（如投稿链接 `/mods/121` ⇒ `"121"`）；与 `id` 无关 |

> **两条身份纪律**：① `id` 主题明确后即定，**已有项目加功能不改 id**；
> ② `id` 影响启用配置/依赖/资源身份/设置/Mod 数据/关卡进度，装了之后换 id **必须先分析迁移影响**。

## 4. 构建 / 安装 / 验证命令链（模板唯一入口）

```powershell
dotnet --list-sdks
python --version
$game = '<你自己的发行目录>'
python tools/mod.py prepare --game-dir $game     # 导入 .game/current，最多留一个 .game/old
python tools/mod.py build                        # -> dist/<id>.pmod + dist/build-info.json
python tools/mod.py check
python tools/mod.py install --mods-dir $env:APPDATA\Godot\app_userdata\植物大战僵尸杂交版\Mods
python tools/mod.py verify --log <本次 godot.log>   # -> dist/verification.json
python tools/runtime_test.py                     # 独立存档实机验证（约 20 s，窗口会弹出）
python -m unittest discover -s tests -v          # 改动工具后必跑
```

发布加严：

```powershell
python tools/mod.py build --release
python tools/mod.py check --release --mods-dir '<实际 Mods 目录>'
```

- `--release` 拒绝已知示例身份（`local.hello-world` / 作者占位值）与占位信息。
- `check --release` 还核对**包内清单与当前 `mod.json` 一致** ⇒ 改名/改作者/改版本后**必须重建**。
- `--mods-dir` 只读扫描该目录**直接包含**的 `.pmod` 按 id 查重（不保证全网唯一）。
- 同 id **同文件名**的旧包确属当前 Mod 时才可加 `--allow-update`。
- **`.pmod` 就是最终分发文件**：ZIP，不是 Godot PCK，**不要** `--export-pack`。
- `dist/build-info.json`、`.work/`、整个发行目录、自己的 `bin/` **都不是分发物**。

## 5. 打包边界

- 包里只有**允许名单**内容：`mod.json` + `Runtime/ModAssembly.dll`（+ 你在 `resources` 里显式列出的自有资源）。
- **禁止**把 `GodotSharp.dll`、`PlantsVsZombies.dll`、游戏 DLL 或整份 `bin/` 放进包（模板排错清单明列）。
- 新素材放 `mod/Assets/`，并在 `resources` 声明；包内相对路径**不会**自动变成宿主 `res://`。
- 普通文件用 `context.PackageRoot` + 包内相对路径读；引用 `res://` 必须由发布索引证实。
- 编译引用只留本地 `.work/references/`（由 `prepare` 从发行包反射/提取）。

## 6. 验证纪律（模板口径，直接取代旧「闸门全绿即可」心态）

1. 先按 `verification-strategy` 明确**本轮变化、实际条件、可证伪断言**，再 build/check。
2. **采集 / 判定 / 报告分离**；报告的修复先做离线复核，不反复重启整套游戏。
3. **构建成功 ≠ 功能成功**；日志/包静态检查**不能**替代运行结论。
4. 优先在**独立用户目录**验证，记录真实路径；人工试用 ≠ 装进日常存档。
5. 最终包必须再验一次**不带测试参数的普通启动**；测试夹具不得默认成为发布功能。
6. 保留日志、退出码、失败证据；**不把未知诊断过滤成成功**。

## 7. 冲突解析

### 7.1 采用模板、改写旧文的项

| # | 旧口径（本仓库技能） | 现行口径（模板） | 处理 |
|---|---|---|---|
| 1 | `schemaVersion: 2` | **3** | 已改写 |
| 2 | 四段版本 `1.0.5.0` / 递增 `+0.0.1.0`、`+0.1.0.0` | **SemVer 三段**，PATCH/MINOR/MAJOR 定档 | 已改写（2026-10-17 规范为准） |
| 3 | `id` 「小写无分隔」（`supergatlingpaper`） | `[0-9a-z_.-]`，**点/短横线合法**，推荐 `local.hello-world` 风格 | 已改写 |
| 4 | 判据来自**解包树**，前置是游戏源码 | 判据来自**已发布发行版**，`prepare` 导入 `.game/current`，**无需源码** | 已改写（源码降级为可选的内部查证） |
| 5 | 游戏内 **F3** 编辑器为默认前提 | 模板**不使用**游戏内编辑器，已删除该流程 | 已标注废弃 |
| 6 | 「一切从 `build_plant_*.py` 复制」的固定生成器 | 构建入口统一为 `tools/mod.py`；自研生成器仅为**历史参考** | 已改写 |
| 7 | 「两份游戏构建各跑一遍」双构建环境 | **单一发行基线** + `--release` 检查 | 已标注废弃 |
| 8 | 手改 `enabled_mods.json` / 登记 `mod_editor_recent_projects.cfg` | 通过 **Mod 管理界面**启用并重启；**不要手工覆盖** `enabled_mods.json` | 已改写 |
| 9 | 绝对化表述（「唯一」「永远」「必须这样」） | 改为**有条件的调查 + 验收步骤** | 逐条软化 |
| 10 | 作者机器绝对路径（`D:\zzz\...`、`<Zombie>/.workbuddy`）作为通用前置 | 属**本地历史工作区**，不得作为他人前置 | 已标注 |

### 7.2 模板已明确删除的本仓库约定（不得再引入）

> 依据模板 `docs/community-skill-extraction.md`「内容优化」节原文：

- 作者机器路径；
- **F3 / 编辑器打开流程**；
- 工程标记交付要求（`.pvzmodeproject`、72 目录、`mod_editor_recent_projects.cfg` 等）；
- **固定生成器复制**；
- **双构建环境**；
- 平台发布 / 邀请等约定；
- 社区口吻的「唯一原因」「永远每帧」「只能用某种工具」。

## 8. 解包口径的重叠与切分（★ 需人工确认，见 §10）

本仓库曾规定「解包**只能**用 GDRE Tools，禁止其他工具或自制脚本」。模板提供另一条官方通道：

| 目的 | 通道 | 产出 | 是否冲突 |
|---|---|---|---|
| 需要**工程级还原**（`.cs`、`.tscn`、可编辑工程树） | **GDRE Tools**（本仓库既定硬规定，仍有效） | Godot 工程树 | — |
| 发行版**按需取资源/配置**（release-only 玩家路径） | `python tools/mod.py extract --pck ... --path/--prefix ...` | **原始文件提取**，不是工程还原 | 用途不同，**不互相替代** |
| 全量发行资源索引 | `python tools/mod.py prepare` → `.work/pck-index.json` | 索引 + 缓存 | — |

模板对 `extract` 的边界写得很明确：只支持**独立未加密 PCK v2/v3/v4**，遇到嵌入式/加密/稀疏/差分包**明确失败**；
且 `.ctex` / `project.binary` / `.gdc` 仍是导入或编译格式，**不会**被还原成可编辑源码。

## 9. 模板 Skill 路由（我方三个技能如何退位）

| 玩家诉求 | 模板 Skill（首选） | 我方技能的角色 |
|---|---|---|
| 需求理解 / 缺口澄清 / 路由 | `pvzhe-mod-guide` | 不参与（避免重复路由） |
| 入口、编译、打包、发布字段 | `pvzhe-mod-develop` + `references/identity-and-release.md` | 仅补实测字段/坑 |
| 安装、启用、运行验证 | `pvzhe-mod-verify` | 仅补实机现象 |
| 改已有数值/费用/冷却 | `pvzhe-resource-edit` | `plant-authoring` 的字段细节 |
| 新植物 | `pvzhe-plant-create` | `pvz-hybrid-plant-authoring`（细节补充） |
| 新僵尸 | `pvzhe-zombie-create` | `pvz-hybrid-zombie-authoring`（细节补充） |
| 发射/射速/散射/出弹点 | `pvzhe-character-fire` | `plant-fire-pipeline`、`zombie-fire-and-marker` |
| 护具/破甲暴走 | `pvzhe-character-armor` | `zombie-package-and-gates` 护具章 |
| 换皮/动画/换头/对部件 | `pvzhe-character-skin` | `plant-skin`、`zombie-skin-and-head` |
| 地图/行数/地形 | `pvzhe-map-create` | `tools/map` 设计线索 |
| 快捷键/触屏 | `pvzhe-input-bindings` | 「暂停期间的输入与 GUI」章 |
| 只有 `.pmod` 想改数值 | `pvzhe-pmod-patch` | `plant-pmod-hotpatch` |
| 新投射物 | `pvzhe-projectile-create` | `plant-fire-pipeline` 弹体章 |
| 设置/存档/控制效果 | `pvzhe-mod-settings`、`pvzhe-gameplay-feature` | 实测细节 |
| 关卡 / 章节 / 模式入口 | `pvzhe-level-create`、`pvzhe-mode-create` | 不覆盖 |
| 同步上游模板 | `pvzhe-project-update`（使用者）/ `pvzhe-template-upgrade`（维护者） | 不覆盖 |

## 10. 仍待人工确认（不要当已决事项）

1. **工程形态**：是否把现有 `ModWorkspace` 生成器工坊整体迁到模板的 MDK 工程形态（`src/` + `mod/`）。
   本文只做「契约对齐」，**未迁移**任何现有 mod 工程。
2. **`schemaVersion` 迁移**：新包写 3 已定；**既有的 28 个 `mod.json` 尚未批量改**（涉及重打包与验证）。
3. **`id` 命名风格**：模板允许点号并推荐点分命名空间；我方既有 id 全是无分隔（`supergatlingpea`）。
   **既有 id 不建议改**（会破坏启用配置/存档/资源身份）。新项目是否统一用点分风格，待定。
4. **解包双通道**（§8）：需确认「GDRE 管工程还原 / `mod.py extract` 管发行取资源」的切分是否采纳。
5. **零散实证内容的去留**：本仓库 900 KB 中的数值/字段/动画细节，模板只承认「线索」地位；
   是否逐条按 0.31 重验，需另立验收轮次。
6. **`version` 32 字符上限**与 `-PRERELEASE` 渠道后缀（如 `-hand`）并用是否会长到超限，需新项目命名时注意。
7. **`runtimeApiVersion` 取值分歧（重要）**：模板示例 `mod.json` 写 `1`，而 0.30 发行版源码实测
   `XWModRuntimeApi.CurrentVersion = 3`（`SupportedVersions = [1,2,3]`）。两者**都能加载**（1 是兼容取值），
   但「当前版本」按引擎是 **3**。本文档取「新包写 3」，与模板示例并存说明；
   若上游后续统一为 1，以模板为准即可，不影响既有包。
8. **`schemaVersion: 3` 与 `contentEntries`**：3 引入 `contentEntries` / `privateResources` 通道（`ModLoader.cs`
   对 `< 3` 的包走 legacy 路径）。本仓库既有 28 个 `mod.json` 仍是 2，**尚未迁移**。

---

**引用自上游的原文位置**（便于核对）：
`README.md`（环境/构建/发布/排错）、`AGENTS.md`（工作约定）、`mod/mod.json`、`game-compatibility.json`、
`template.lock.json`、`.gitignore`、`docs/architecture.md`、`docs/upgrade-0.31.0.md`、
`docs/community-skill-extraction.md`、`.agents/skills/pvzhe-mod-develop/SKILL.md`、
`.agents/skills/pvzhe-mod-develop/references/identity-and-release.md`、`.agents/skills/pvzhe-mod-verify/SKILL.md`。
