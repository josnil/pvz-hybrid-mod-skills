# 🚀 快速上手：从零做出你的第一个 Mod

> 写给「完全没接触过 Mod 制作」的你 + 帮你干活的 AI agent。
> 目标：**约 30–60 分钟，跑通官方样板「超级机枪射手」，做出一个你亲手改过数值的植物 Mod，并在游戏里亲眼验收**。
> 样板 = `tools/plant/build_plant_super_gatling.py`——三个技能文档指定的**「一切从它复制」标准样板**（植物技能 Step 1 原话）。

---

## 你将做出什么

**超级机枪射手（SuperGatlingPea）**：一株连发多颗豌豆的机枪射手，含完整链路——场景 / 组件集 / 卡片 / 图鉴 / 托管插件（概率与连射）。你将：

1. **原样跑通它**（验证你的环境是好的）；
2. **改一个数值**（比如费用、血量、射速）重新生成——这就是"你的第一个 Mod"；
3. 离线校验 → 装进游戏 → 亲眼验收。

走完这一遍，你就掌握了杂交版 Mod 的完整生命周期。之后想做自己的新卡、换外观，走[进阶路线](#进阶路线)。

---

## 第 0 步：环境准备（硬前提，让 agent 代劳）

把这段话丢给 agent，逐项确认：

> 请按 `tools/README.md` 的「环境适配」一节，帮我完成三件事：
> ① 确认本机 Python ≥ 3.13（没有就装）；
> ② 我的游戏解包目录在 `<你的路径>`，请把 `tools/plant/` 下生成器与闸门脚本里写死的作者路径（`D:\zzz\pvzHE\...`、remake/console 双构建）替换成我的（我只有一份构建，闸门只跑它）；
> ③ 替换后跑 `python tools/plant/build_plant_super_gatling.py --self-check`，把结果贴给我。

三个前提：

| 前提 | 说明 |
|---|---|
| **Python ≥ 3.13** | 生成器 / 校验脚本；外观管线另需 `pip install pillow`（现在不用） |
| **游戏解包目录** | 含 `Asset/`、`Prefab/`、`addons/ModEditor/ModSystem/` 的树。生成器要读里面的基底资源，技能文档所有"以源码为准"的判据也指向它。确认找对了：能找到 `Asset/Config/Projectile/ProjectileResource.json` |
| **路径适配** | 仓库脚本按作者 Windows 环境写死了绝对路径；这一步没做完，生成器跑不起来 |

> 手头还没有解包树？跳到文末「[热身备选](#热身备选零解包的-5-分钟)」先感受一下打包-校验闭环，回头再回来。

---

## 第 1 步：先原样跑通（一个数值都别改）

```bash
python tools/plant/build_plant_super_gatling.py --self-check   # ① 自检，预期 fails = 0
python tools/plant/build_plant_super_gatling.py                # ② 构建 + 打包 + 安装
```

生成器会自动做完一整条流水线：产出 Mod 工程 → 打出 `.pmod` → 装进游戏用户数据目录 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\` → 登记 `enabled_mods.json`。

**重启游戏**验收默认版：超级机枪射手应能进选卡界面 / 图鉴，种下后连发多颗豌豆。不开游戏也可以先读加载日志兜底确认：

```
%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\PVZHE_Logs\
```

好信号：`[ModLoader] package extracted safely: ...`、`package applied: ...`、`rollbackBlocked=False`。

> ★ **为什么先跑默认版？** 建立基线——之后出问题时能立刻确定"不是你改出来的"。这一步过了，说明环境、解包树、路径全部正确。

---

## 第 2 步：改出"你的版本"

打开 `tools/plant/build_plant_super_gatling.py` 的**顶部常量区**，挑一个好认的数值改掉（只改常量，**别重构生成器**）：

| 想改什么 | 常量 |
|---|---|
| 阳光费用 | `COST` |
| 血量 | `HITPOINTS` |
| 射速（发弹间隔秒） | `FIRE_INTERVAL` |
| 每轮豌豆数 | `PEA_COUNT` |
| 充能冷却 | `PACKET_COOLDOWN` |
| 卡片类型 | `PACKET_TYPE` |

改完重跑三连（让 agent 执行）：

```bash
python tools/plant/build_plant_super_gatling.py --self-check       # ① 改完必须自检
python tools/plant/build_plant_super_gatling.py                    # ② 重新生成 + 装机
python tools/pmod-toolchain/verify_pmod.py dist/SuperGatlingPea/*.pmod   # ③ 离线校验，FAIL=0
```

**重启游戏**，亲眼确认你的数值生效了：费用对不对、血条对不对、射速对不对。

> ⚠️ 两条铁律现在就记住：① `CHAR_KEY` 是整条链的主键（目录名 = 场景名 = config.name = saveKey = 卡片文件名），做新卡时四处必须一致；② **改了生成逻辑必须同步改 `self_check()`**，否则下次重跑会静默回退（技能文档"假绿"警告）。

✅ **走到这里，你已经完成一个属于自己的 Mod 了。**

---

## 进阶路线

### 路线 B：做一张你自己的新卡（不叫超级机枪射手）

1. **先把需求问全**——打开 `skills/pvz-hybrid-plant-authoring/assets/新建植物清单.md` 逐项打勾（改哪个内置角色、数值、要不要进图鉴、要不要换外观、玩法是否纯数据做不到）；
2. **复制样板**：`cp tools/plant/build_plant_super_gatling.py tools/plant/build_plant_<新名>.py`（需要插件时连 `tools/plant/runtime_src_plant/` 一起复制）；
3. **按 12 步流程走**：`skills/pvz-hybrid-plant-authoring/SKILL.md`（含坑 Top 15 与闸门总览）；
4. 僵尸卡对应 `skills/pvz-hybrid-zombie-authoring/SKILL.md`（样板 `tools/zombie/build_zombie_super_gatling_paper.py` 等）。

### 路线 C：换外观（贴图 / 动画 / 换头）

先准备素材来源（经典版 reanim，或一张角色图），再走 `tools/skin/` 直转管线（`build_official_skin.py` + `verify_official_skin.py`）；换头 / 头位调整用 `tools/zombie/head-tools/`——尺寸位置**禁止目测猜**，量化规程见 `skills/pvz-hybrid-zombie-authoring/references/zombie-skin-and-head.md` §10 系列。

### 想要「概率大招 / 连射 / 真随机」这类玩法？

纯数据做不到，需要托管 C# 插件（装 .NET SDK）：配方在 `skills/*/references/*-runtime-plugin.md`，样板源码在 `tools/*/runtime_src*/`。超级机枪射手本体就带一个（概率触发 + 逐颗连射），是最好的活教材。

### 热身备选（零解包的 5 分钟）

手头还没有解包树、只想先感受"改数值 → 打包 → 校验"闭环？用仓库自带的纯资源小样板 `tools/pmod-toolchain/PeaOverhaul/`（豌豆子弹数值改写）：图形编辑器 `start_editor.bat` 打开它改数值并打包，或直接编辑其中的 `.tres`，再 `python tools/pmod-toolchain/verify_pmod.py <打包产物>` 校验。它只是流程演示，**正式做 Mod 请回主路线用超级机枪射手样板**。

---

## 卡住了？错误速查表

| 症状 | 去哪查 |
|---|---|
| 生成器跑不起来 / 找不到基底资源 | 多半是「环境适配」没做完或解包树版本不对——重跑 `--self-check` 看报错，对照 `tools/README.md` 环境适配节 |
| `.pmod` 被拒收 / 加载后回滚 | `PVZHE_Logs` 的 `[ModLoader]` 行；关键词对照 `skills/pvz-hybrid-mod-authoring` 的「铁律」节与 `tools/pmod-toolchain/docs/README.md` |
| 植物动画播了但没子弹 | `skills/pvz-hybrid-plant-authoring` Step 4（漏 `ComponentSet`）与 Step 5（动画 `events` 缺 `fire`） |
| 自定义皮肤动画完全静止 | 委托插件设 `forceLocalRender` + `forceCpuPoseRender`（`tools/zombie/runtime_shared/AnimeSpriteLocalRender.cs` 是现成实现；完整案例见奶龙僵尸交付说明） |
| 换头后头变成"别的角色的碎片" | 三节点换头（`skills/pvz-hybrid-zombie-authoring` Step 5），别直接换子精灵贴图 |
| 头调大小/位置总是不对 | 铁律 30：**别目测猜**，用 `tools/zombie/head-tools/` 量出来 |
| 给 agent 的排障提示词 | "读仓库里 <某技能/文档> 的 <某节>，对照我的报错 <粘贴日志>，给出根因和最小修复" |

## 里程碑自测

- [ ] 原样跑通超级机枪射手样板（自检 fails=0，游戏里能看到它）
- [ ] 改一个数值重新生成，`verify_pmod.py` FAIL=0，游戏里亲眼确认生效
- [ ] 会读 `PVZHE_Logs` 的 `[ModLoader]` 行判断加载成功/失败
- [ ] （进阶）用生成器做出一张自己的新卡，能进选卡界面/图鉴
- [ ] （进阶）跑通一次完整的离线闸门（自检 + 负向 + 幂等）

> 全部走完，你就不是小白了。剩下的深水区（头位量化、共享判定核心、图鉴去重），技能文档里都有源码级的答案。
