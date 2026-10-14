# tools/ —— 配套工具链与样板生成器

本目录是 [`skills/`](../skills/) 三个技能所引用的**可复用实现**：`.pmod` 工具链、四条流水线的样板生成器、离线闸门脚本、官方素材直转管线，以及五份成套案例文档。**先读对应技能的 SKILL.md 再用这里的工具**——工具的用法、硬约束与坑都写在技能文档里。

## 目录总览

| 目录 | 内容 | 对应技能 |
|---|---|---|
| `pmod-toolchain/` | `.pmod` 通用工具链：构建/校验/热补丁 + 图形编辑器 + 纯资源 Mod 样板工程 | pvz-hybrid-mod-authoring |
| `plant/` | 植物流水线样板（超级机枪射手）+ 离线闸门 | pvz-hybrid-plant-authoring |
| `zombie/` | 僵尸流水线样板（读报机枪/舞王投掷/向日葵女王）+ 共享源文件 + 闸门 + 头位量化工具 | pvz-hybrid-zombie-authoring |
| `map/` | 地图流水线样板（吸血鬼屋泳池）+ 闸门 | pvz-hybrid-mod-authoring（地图节） |
| `skin/` | 经典 reanim → `.dat`/`.tres`/图集 官方素材直转管线 + 校验 | 三个技能的"换外观"章节 |
| `case-docs/` | 五份成套案例交付文档（植物×2 / 僵尸×2 / 地图×1） | 全部 |

## 各文件用途

### pmod-toolchain/（通用工具链）

| 文件 | 用途 |
|---|---|
| `build_pmod.py` | 构建 + 打包 `.pmod` + 安装到游戏 Mods 目录 |
| `verify_pmod.py` | 离线校验一个 `.pmod`（22 项：清单结构 / 路径类别 / 注册一致性…），用法 `python verify_pmod.py <文件.pmod>` |
| `patch_pmod_attrs.py` + `pmod.bat` | **只有 `.pmod` 没有生成器时**的数值热补丁（cost / fireInterval / 血量…），支持 `--dry-run`；`pmod.bat` 是 ASCII 包装器 |
| `mod_editor.py` + `mod_editor_ui.html` | **游戏外图形编辑器**（网页 UI，点鼠标改数值/打包/校验，免写代码） |
| `start_editor.bat` | 编辑器启动器（自动找 Python，回退 `python`） |
| `PeaOverhaul/` | **纯资源 Mod 最小样板工程**（改子弹数值，无插件）：`mod.json` + 4 个 `.tres` |
| `docs/README.md` | Mod 工坊主文档（`.pmod` 包格式全表） |
| `docs/使用说明书.md` | 图形编辑器完整教程（先看这个） |
| `docs/植物管线逆向结论.md` | 植物发射管线逆向笔记 |
| `界面截图.png` | 编辑器界面截图 |

### plant/（植物样板：超级机枪射手）

| 文件 | 用途 |
|---|---|
| `build_plant_super_gatling.py` | 生成器（138 KB，含 `self_check()`）：常量区 → 场景/配置渲染 → 打包 → 装机，**一切从它复制** |
| `runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs` | 托管插件（概率触发 / 逐颗连射 / 图鉴入库） |
| `runtime_src_plant/check_gates_plant.cs` | 反射直调引擎真函数的闸门程序 |
| `runtime_src_plant/build_runtime.py` | DLL 编译脚本（两次编译比 sha256） |
| `gates/check_plant_super_gatling.py` | 包内容 + 源码证据双层断言 |
| `gates/check_modloader_gates.py` | 离线复刻 ModLoader 硬闸门 |
| `gates/check_project_folder.py` | 工程目录形态检查（编辑器视角） |
| `gates/check_idempotent_plant.py` + `run_gates_plant.py` | 幂等（3 连跑字节稳定）+ 闸门跑批 |

### zombie/（僵尸样板 ×3 + 共享源 + 闸门 + 头位量化）

| 文件 | 用途 |
|---|---|
| `build_zombie_super_gatling_paper.py` | 读报僵尸样板（护具 + 暴走 + 发射 + 换头三节点） |
| `build_zombie_disco_pult.py` | 舞王投掷车样板（复用内置 `.cs` / 投掷单位替换） |
| `build_zombie_sunflower_queen.py` | 向日葵女王样板（**一包两角色** / 6 齐射 / 光环 / 头 2.0 倍） |
| `runtime_shared/GatlingVolleyCore.cs` | 两包共用的齐射判定核心（"共享源文件"铁律的实例） |
| `runtime_shared/AnimeSpriteLocalRender.cs` | 自制皮肤 `forceLocalRender` 渲染修复（共享） |
| `runtime_src_zombie_super_gatling/` | 读报僵尸插件 + 闸门 C#（`SuperGatlingPaperRuntimeEntry.cs` 83 KB） |
| `runtime_src_zombie/` | 舞王投掷插件 + 闸门 C# |
| `runtime_src_zombie_sunflower_queen/` | 女王插件（无闸门 cs，用 gates/ 下负向与幂等脚本） |
| `gates/check_head_fit.py` | 几何门：头对位反解 + 换头落点 + 炮口/生成点双来源 |
| `gates/_neg_test_head.py` / `_neg_test_sunflower_queen.py` / `_neg_test_volley.py` | 负向测试：逐条篡改常量，断言必须响 |
| `gates/_byte_check_head.py` | 落盘产物按字节核对（含工作区 == 安装镜像） |
| `gates/run_entry_sgp.py` / `run_gates_sgp.py` | 插件入口检查 / 两份构建闸门跑批 |
| `gates/check_sgp_idempotent.py` / `check_sgp_idem_single.py` / `check_idempotent_zombie.py` | 幂等校验 |
| `gates/_idem_sunflower_queen.py` / `final_report_zombie.py` | 女王包幂等 / 只读收尾核对 |
| `gates/_sq_quotefix_scan.py` / `_sq_layercover.py` | `Animation/LayerVisible` 引号包整条的全库对照扫描 / 层覆盖检查 |
| `head-tools/_j16_resize.py` | **改 `head_scale` 后一次解出「新 scale + 保位置」**（`--scale` / `--pos-src`） |
| `head-tools/_j15_shift.py` | 「整体移一点」按口径位移重解（`--char queen --dy N`） |
| `head-tools/_sq_refmeasure.py` / `_sq_preview.py` / `_sq_sbs.py` / `_sq_final_cmp.py` / `_sq_scale12.py` / `_sq_overlay2.py` / `_sq_shift13.py` | 尺寸/位置量化工具组：泛洪分割量参考图 / 离线渲染扫倍率 / 并排对照 / alpha 轮廓叠加 / 四格位移对照 |

**奶龙僵尸（NaiLong）——从零自制皮肤的完整案例**（2026-09-25 交付，作者：云漫行）：

| 文件 | 用途 |
|---|---|
| `build_zombie_nailong.py` | 生成器：普通僵尸全部基础行为 + 每 10 秒大笑控场，皮肤由用户三份素材（站立图/大笑图/笑声音频）离线程序化扩帧 |
| `nailong_art.py` / `nailong_skin.py` / `anime_io.py` | 素材抠像扩帧 / reanim 直转皮肤管线 / 动画 IO |
| `runtime_src_zombie_nailong/` | 托管插件源码：大笑节拍、`GroundMoveComponent` 行走修复、自制皮肤 `NaiLongLocalRender`（源码，`obj/`/`.build/` 编译产物不入库，`build_runtime.py` 重新编译） |
| `gates/nailong/check_nailong_install.py` / `check_nailong_negative.py` / `make_preview.py` | 装机核对 / 负向测试 / 预览图生成 |
| `NaiLong/` | 完整 Mod 工程（可被编辑器直接打开）：场景/组件集/卡片/图集三件套/音效 |
| `奶龙僵尸-交付说明.md` | ★ 交付文档：含「僵尸不会往前走」的根因复盘（`GroundMoveComponent` 只认 `_ground` 层位姿——皮肤缺 ground 层动画就会原地不动）与三轮修复实录 |
| `奶龙僵尸-预览.png` | 成品预览图 |

### map/（地图样板：吸血鬼屋泳池）

| 文件 | 用途 |
|---|---|
| `build_map_vampire_pool.py` | 生成器：5 行 → 6 行 + 泳池水面 + 换战斗背景 |
| `runtime_src/VampirePoolRuntimeEntry.cs` | 插件：运行期换背景 `Sprite2D.Texture` |
| `runtime_src/check_gates.cs` / `check_entry.cs` / `check_api.cs` | 闸门 / 入口 / API 探针 C# |
| `gates/check_map_tres.py` / `check_idempotent_map.py` | 地图 `.tres` 断言 / 幂等 |

### skin/（外观管线）

| 文件 | 用途 |
|---|---|
| `build_official_skin.py` | **首选换外观路线**：经典未重置版 reanim → 重置版 `.dat` + `.tres` + 图集 + `skin_params.json`（带 on-disk 断言） |
| `verify_official_skin.py` | 直转产物的四层独立交叉校验 + `--negative` 负向测试 |
| `reanim_decode.py` / `build_dat.py` / `build_tres.py` / `build_atlas2.py` / `verify_dat.py` / `pnglib.py` | 自制逐帧管线：reanim 解码 / `.dat` 二进制打包（头 18B + 元素 30B + 事件段）/ 动画数据 / 图集合成 / 校验 / PNG 无 PIL 读写 |
| `FINDINGS_tres_format.md` | `.tres` / `.dat` 格式逆向发现 |

### case-docs/（成套案例）

| 文件 | 内容 |
|---|---|
| `植物Mod-超级机枪射手.md` | 植物 Mod 全流程交付文档（数值 / 发射 / 图鉴 / 插件） |
| `植物Mod-超级机枪射手-换贴图换动画指南.md` | 换外观专项（官方素材直转 + 头位标定） |
| `僵尸Mod-超级机枪读报僵尸.md` | 僵尸 Mod 全流程交付文档（护具 / 发射 / 子弹生成点 / 图鉴去重） |
| `僵尸Mod-暴走舞王伽刚特尔投石车僵尸.md` | 投掷替换 + 复用内置脚本案例 |
| `地图Mod-吸血鬼屋泳池.md` | 地图 Mod 案例（加行 / 泳池 / 换背景） |

## 快速开始

```bash
# 0) 依赖：Python 3.13+（外观管线需 Pillow）；托管插件需 .NET SDK（dotnet）
pip install pillow

# 1) 只想改数值 → 打开图形编辑器（免写代码）
cd tools/pmod-toolchain && start_editor.bat

# 2) 要做新角色 → 复制对应生成器改常量（见技能文档 Step 1）
cp plant/build_plant_super_gatling.py plant/build_plant_<新名>.py

# 3) 打包校验
python tools/pmod-toolchain/verify_pmod.py dist/<你的mod>.pmod
```

## ⚠️ 环境适配

> ✅ **本工作区已经做完适配**（2026-10-01）。下面第 1~3 条讲的写死路径**已经改掉**：
> 现在所有脚本都从 `tools/_env.py`（唯一路径真相源）推导，各流水线另有 `_gen.py`
> 定位自己的工作区。换机器时**只需要改 `_env.py` 一个文件**，或者设环境变量。
> 各脚本顶部会自动注入一段适配块（带 `# --- 本机路径适配 ---` 标记），
> 原来的写死常量已替换成 `from _env import …`。

### 路径怎么解析的

```
<工作区>/                       ← 含 unpack/ 、data_PlantsVsZombies_*/ 、mods/
├── pvz-hybrid-mod-skills/
│   └── tools/
│       ├── _env.py             ← ★ 唯一路径真相源（UNPACK / GAME / CLASSIC / MODS / PY）
│       └── <流水线>/_gen.py     ← 该流水线的工作区 WS（生成器 + runtime_src_*/ + dist/）
├── unpack/                     ← 解包树（判据）
├── data_PlantsVsZombies_*/     ← 游戏本体（GodotSharp.dll + PlantsVsZombies.dll）
└── mods/                       ← 6 个成品 Mod，另有 mods/_modenv.py
```

### 可覆盖的环境变量

| 变量 | 用途 | 本机默认 |
|---|---|---|
| `PVZ_WORKSPACE` | 工作区根（跳过自动推导） | 自动向上找 `unpack/` + `data_PlantsVsZombies_*/` |
| `PVZ_UNPACK` | 游戏解包树（引擎源码判据） | `<工作区>/unpack` |
| `PVZ_GAME` | 游戏本体目录（编译插件要的 DLL） | `<工作区>/data_PlantsVsZombies_windows_x86_64` |
| `PVZ_CLASSIC` | 经典未重置版素材树（**换外观才需要**） | ⚠️ **未配置**（这份素材不在本仓库里） |
| `PVZ_MODS` / `PVZ_UD` | 游戏 Mods / app_userdata 目录 | `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版` |
| `PVZ_PY` | `.bat` 启动器用的解释器 | PATH 上的 `python` / `py` |

### 其余注意事项

1. **解包树**必须用 [GDRE Tools（gdsdecomp）](https://github.com/GDRETools/gdsdecomp/releases) 解出（**禁止**其他工具 / 自制脚本），下载与用法见 **[UNPACKING.md](../UNPACKING.md)**。
   自检：树里同时有 `Asset/`、`Prefab/`、`addons/ModEditor/ModSystem/`，且能搜到 `Asset/Config/Projectile/ProjectileResource.json`。
2. **单构建**：闸门脚本原本各跑一遍 remake/console 两份构建，本机只有一份 ⇒ 已收敛成 `("ref", REF_DIR)` 一行。
3. **生成器的外观标定文件**：`build_plant_super_gatling.py` 依赖 `<工作区>/.cache/skin_params.json`，
   它由 `skin/build_official_skin.py` 从 **经典版 reanim** 生成。**没有 `PVZ_CLASSIC` 就跑不了**
   （`--self-check` 会以 `FileNotFoundError` 明确报出来，不会静默出错）。要跑通这条样板请先准备经典版解包树。
   > 📌 技能文档 `GETTING_STARTED.md` 里写的 `--self-check` 开关在生成器里实际叫 **`--check`**
   > （`--check` = 只验证磁盘现状、不重建；不带参数 = 重建后再自检）。
4. **.NET SDK**：插件是 `net9.0`（游戏自带 .NET 9.0.17 运行时、`global.json` 锁 SDK 9.0.315）。
   本机已装 **9.0.318**。⚠️ 只有 SDK 6 的机器**编不过**：`GodotSharp` 用 `System.Runtime 8.0`，
   SDK 6 会报 `CS1705`。
5. **角色定制**：生成器顶部常量区（`MOD_NAME` / `CHAR_KEY` / 数值）就是给你改的——**只改常量，别重构**。
6. 版本基准为杂交版 **V0.28**（本工作区是 **0.29.0**）；引擎更新后以 `addons/ModEditor/ModSystem/` 源码为最终判据。

### 验证过的状态（2026-10-01）

| 项 | 结果 |
|---|---|
| 全部 70 个 `.py` | 语法解析通过（Python 3.12.14） |
| 编译 6 个 Mod 插件（net9.0 + 真实游戏 DLL） | 6/6 成功，产物与包内 `ModAssembly.dll` **逐字节一致** |
| `mods/TimeStop` 全链路（编译→打包→装机） | 通过；重新生成的 `.pmod` 与原发布包 **MD5 一致** |
| `verify_pmod.py` 校验 6 个成品包 | 6/6 通过，FAIL=0 |
| `build_plant_super_gatling.py` | ⚠️ 卡在缺 `PVZ_CLASSIC`（见上第 3 条） |

排除了什么：编译中间产物（`obj/` `.build/` `bin/`）、生成器的构建输出工程（`SuperGatlingPea/` 等可由生成器再生成）、成品 `.pmod`、对照用 PNG 截图、一次性探针脚本，以及已过期的 `_sq_head_place.py`（被 `head-tools/_j16_resize.py` 取代）。

排除了什么：编译中间产物（`obj/` `.build/` `bin/`）、生成器的构建输出工程（`SuperGatlingPea/` 等可由生成器再生成）、成品 `.pmod`、对照用 PNG 截图、一次性探针脚本，以及已过期的 `_sq_head_place.py`（被 `head-tools/_j16_resize.py` 取代）。
