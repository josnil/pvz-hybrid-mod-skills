# 解包游戏（工程还原唯一指定工具：GDRE Tools）

> 本仓库的技能与工具都以**解包后的游戏目录**为"事实判据"。
> **需要工程级还原（`.cs` / `.tscn` / 可编辑工程树）时，必须使用下面的唯一指定工具；这条路上禁止其他工具或自制脚本。**
> **2026-10-24 放宽**：若只是**取资源**（贴图 / `.dat` / `.tres` / 配置 JSON），可以直接用官方模板
> [pvzhe-mod-template](https://github.com/axh-xecoy/pvzhe-mod-template) 的 `python tools/mod.py prepare` + `extract`
> （只支持独立未加密 PCK v2/v3/v4）；若**制作者已经解包过游戏**，直接用现有解包树即可，不必重解。

[返回首页](README.md) · [快速上手](GETTING_STARTED.md) · [贡献规范](CONTRIBUTING.md) · [工具环境适配](tools/README.md)

---

## 1. 为什么要解包

杂交版的技能不是凭记忆写的，几乎每条结论都指向解包树里的具体位置：

| 你需要什么 | 在解包树里的哪里 |
|---|---|
| 引擎行为、ModLoader 约束、包格式 | `addons/ModEditor/ModSystem/*.cs`（`ModLoader.cs`、`XWModManifest.cs` …） |
| 基底资源（角色 / 子弹 / 卡片 / 关卡 …） | `Asset/…` 下的 `.tres` / `.json` |
| 场景与节点结构 | `Prefab/…` 下的 `.tscn` |
| 图鉴 / 面板等 UI | `Prefab/GUI/…` |
| 资源分类全表、路径解析规则 | `addons/ModEditor/FileSystem/…` |

技能里大量"以源码为准"的判据（含文件与行号）都指向这棵树。**没有它，技能只能靠猜。**

---

## 2. 工程还原的唯一指定工具（硬性规定）

| 项 | 内容 |
|---|---|
| 工具名 | **Godot RE Tools（GDRE Tools / gdsdecomp）** |
| 项目主页 | https://github.com/GDRETools/gdsdecomp |
| **下载地址** | **https://github.com/GDRETools/gdsdecomp/releases** |
| 能力 | Godot 4.x / 3.x / 2.x 工程恢复；PCK 提取与创建；GDScript 批量反编译；资源二进制 ⇄ 文本批量转换 |

> ### ⛔ 强制条款（对人和 agent 同样适用 · 仅限工程还原通道）
>
> 1. 需要**工程级还原**时，**必须**使用上面这个工具。这条路上**不接受**其他解包器、第三方 PCK 工具，或自行编写的 PCK 解析脚本。
> 2. **只是取资源**时不必还原整个工程：用模板 `tools/mod.py prepare` + `extract`，或者直接使用**已有的解包树**。
>    注意 `mod.py extract` 只支持独立未加密 PCK v2/v3/v4，且 `.ctex` / `project.binary` / `.gdc` 仍是导入/编译格式，**不会**变成可编辑源码。
> 3. **agent 不得绕过**：需要工程还原时，正确做法是**引导用户从上面的地址下载 GDRE 并用它解包**；
>    不得自行实现 PCK 解析、不得从非官方渠道获取解包结果、不得拿来路不明的树当本仓库的事实判据。
> 4. **为什么工程还原这条是硬的**：本作是 **Godot 4 + C#（Mono）** 工程。只有 GDRE 能同时正确处理
>    ① PCK 的校验和与加密、② 二进制资源 → 原始文本格式的反转换、③ C# 程序集的定位与反编译。
>    用别的路子解出来的树会表现为"资源还是二进制""缺字段""`.cs` 行号对不上"——
>    技能里所有"以源码为准"的判据会**当场失效，而且错得没有症状**。

---

## 3. 下载说明

### 3.1 选哪个文件

打开 [Releases](https://github.com/GDRETools/gdsdecomp/releases)，在目标版本的 **Assets** 里按平台选（以下以稳定版 `v2.6.4` 为例）：

| 平台 | 文件名 | 体积 |
|---|---|---|
| **Windows**（本仓库主要环境） | `GDRE_tools-v2.6.4-windows.zip` | 约 40 MB |
| Linux | `GDRE_tools-v2.6.4-linux.zip` | 约 34 MB |
| macOS | `GDRE_tools-v2.6.4-macos.zip` | 约 68 MB |
| Android | `GDRE_tools-v2.6.4-android.apk` | 约 73 MB |

解压后，Windows 下的可执行文件是 **`gdre_tools.exe`**（便携版，**无需安装**；若压缩包内文件名有出入，以实际为准）。

> ⚠️ **不要**下载 Releases 页面最下面的 "Source code (zip / tar.gz)"——那是工具源码，不是可用程序。

### 3.2 选哪个版本

| 情况 | 建议 |
|---|---|
| 默认 | **最新稳定版**（非 pre-release，如 `v2.6.4`） |
| 解包时提示**找不到 C# 程序集** | 改用 `v2.7.0-beta.2`——该版更新日志明确修复了 *"finding C# assembly when assembly name does not match that specified in project config"* |

### 3.3 用 Scoop 安装（Windows，可选）

```powershell
scoop bucket add games
scoop install gdsdecomp
```

---

## 4. 使用方法

### 4.1 GUI（推荐，最省事）

1. 解压 zip，双击 **`gdre_tools.exe`**；
2. 菜单 **「RE Tools」→「Recover project...」**；
3. 选择游戏文件——**`.pck` / 游戏可执行文件 / `.apk` / 已解包目录都可以直接选**；也可以把文件**拖拽**到窗口上；
4. 指定输出目录（留空则默认输出到 `<名字>_extracted`）；
5. 等待跑完。

> 游戏是「`.exe` + 同目录 `data_*` 文件夹 + `.pck`」的形态时，直接选那个 **`.pck`** 或 `.exe` 即可。

### 4.2 命令行（可脚本化 / 适合让 agent 执行）

```bash
# 完整工程恢复（推荐）——反编译脚本，并把二进制资源还原成 .tres/.tscn 文本
gdre_tools --headless --recover="<游戏目录>/xxx.pck" --output="<你的解包目录>"

# 只提取文件（不还原资源文本格式，一般不用）
gdre_tools --headless --extract="<游戏目录>/xxx.pck" --output="<你的解包目录>"

# 先看看包里有什么
gdre_tools --headless --list-files="<游戏目录>/xxx.pck"
```

常用参数：

| 参数 | 用途 |
|---|---|
| `--output=<DIR>` | 输出目录 |
| `--csharp-assembly=<PATH>` | C# 工程的托管程序集路径；**不指定时从 PCK 路径自动探测**，探测不到就手动指向游戏目录里的 `.dll` |
| `--key=<64 位十六进制>` | 工程加密时使用 |
| `--include=<GLOB>` / `--exclude=<GLOB>` | 按 `res://` 根的通配符筛选（支持 `**`） |
| `--scripts-only` | 只提取 / 恢复脚本 |
| `--ignore-checksum-errors` / `--skip-checksum-check` | 遇到 MD5 校验报错时使用 |
| `--help`（或 `--gdre-help`） | 打印完整帮助 |

> ★ **`--recover` 与 `--extract` 的区别**：只有 **`--recover`** 会把二进制资源还原成 `.tres` / `.tscn` 文本并反编译脚本。
> **本仓库需要的是 `--recover` 的结果**——用 `--extract` 你会得到一堆看不懂的二进制。

---

## 5. 解包后必须自检（别急着跑下游）

解包树**必须**同时具备这三样，缺一说明解包没成功或游戏版本不对：

- [ ] `Asset/` —— 资源目录
- [ ] `Prefab/` —— 场景目录
- [ ] `addons/ModEditor/ModSystem/` —— 引擎源码（`ModLoader.cs`、`XWModManifest.cs` …）

**最快的"找对了"判据**：树里能搜到

```
Asset/Config/Projectile/ProjectileResource.json
```

找得到 → 树是完整可用的；找不到 → 回第 4 步重来，或按第 6 节排查。

> 自检通过后，把它作为"游戏解包目录"，接着按 [`tools/README.md` 的「环境适配」](tools/README.md) 把仓库脚本里写死的作者路径替换成你自己的。

---

## 6. 常见问题

| 症状 | 原因 / 处理 |
|---|---|
| 提示找不到 **C# assembly** | ① 换成 `v2.7.0-beta.2`；② 用 `--csharp-assembly=` 手动指向游戏目录里的托管 `.dll` |
| 解包报 **MD5 / checksum** 错 | 加 `--ignore-checksum-errors` 或 `--skip-checksum-check`；仍失败多半是游戏文件本身不完整 |
| 提示需要 **key**（工程加密） | 用 `--key=<64 位十六进制>`；key 需自行从游戏本体取得，**本仓库不提供** |
| 解出来**只有二进制资源**，没有 `.tres` / `.tscn` | 你用的是 `--extract`，改用 `--recover` |
| `.cs` 内容不全 / 行号对不上 | 确认用 `--recover` 且 C# 程序集已正确加载；**行号以你自己那棵树的源码为准**，不要照抄文档里作者环境的行号 |
| `Asset/` 里找不到某些图片（如 `.dat`） | 正常：部分动画资源在游戏 PCK 内、**不在**解包树里，技能文档已注明 |
| 解包很慢 / 卡住 | 首次恢复整个工程本来就慢（数万文件）；确认磁盘空间与输出目录可写后耐心等 |
| 能不能用别的工具解包？ | **不能**。见第 2 节强制条款——其他路子解出来的树不可作为本仓库的事实判据 |

---

## 7. 版本与更新记录

| 日期 | 记录 |
|---|---|
| 2026-09-28 | 首次编写。工具版本参照稳定版 **v2.6.4**（2026-08-12 发布）与预发布 **v2.7.0-beta.2**（2026-08-16 发布） |

工具本身在持续更新——**始终以 [Releases](https://github.com/GDRETools/gdsdecomp/releases) 页面的最新稳定版为准**；本文件里的版本号只是撰写时的快照。
