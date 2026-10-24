# 子弹行为扩展点（`ProjectileBehaviorKernel`）—— 让子弹自己"会做事"

> 2026-09-30 首次打通（电能超级机枪射手）。**全部结论逐行核对 `PlantsVsZombies.dll` 反编译。**

## 0. 什么时候需要它

需求里出现「**子弹自己**做某件事」时 —— 例：子弹每 0.15 秒对周围 3×3 造成范围伤害、
命中第 N 次时触发连锁、飞行途中变形……**纯数据做不到**（`useRange` 只在命中/落地各爆一次），
必须挂一个**自定义子弹行为**。

## 1. 挂载链（行号 = `BulletField.cs` 实证）

```text
TowerDefenseProjectileConfig.behaviors : Array<ProjectileBehaviorDefinition>
   ↓ :7399-7448  遍历 behaviors → def.CreateBulletFieldKernel(65536) 编成 kernel
   ↓ :4432       BulletData.behaviorProgramId = programId
   ↓ :7476-7545  每帧对 behaviorProgramId>0 的子弹调 kernel.Process(index, ref bullet, delta)
   ↓           命中目标时调 kernel.OnHitTarget(index, ref bullet, target)
```

`ProjectileBehaviorKernel`（抽象类，**可直接继承**）：

```csharp
public abstract class ProjectileBehaviorKernel
{
    public BulletField Field { get; }                                  // Bind() 注入
    public virtual void OnSpawn(int index, ref BulletData bullet) { }
    public virtual void Process(int index, ref BulletData bullet, double delta) { }
    public virtual void OnHitTarget(int index, ref BulletData bullet, TowerDefenseCharacter target) { }
    public virtual void OnLand(int index, ref BulletData bullet) { }
    public virtual void OnDespawn(int index, ref BulletData bullet) { }
}
```

`ProjectileBehaviorDefinition`（`[GlobalClass]`，`BehaviorTypeId = "projectile"`）：

```csharp
public virtual ProjectileBehaviorKernel CreateBulletFieldKernel(int capacity) => null;
```

★ **现成范例**：`ProjectileBehaviorYMoveSin`（正弦飘动）—— 定义类 + 内嵌 `SineKernel`，
`Process` 里按 `_timers[index] += delta` 累积。**照抄它的形状即可**。

★ `index` = BulletField 的**槽号**（0..65535），所以 kernel 里用**并列数组**存每颗弹的状态
（`new double[capacity]`），别用字典。

## 2. 三件套：怎么让子弹"无限穿透 + 范围伤害 + 命中回调"

| 需求 | 数据侧 | 代码侧（kernel） |
|---|---|---|
| 无限穿透 | `config.penetrateNum = -1`（`:3585` 明确支持 -1） | —— |
| 每 X 秒范围伤害 | `config.rangeSize = (半宽格, 半宽格)`（供下面调用时取范围） | `Process` 里累积 delta，到点调 `TowerDefenseExplode.CreateProjectileExplode(...)` |
| 命中事件 | —— | `OnHitTarget` |
| 范围找目标 | —— | `TowerDefenseManager.Instance.GetCharactersIntersectingRect(rect, false, 0)` |

⚠️ **不要**把 `config.useRange` 置 true：那会让子弹在**命中 / 落地**时各爆一次
（`:3666-3671`、`:3821-3823`），与"每 X 秒一次"冲突。

### 范围伤害入口（两个重载）

```csharp
// ① 用配置里的伤害
TowerDefenseExplode.CreateProjectileExplode(pos, config, exclude, camp, canHitShieldedTargets);
// ② ★ 传运行时伤害（本 Mod 用的这条）—— TowerDefenseExplode.cs:305
TowerDefenseExplode.CreateProjectileExplode(pos, config, exclude, camp, canHitShieldedTargets,
    runtimeDamage, runtimeDamageFlags, runtimeFireMethodFlags, runtimeCollisionFlags);
// ③ 直接给 size（归一化，size=1 ⇒ 直径 2 格）—— :378
TowerDefenseExplode.CreateExplode(pos, size, eventList, exclude, camp, collisionFlags);
```

**范围口径**（`:540-541`）：`实际尺寸 = GetMapGridSize() * 2f * config.rangeSize`
⇒ `rangeSize = 1.5` = 边长 3 格 = **「3×3 格」=「半径 1.5 格」**（同义）。

## 3. 定身 / 状态：直接用游戏内置 buff

```csharp
var cfg = TowerDefenseCharacterBuffConfig.CreateBuffByKey("MagicImmobilize");  // 定身
if (cfg is TowerDefenseCharacterBuffMagicImmobilize imm) imm.time = 0.5;       // 时长
target.buff.AddBuff(cfg);                                                       // 挂上
```

- key 实证：`TowerDefenseCharacter.cs:4010` → `buff?.BuffHas("MagicImmobilize")`。
- 其它常用 key 从 `TowerDefenseCharacterBuff*` 的类名推（`Frozen` / `Dizziness` / `Burn` / …）。
- `BuffComponent` 还有 `BuffHas(key)` / `BuffGet(key)` / `DeleteBuff(key)` / `BuffClear()`。

## 4. 五个必踩的坑（都踩过）

1. ★★ **`BuffComponent` / `CharacterComponentRuntime` 不是 `GodotObject`**（纯 C# 抽象类）
   ⇒ **不能** `GodotObject.IsInstanceValid(buff)`，只能判 `null`（否则 CS1503）。
2. ★★ **`TowerDefenseCharacter.GetGlobalPositionForPhysicsFrame(ulong)` 是 `protected`**
   ⇒ 外部拿坐标用 `Node2D.GlobalPosition`（CS0122）。
3. ★★ **入口接口的命名空间是 `PVZHE.ModEditor.ModSystem`**（`IXWModRuntimeEntry` / `XWModRuntimeContext`），
   不在全局里 —— 忘了 `using` 就是 3 个 CS0246。
4. ★ **`[GlobalClass]` 注册的可行性仍未实机验证**：本工程刻意不用 Godot.NET.Sdk（无源码生成器），
   `new MyBehavior()` 出来的对象是否被 Godot 接受（`IsInstanceValid` 是否为 true）**必须实机确认**。
   失败退路：改用数据驱动（把逻辑挪到插件每帧自扫），或改走 `useRange` 路径（但要接受多两次爆炸）。
5. ★ **参数别改共用的 `runtime_shared/GatlingVolleyCore.cs`** —— 那是植物/僵尸两个包共用的单一真源
   （7 颗 / 300 颗）。新角色要自己的参数就在自己的 `XxxVolleyCore.cs` 里独立定义。

## 5. 交付时的参数闸门（务必配）

参数一旦是"用户逐条点名"的，就要有**机械闸门**：
`check_xxx_params.py` —— 对**源码**做 GOLD 字面量断言 + 自洽性断言（如 `5/0.02==250`、`250×3==750`、`10×30==300`），
并配 `--neg`（故意篡改一条必须报 FAIL）。本 Mod 实测 **25 OK / 0 FAIL**、负向 2 FAIL。
