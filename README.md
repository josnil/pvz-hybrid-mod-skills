# PvZ 杂交版 Mod 制作技能包（WorkBuddy Agent Skills）

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)]()
[![Game](https://img.shields.io/badge/game-PvZ%20Hybrid%20V0.28%20(Godot%204%20%2B%20C%23)-orange)]()

> 🤖 **本技能包在 [WorkBuddy](https://www.workbuddy.cn) 中使用。**
> **新用户邀请链接：** <https://www.workbuddy.cn/events/invite?inviteCode=2x5jma1axhe8>
> 该链接是 WorkBuddy AI Agent 工作台的**新用户邀请注册入口**——WorkBuddy 是承载并驱动这三个技能的 AI 助手环境（对话式 Mod 制作、技能自动加载、自动化闸门执行），通过链接注册后即可在 WorkBuddy 中直接安装并使用本仓库的技能。

一套面向《植物大战僵尸杂交版》（Godot 4 + C#）Mod 开发的 **WorkBuddy Agent Skills（AI 技能包）**，由三个互相衔接的技能组成：一个覆盖 `.pmod` 包格式的通用底座，加上植物、僵尸两条端到端的专用流水线。全部内容来自真实项目的反复实测——每条"铁律"都对应一次踩坑，每个坑都附了根因与源码级证据。

---

## 目录

- [这是什么](#这是什么)
- [三个技能总览](#三个技能总览)
- [仓库结构](#仓库结构)
- [安装与配置](#安装与配置)
- [各技能详细说明](#各技能详细说明)
  - [pvz-hybrid-mod-authoring（通用底座）](#1-pvz-hybrid-mod-authoring通用底座)
  - [pvz-hybrid-plant-authoring（植物流水线）](#2-pvz-hybrid-plant-authoring植物流水线)
  - [pvz-hybrid-zombie-authoring（僵尸流水线）](#3-pvz-hybrid-zombie-authoring僵尸流水线)
- [环境与依赖清单](#环境与依赖清单)
- [标准工作流（三技能如何配合）](#标准工作流三技能如何配合)
- [注意事项](#注意事项)
- [常见问题 FAQ](#常见问题-faq)
- [English Documentation](README_EN.md)
- [License](#license)

---

## 这是什么

《植物大战僵尸杂交版》的 Mod 是 `.pmod` 文件（本质是 `zip + 根 mod.json`），游戏内虽自带 F3 图形化 Mod 编辑器，但**无法被 AI 驱动**；而 `.pmod` 可以纯脚本生成——这正是本技能包的立足点。

三个技能把"从一句需求到装机可玩"的全过程拆成了可被 AI 精确执行的操作手册：

- **为什么是知识文档而不是一堆脚本？** 技能包交付的是经过验证的**方法论与硬约束**（包格式、字段语义、发射链路、渲染管线、离线闸门设计），配合你自己的生成器脚本使用。技能中引用的生成器/闸门脚本属于作者的工作区，请按文档指引自行搭建等价物。
- **为什么值得信？** 每条结论都以引擎源码（`addons/ModEditor/ModSystem/`、`Script/Component/`）为最终判据，并配有"负向测试"验证闸门本身不是假绿。

## 三个技能总览

| 技能 | 定位 | 一句话能力 | 体量 |
|---|---|---|---|
| **pvz-hybrid-mod-authoring** | 通用底座（百科） | 手写/生成任意类别的 `.pmod`：子弹、地图、角色、商店、音频、图集……含图形编辑器 `mod_editor.py` 用法与"单张截图 → 角色贴图"流程 | 单文件 SKILL.md，约 159 KB |
| **pvz-hybrid-plant-authoring** | 植物专用流水线 | 从零做一个植物 Mod：数值、卡片、图鉴、发射（射速/弹数/散射）、换外观、托管 C# 插件（概率/连射/真随机） | SKILL.md + 7 篇 references + 1 份清单 |
| **pvz-hybrid-zombie-authoring** | 僵尸专用流水线 | 从零做一个僵尸 Mod：护具三件套、换头"三节点"、给僵尸加发射、子弹生成点对齐炮口、图鉴去重 | SKILL.md + 3 篇 references |

三个技能的关系：**mod-authoring 是字典，plant / zombie 是两条施工路线图**。plant / zombie 技能开头都注明了分工边界——遇到包格式细节回底座查，流程与硬约束按各自技能走。

## 仓库结构

```
pvz-hybrid-mod-skills/
├── README.md                       # 本文档（中文）
├── README_EN.md                    # 英文文档
├── LICENSE                         # MIT
└── skills/                         # 三个技能模块，每个文件夹即一个可独立安装的技能
    ├── pvz-hybrid-mod-authoring/
    │   └── SKILL.md                # 技能主文档（含全部铁律与包格式细节）
    ├── pvz-hybrid-plant-authoring/
    │   ├── SKILL.md                # 12 步标准流程 + 坑 Top 15
    │   ├── assets/
    │   │   └── 新建植物清单.md      # 动手前的需求打勾清单
    │   └── references/             # 按主题展开的参考文档
    │       ├── plant-package-and-gates.md   # 建包与 8 条硬闸门
    │       ├── plant-data-fields.md         # 数值字段 / 卡库 / 直接种空地
    │       ├── plant-fire-pipeline.md       # 发射管线与动画事件表
    │       ├── plant-skin.md                # 换外观三件套
    │       ├── plant-runtime-plugin.md      # 托管 C# 插件配方
    │       ├── plant-verification.md        # 离线闸门与验收
    │       └── plant-pmod-hotpatch.md       # 只有 .pmod 时的数值热补丁
    └── pvz-hybrid-zombie-authoring/
        ├── SKILL.md                # 12 步标准流程 + 坑 Top 10
        └── references/
            ├── zombie-package-and-gates.md  # 13 文件包结构 / 护具 / 卡库
            ├── zombie-fire-and-marker.md    # 发射体系 / 子弹生成点对齐炮口
            └── zombie-skin-and-head.md      # 换外观 / 三节点换头 / 头对位量化
```

## 安装与配置

### 前置条件

1. **WorkBuddy**（推荐，通过顶部邀请链接注册）：技能由 WorkBuddy 的 AI 助手自动加载与执行。
2. 《植物大战僵尸杂交版》**V0.28 解包目录**（技能大量引用其中的引擎源码 `.cs` 与资源结构作为"事实判据"）。
3. 见下文[环境与依赖清单](#环境与依赖清单)。

### 安装步骤

1. 克隆本仓库（或下载 ZIP 解压）：

   ```bash
   git clone https://github.com/<your-account>/pvz-hybrid-mod-skills.git
   ```

2. 将需要的技能文件夹复制到技能目录（**每个技能文件夹独立安装，按需选取**）：

   - **用户级**（所有项目可用）：复制到 `C:\Users\<你>\.workbuddy\skills\`
   - **项目级**（仅当前项目可用）：复制到 `<你的工作区>\.workbuddy\skills\`

   ```bash
   # 示例：安装全部三个技能到用户级目录
   cp -r skills/pvz-hybrid-mod-authoring  ~/.workbuddy/skills/
   cp -r skills/pvz-hybrid-plant-authoring ~/.workbuddy/skills/
   cp -r skills/pvz-hybrid-zombie-authoring ~/.workbuddy/skills/
   ```

3. 重启 WorkBuddy 会话（新会话生效），对 AI 说触发词即可，例如：
   - "做一个植物 Mod，让 XX 射速翻倍" → 自动命中 plant 技能；
   - "给僵尸换头成向日葵女王" → 自动命中 zombie 技能；
   - "把这个 .pmod 的子弹伤害改了" → 自动命中 mod-authoring。

> 不使用 WorkBuddy？三个技能本质是结构化的 Markdown 知识库，直接当开发手册阅读同样成立——从各 SKILL.md 的"标准流程"一节读起。

## 各技能详细说明

### 1. pvz-hybrid-mod-authoring（通用底座）

**功能简介**：`.pmod` 包格式的完整百科。覆盖内置资源覆盖（子弹 / 地图 / 角色 / 关卡 / 商店 / 收集物 / 铲子 / 推车 / 生存 / 教程 / NPC 对话 / BGM / 音频 / 纹理 / 图集）与托管代码 Mod（C# DLL）两条路线；包含游戏外图形编辑器 `mod_editor.py` 的用法（免写代码改数值 / 打包 / 校验），以及"从单张角色截图制作角色贴图"的抠像 + 逐帧动画流程。

**核心内容**：

- **前提认知**：游戏内 F3 编辑器是 GUI、AI 不可驱动；`.pmod = zip + 根 mod.json` 可纯脚本生成。
- **包结构**：`mod.json` 必须在根且唯一（≤ 1 MiB）；资源按 `Resources/<类>/<文件名>.tres` 的路径前缀决定类别；打包排除清单（`.uid` `.import` `.cs` `.csproj` `.sln` 等）。
- **两种形态**：`.pmod`（游戏加载）vs 工程目录（编辑器）的差异——最容易白忙一场的地方。
- **路径前缀 → (category, key) 全表** + **铁律清单**（违反就加载失败）。
- **地图类专项**：`TowerDefenseMapConfig` 坐标系（1-based 闭区间）、加行几何、换底图换背景。
- **植物类 / 僵尸类专项**：6 文件植物包结构、发射管线（`ComponentSet`）、`FireMarker` 子弹生成点、外观"三件套"（`.tscn` + `.tres` + `.dat`）、血量与直接种空地、僵尸与植物的四处关键差异。
- **托管代码 Mod**：四条硬约束、`Runtime/` 目录只许一个 `ModAssembly.dll`、入口实现纪律、不开游戏的验证方法。
- **角色贴图制作**：抠像（含软泥背景的失败边界）、部件分层动画法、可量化交付自检。

**使用方法**：由 WorkBuddy 依据描述自动触发；也可在对话中点名（"按 pvz-hybrid-mod-authoring 的包格式来"）。技能内的"铁律"与"路径全表"适合作为后续两个技能的字典随查随用。

**主要依赖**：见[环境与依赖清单](#环境与依赖清单)；图形编辑器与抠像脚本需要 Python + Pillow。

### 2. pvz-hybrid-plant-authoring（植物流水线）

**功能简介**：一条植物 Mod 从需求到"装机可玩"的 12 步端到端流程，重点解决四类决策：复用内置植物还是全新、要不要写托管 C# 插件、外观走官方素材直转还是自制、要不要进选卡界面与图鉴。

**核心内容**：

- **12 步标准流程**：问全需求 → 复制生成器改常量（`CHAR_KEY` 四处同名是主键）→ 6 文件建包 → 显式声明 `ComponentSet`（漏了 = 打不出弹且零日志）→ 发射数据侧写法（齐射 vs 逐颗的硬约束）→ 换外观 → 卡进选卡/图鉴（附副作用说明）→ 血量/直接种空地 → 托管插件 → 离线闸门 → 装机 → 实机验收。
- **坑 Top 15**：每条都有根因源码引用，包括著名的"子精灵必被父代画"（⇒ 换头必须三节点）、`.tscn` 节点头写 `>` 被 Godot 静默吞行、"断言与实现同错 = 假绿"等。
- **闸门总览**：`self_check()`、on-disk 断言、负向测试、离线复刻 ModLoader 闸门、幂等校验的分层设计。

**使用方法**：让 AI"做一个植物 Mod / 改射速 / 让卡进图鉴 / 换贴图"即触发；动手前 AI 会先打开 `assets/新建植物清单.md` 逐项确认需求。细节按需读对应 reference（SKILL.md 末尾有索引表）。

**主要依赖**：Python 3.13+（生成器）、.NET SDK（托管插件编译）、Pillow（官方素材直转 / 自制皮肤）、游戏解包目录。

### 3. pvz-hybrid-zombie-authoring（僵尸流水线）

**功能简介**：僵尸 Mod 的 12 步端到端流程，只讲僵尸这条路以及它与植物的**每一个差异**。僵尸默认没有发射组件、朝左横翻、头部跟随渲染有特殊性——这些差异全部被显式列出。

**核心内容**：

- **13 文件包结构**：卡片 / 本体配置 / 卡包条目 / 场景 / 组件集 / 发射定义 / 精灵场景 / 护具数据 / 护具槽 / 外观三件套 / 托管插件，逐个说明，路径硬约束（恰 6 段、`Zombies` 类别目录）。
- **护具体系**：Armor 三件套、濒死暴走状态机（读报僵尸样板）。
- **三节点换头**：`HeadShadow` + `HeadHolder` + `Head`——为什么直接换子精灵贴图必然得到"别的角色的碎片"（父代画机制），以及反向需求（子精灵排父后面）只能用 `insertLayerId`。
- **给僵尸加发射**：组件集加 `FireComponent`、`fireProjectileList` 只留 1 条、`speed` 为负（朝左才是向前）、托管插件自建节拍、`CanFireCheckOnceByData` 而非 `CanFire`、**子弹生成点每帧对齐炮口**。
- **图鉴去重**：图鉴僵尸页两条来源都不去重 ⇒ 运行期反射去重。
- **尺寸/位置量化规程**（铁律 30 的完整展开）：头调大调小、往上挪一点这类需求**禁止目测猜**——泛洪分割量参考图、离线合成渲染扫倍率、刚性锚点（脸/王冠，而非逐帧变化的火焰花瓣）。

**使用方法**：让 AI"做个僵尸 Mod / 换头 / 让僵尸开枪 / 加护具"即触发；references 按主题查（SKILL.md 末尾有索引）。

**主要依赖**：同植物流水线；另需 `dotnet` CLI 编译 `ModAssembly.dll`。

## 环境与依赖清单

### 硬依赖

| 依赖 | 用途 | 说明 |
|---|---|---|
| **WorkBuddy**（推荐） | 技能的运行载体 | 通过[邀请链接](https://www.workbuddy.cn/events/invite?inviteCode=2x5jma1axhe8)注册；不用 WorkBuddy 也可当文档读 |
| **《植物大战僵尸杂交版》V0.28 解包** | 事实判据来源 | 技能需要读 `addons/ModEditor/ModSystem/` 下的引擎源码（`ModLoader.cs`、`XWModManifest.cs` 等）与 `Asset/` 资源结构 |
| **Python ≥ 3.13** | 生成器 / 闸门 / 校验脚本 | 纯数学脚本零第三方依赖 |
| **Pillow (PIL)** | 外观直转、抠像、离线渲染、对照图 | `pip install pillow` |

### 按需依赖

| 依赖 | 何时需要 |
|---|---|
| **.NET SDK（`dotnet` CLI）** | 托管 C# 插件（概率 / 连射 / 真随机 / 修动画静止 / 僵尸发射节拍）编译 `ModAssembly.dll` |
| **Node.js（可选）** | 个别工具脚本 |
| **经典版 PvZ 素材（reanim）** | 走"官方素材直转"换外观路线时（技能描述了 reanim → `.dat`/`.tres`/图集 的转换流程，转换脚本需自行搭建） |

### 技能包内不含的东西（如实说明）

本仓库交付的是**知识文档（Agent Skills）**，不含可执行脚本。技能中引用的作者工作区工具（如 `build_plant_super_gatling.py` 生成器、`mod_editor.py` 图形编辑器、各类闸门脚本）没有随包发布；按文档描述的规格自行实现等价脚本即可，规格本身是完整的（字段、字节布局、判据、负向用例都在文档里）。

## 标准工作流（三技能如何配合）

```
需求（"做一个会开枪的向日葵女王僵尸"）
   │
   ├─ ① mod-authoring：查包格式与铁律（mod.json 字段、路径→类别全表、托管插件四约束）
   │
   ├─ ② zombie-authoring：走 12 步流程
   │      Step 0 问全需求 → 复制生成器 → 13 文件建包 → 三节点换头
   │      → 组件集加 FireComponent → 托管插件（节拍/判定/头位姿/生成点）
   │      → 卡库入库与图鉴去重
   │
   ├─ ③ 离线闸门（两技能的闸门总览）：自检 + on-disk 断言 + 负向测试
   │      + 离线复刻 ModLoader 校验 + 幂等（3 连跑字节稳定）
   │
   └─ ④ 装机与实机验收：.pmod 落到 %APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\
          → 读 PVZHE_Logs 加载日志确认 → 游戏内观感逐项确认
```

植物 Mod 同理，把 ② 换成 plant-authoring 的 12 步。

## 注意事项

1. **技能中的本机路径是作者环境示例**。文档里大量出现 `D:\zzz\pvzHE\...`、`C:\Users\...` 等绝对路径，它们描述的是"哪类信息去哪找"（解包树、日志目录、Mod 安装目录等），使用时请替换为你自己的对应路径。游戏用户数据目录是固定的：`%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\`。
2. **版本基准是 V0.28**。引擎更新后字段、闸门、行为可能变化——一切以 `addons/ModEditor/ModSystem/` 与 `Script/Component/` 的源码为最终判据，技能教的正是"如何用源码判定"。
3. **不要手删 `ModsCache`**。改完包重启游戏即可，缓存由游戏自动管理。
4. **包内绝不能出现 `.cs` 文件**（`.exe`/`.bat`/`.cmd`/`.ps1` 等可执行文件同理），`Runtime/` 目录只许有一个 `ModAssembly.dll`，否则整包拒收。
5. **AI 无法驱动游戏内 F3 编辑器**（GUI）；所有自动化都走"纯脚本生成 `.pmod`"路线。
6. **自检必须配负向测试**。只比对生成文本的自检会"假绿"（断言与实现同错）；技能反复强调每条断言都要"篡改常量确认报警"。
7. **进选卡/图鉴有副作用**（金卡碎片掉落、随机取卡可能开出），技能会要求如实告知玩家，使用时请保留这一环节。
8. **双构建环境者闸门各跑一遍**：作者本机有 remake / console 两份游戏构建；普通用户只有一份构建跑一遍即可。
9. **请遵守游戏社区的相关规则**：制作与分享 Mod 请尊重原作及杂交版作者的版权与劳动成果，勿用于商业用途。

## 常见问题 FAQ

**Q1：植物动画播了但打不出子弹，控制台也不报错？**
两个最高频根因：① 角色场景**没有显式声明 `ComponentSet`**（继承到基场景那份、没有 FireComponent，且全程零日志）；② 动画 `events` 表里**没有 `fire` 条目**——普通射击 100% 由动画事件驱动，只设 `fireAnimeClips` 不够。见 plant 技能 Step 4 / Step 5。

**Q2：自定义皮肤动画完全静止，按 ESC 暂停一次才跳一帧？**
自制 `.dat` 不在全局图集清单 ⇒ GPU 姿态纹理无效 ⇒ 定格。修法是托管插件运行期设 `forceLocalRender = true` + `forceCpuPoseRender = true`。⚠️ 前提是该精灵不被父精灵代画——子精灵设了也无效，必须"三节点"。

**Q3：换头之后头显示成一堆别的角色的碎片？**
引擎按节点类型收集"精灵的直接子精灵"并**由父批次代画**，采样的是父精灵那张全员共用的图集 ⇒ 跨 `.tres` 的子精灵必然错图。唯一修法是三节点结构（影子吃定位 + 普通容器打断代画 + 独立渲染的可见头）。见 zombie 技能 Step 5。

**Q4：`.pmod` 被整包拒收 / 加载后回滚？**
按四条硬约束对号：`runtimeAssembly` 必须是字面量 `Runtime/ModAssembly.dll`、`runtimeApiVersion = 1`、回调绝不抛异常、`provides`/`overrides` 必须声明包内每个被识别文件。另外 `Runtime/` 多一个文件（连 `.pdb` 都算）即拒收。错误关键词可在 `PVZHE_Logs` 的 `[ModLoader]` 行里搜。

**Q5：改了 C# 源码但行为没变？**
生成器**不会自动重编 DLL**——改 `.cs` 后必须单独跑一次构建（两次编译比对 sha256），否则打进包的还是旧 DLL。

**Q6：想"头调大一点 / 往上挪一点"，拍脑袋改数字总是错？**
铁律：**尺寸/位置禁止目测猜**。有参考图就"量出来"（泛洪分割 + 离线渲染扫倍率 + 刚性锚点）；没参考图就按项目历史口径取保守值。且**改 `head_scale` 必须重解 `head_offset`**（缩放矩阵含节点 scale）。详见 zombie 技能坑 11 与 references 的 §10 系列。

**Q7：需要写托管插件吗？怎么判断？**
纯数据做不到的才写：概率触发、延时/持续改发射模式、真随机、逐颗发射、投掷单位替换、修自制皮肤动画静止。射速/弹数/散射/伤害/费用/冷却/卡类型全部纯数据可解——别为了"稳"上插件。

**Q8：`Animation/LayerVisible` 关不掉某个图层（比如多长出一个头）？**
引号必须包住**整条**属性名：`"Animation/LayerVisible/图层_1" = false`。只包末段（`Animation/LayerVisible/"图层_1"`）该行**完全无效**且不留任何日志，层保持默认可见。

**Q9：翻译表（translations.csv）要往包里放吗？**
不需要。`translate` 字段直接写中文字面量即可；`translations.csv` 是编辑器专用的，放进去只会多一条无害的 diagnostics。

**Q10：这些技能能在别的 AI 工具里用吗？**
技能是纯 Markdown（frontmatter + 正文），格式通用；但"描述自动触发、闸门自动执行"的体验依赖 WorkBuddy。任何支持自定义系统提示/知识库的 AI 工具都可以手动注入使用。

---

## English Documentation

See [README_EN.md](README_EN.md).

## License

Released under the [MIT License](LICENSE). 《植物大战僵尸杂交版》版权归其原作者所有；本仓库仅包含原创的 Mod 开发方法论文档。
