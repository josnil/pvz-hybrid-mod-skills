# 验证闸门：跑什么、怎么跑、怎么不被假绿骗

## 0. 铁律：`self_check()` 不够

生成器自带的 `self_check()` 比的是**刚生成的内存文本** ⇒ 一旦「生成函数写错 + 断言跟着写错」，
两边一起错就是**永远为真**。**必须再叠三层**：

1. **on-disk 断言** —— 断言读的是**磁盘上刚写下的字节**，不是内存变量；
2. **负向测试（`--negative`）** —— 故意写坏**副本**，断言**必须报错**；不报错 = 断言失效；
3. **离线复刻的 ModLoader 闸门** —— 反射直调引擎真函数，跑**真实 `.pmod` 的 namelist**。

## 1. 闸门清单

| 闸门 | 位置 | 断言什么 |
|---|---|---|
| `self_check()` | 生成器内 | 内容断言（**必配 on-disk 断言**） |
| `check_plant_<名>.py` | `ModWorkspace/.cache/` | 包内容 + **源码证据双层**断言（如「插件里确实有 `OnFireReady`」「常量为 7」「`(BurstEmitted+1)*intervalMsec`」） |
| `run_gates_plant.py` | 同 | 反射直调 **ModLoader / 校验器真函数**，**两份构建各跑一遍** |
| `check_modloader_gates.py` | 同 | 离线复刻 8 条角色包硬闸门（不需进游戏） |
| `check_project_folder.py` | 同 | 工程目录形态（编辑器视角：72 标准目录 / 规范序 / 无违禁文件） |
| `check_sgp_idem_single.py` | 同 | **幂等**：3 连跑字节稳定 + 增量清理 + 镜像一致 |
| `verify_official_skin.py` | `../.cache/` | 官方素材直转的**四层独立交叉** + `--negative` |

> 换外观后**旧管线验证器要退役**：它们硬编码 `frameMax=1` / 2 media / 176×192 画布，
> 对多帧素材只会报**误导性 FAIL**。做法 = 文件头插 **LEGACY GUARD**
> （读 `.dat` 的 `frameMax`，`!= 1` 时打印 `[SKIP]` 并 `rc=0` 退出），或改名 `legacy_*`。

## 2. 怎么跑（本机环境）

⚠️ **bash 的 coreutils 极不可靠**（`grep`/`tail`/`head`/`wc`/`cp`/`rm` 常缺失，`rm` 被安全壳接管）
⇒ **一律走 managed Python**，别用管道。

```bash
PY="C:/Users/yanxulin002/.workbuddy/binaries/python/versions/3.13.12/python.exe"

# 生成 + 打包 + 装机（自检在生成器内）
$PY build_plant_<名>.py

# 包内容 + 源码证据
$PY .cache/check_plant_<名>.py

# 两份构建的引擎闸门（各一遍）
$PY .cache/run_gates_plant.py --godot-ref-dir "<remake>\data_PlantsVsZombies_windows_x86_64"
$PY .cache/run_gates_plant.py --godot-ref-dir "<console>\data_PlantsVsZombies_windows_x86_64"

# 其余
$PY .cache/check_modloader_gates.py
$PY .cache/check_project_folder.py
$PY .cache/check_sgp_idem_single.py

# 外观（若走了官方素材直转）
$PY ../.cache/verify_official_skin.py
$PY ../.cache/verify_official_skin.py --negative      # 必须全部报错
```

**日志落盘再读**（长输出别指望管道）：

```bash
$PY .cache/check_plant_<名>.py > .cache/_out.txt 2>&1
$PY -c "print(open(r'.cache/_out.txt',encoding='utf-8',errors='replace').read()[-3000:])"
```

## 3. 基线（当前植物质检的实测结果，用来判断「有没有跑歪」）

| 项 | 结果 |
|---|---|
| `check_plant_super_gatling.py` | **259 ok / 1 warn / 0 FAIL**（2026-09-22 起；其中 `K15` 系列 16 + `K16` 1 + `K18` 2 + `K19` 4 = **23 项**「共用判定核心」断言）。⚠️ 各段条数**别手写**：脚本末尾自带 `分节断言数: …` 与 `共享判定核心断言(…): … => 合计 23` 两行，是**从脚本自身源码现算**的（增删小节自动跟随），文档引用它即可 |
| `run_gates_plant.py`（remake + console） | **各 52 PASS / 0 FAIL** |
| `check_project_folder.py` | **40 ok / 0 warn / 0 FAIL** |
| `check_modloader_gates.py` | **33 ok / 1 warn / 0 FAIL** |
| `check_sgp_idem_single.py` | **13 一致 / 0 不同** |
| `verify_official_skin.py` | **114 OK / 0 FAIL**；`--negative` **5/5 报错** |

> 唯一的 WARN 通常是「翻译表仅编辑器可见」（见 `plant-package-and-gates.md` §11），**不致命**。

## 4. 交付前必做的三处「一致性」核对

改完包后，同一份内容在**三个地方**都有副本，必须**逐字节一致**：

```
工作区构建目录  ModWorkspace/<BUILD_DIR>/
Mods 镜像       %APPDATA%\…\Mods\<MOD_NAME>/
.pmod 内部      Mods\<MOD_NAME>.pmod（zip 条目）
```

```bash
$PY -c "
import zipfile,hashlib,os
p=r'C:\Users\yanxulin002\AppData\Roaming\Godot\app_userdata\植物大战僵尸杂交版\Mods\超级机枪射手.pmod'
print('pmod', os.path.getsize(p), hashlib.sha256(open(p,'rb').read()).hexdigest()[:16])
z=zipfile.ZipFile(p); 
print([n for n in z.namelist() if 'ComponentSet' in n or n.endswith('.dll')])
"
```

同时确认 `enabled_mods.json` 里有自己的 **`manifest.id`**（**缺这个文件 ⇒ 零 Mod 加载**）。

## 5. 静态闸门保证不了的（必须实机看）

* 动画**到底动没动**（`forceLocalRender` 的效果无法静态断言）；
* 头身接缝、炮口位置、抬高多少 px 合适；
* 子弹出膛点是否在炮口（`Marker2D` 定位）；
* 命中判定、伤害数字；
* 图鉴 / 选卡界面里的显示（图标、名称、费用、冷却）；
* 大招的**观感**（300 颗是否卡、角度是否合理）。

⇒ 结论里**逐条列出「仍需实机确认」的项**，别把静态绿当成 done。

## 6. 本机环境坑（会浪费时间的那些）

* ⚠️ **别 `shutil.rmtree` / 整目录重建** ⇒ 会触发 `SHFileOperationW 0x2`。用增量写入 + 增量清理。
* ⚠️ **同一文件别在一次消息里并发多个 Edit**。
* ⚠️ **覆盖已被外部改动的文件前必须先 Read**（否则 `File has been modified since read`）。
  绕法：先写临时名 → Python 读临时候处理落盘 → 删临时。
* ⚠️ **引源码行号前先打开文件确认**（源码版本可能变）。
* ⚠️ 读取游戏是否真的加载了：`logs\godot.log` 搜 `[ModLoader] package applied:`；
  或 `dotnet run --file check_*.cs` 反射直调（见 `plant-runtime-plugin.md` §6）。
