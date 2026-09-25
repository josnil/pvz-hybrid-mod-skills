# 只有 .pmod 文件时怎么改数值属性（热补丁）

> 场景：手头只有一个 `.pmod`（别人发的 / 生成器丢了），想改阳光、射速、血量、冷却、卡类型。
> 工具：`ModWorkspace/patch_pmod_attrs.py`（2026-09-25 建，已实测 3 条写盘路径 + verify_pmod 闸门通过）。
> **SKILL.md §6 索引已收录本文件**。

## 0. 原理与证据

`.pmod` = zip + 根 `mod.json`。所有数值属性都是包内 `.tres`/`.tscn` 文本资源里的
**列首（col0）`键 = 值` 行**（2026-09-25 扫描装机目录 5 个含角色包 + dist 10 个包实测）：

| 键 | 位置（实测） | 备注 |
|---|---|---|
| `cost` / `costRise` / `costNight` / `packetCooldown` / `hitpoints` | `**/Config/TowerDefense*.tres` 列首 | 植物、僵尸同规律 |
| `fireInterval` | 植物: `**/Scene/<Key>.tscn` 列首；僵尸: `**/Scene/*FireComponentDefinition.tres` 列首 | 秒/轮 |
| `fireNum` | 场景 `.tscn` **和** ComponentSet `.tres` 各一处 | 两处须一致 ⇒ 工具会一起改 |
| `type`(卡类型) | `**/Cards/*.tres` 列首 | NOONE=-1 WHITE=0 GOLD=1 DIAMOND=2 COLOUR=3 STAR=4 ORIGINAL=5 ZOMBIE=6 COVER=7 GRAY=8 |

⚠️ 只改**列首**行：`[sub_resource]` 内缩进属性、override 子资源（如 `type=-1`）、`; # [` 注释/段头一律不碰。
⇒ 这就是"改卡类型不会误伤 override 子资源"的保证。

## 1. 用法

```bash
PY="C:/Users/yanxulin002/.workbuddy/binaries/python/versions/3.13.12/python.exe"
TOOL="…/ModWorkspace/patch_pmod_attrs.py"

"$PY" "$TOOL" <pmod> --list                    # ① 先看现状（只读）
"$PY" "$TOOL" <pmod> --cost 500 --fire-interval 1.0 \
    --hitpoints 2000 --cost-rise -1 --cooldown 20 --card-type 1 \
    --dry-run                                  # ② 预览
"$PY" "$TOOL" <pmod> --cost 500 --fire-interval 1.0   # ③ 执行（原地改，自动备份）
```

* 糖参数：`--cost --cost-rise --cost-night --cooldown --hitpoints --fire-interval --fire-num --card-type`
* 通用：`--set 键=值`（任意已存在键）；`--file "*ComponentSet*.tres"` 限定文件（fnmatch，大小写不敏感）
* `--out PATH` 写到新路径（不动原包）；`--no-backup` 跳过备份
* 浮点字段自动补小数点（Godot 语法要求：`30` → `30.0`）；整数/布尔强类型校验

## 2. 安全设计（为什么它不会改坏包）

1. **只改已存在的键，绝不新增**——键不存在 ⇒ exit 2 并指出搜过哪些范围（新增字段要懂类默认值/字段顺序，是另一门学问）。
2. **文件集合不变 ⇒ mod.json 的 resources 列表天然有效**，不需要重算（闸门 6 不触发）。
3. 重打包**逐条保留**原 entry 顺序/压缩方式/时间戳/属性 + zip 注释。
4. 写后自校验：文件名清单逐项一致、未改 entry CRC 一致、改动字段读回复核。
5. 原地改默认先备份 `<名>.pmod.bak-时间戳`；失败清理 `.tmp-pmod` 孤儿文件。

## 3. 修完之后

1. 结构闸门：`PY ModWorkspace/verify_pmod.py <pmod>` → 须 `FAIL=0`（`entry.unsupported`/`provide.unchecked` 是已知无害 warn）；
2. 替换/放回 `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\`（若不是原地改的）；
3. **重启游戏**（铁律 6：别删 ModsCache），选卡界面读费用/冷却，实战读射速。

## 4. 边界（工具刻意不做的事）

* **不新增字段**（如给没有 `costNight` 的包加夜间价）——走生成器或手工编辑 `.tres`。
* **不碰 `.dat`/图集/`mod.json`/`Runtime/`**——数值属性全部在文本资源里，二进制不涉及。
* **不做"多角色挑一个改"**——如女王包有两张卡（`--card-type` 会两张一起改）；
  要单改某个文件用 `--file + --set`。
* 改完的包与生成器产物**不再逐字节一致** ⇒ 该包以后要继续改，优先回生成器改参数重生成；
  热补丁适合"没有源"的场景。

## 5. 实测记录（2026-09-25）

* `--list` / `--dry-run` / `--out` 副本 / 原地+备份 / 负向（不存在键 exit 2）全过；
* 补丁后 `verify_pmod.py`：ok=12 warn=9 **FAIL=0**；
* 过程抓到两个真 bug（已修，写新工具必跑 dry-run + 原地两条路径的教训）：
  ① `collect_plan` 里同文件多键 `plan[n]=found` 覆盖而非合并 ⇒ 同 scope 第二个键被静默丢掉；
  ② Windows 下原包 `ZipFile` 未 `close()` 就 `os.replace` 同路径 ⇒ WinError 5。
