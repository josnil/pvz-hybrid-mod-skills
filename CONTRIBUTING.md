# 贡献指南 —— Issue 与 PR 规范

> 本仓库是《植物大战僵尸杂交版》(Godot 4 + C#) 的 WorkBuddy Agent Skills 集合。
> **⚠️ 本仓库的 `SKILL.md` 会被 AI 直接当作指令加载**——一条错的结论会持续误导后续**所有**会话。
> 所以这里最看重的是**「能核对」**：写出出处、区分事实与推测、拿不准就老实标注。**不要求你一次就对、也不要求你什么都齐全。**

---

## 0. 收录范围

| 目录 | 收录 | 说明 |
|---|---|---|
| `skills/pvz-hybrid-mod-authoring/` | 通用 `.pmod` 包格式、打包、资源覆盖、托管插件 | 主百科 |
| `skills/pvz-hybrid-plant-authoring/` | 植物 Mod 端到端流程 | |
| `skills/pvz-hybrid-zombie-authoring/` | 僵尸 Mod 端到端流程 | |
| `tools/` | 生成器、工具链、离线闸门、实战案例文档 | |
| 根目录 `README.md` / `README_EN.md` / `GETTING_STARTED.md` / `UNPACKING.md` | 对外说明与入门 | 中英双语需同步 |

**不收**：游戏本体资源的分发/破解、与本仓库 mod 制作流程无关的讨论、要求改写官方构建器 exe（`pvzhe-level-builder.exe` 是二进制，纯 config 不可达的能力属既有边界）、未获授权的商业素材（贴图/音频/字体）。**不要求开源，也不要求你先自己跑通**。

---

## 1. 通用要求（Issue 与 PR 共通）

1. **说清楚就够，不必完备。** 能填的填；暂时拿不准的**直接写「未确认」或「待补充」**即可——**不要编造，也不要因为缺一项就不提**。维护者可以据此先建条目、标注状态，后续再补。
2. **把「事实」和「推测」分开写。** 有出处的就写出处（文档、代码文件、日志、截图、游戏内观察、聊天记录都算）；只是推测的标注「推测」。
   - **不要把"没人报告过问题"当作"已验证"**；也不要把自己的记忆直接写成结论。
3. **能给证据就给，给不了就直说。** 代码文件 + 行号、命令输出、日志片段、截图、游戏内现象都算证据；确实没有的，写「暂无法提供」而不是留空或硬凑一个。
4. **一事一议（建议，不是铁律）。** 一个 Issue / PR 尽量只讲一件事；同一批的改动可以合并提交，在描述里分条写清就行。
5. **语言**：中文叙述即可；代码、路径、字段名、JSON 标识符保留英文原文。英文不好没关系，写中文。
6. **被指出问题不用有压力**：维护者更在意"能否核对"，而不是"一次说对"。信息不全的投稿不会被拒收，只会被标记为待补充。

---

## 2. Issue 提交规范

### 2.1 用模板

从 `.github/ISSUE_TEMPLATE/` 里选对应表单（空白 Issue 已关闭）：

| 模板 | 适用场景 | 自动标签 |
|---|---|---|
| **内容纠错** | 技能/文档里的结论、口径、命令、行号与实际不符 | `bug` `documentation` |
| **工具缺陷** | `tools/` 下脚本报错、产物不正确、闸门失败 | `bug` `tools` |
| **提案** | 新技能 / 新案例文档 / 新工具 | `enhancement` |
| **用法提问** | 按文档操作卡住、不确定选哪条路线 | `question` |

### 2.2 标题格式（建议）

```
[类型] 一句话结论
```

类型 ∈ `纠错` / `工具` / `提案` / `提问`（模板会自动带上前缀）。**尽量写结论而不是现象**：

- ✅ `[纠错] 僵尸技能里 offset 的口径与引擎实际绘制原点不一致`
- ❌ `[纠错] 有个地方好像不对`

### 2.3 内容纠错类建议提供

以下**能填就填，填不了写「未确认」**，都不会导致你的 Issue 被拒收：

| 项 | 说明 |
|---|---|
| 涉及文件与位置 | 章节标题或行号即可 |
| 原文摘录 | 尽量直接粘贴，不要转述（转述容易失真） |
| 为什么是错的 | 有出处最佳；只是觉得不对也可以直说「感觉不对，没深究」 |
| 正确做法 / 建议改法 | 你验证过的结论，或只是建议 |
| 影响面 | 按这条错内容操作会怎样（这条很有用，但不是门槛） |
| 环境 | 游戏版本 / 构建器版本 / .NET 或 Godot 版本 / 操作系统 |

### 2.4 优先级与响应

| 级别 | 判据 | 处理 |
|---|---|---|
| **P0** | 按文档操作会直接失败、崩溃或损坏存档 | 优先修 |
| **P1** | 结论错误但使用者可自行绕过 | 排期修 |
| **P2** | 表述不清、错别字、排版 | 随手修 |

维护者一般会在若干工作日内给出首个回复；长时间没动静可以礼貌 ping 一次。

### 2.5 会直接关闭的情形

只关这几类：与游戏本体机制无关（如平衡性意见、联机功能请求）、要求收录第三方付费或未授权素材、重复提交（打 `duplicate`）。
**信息不全不会关闭**——缺什么都写「未确认」即可，那属于"待补充"，不属"不合格"。

---

## 3. PR 提交规范

### 3.1 分支命名（建议）

```
<type>/<scope>-<short-desc>
```

`type` ∈ `feat` | `fix` | `docs` | `tools` | `chore`。示例：`docs/plant-fix-typo`、`fix/zombie-offset-origin`、`tools/pmod-guardrail`。

### 3.2 提交信息

```
<scope>: <imperative summary>      ← 首行 ≤ 72 字符，英文，不加句号

为什么改 + 关键结论
验证证据：命令与结果（有就贴，没有就说明为什么没有）
影响面 / 破坏性变更（无则省略）
```

- `<scope>` = 技能名 / 目录名 / 主题，例如 `pvz-hybrid-zombie-authoring`、`tools/README.md`、`GETTING_STARTED`。
- 参考本仓库既有风格：`GETTING_STARTED: switch the hands-on template to SuperGatlingPea`。

### 3.3 PR 必填项

PR 描述由 `.github/PULL_REQUEST_TEMPLATE.md` 引导，包含：变更类型、动机与结论、变更文件清单、验证证据、不变量自查、影响面、关联 Issue。**其中只有「不变量自查」是硬性的**（见 3.5）。

### 3.4 验证证据（建议，能提供就提供）

| 变更类型 | 建议提供 |
|---|---|
| 纯文档 / 错别字 / 排版 | 说明影响面即可 |
| 技能内容修正（口径、判据、行号） | 出处 + 修改前后对照 |
| 生成器 / 工具链改动 | **on-disk 断言 + 负向测试** 的运行输出（含 PASS 计数） |
| 新增技能 / 新案例 | 对应闸门结果 + 至少一个真实跑通案例 |

> **没有证据也能提 PR**——写清"哪些已验证、哪些没验"，维护者会据此标注。但**不要把没验证的写成已验证**。

如果这条变更动了生成器或闸门，请顺带确认下面几点（**这是本仓库唯一强烈建议的"严谨性"要求**）：

1. 断言与 **GOLD 字面量**比较，而不是拿实现产物的输出和自己比；
2. **「实现产物」自己也有一条对账断言**——只断言「抄写目标 vs 金标」而放空实现产物 = 无效验证（本仓库称之"假绿"）；
3. 断言能**容忍上游被改坏**：循环上界做长度守卫，上游改坏时报 FAIL，而不是 `IndexError` 把整个自检崩掉；
4. 判据不足的用例**删掉**，别留永远为真的假用例。

### 3.5 不变量自查（硬性）

这几条是仓库卫生底线，**合并前必须成立**：

- [ ] 未提交构建产物：`**/obj/`、`**/.build/`、`bin/`、生成的 mod 工程、构建好的 `.pmod`、对比 PNG
- [ ] 未提交 `.workbuddy/` 会话数据
- [ ] 未提交一次性探针 / 废弃脚本（`_*` 临时脚手架已在 `.gitignore`）
- [ ] `.bat` / `.cmd`：**纯 ASCII + CRLF 行尾 + 括号平衡**（cmd 按当前代码页逐字节读脚本，非 ASCII 会让整行被吞）
- [ ] 涉及「两份构建」（remake / console）的改动，两侧保持一致
- [ ] 改了对外能力 / 目录树 / 邀请码时，`README.md` 与 `README_EN.md` **双语同步**
- [ ] 脚本内不 spawn git 子进程、不把 token 写进仓库
- [ ] **工程级还原用的是 GDRE**（其他工具 / 自制脚本不得用于还原工程树；只是取资源可用模板 `tools/mod.py extract` 或现有解包树。详见 README「[解包游戏](README.md#解包游戏唯一指定工具-gdre-tools)」与 [UNPACKING.md](UNPACKING.md)）

### 3.6 评审与合并

- 至少 **1 名维护者 Approve**；**凡改动 `SKILL.md` 指令内容的 PR，维护者必须逐行过目**（这类文件等价于代码）。
- 合并策略：**Squash merge**，保持 `main` 线性。
  ⇒ **PR 标题会成为最终提交信息**，所以标题尽量按 3.2 的格式写。
- 直推 `main` 仅限维护者做纯文档或脚手架改动。

---

## 4. 环境声明要求

报告问题或提交 PR 时，**尽量**注明以下版本（缺失不致命，但有的话能显著加快定位）：

| 项 | 示例 |
|---|---|
| 游戏版本 | V0.28 / V0.29 |
| 关卡构建器版本 | v0.28 |
| .NET / Godot 版本 | .NET 9 / Godot 4.x |
| 操作系统 | Windows 11 |

本仓库内容默认对应 **游戏 V0.28/V0.29 + 构建器 v0.28**。其他版本请说明差异；不清楚的写「未确认」。

---

## 5. 目录与命名约定

```
skills/<skill-name>/SKILL.md        # 技能主体（被 AI 加载的指令）
skills/<skill-name>/references/     # 参考资料
skills/<skill-name>/assets/         # 技能自带素材
tools/<category>/                   # 生成器 / 工具链 / 闸门
tools/case-docs/<类型>Mod-<名称>.md  # 实战案例文档
```

---

## 6. English summary (TL;DR)

- **Every `SKILL.md` here is loaded by an AI as instructions.** A wrong statement keeps misleading every future session. What matters most is that things can be *checked* — **not** that a submission is complete.
- **Be lenient with yourself**: fill in what you know, write `未确认` / *unconfirmed* or `待补充` / *to be filled in* for the rest. Do not fabricate, and do not withhold something just because it is incomplete. Incomplete issues are **not** closed; they are marked as pending.
- **Separate facts from guesses**; cite sources when you have them (docs, code files, logs, screenshots, in-game observations). "Nobody reported a problem" is **not** evidence of correctness.
- **Unpacking is a prerequisite, not a contribution rule**: the game **must** be unpacked with GDRE Tools. See the "Unpacking the Game" section in the README and [UNPACKING.md](UNPACKING.md). Nothing in this repo may be built on a tree produced by another unpacker — agents must direct users to download GDRE instead.
- **Issues**: use the templates under `.github/ISSUE_TEMPLATE/` (blank issues are disabled). Title `[type] one-line conclusion`.
- **PRs**: branch `<type>/<scope>-<desc>`; subject `<scope>: <imperative summary>` (≤72 chars, no trailing period); fill the PR template. The **invariant checklist** is mandatory (no build artifacts, no `.workbuddy/` data, ASCII+CRLF `.bat`, bilingual README sync).
- Verification evidence is **recommended, not required** — but never label unverified work as verified. If you touch generators or gates, avoid "false green" assertions: compare against GOLD literals, give the produced artefact its own reconciliation assertion, keep assertions robust to upstream breakage, and drop test cases that cannot fail.
- Merging is **squash-only**; the PR title becomes the commit subject.
