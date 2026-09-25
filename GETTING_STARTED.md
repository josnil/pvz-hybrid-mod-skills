# 🚀 快速上手：从零做出你的第一个 Mod

> 写给「完全没接触过 Mod 制作」的你 + 帮你干活的 AI agent。
> 目标：**约 30 分钟，做出一个能进游戏的数值 Mod，并亲手验收它**。
> 这条路线**不需要解包游戏、不需要写代码**——只用到仓库自带的文件。

---

## 你将做出什么

把仓库自带的样板 Mod `tools/pmod-toolchain/PeaOverhaul/`（豌豆强化：默认豌豆 / 雪豌豆 / 火豌豆 / 金豌豆 四发子弹的数值改写）**改一个数值 → 打包成 `.pmod` → 校验 → 装进游戏 → 在游戏里亲眼看到效果**。

走完这一遍，你就理解了杂交版 Mod 的全部生命周期；之后想做新角色、换外观，再按 [进阶路线](#进阶路线) 走。

---

## 第 0 步：环境准备（让 agent 代劳）

只需要 **Python 3.13+**。把下面这段话直接丢给 agent：

> 请帮我检查本机 Python 版本；没有 3.13 以上就安装一个。然后执行
> `python -c "import zipfile; print('ok')"` 确认可用。
> 本仓库路径：<clone 下来的目录>，后续操作都在这个目录里做。

可选（现在不用装）：做托管 C# 插件（概率触发、连射这类玩法）时才需要 **.NET SDK**；换外观做图集时才需要 `pip install pillow`。

---

## 第 1 步：第一次演练——改一个数值（点鼠标路线）

### 1a. 打开图形编辑器

双击运行（或让 agent 执行）：

```bat
tools\pmod-toolchain\start_editor.bat
```

会自动打开浏览器进入编辑器界面。这是**游戏外运行的 Mod 编辑器**，改数值不用写代码。界面长什么样、每个按钮干什么，看 [`tools/pmod-toolchain/docs/使用说明书.md`](tools/pmod-toolchain/docs/使用说明书.md)。

### 1b. 打开样板工程并改数值

在编辑器里打开工程：`tools/pmod-toolchain/PeaOverhaul/`（它就是一个现成的「豌豆子弹数值改写」Mod，含 `mod.json` + 4 个子弹 `.tres`）。

随手改一个好认的数值，比如把某颗豌豆的 `damage` 改成一个夸张的数字（如 `9999`）——**第一节课的目标是跑通流程，不是平衡性**。

> 不想用图形界面？命令行等价操作（让 agent 执行）：
> 直接编辑 `PeaOverhaul/Resources/Projectiles/*.tres` 里的数字，或对任意现成 `.pmod` 用
> `tools\pmod-toolchain\pmod.bat <文件.pmod> --list` 查看、`--damage 9999 --dry-run` 预览热补丁。

### 1c. 打包与校验

在编辑器里打包出 `.pmod`（或让 agent 用 `tools/pmod-toolchain/build_pmod.py`），然后**离线校验**（不用开游戏）：

```bash
python tools/pmod-toolchain/verify_pmod.py dist/<你的mod>.pmod
```

`verify_pmod.py` 会做 22 项检查（清单结构 / 路径类别 / 注册一致性…）。**FAIL=0 才算过**；有红就把它打印的报错原样丢给 agent 排查。

---

## 第 2 步：装进游戏，亲眼验收

1. 把 `.pmod` 放进游戏用户数据目录（资源管理器地址栏粘贴即可打开）：

   ```
   %APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\
   ```

   > 用编辑器/生成器打包的会自动装好并登记 `enabled_mods.json`——**手动放的话需要确保该 json 里有你的 mod 条目**（缺它 = 零 Mod 加载）。

2. **重启游戏**（改完包重启即可，**不要**手删 `ModsCache`）。

3. 进游戏看效果：豌豆是不是打出你改的那个数值了？（植物僵尸的血条 / 伤害数字一目了然。）

4. 兜底验收（不开游戏也能确认加载）——读加载日志：

   ```
   %APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\PVZHE_Logs\
   ```

   好信号：`[ModLoader] package extracted safely: <你的modid>`、`package applied: ...`、`rollbackBlocked=False`。
   坏信号：`is not unambiguously declared by manifest`、`undeclared executable package file`——原样丢给 agent。

✅ **走到这里，你已经完成一个完整的 Mod 了。** 之后的进阶都是「同一条流水线，换更花的内容」。

---

## 进阶路线

### 路线 B：做一张新植物/僵尸卡（生成器路线）

- **硬前提：一份游戏解包目录**（含 `Asset/`、`Prefab/` 等，以及能查引擎源码的 `addons/ModEditor/ModSystem/`）。生成器要从里面读基底资源；技能里所有「以源码为准」的判据也指向它。如果你的游戏只有打包的 `.pck`，先让 agent 帮你用 PCK 解包工具解出来，或向游戏社区获取对应版本的解包包。
- 把解包路径告诉你仓库里的脚本：让 agent 按 [`tools/README.md`](tools/README.md) 的「**环境适配**」一节，把写死的作者本机路径全局替换成你的。
- 然后**先读流程再动手**：
  - 植物卡 → `skills/pvz-hybrid-plant-authoring/SKILL.md`（12 步流程 + 坑 Top 15 + `assets/新建植物清单.md` 需求打勾表）
  - 僵尸卡 → `skills/pvz-hybrid-zombie-authoring/SKILL.md`（护具 / 换头三节点 / 给僵尸加发射）
- 核心动作就一个：**复制样板生成器、改顶部常量区**（`MOD_NAME` / `MOD_ID` / `CHAR_KEY` / 数值），跑 `--self-check` 与各闸门脚本（见对应技能的「闸门总览」），最后装机验收。

### 路线 C：换外观（贴图 / 动画 / 换头）

先确认你有素材来源（经典版 reanim 素材，或一张角色图），再按：

- `tools/skin/`：经典 reanim → `.dat`/`.tres`/图集 的直转管线（`build_official_skin.py` + `verify_official_skin.py`）
- 换头 / 头位调整：`tools/zombie/head-tools/`（尺寸/位置**禁止目测猜**——量化规程见 `skills/pvz-hybrid-zombie-authoring/references/zombie-skin-and-head.md` §10 系列）

### 想要「概率大招 / 连射 / 真随机」这类玩法？

纯数据做不到，需要托管 C# 插件（装 .NET SDK 后）：配方在 `skills/*/references/*-runtime-plugin.md`，样板源码在 `tools/*/runtime_src*/`。

---

## 卡住了？错误速查表

| 症状 | 去哪查 |
|---|---|
| `.pmod` 被拒收 / 加载后回滚 | 先看 `PVZHE_Logs` 的 `[ModLoader]` 行；关键词对照 `skills/pvz-hybrid-mod-authoring` 的「铁律」节与 `tools/pmod-toolchain/docs/README.md` |
| 植物动画播了但没子弹 | `skills/pvz-hybrid-plant-authoring` Step 4（漏 `ComponentSet`）与 Step 5（动画 `events` 缺 `fire`） |
| 自定义皮肤动画完全静止 | 委托插件设 `forceLocalRender` + `forceCpuPoseRender`（`tools/zombie/runtime_shared/AnimeSpriteLocalRender.cs` 是现成实现） |
| 换头后头变成"别的角色的碎片" | 三节点换头（`skills/pvz-hybrid-zombie-authoring` Step 5），别直接换子精灵贴图 |
| 头调大小/位置总是不对 | 铁律 30：**别目测猜**，用 `tools/zombie/head-tools/` 量出来 |
| 给 agent 的排障提示词 | "读仓库里 <某技能/文档> 的 <某节>，对照我的报错 <粘贴日志>，给出根因和最小修复" |

## 里程碑自测

- [ ] 用编辑器改出一个数值 Mod 并通过 `verify_pmod.py`（FAIL=0）
- [ ] 装进游戏，在游戏里亲眼看到改动
- [ ] 会读 `PVZHE_Logs` 的 `[ModLoader]` 行判断加载成功/失败
- [ ] （进阶）用生成器做出一张能进选卡界面/图鉴的新卡
- [ ] （进阶）跑通一次完整的离线闸门（自检 + 负向 + 幂等）

> 全部走完，你就不是小白了。剩下的深水区（头位量化、共享判定核心、图鉴去重），技能文档里都有源码级的答案。
