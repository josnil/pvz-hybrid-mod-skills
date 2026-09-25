using System;
using System.Collections.Generic;
using System.Reflection;
using Godot;
using PVZHE.ModEditor.ModSystem;

/// <summary>
/// 「向日葵女王僵尸 + 火焰向日葵舞者僵尸」双角色 Mod 的托管运行时入口。
///
/// ════════════════════════════════════════════════════════════════════════
/// 〇、一个包两个角色
/// ════════════════════════════════════════════════════════════════════════
/// `ModLoader.ApplyRuntimeResources` 的候选是**逐文件**的 `RuntimeCandidate`，按
/// `(NormalizeCategory(Category), InferredKey)` 分组（`ModLoader.cs:566-597`）
/// ⇒ 同一个包里放两个 `Resources/Characters/Zombies/&lt;Key&gt;/…` 是被支持的。
/// 好处：两份角色共用**一个** `Runtime/ModAssembly.dll` 与**一个**入口实例，
/// 不会出现「同名 DLL 被两个包各加载一次 ⇒ 两条光环 / 两倍火球」的重复执行。
/// ⇒ 所以本入口用 `config.name` 分辨是哪一个，而不是靠「包身份」。
///
/// ════════════════════════════════════════════════════════════════════════
/// 一、为什么要插件（纯数据做不到的部分）
/// ════════════════════════════════════════════════════════════════════════
///   1. **3×3 友方（含自身）免疫减速与冻结** —— 「给友方加 buff」在数据侧没有通道：
///      `TowerDefenseExplode.PrepareCharacters`（`:502`）走
///      `FillCharactersIntersectingRectListExcludingCamp(rect, item.Camp, …)`，
///      而 `TowerDefenseBattleCharacterRegistry.cs:3279` 的判定是
///      `towerDefenseCharacter.camp != excludedCamp` ⇒ 传 `camp = ZOMBIE` 就只打**敌方**，
///      传 `CHARACTER_CAMP.ALL` 才会命中**所有**具体阵营（含自己）。
///      内置`PeriodicAreaEventComponent` 同款（`:256`）⇒ 也够不着友方。
///   2. **每 0.5 秒 25 点灼烧** —— 内置植物《向日葵女王》的节拍是
///      `attackTimer >= attackInterval`（`attackInterval = 3.0`）+ `Hurt.num = 40`；
///      用户口径是 0.5s / 25 ⇒ 节拍与数值只能插件自己控。
///   3. **火球齐射的 1.5 秒节拍** —— `FireComponent` 的自发发射是
///      「有目标才发 → 动画事件 `fire` → `FireConfiguredVolley()`」这条链，
///      节拍由动画长度决定；而本包的头是独立渲染的向日葵头、**没有 `HeadFire` clip**
///      ⇒ 动画链路整条失效 ⇒ 必须由插件推进节拍。
///      ⚠️ **6 颗本身走数据侧**（见第四节），插件只负责「什么时候叫一次」。
///
/// ════════════════════════════════════════════════════════════════════════
/// 二、3×3 是怎么算出来的（逐字对标内置植物《向日葵女王》）
/// ════════════════════════════════════════════════════════════════════════
/// `TowerDefenseExplode.PrepareCharacters:502`：
///     `Vector2 size = instance.GetMapGridSize() * 2f * item.Size;`
///     `RectFromCenter(item.Position, size)`
/// 植物女王的场景里两次调用都传 `size = Vector2(1.3f, 1.3f)`
/// ⇒ 矩形边长 = 格宽 × 2 × 1.3 = **2.6 格** ⇒ 半边长 1.3 格 ⇒ 覆盖**中心格 ±1 格 = 3×3**
///   （留 0.3 格余量让贴边的角色也被扫到）。
/// ⇒ 本入口常量 `GridSpan = 3.0f`，实际传值 `AreaHalfSpan = GridSpan / 2 - 0.2 = 1.3f`，
///   与植物女王**逐字相同** ⇒ 不依赖任何地图的硬编码像素。
///
/// ════════════════════════════════════════════════════════════════════════
/// 三、免疫是怎么实现的
/// ════════════════════════════════════════════════════════════════════════
/// 植物女王的 `allEventList` 只有一条 `TowerDefenseCharacterEventAddBuff`，里面挂
/// `TowerDefenseCharacterBuffFireHit`。看它的 `Enter()`（`TowerDefenseCharacterBuffFireHit.cs:11-16`）：
///     `character.buff.DeleteBuff("IceSpeedDown"); DeleteBuff("EMSpeedDown"); DeleteBuff("Frozen");`
/// ⇒ **「免疫减速与冻结」= 施加 FireHit buff**（不是改 `unUseBuffFlags` 掩码）。
///   `unUseBuffFlags`（数据侧已写 19 = bit0|bit1|bit4）只是「不再新中招」的**预防**位，
///   而 FireHit 的 `Enter()` 会把**已经中的**减速/冻结就地删掉 ⇒ 两者互补。
/// `AddBuff` 走 `ApplyFireHit()` 分支（`TowerDefenseCharacterEventAddBuff.cs:42-45`），
/// 后者对「已存在」的走 `Refresh` ⇒ **不会堆积** buff 条目（`BuffComponent.cs:447-470`）。
///
/// ════════════════════════════════════════════════════════════════════════
/// 四、6 颗齐射为什么不需要插件循环
/// ════════════════════════════════════════════════════════════════════════
/// `FireComponent.Fire()`（`:3429/3434`）**一次遍历 `fireProjectileList` 全部配置**，
/// 每条各自 `CreateProjectile(cfg.firePosId, …)`，而 `CreateProjectile`（`:2684`）里
/// `posId` 就是 `_firePosMarkers[posId]` 的下标（`:2708-2715`）。
/// ⇒ 数据侧写 **6 条配置 + 6 个 `FireMarker{i}`**，一次 `Fire()` 就同帧 6 颗。
/// 「追踪」也是引擎自带的：`fireMethodFlags = 32`（TRACK）⇒ `:2718` 走
/// `GetProjectileInitialTrackTarget(...)` 锁最近目标。
/// ⚠️ 千万别用 `fireNumAtOnce = true` + `fireNum = 6` 配 6 条配置 ——
///    `FireConfiguredVolley()`（`:3413`）会循环 6 次 `Fire()` ⇒ **36 颗**。
///
/// ════════════════════════════════════════════════════════════════════════
/// 五、换头三节点的运行期纽带（与「超级机枪读报僵尸」同款）
/// ════════════════════════════════════════════════════════════════════════
/// `AdobeAnimateSprite.CollectOwnedChildBindings`（`:5385`）只看节点类型、`_Draw`（`:9534`）
/// 首行 `return` ⇒ 子精灵必被父批次代画 ⇒ 跨 `.tres` 的子精灵会被父的图集采样成碎片。
/// 数据侧用三节点规避（`HeadShadow` 零切片吃定位 + `HeadHolder` 打断递归 + `Head` 独立渲染），
/// 运行期**每帧**把影子的 `Position`/`Rotation` 抄给可见头（`SyncHeadPairs`），
/// 并把 6 个火球生成点摆到当帧真炮口（`head.GlobalTransform * MuzzleLocal`）。
///
/// ════════════════════════════════════════════════════════════════════════
/// 六、纪律
/// ════════════════════════════════════════════════════════════════════════
/// `Initialize` / `OnAllModsLoaded` / `Shutdown` **一律不许抛**（抛了 = 无条件整包回滚），
/// 所以三个回调整体 try/catch；其余每条功能路径**各自**一个「已报告」标志
/// （共用会把先报的静音掉后面的）。所有反射调用都包在 try/catch 里。
/// </summary>
public sealed class SunFlowerQueenRuntimeEntry : IXWModRuntimeEntry
{
	private const string LogPrefix = "[SunFlowerQueen] ";

	// ---------------------------------------------------------------- 角色识别
	//
	// 身份标识 = `TowerDefenseZombieConfig.name`（== 角色包 Key）。
	// 插件与卡库都靠它认人；`metadata/mod_display_name` 那张中文名不参与。

	private const string QueenConfigName = "ZombieSunFlowerQueen";
	private const string DancerConfigName = "ZombieFireSunFlowerBackup";

	// ---------------------------------------------------------------- 组件接线键

	private const string FireInstanceId = "character.fire";
	private const string ProduceInstanceId = "character.produce";

	// ---------------------------------------------------------------- 发射（需求 4）

	/// <summary>齐射颗数（需求 4「6 颗」）。同时是数据侧 `FireMarker{i}` 的个数。</summary>
	private const int FireNum = 6;

	/// <summary>齐射周期（秒）（需求 4「每 1.5 秒」）。</summary>
	private const float FireInterval = 1.5f;

	private static readonly ulong FireIntervalMsec = (ulong)(FireInterval * 1000f);

	// ---------------------------------------------------------------- 光环（需求 4）

	/// <summary>作用范围 = 3×3 格。实际传给 `CreateExplode` 的是 `GridSpan / 2 - 0.2`（见类注释第二节）。</summary>
	private const float GridSpan = 3.0f;

	/// <summary>灼烧周期（秒）（需求 4「每 0.5 秒」）。</summary>
	private const float BurnInterval = 0.5f;

	/// <summary>每跳灼烧伤害（需求 4「25 点」）。</summary>
	private const float BurnDamage = 25.0f;

	/// <summary>`unUseBuffFlags` 的「免疫减速 + 免疫冻结」两位（bit0 | bit1），数据侧已写 19。</summary>
	private const int ImmuneFlags = 3;

	private static readonly ulong BurnIntervalMsec = (ulong)(BurnInterval * 1000f);

	/// <summary>
	/// 传给 `CreateExplode` 的半边长（**格**）—— 与内置植物《向日葵女王》场景里的
	/// `Vector2(1.3f, 1.3f)` 逐字相同。`1.3 = 3/2 - 0.2`。
	/// </summary>
	private static readonly Vector2 AreaHalfSpan = new Vector2(GridSpan * 0.5f - 0.2f, GridSpan * 0.5f - 0.2f);

	// 照抄内置 `TowerDefensePlantQueenSunFlower.tscn` 的 `Resource_qxxii`（`TowerDefenseCharacterEventHurt`）
	private const int HurtDamageFlags = 6;
	private const int HurtCollisionFlags = 27;

	/// <summary>灼烧特效（植物女王同款）。加载失败就只用裸伤害。</summary>
	private const string BurnEffectScenePath =
		"res://Prefab/Particles/Splats/FireSplats/TowerDefenseEffectSpriteFireSplats.tscn";

	// ---------------------------------------------------------------- 调度

	/// <summary>扫场景找僵尸的间隔（帧）。光环节拍与头位姿同步都不受它限制。</summary>
	private const int ScanIntervalFrames = 10;

	/// <summary>两帧间隔超过它就认为「暂停 / 长卡顿」，把节拍整体后移，不补发欠账。</summary>
	private const ulong StallThresholdMsec = 250;

	// ---------------------------------------------------------------- 换头

	private const string HeadShadowNodeName = "HeadShadow";
	private const string HeadHolderNodeName = "HeadHolder";
	private const string HeadNodeName = "Head";

	/// <summary>头 `.tres` 里唯一的 clip（`QueenSunFlower.tres` / `SunFlowerHead.tres` 都只有 `Idle`）。</summary>
	private const string HeadClipName = "Idle";

	/// <summary>
	/// 火球生成点在**可见头节点局部**空间的位置。
	///
	/// 向日葵头没有「炮口」概念 ⇒ 就用头节点原点（数据侧 `HEAD_OFFSET` 已经把原点对到头上），
	/// 6 个生成点再沿局部 y 各自偏移 `MarkerYStep`（与 Sprite 场景里 `FireMarker{i}` 的静态兜底一致）。
	/// </summary>
	private static readonly Vector2 MuzzleLocal = Vector2.Zero;

	/// <summary>相邻两个火球生成点的局部 y 间距（px），与生成器的 `FIRE_MARKER_Y_STEP` 一致。</summary>
	private const float MarkerYStep = 14.0f;

	private const string FireMarkerNamePrefix = "FireMarker";

	/// <summary>
	/// 换头兜底：构成「原版头」的图层名，必须全部不可见（否则从新头底下透出来）。
	/// 女王 7 层（含 `anim_hair4`）/ 舞者 6 层，合并成一张表；
	/// 某层在该皮肤的 `layerDictionary` 里不存在就自动跳过。
	/// </summary>
	private static readonly string[] BodyHiddenHeadLayers = new string[]
	{
		"anim_hair",
		"anim_hair1",
		"anim_hair2",
		"anim_hair3",
		"anim_hair4",
		"anim_head1",
		"anim_head2"
	};

	// ---------------------------------------------------------------- 卡库

	private const string RootZombieBankKey = "GeneralZombie";
	private const string ZombieCategory = "Zombie";
	private const string PacketBankResourcePath = "res://Asset/Config/PacketBank/PacketBankResource.json";
	private static readonly string[] FallbackDerivedBankKeys =
		new string[] { "GeneralZombie", "TotalZombie", "Total" };

	// ---------------------------------------------------------------- 内部类型

	/// <summary>一只已被本插件接管的角色（女王带发射/光环，舞者只有卡库与换头）。</summary>
	private sealed class ZombieHook
	{
		public TowerDefenseCharacter Character;

		/// <summary>仅女王有（`want_fire = true`）。</summary>
		public FireComponent Fire;

		public bool IsQueen;

		/// <summary>下一次齐射的时刻（ms 墙钟）。</summary>
		public ulong NextFireMsec;

		/// <summary>下一次灼烧敌方（3×3 内）的时刻（ms 墙钟）。</summary>
		public ulong NextBurnMsec;

		/// <summary>下一次给 3×3 内友方（含自身）刷免疫的时刻（ms 墙钟）。</summary>
		public ulong NextImmuneMsec;
	}

	/// <summary>「影子 → 可见头」配对（换头三节点的运行期纽带）。</summary>
	private sealed class HeadPair
	{
		public AdobeAnimateSprite Shadow;
		public AdobeAnimateSprite Visible;

		/// <summary>本角色的火球生成点（`FireMarker0..5`）；舞者为空数组。</summary>
		public Marker2D[] Markers;
	}

	// ---------------------------------------------------------------- 状态

	private XWModRuntimeContext _context;
	private SceneTree _tree;
	private Callable _tickCallable;
	// ★★ 第十五轮：**同帧**同步用的回调（`CallDeferred` ⇒ 排到帧末，晚于所有节点 `_process`）。
	private Callable _syncCallable;
	private readonly List<ZombieHook> _hooks = new List<ZombieHook>();
	private readonly List<HeadPair> _headPairs = new List<HeadPair>();
	private bool _hooked;
	private bool _connected;
	private int _frameCounter;
	private ulong _lastFrameMsec;

	// 每条出错路径**各用一个**「已报告」标志（共用会把先报的把后报的静音掉）
	private bool _tickFaultReported;
	private bool _bankFaultReported;
	private bool _hookFaultReported;
	private bool _fireFaultReported;
	private bool _fireMissingReported;
	private bool _auraFaultReported;
	private bool _dedupeFaultReported;
	private bool _headShadowMissingReported;
	private bool _fireMarkerMissingReported;
	private bool _immuneFlagFixReported;

	private Godot.Collections.Array<TowerDefenseCharacterEventBase> _burnEvents;
	private Godot.Collections.Array<TowerDefenseCharacterEventBase> _immuneEvents;
	private Godot.Collections.Array<TowerDefenseCharacter> _emptyChars;

	private string[] _bankKeys;
	private int _bankPatchCount;

	private static FieldInfo _zombieLogicalField;
	private static bool _zombieLogicalFieldProbed;
	private int _almanacDedupeCount;

	private int _volleyCount;
	private int _burnCount;
	private int _immuneCount;
	private int _headClipFixCount;
	private int _bodyHeadHideCount;

	// ================================================================ 三回调

	public void Initialize(XWModRuntimeContext context)
	{
		try
		{
			_context = context;
			_hooked = false;
			_connected = false;
			_frameCounter = 0;
			_lastFrameMsec = 0UL;
			_tickFaultReported = false;
			_bankFaultReported = false;
			_hookFaultReported = false;
			_fireFaultReported = false;
			_fireMissingReported = false;
			_auraFaultReported = false;
			_dedupeFaultReported = false;
			_headShadowMissingReported = false;
			_fireMarkerMissingReported = false;
			_immuneFlagFixReported = false;
			_burnEvents = null;
			_immuneEvents = null;
			_emptyChars = null;
			_bankKeys = null;
			_bankPatchCount = 0;
			_almanacDedupeCount = 0;
			_volleyCount = 0;
			_burnCount = 0;
			_immuneCount = 0;
			_headClipFixCount = 0;
			_bodyHeadHideCount = 0;
			_hooks.Clear();
			_headPairs.Clear();

			string root = (context == null) ? "<null>" : context.PackageRoot;
			Info("运行入口已初始化；PackageRoot=" + root
				+ "；角色 = " + QueenConfigName + " / " + DancerConfigName
				+ "；齐射 " + FireNum + " 颗 / " + FireInterval.ToString("0.#") + "s"
				+ "；光环 " + GridSpan.ToString("0.#") + "×" + GridSpan.ToString("0.#")
				+ " 格内每 " + BurnInterval.ToString("0.#") + "s 对敌方 " + BurnDamage.ToString("0.#")
				+ " 点灼烧、并给友方（含自身）挂 FireHit（免疫减速+冻结）。");
		}
		catch (Exception ex)
		{
			Warn("Initialize 异常（已吞掉，避免整包被拒）：" + ex.Message);
		}
	}

	public void OnAllModsLoaded()
	{
		try
		{
			if (_hooked)
			{
				return;
			}
			_tree = Engine.GetMainLoop() as SceneTree;
			if (_tree == null)
			{
				Warn("拿不到 SceneTree；光环与齐射不会生效（角色本身仍可正常行走/啃食）。");
				return;
			}
			_tickCallable = Callable.From(new Action(OnProcessFrame));
			_tree.Connect("process_frame", _tickCallable);
			// ★★ 第十五轮：「抬头/收头时头与身体分离」的**真凶 = 1 帧延迟**。
			//    `process_frame` 早于**所有**节点的 `_process`，而影子的位姿是身体精灵在
			//    `_process` 里逐帧改写的（`UpdateChild()`）⇒ 这里读到的永远是**上一帧**值
			//    ⇒ 可见头永远落后身体 1 帧。正常帧位移 < 1px 察觉不到，但**抬头/收头交界**
			//    一帧位移可达 20~33px（女王 `PointDown`f45→`Walk`f46）⇒ 头与身体错位。
			//    修法：额外排一个 `CallDeferred`，在**帧末**（所有 `_process` 之后、绘制之前）
			//    再同步一次 ⇒ 用**当帧**位姿覆盖上面那次旧值。即使它落到下一帧初，此刻影子
			//    仍是「当帧」值 ⇒ 同样正确。（无需改数据侧：影子本来就自己跟层。）
			_syncCallable = Callable.From(new Action(SyncHeadPairs));
			_connected = true;
			_hooked = true;
			_lastFrameMsec = Time.GetTicksMsec();
			Info("已挂载 process_frame；并会把「" + QueenConfigName + "」「" + DancerConfigName
				+ "」补进卡库「" + RootZombieBankKey + "」的「" + ZombieCategory + "」分类。");
		}
		catch (Exception ex)
		{
			Warn("OnAllModsLoaded 异常（已吞掉）：" + ex.Message);
		}
	}

	public void Shutdown()
	{
		try
		{
			if (_connected && _tree != null && GodotObject.IsInstanceValid(_tree))
			{
				_tree.Disconnect("process_frame", _tickCallable);
			}
		}
		catch (Exception ex)
		{
			Warn("Shutdown 取消失效：process_frame 断开异常（已吞掉）：" + ex.Message);
		}
		finally
		{
			_connected = false;
			_hooked = false;
			_tree = null;
			_hooks.Clear();
			_headPairs.Clear();
		}
	}

	// ================================================================ 每帧

	private void OnProcessFrame()
	{
		try
		{
			_frameCounter++;
			ulong now = Time.GetTicksMsec();
			ulong gap = now - _lastFrameMsec;
			_lastFrameMsec = now;
			bool stalled = gap > StallThresholdMsec;

			AdvanceAll(now, stalled, gap);

			// ★ 换头三节点的纽带 + 6 个火球生成点：**每帧**同步。
			//   必须在 ScanIntervalFrames 早退**之前** —— 10 帧一档对头来说太粗，会抖。
			//   ⚠️ 这一次读到的是**上一帧**位姿（见 `SyncHeadPairs` 的说明），只作**兜底**；
			//   紧接着排一个 `CallDeferred`，在**帧末**用当帧位姿覆盖它（★ 第十五轮）。
			SyncHeadPairs();
			try
			{
				_syncCallable.CallDeferred();
			}
			catch
			{
				// `CallDeferred` 不可用 ⇒ 退化成「只有 process_frame 那一次」= 旧行为，不更差。
			}

			if ((_frameCounter % ScanIntervalFrames) != 0)
			{
				return;
			}
			ScanScene();
		}
		catch (Exception ex)
		{
			if (!_tickFaultReported)
			{
				_tickFaultReported = true;
				Warn("节拍推进异常（本条只报一次，仍会继续尝试）：" + ex.Message);
			}
		}
	}

	private void ScanScene()
	{
		TryPatchCardBanks();

		if (_tree == null || !GodotObject.IsInstanceValid(_tree))
		{
			return;
		}
		Node root = _tree.Root;
		if (root == null || !GodotObject.IsInstanceValid(root))
		{
			return;
		}
		ScanRecursive(root);
	}

	private void ScanRecursive(Node node)
	{
		if (node == null || !GodotObject.IsInstanceValid(node))
		{
			return;
		}
		if (node is TowerDefenseCharacter character)
		{
			TryHookCharacter(character);
		}
		else if (node is Almanac almanac)
		{
			TryDedupeAlmanacZombie(almanac);
		}
		else if (node is AdobeAnimateSprite animeSprite)
		{
			TryEnforceHeadSwap(animeSprite);
			TryRegisterHeadPair(animeSprite);
		}
		Godot.Collections.Array<Node> children = node.GetChildren();
		for (int i = 0; i < children.Count; i++)
		{
			ScanRecursive(children[i]);
		}
	}

	// ================================================================ 换头兜底

	/// <summary>
	/// 换头的运行期兜底（数据侧已经把 clip 与「关原头层」都写对了，但两者各有一条**静默失败**路径）：
	///   · **clip**：`Head` 是场景里新增的节点，`_clip` 只靠 `.tscn` 属性落下；没生效时
	///     `ApplyFlashAnimeDataChange()`（`AdobeAnimateSprite.cs:10222-10230`）会兜成 `clips.Keys[0]`。
	///   · **可见性**：`_layerVisible.Count != 图层数` 时引擎把整表**重置为全 true**
	///     （`:10190-10205` / `:10267-10275`）⇒ 原头立刻透出来。
	/// 幂等：已经对了就什么都不写。绝不抛。
	/// </summary>
	private void TryEnforceHeadSwap(AdobeAnimateSprite sprite)
	{
		try
		{
			if (sprite.Name != HeadNodeName || !sprite.IsInsideTree() || !sprite.IsNodeReady())
			{
				return;
			}
			AdobeAnimateData data = sprite.flashAnimeData;
			if (data != null && GodotObject.IsInstanceValid(data)
				&& data.clips != null && data.clips.ContainsKey(HeadClipName))
			{
				string current = sprite.Get("Animation/Clip").AsString();
				if (current != HeadClipName)
				{
					sprite.SetClip(HeadClipName);
					_headClipFixCount++;
					Info("换头兜底：把头的 clip 从「" + current + "」纠正为「" + HeadClipName
						+ "」（第 " + _headClipFixCount + " 个）。");
				}
			}
			EnforceBodyHeadLayersHidden(ResolveBodyForHead(sprite));
		}
		catch
		{
			// 视觉兜底失败不该影响战斗逻辑：静默放弃，下一轮扫描还会再来。
		}
	}

	/// <summary>可见头 → 它所属的**身体精灵**（`身体 / HeadHolder / Head`，见类注释第五节）。绝不抛。</summary>
	private static AdobeAnimateSprite ResolveBodyForHead(AdobeAnimateSprite head)
	{
		try
		{
			Node holder = head.GetParent();
			if (holder != null && holder.Name == HeadHolderNodeName)
			{
				AdobeAnimateSprite direct = holder.GetParent() as AdobeAnimateSprite;
				if (direct != null)
				{
					return direct;
				}
			}
			Node node = head.GetParent();
			int guard = 0;
			while (node != null && guard++ < 64)
			{
				if (node is AdobeAnimateSprite body)
				{
					return body;
				}
				node = node.GetParent();
			}
		}
		catch
		{
		}
		return null;
	}

	/// <summary>
	/// 把身体上构成「原版头」的图层关掉。只在**表长正好等于图层数**时才动
	/// （表长不符时引擎自己会重置成「全 true」，抢先写会被盖掉）。幂等、绝不抛。
	/// </summary>
	private void EnforceBodyHeadLayersHidden(AdobeAnimateSprite body)
	{
		try
		{
			if (body == null || !GodotObject.IsInstanceValid(body))
			{
				return;
			}
			AdobeAnimateData data = body.flashAnimeData;
			if (data == null || !GodotObject.IsInstanceValid(data) || data.layerDictionary == null)
			{
				return;
			}
			Godot.Collections.Array<bool> visible = body.layerVisible;
			if (visible == null || visible.Count != data.layerDictionary.Count)
			{
				return;
			}
			int changed = 0;
			for (int i = 0; i < BodyHiddenHeadLayers.Length; i++)
			{
				string layerName = BodyHiddenHeadLayers[i];
				if (!data.layerDictionary.ContainsKey(layerName))
				{
					continue;
				}
				int layerId = (int)data.layerDictionary[layerName].AsInt64();
				if (layerId >= 0 && layerId < visible.Count && visible[layerId])
				{
					visible[layerId] = false;
					changed++;
				}
			}
			if (changed > 0)
			{
				body.layerVisible = visible;   // 走 setter ⇒ 内部 MarkLayerStateChanged()
				_bodyHeadHideCount++;
				Info("换头兜底：关掉身体上 " + changed + " 层原版头（第 " + _bodyHeadHideCount
					+ " 个精灵）。节点=" + body.Name);
			}
		}
		catch
		{
		}
	}

	/// <summary>登记「影子 → 可见头 → 6 个生成点」。幂等、绝不抛。</summary>
	private void TryRegisterHeadPair(AdobeAnimateSprite visible)
	{
		try
		{
			if (visible.Name != HeadNodeName)
			{
				return;
			}
			AdobeAnimateSprite body = ResolveBodyForHead(visible);
			if (body == null)
			{
				return;
			}
			AdobeAnimateSprite shadow = body.GetNodeOrNull<AdobeAnimateSprite>(HeadShadowNodeName);
			if (shadow == null || ReferenceEquals(shadow, visible))
			{
				if (!_headShadowMissingReported)
				{
					_headShadowMissingReported = true;
					Warn("找到换头可见头 `" + HeadNodeName + "`，但身体 `" + body.Name
						+ "` 下没有 `" + HeadShadowNodeName + "` ⇒ 头不会跟随身体位移，会停在身体原点。"
						+ "请重跑 build_zombie_sunflower_queen.py（换头必须是「影子 + 容器 + 可见头」三节点结构）。");
				}
				return;
			}
			for (int i = 0; i < _headPairs.Count; i++)
			{
				if (ReferenceEquals(_headPairs[i].Visible, visible))
				{
					return;
				}
			}
			Marker2D[] markers = CollectFireMarkers(body);
			HeadPair pair = new HeadPair();
			pair.Shadow = shadow;
			pair.Visible = visible;
			pair.Markers = markers;
			_headPairs.Add(pair);
			Info("已登记换头纽带（第 " + _headPairs.Count + " 对）：影子=" + shadow.Name
				+ "，可见头=" + visible.Name + "，火球生成点=" + markers.Length + " 个。");
		}
		catch
		{
			// 登记失败只影响外观：静默放弃，下一轮扫描还会再来。
		}
	}

	/// <summary>取身体下的 `FireMarker0..FireNum-1`（舞者没有，返回空数组）。</summary>
	private Marker2D[] CollectFireMarkers(AdobeAnimateSprite body)
	{
		List<Marker2D> found = new List<Marker2D>();
		for (int i = 0; i < FireNum; i++)
		{
			Marker2D m = body.GetNodeOrNull<Marker2D>(FireMarkerNamePrefix + i);
			if (m != null)
			{
				found.Add(m);
			}
		}
		if (found.Count == 0)
		{
			return new Marker2D[0];
		}
		if (found.Count != FireNum && !_fireMarkerMissingReported)
		{
			_fireMarkerMissingReported = true;
			Warn("身体 `" + body.Name + "` 下只找到 " + found.Count + " / " + FireNum
				+ " 个火球生成点 `" + FireMarkerNamePrefix + "i` ⇒ 缺的那些配置会把子弹丢在僵尸原点。"
				+ "请重跑 build_zombie_sunflower_queen.py。");
		}
		return found.ToArray();
	}

	/// <summary>
	/// **每帧**把影子的位姿抄给可见头，并把 6 个火球生成点摆到当帧真位置。
	///
	/// 影子的 `Position`/`Rotation` 是 `UpdateChild()`（`AdobeAnimateSprite.cs:5259-5281`）
	/// 在身体的 `_process` 里逐帧改写的 ⇒ 10 帧一档的 `ScanRecursive` 太粗，头会抖。
	/// 只抄 `Position`/`Rotation`：两者 `scale`/`offset`/`offsetRotate` 在场景里已逐字相同。
	/// ⚠️ `process_frame` 早于节点 `_process` ⇒ 这一次读到的是**上一帧**位姿。正常帧的位移
	///    < 1px 无所谓，但**抬头/收头**交界一帧可达 20~33px ⇒ 头与身体错位（用户说的「分离」）。
	///    ★★ 第十五轮：`OnProcessFrame` 里紧接着排了一个 `CallDeferred` ⇒ 本函数在同一帧的
	///    **帧末**（所有 `_process` 之后、绘制之前）会再跑一次，用**当帧**位姿覆盖 ⇒ 零延迟。
	/// 幂等、绝不抛；失效的对会被剔除（下一轮扫描重新登记）。
	/// </summary>
	private void SyncHeadPairs()
	{
		if (_headPairs.Count == 0)
		{
			return;
		}
		for (int i = _headPairs.Count - 1; i >= 0; i--)
		{
			HeadPair pair = _headPairs[i];
			if (!IsLiveSprite(pair.Shadow) || !IsLiveSprite(pair.Visible))
			{
				_headPairs.RemoveAt(i);
				continue;
			}
			try
			{
				if (pair.Visible.Position != pair.Shadow.Position)
				{
					pair.Visible.Position = pair.Shadow.Position;
				}
				if (!Mathf.IsEqualApprox(pair.Visible.Rotation, pair.Shadow.Rotation))
				{
					pair.Visible.Rotation = pair.Shadow.Rotation;
				}
				// 阳光/火球生成点：头是逐帧在摆的 ⇒ 场景里的静态 position 只能对上参考帧。
				// `head.GlobalTransform * local` = 生成点的世界坐标（头绘制时是
				// `transform.Translated(offset)` 再画 pose 点 ⇒ 局部点 = pose + offset）。
				// ⚠️ 必须在抄完 Position/Rotation **之后**（GlobalTransform 跟着这两个量变）。
				if (pair.Markers != null)
				{
					Transform2D xf = pair.Visible.GlobalTransform;
					for (int k = 0; k < pair.Markers.Length; k++)
					{
						Marker2D marker = pair.Markers[k];
						if (marker == null || !GodotObject.IsInstanceValid(marker))
						{
							continue;
						}
						Vector2 local = MuzzleLocal + new Vector2(0f, k * MarkerYStep);
						Vector2 world = xf * local;
						if (!marker.GlobalPosition.IsEqualApprox(world))
						{
							marker.GlobalPosition = world;
						}
					}
				}
			}
			catch
			{
				_headPairs.RemoveAt(i);
			}
		}
	}

	/// <summary>精灵是否还能安全读写（节点有效 + 在树内）。绝不抛。</summary>
	private static bool IsLiveSprite(AdobeAnimateSprite sprite)
	{
		try
		{
			return sprite != null && GodotObject.IsInstanceValid(sprite) && sprite.IsInsideTree();
		}
		catch
		{
			return false;
		}
	}

	// ================================================================ 节拍推进

	private void AdvanceAll(ulong now, bool stalled, ulong gap)
	{
		for (int i = _hooks.Count - 1; i >= 0; i--)
		{
			ZombieHook hook = _hooks[i];
			if (!IsUsable(hook.Character))
			{
				_hooks.RemoveAt(i);
				continue;
			}
			if (stalled)
			{
				// 暂停 / 长卡顿：三条时间轴整体后移，欠账作废（不补发）。
				hook.NextFireMsec += gap;
				hook.NextBurnMsec += gap;
				hook.NextImmuneMsec += gap;
			}
			if (hook.IsQueen)
			{
				AdvanceFire(hook, now);
				AdvanceAura(hook, now);
			}
		}
	}

	/// <summary>
	/// 齐射：到点就调**一次** `Fire()` —— 数据侧 6 条配置会各自从 `FireMarker{i}` 出膛（见类注释第四节）。
	/// 开火判定用 `CanFireCheckOnceByData`（不是 `CanFire`，见「铁律 12」）。
	/// </summary>
	private void AdvanceFire(ZombieHook hook, ulong now)
	{
		if (hook.Fire == null || now < hook.NextFireMsec)
		{
			return;
		}
		hook.NextFireMsec = now + FireIntervalMsec;
		// 目标判定失败本身是正常路径（没敌人时不该放空枪），不打日志。
		if (!HasFireTarget(hook.Fire))
		{
			return;
		}
		try
		{
			hook.Fire.Fire();
			_volleyCount++;
			if (_volleyCount <= 3)
			{
				Info("第 " + _volleyCount + " 次齐射（一次 Fire() ⇒ " + FireNum + " 颗追踪火球）。");
			}
		}
		catch (Exception ex)
		{
			if (!_fireFaultReported)
			{
				_fireFaultReported = true;
				Warn("调用 FireComponent.Fire() 失败（本条只报一次；僵尸仍会行走/啃食）：" + ex.Message);
			}
		}
	}

	private bool HasFireTarget(FireComponent fire)
	{
		try
		{
			TowerDefenseProjectileCreateData data = null;
			Godot.Collections.Array<FireComponentCheckConfig> checks = fire.fireCheckList;
			if (checks != null && checks.Count > 0 && checks[0] != null
				&& GodotObject.IsInstanceValid(checks[0]))
			{
				data = checks[0].GetProjectile();   // projectile 无效时自己返回 null
			}
			return fire.CanFireCheckOnceByData(data);
		}
		catch (Exception ex)
		{
			if (!_auraFaultReported)
			{
				_auraFaultReported = true;
				Warn("开火前目标判定异常（本条只报一次；已放行）：" + ex.Message);
			}
			return true;
		}
	}

	/// <summary>
	/// 光环两个节拍（只女王有）：
	///   · 每 `BurnInterval` 秒：`CreateExplode(pos, 1.3 格, [Hurt(BurnDamage)], camp = ZOMBIE, flags)`
	///     ⇒ 3×3 内的**敌方**吃 25 点灼烧（照抄植物女王的 `eventList`）。
	///   · 每 `BurnInterval` 秒：`CreateExplode(pos, 1.3 格, [AddBuff(FireHit)], camp = ALL, -1)`
	///     ⇒ 3×3 内**所有阵营（含自己）**挂 FireHit ⇒ 免疫减速+冻结（照抄植物女王的 `allEventList`）。
	/// 绝不抛（失败只报一次，不影响角色本体）。
	/// </summary>
	private void AdvanceAura(ZombieHook hook, ulong now)
	{
		TowerDefenseCharacter character = hook.Character;
		Vector2 pos;
		int collisionFlags;
		try
		{
			EnsureAuraEvents();
			if (_burnEvents == null)
			{
				return;
			}
			pos = character.GetLogicalGlobalPosition();
			collisionFlags = character.instance.collisionFlags;
		}
		catch (Exception ex)
		{
			if (!_auraFaultReported)
			{
				_auraFaultReported = true;
				Warn("读光环所需的角色数据失败（本条只报一次）：" + ex.Message);
			}
			return;
		}

		if (now >= hook.NextBurnMsec)
		{
			hook.NextBurnMsec = now + BurnIntervalMsec;
			try
			{
				TowerDefenseExplode.CreateExplode(pos, AreaHalfSpan, _burnEvents, _emptyChars,
					TowerDefenseEnum.CHARACTER_CAMP.ZOMBIE, collisionFlags);
				_burnCount++;
			}
			catch (Exception ex)
			{
				if (!_auraFaultReported)
				{
					_auraFaultReported = true;
					Warn("3×3 灼烧异常（本条只报一次）：" + ex.Message);
				}
			}
		}

		if (now >= hook.NextImmuneMsec)
		{
			hook.NextImmuneMsec = now + BurnIntervalMsec;
			try
			{
				TowerDefenseExplode.CreateExplode(pos, AreaHalfSpan, _immuneEvents, _emptyChars,
					TowerDefenseEnum.CHARACTER_CAMP.ALL, -1);
				_immuneCount++;
				EnsureImmuneFlags(character);
			}
			catch (Exception ex)
			{
				if (!_auraFaultReported)
				{
					_auraFaultReported = true;
					Warn("3×3 友方免疫异常（本条只报一次）：" + ex.Message);
				}
			}
		}
	}

	/// <summary>
	/// 绷带：数据侧 `unUseBuffFlags` 已写 19（bit0|bit1|bit4），万一被别的逻辑改掉就补回来。
	/// 这只是**预防**位；「已经中的减速/冻结」由 `FireHit.Enter()` 删除（见类注释第三节）。
	/// </summary>
	private void EnsureImmuneFlags(TowerDefenseCharacter character)
	{
		try
		{
			int flags = character.instance.unUseBuffFlags;
			if ((flags & ImmuneFlags) == ImmuneFlags)
			{
				return;
			}
			character.instance.unUseBuffFlags = flags | ImmuneFlags;
			if (!_immuneFlagFixReported)
			{
				_immuneFlagFixReported = true;
				Info("免疫位兜底：把 unUseBuffFlags 从 " + flags + " 补成 "
					+ character.instance.unUseBuffFlags + "（bit0 减速 + bit1 冻结）。");
			}
		}
		catch
		{
		}
	}

	/// <summary>
	/// 懒构造两张事件表（只在第一次需要时建，避免每帧 new 一堆 `Resource`）：
	///   · `_burnEvents`  = `[Hurt(num = BurnDamage, damageFlags = 6, collisionFlags = 27, playSplatAudio = false)]`
	///     （照抄植物女王 `.tscn` 的 `Resource_qxxii`，只把 num 按用户口径改成 25）
	///   · `_immuneEvents` = `[AddBuff(FireHit)]`（照抄 `Resource_lujgt`）
	/// ⚠️ 特效（`Resource_eia3h` 的 FireSplats）尽力而为：加载失败就只用裸伤害。
	/// </summary>
	private void EnsureAuraEvents()
	{
		if (_burnEvents != null)
		{
			return;
		}
		_emptyChars = new Godot.Collections.Array<TowerDefenseCharacter>();

		TowerDefenseCharacterEventHurt hurt = new TowerDefenseCharacterEventHurt();
		hurt.num = BurnDamage;
		hurt.damageFlags = HurtDamageFlags;
		hurt.collisionFlags = HurtCollisionFlags;
		hurt.playSplatAudio = false;   // 每 0.5 秒一次，别刷音效
		_burnEvents = new Godot.Collections.Array<TowerDefenseCharacterEventBase>();
		_burnEvents.Add(hurt);
		try
		{
			PackedScene effect = GD.Load<PackedScene>(BurnEffectScenePath);
			if (effect != null && GodotObject.IsInstanceValid(effect))
			{
				TowerDefenseCharacterEventCreateEffect fx = new TowerDefenseCharacterEventCreateEffect();
				fx.effectScene = effect;
				_burnEvents.Add(fx);
			}
		}
		catch (Exception ex)
		{
			Info("灼烧特效不可用（只用裸伤害）：" + ex.Message);
		}

		TowerDefenseCharacterEventAddBuff addBuff = new TowerDefenseCharacterEventAddBuff();
		addBuff.buffList = new Godot.Collections.Array<TowerDefenseCharacterBuffConfig>();
		addBuff.buffList.Add(new TowerDefenseCharacterBuffFireHit());
		_immuneEvents = new Godot.Collections.Array<TowerDefenseCharacterEventBase>();
		_immuneEvents.Add(addBuff);
	}

	// ================================================================ 挂载

	private void TryHookCharacter(TowerDefenseCharacter character)
	{
		try
		{
			TowerDefenseCharacterConfig config = character.config;
			if (config == null || !GodotObject.IsInstanceValid(config))
			{
				return;
			}
			string name = config.name;
			bool isQueen = string.Equals(name, QueenConfigName, StringComparison.Ordinal);
			bool isDancer = string.Equals(name, DancerConfigName, StringComparison.Ordinal);
			if (!isQueen && !isDancer)
			{
				return;
			}
			for (int i = 0; i < _hooks.Count; i++)
			{
				if (ReferenceEquals(_hooks[i].Character, character))
				{
					return;   // 已经接管
				}
			}

			ZombieHook hook = new ZombieHook();
			hook.Character = character;
			hook.IsQueen = isQueen;
			ulong now = Time.GetTicksMsec();
			hook.NextFireMsec = now + FireIntervalMsec;
			hook.NextBurnMsec = now + BurnIntervalMsec;
			hook.NextImmuneMsec = now + BurnIntervalMsec;
			hook.Fire = null;

			if (isQueen)
			{
				ComponentManager components = character.componentManager;
				FireComponent fire = (components == null)
					? null
					: components.GetRuntime<FireComponent>(FireInstanceId);
				if (!IsUsable(fire))
				{
					// ⚠️ 这条以前是**静默** return 的，结果是「一颗粒子都不出、日志里什么都看不到」。
					// 最常见原因：角色场景根节点漏了 `ComponentSet = ExtResource(…)`。
					if (!_fireMissingReported)
					{
						_fireMissingReported = true;
						Warn("找到了「" + QueenConfigName + "」但拿不到组件 \"" + FireInstanceId
							+ "\"（火球不会发射；僵尸仍会正常行走/啃食）。最常见原因：角色场景根节点"
							+ "漏了 `ComponentSet = ExtResource(…)`，于是基场景那份不含 FireComponent 的组件集生效。");
					}
				}
				else
				{
					hook.Fire = fire;
				}
				if (components != null
					&& components.GetRuntime<ProduceComponent>(ProduceInstanceId) == null)
				{
					Warn("「" + QueenConfigName + "」拿不到组件 \"" + ProduceInstanceId
						+ "\"（不会产脑光）；请核对包内 ComponentSet。");
				}
			}

			_hooks.Add(hook);
			Info("已接管第 " + _hooks.Count + " 只「" + name + "」（"
				+ (isQueen ? "女王：齐射 " + FireNum + " 颗 / " + FireInterval.ToString("0.#")
					+ "s + 3×3 光环" : "舞者：无发射、无光环") + "）。");
		}
		catch (Exception ex)
		{
			if (!_hookFaultReported)
			{
				_hookFaultReported = true;
				Warn("读取角色组件失败（本条只报一次；不影响正常行走/啃食）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 组件是否仍可用。
	/// ⚠️ `CharacterComponentRuntime` **不是 GodotObject**（是纯 C# 抽象类）⇒
	/// 既没有 `GodotObject.IsInstanceValid` 也没有 `GetInstanceId()`；只能看 `IsReleased` + `Owner`。
	/// </summary>
	private static bool IsUsable(FireComponent fire)
	{
		try
		{
			return fire != null && !fire.IsReleased && fire.Owner != null
				&& GodotObject.IsInstanceValid(fire.Owner);
		}
		catch
		{
			return false;
		}
	}

	/// <summary>角色是否仍在场。绝不抛。</summary>
	private static bool IsUsable(TowerDefenseCharacter character)
	{
		try
		{
			return character != null && GodotObject.IsInstanceValid(character)
				&& character.IsInsideTree();
		}
		catch
		{
			return false;
		}
	}

	// ================================================================ 卡库

	/// <summary>
	/// 把**两张卡**都补进共享卡库 `GeneralZombie` 的 `Zombie` 分类 —— 这一步决定
	/// 「选卡界面 / 关卡编辑器里能不能选到它们」。
	///
	/// 依据（源码位置）：
	///   · `Almanac.cs:220` `zombiePacketBank = GetPacketBankData("GeneralZombie")` —— **同一实例**；
	///   · `Almanac.InitZombie()` 读 `zombiePacketBank.GetCategory("Zombie")`；
	///   · `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync` 也按 `packetBankData.category[分类]` 列卡。
	///   ⇒ 补一处 = 三处同时生效。
	/// 幂等且可恢复：每次扫描都检查一遍，缺了再补，补上才打日志。
	/// </summary>
	private void TryPatchCardBanks()
	{
		try
		{
			ResourceManager manager = ResourceManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;   // 资源管理器还没起来，下次扫描再说
			}
			System.Collections.Generic.Dictionary<string, TowerDefensePacketBankData> banks =
				manager.TOWERDEFENSE_PACKETBANKS;
			if (banks == null || banks.Count == 0)
			{
				return;   // 全量资源还在加载
			}
			string[] keys = _bankKeys ?? (_bankKeys = ResolveDerivedBankKeys());
			for (int i = 0; i < keys.Length; i++)
			{
				TowerDefensePacketBankData bank;
				if (!banks.TryGetValue(keys[i], out bank) || bank == null
					|| !GodotObject.IsInstanceValid(bank))
				{
					continue;
				}
				if (EnsureCategoryContains(bank, keys[i]))
				{
					_bankPatchCount++;
				}
			}
		}
		catch (Exception ex)
		{
			if (!_bankFaultReported)
			{
				_bankFaultReported = true;
				Warn("补共享卡库「" + ZombieCategory + "」分类失败（本条只报一次；"
					+ "不影响角色本体与战斗）：" + ex.Message);
			}
		}
	}

	private bool EnsureCategoryContains(TowerDefensePacketBankData bank, string bankKey)
	{
		Godot.Collections.Dictionary categories = bank.category;
		if (categories == null || !categories.ContainsKey(ZombieCategory))
		{
			return false;
		}
		Godot.Collections.Array list = categories[ZombieCategory].AsGodotArray();
		if (list == null)
		{
			return false;
		}
		bool added = false;
		for (int c = 0; c < 2; c++)
		{
			string want = (c == 0) ? QueenConfigName : DancerConfigName;
			bool present = false;
			for (int i = 0; i < list.Count; i++)
			{
				if (string.Equals(list[i].AsString(), want, StringComparison.Ordinal))
				{
					present = true;
					break;
				}
			}
			if (present)
			{
				continue;
			}
			list.Add(want);
			added = true;
			Info("已把「" + want + "」补进卡库「" + bankKey + "」的「" + ZombieCategory
				+ "」分类 ⇒ 选卡界面/关卡编辑器里可以选到它了。");
		}
		if (added)
		{
			categories[ZombieCategory] = list;   // 显式回写（Array 是引用语义，写回最稳）
		}
		return added;
	}

	/// <summary>
	/// 图鉴僵尸页**运行时去重**（本包的**两张卡各自**都要）。
	///
	/// 根因（`Prefab/GUI/DialogBox/Almanac/Almanac.cs`）：`InitZombie()` 有**两条独立来源**
	/// 且**都不去重** —— 共享卡库的 `Zombie` 分类（= 本插件补进去的那条）与
	/// `XWModContentCatalog.GetPackets(plants: false)`（引擎把 `Resources/Cards/` 注册成
	/// `Packet` 类别后自动收录）⇒ 每张卡在图鉴僵尸页出现**两条**。
	///
	/// 为什么不能「删掉其中一条」：
	///   · 卡库那条删不得 —— 选卡界面是 `packetBankData.category[分类]` **直读**，
	///     而 `BuildExpandedPacketBanks` 只从内置 json 构建、**不合并** Mod 注册 ⇒ 不补就选不到；
	///   · `Resources/Cards/` 那条也删不得 —— 它是 `TOWERDEFENSE_PACKETS` 里 config 的来源。
	///   ⇒ 只剩「在图鉴侧就地去掉重复项」这一条路。
	///
	/// 做法：反射取 `Almanac._zombieLogicalConfigs` 的**列表引用**，把 `saveKey` 等于本包两张卡
	///   之一的重复项（各自保留最靠前的一条）原地 `RemoveAt`，再用**公开**的
	///   `Almanac.QueueZombieVirtualRefresh()` 重建虚拟列表。卡库 / `_packetPaths` / 解锁状态一个字节不动。
	/// 幂等且安全：列表 ≤1 条直接返回；从后往前遍历保留最先命中的那条，顺序不变；绝不抛。
	/// </summary>
	private void TryDedupeAlmanacZombie(Almanac almanac)
	{
		try
		{
			if (almanac == null || !GodotObject.IsInstanceValid(almanac))
			{
				return;
			}
			if (almanac.ZombieLogicalEntryCount <= 1)
			{
				return;
			}
			List<TowerDefensePacketConfig> list = GetZombieLogicalConfigs(almanac);
			if (list == null || list.Count <= 1)
			{
				return;
			}

			int removed = 0;
			removed += DedupeSaveKey(list, QueenConfigName);
			removed += DedupeSaveKey(list, DancerConfigName);
			if (removed == 0)
			{
				return;
			}
			_almanacDedupeCount += removed;
			almanac.QueueZombieVirtualRefresh();   // public，不必反射
			Info("图鉴僵尸页去重：抹掉 " + removed + " 条重复项（累计 " + _almanacDedupeCount
				+ " 条）。选卡界面 / 关卡编辑器不受影响。");
		}
		catch (Exception ex)
		{
			if (!_dedupeFaultReported)
			{
				_dedupeFaultReported = true;
				Warn("图鉴僵尸页去重失败（本条只报一次；不影响角色本体、发射与选卡）：" + ex.Message);
			}
		}
	}

	/// <summary>把 `saveKey == key` 的重复项删到只剩 1 条（保留原本最靠前的那条）。</summary>
	private static int DedupeSaveKey(List<TowerDefensePacketConfig> list, string key)
	{
		int kept = 0;
		int removed = 0;
		for (int i = list.Count - 1; i >= 0; i--)
		{
			TowerDefensePacketConfig config = list[i];
			if (config == null || !GodotObject.IsInstanceValid(config))
			{
				continue;
			}
			if (!string.Equals(config.saveKey, key, StringComparison.Ordinal))
			{
				continue;
			}
			kept++;
			if (kept == 1)
			{
				continue;   // 从后往前，第一个命中的就是原本最靠前的那条 ⇒ 保留、顺序不变
			}
			list.RemoveAt(i);
			removed++;
		}
		return removed;
	}

	/// <summary>反射拿 `Almanac._zombieLogicalConfigs` 的列表引用；字段名对不上就返回 null。绝不抛。</summary>
	private static List<TowerDefensePacketConfig> GetZombieLogicalConfigs(Almanac almanac)
	{
		if (!_zombieLogicalFieldProbed)
		{
			_zombieLogicalFieldProbed = true;
			try
			{
				_zombieLogicalField = typeof(Almanac).GetField(
					"_zombieLogicalConfigs",
					BindingFlags.Instance | BindingFlags.NonPublic);
			}
			catch
			{
				_zombieLogicalField = null;
			}
		}
		if (_zombieLogicalField == null)
		{
			return null;
		}
		try
		{
			return _zombieLogicalField.GetValue(almanac) as List<TowerDefensePacketConfig>;
		}
		catch
		{
			return null;
		}
	}

	/// <summary>
	/// `GeneralZombie` 自身 + 所有通过 `Include` **间接包含**它的卡库
	/// （`ResourceManager.BuildExpandedPacketBank` 是递归合并语义）。
	/// json 读不到就回落 `FallbackDerivedBankKeys`。
	/// </summary>
	private string[] ResolveDerivedBankKeys()
	{
		try
		{
			Json json = GD.Load<Json>(PacketBankResourcePath);
			if (json == null || json.Data.VariantType != Variant.Type.Dictionary)
			{
				return FallbackDerivedBankKeys;
			}
			Godot.Collections.Dictionary raw = json.Data.AsGodotDictionary();
			List<string> result = new List<string>();
			foreach (Variant bankKey in raw.Keys)
			{
				string name = bankKey.AsString();
				if (string.Equals(name, RootZombieBankKey, StringComparison.OrdinalIgnoreCase)
					|| IncludesTransitively(raw, name, RootZombieBankKey,
						new HashSet<string>(StringComparer.OrdinalIgnoreCase)))
				{
					result.Add(name);
				}
			}
			if (result.Count == 0)
			{
				return FallbackDerivedBankKeys;
			}
			return result.ToArray();
		}
		catch (Exception ex)
		{
			Warn("读 PacketBankResource.json 失败，改用兜底卡库列表：" + ex.Message);
			return FallbackDerivedBankKeys;
		}
	}

	private static bool IncludesTransitively(
		Godot.Collections.Dictionary raw, string fromBank, string target, HashSet<string> visited)
	{
		if (!raw.ContainsKey(fromBank))
		{
			return false;
		}
		Godot.Collections.Dictionary bank = raw[fromBank].AsGodotDictionary();
		if (bank == null || !bank.ContainsKey("Include"))
		{
			return false;
		}
		Godot.Collections.Array includes = bank["Include"].AsGodotArray();
		if (includes == null)
		{
			return false;
		}
		for (int i = 0; i < includes.Count; i++)
		{
			string name = includes[i].AsString();
			if (string.IsNullOrEmpty(name) || !visited.Add(name))
			{
				continue;
			}
			if (string.Equals(name, target, StringComparison.OrdinalIgnoreCase)
				|| IncludesTransitively(raw, name, target, visited))
			{
				return true;
			}
		}
		return false;
	}

	// ================================================================ 日志

	private void Info(string message)
	{
		try
		{
			if (_context != null)
			{
				_context.Log(message);
				return;
			}
		}
		catch
		{
			// 落到 GD.Print
		}
		try
		{
			GD.Print(LogPrefix + message);
		}
		catch
		{
			// 日志本身绝不能成为异常源：入口三回调抛异常 = 无条件整包回滚。
		}
	}

	private void Warn(string message)
	{
		try
		{
			if (_context != null)
			{
				_context.Warn(message);
				return;
			}
		}
		catch
		{
			// 落到 GD.PushWarning
		}
		try
		{
			GD.PushWarning(LogPrefix + message);
		}
		catch
		{
			// 同上：日志不许抛。
		}
	}
}
