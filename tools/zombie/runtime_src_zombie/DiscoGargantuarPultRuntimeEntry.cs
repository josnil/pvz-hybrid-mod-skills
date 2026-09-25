using System;
using System.Collections.Generic;
using System.Reflection;
using Godot;
using PVZHE.ModEditor.ModSystem;

/// <summary>
/// 「暴走舞王伽刚特尔投石车僵尸」僵尸 Mod 的托管运行时入口。
///
/// 需求里有一条**纯数据做不到**：投石车僵尸投出来的僵尸要换成「暴走舞王伽刚特尔」
/// —— 证据在解包源码里，不是猜的：
///   * 本僵尸复用内置「小鬼投石车僵尸」的场景脚本
///     `Asset/Anime/Character/Zombie/Chapter5/Imppult/Scene/TowerDefenseZombieImppult.cs`，
///     它的 `ImpSpawn()`（该文件 127-174 行）**硬编码**了
///     `TowerDefenseManager.GetPacketConfig("ZombieImp")` 与
///     `... as TowerDefenseZombieImpBase`，任何配置都改不动这一行；
///   * 投掷单位也不是 ComponentSet 能配的：`CatapultComponentDefinition.projectileName`
///     只喂投射物视觉，真正被生成的是 `ImpSpawn()` 里那串字面量。
///   ⇒ 想让投出来的是别的单位，只能写托管代码做「狸猫换太子」。
///
/// 拦截点（全部公开 API，没有反射）：
///   1. 扫场景找到 `config.name == "ZombieDiscoGargantuarPult"` 的角色节点；
///   2. 取它的 `CatapultComponent`（InstanceId `"character.catapult"`），
///      订阅 `OnFireEvent`（`CatapultComponent.cs:139` 声明的公开事件，
///      在 `OnFireAnimeEvent()` 的 568 行触发 —— **早于** `ImpSpawn()`）；
///   3. `ImpSpawn()` 是 `async void`，会先 `await` 一个物理帧再真正造小鬼，
///      所以事件发生的**下一帧**小鬼才会 `AddChild` 进 `characterNode`；
///      于是我们订阅 `characterNode` 的 `child_entered_tree`（**同步**信号），
///      在小鬼刚进树、还没被渲染出去的那一瞬间把它 `QueueFree()` 掉；
///   4. 用同款参数造「暴走舞王伽刚特尔」并复刻抛物线：
///      位置/行号/z/初速全部**直接抄被丢掉的那只小鬼**（它是引擎刚算好的），
///      落点用与 `ImpSpawn()` 完全相同的「第 3~5 列随机」公式，
///      水平位移用 `Tween` 走 `GetFallTime()`，竖直方向交给基类重力
///      （`TowerDefenseGroundItemBase.PhysiceUpdate`，`ySpeed < 0` ⇒ 先升后落），
///      落地靠公开事件 `OnLand` 收到后 `Walk()`。
///
/// 本入口顺带干第二、第三件事（都与「卡牌出现在哪里」有关）：
///   ② 把卡补进**僵尸根卡库** `GeneralZombie` 的 `Zombie` 分类 ⇒ 选卡界面/关卡编辑器里能选到；
///   ③ 补 `Include` 闭包里的派生卡库（`TotalZombie`、`Total`）⇒ 「全部卡」调试开关下也在。
///      僵尸卡不进图鉴的植物页；图鉴僵尸页读的就是 `GeneralZombie` 本体（`Almanac.cs:220`），
///      所以我们补完根卡库它就自然出现，只需在「僵尸页已初始化」时兜底刷一次列表。
///
/// ⚠️ 铁律：Initialize / OnAllModsLoaded / Shutdown 一律**不许抛异常**。
/// 依据 ModLoader.cs:667-671：运行入口初始化失败 ⇒ **无条件整包回滚**（policy 救不了）。
/// </summary>
public sealed class DiscoGargantuarPultRuntimeEntry : IXWModRuntimeEntry
{
	private const string LogPrefix = "[DiscoGargantuarPult] ";

	/// <summary>识别本 Mod 僵尸：按场景 config 资源里的 name 字段（不按类名 —— 它复用内置小鬼投石车的脚本）。</summary>
	private const string CharacterConfigName = "ZombieDiscoGargantuarPult";

	/// <summary>CatapultComponent 在 ComponentSet 里的 InstanceId。</summary>
	private const string CatapultInstanceId = "character.catapult";

	/// <summary>要被**换上去**的单位（游戏内置，V0.28 已有：`Asset/Anime/Character/Zombie/Chapter6/DiscoGargantuar/`）。</summary>
	private const string ThrownPacketName = "ZombieDiscoGargantuar";

	/// <summary>要被**换下来**的单位 —— 内置小鬼投石车僵尸硬编码投的这个。</summary>
	private const string ImpPacketName = "ZombieImp";

	/// <summary>投石落点所在列区间（与 `TowerDefenseZombieImppult.ImpSpawn()` 第 168 行一致）。</summary>
	private const int LandingGridMin = 3;

	private const int LandingGridMax = 5;

	/// <summary>
	/// 一个「已开火、等小鬼出现」的待办。
	/// `ImpSpawn()` 是 async，事件与真正生成之间隔一个物理帧，所以要排队等。
	/// 队列是 FIFO：同一帧两只一起开火也能一一对上（对不上也只是「谁投的不重要」）。
	/// </summary>
	private sealed class FireTicket
	{
		public TowerDefenseZombie Shooter;
		public ulong DeadlineMsec;
	}

	/// <summary>一个「已抛出、等落地」的暴走舞王伽刚特尔。</summary>
	private sealed class ThrownUnit
	{
		public TowerDefenseZombie Node;
		public TowerDefenseGroundItemBase.LandEventHandler LandHandler;
		public ulong WalkDeadlineMsec;
		public bool Landed;
	}

	/// <summary>一个已订阅的投石组件（信号无 sender 参数，用闭包把组件绑进回调）。</summary>
	private sealed class CatapultHook
	{
		public CatapultComponent Component;
		public CatapultComponent.FireEventEventHandler Handler;
		public TowerDefenseZombie Shooter;
	}

	/// <summary>
	/// 僵尸卡库的「根」：`Almanac.cs:220` 图鉴僵尸页就是
	/// `TowerDefenseManager.GetPacketBankData("GeneralZombie")`（**不是拷贝**，是同一个实例），
	/// 所以补它 = 图鉴与选卡界面同时生效，天然同源。
	/// </summary>
	private const string RootZombieBankKey = "GeneralZombie";

	/// <summary>僵尸卡在卡库里的分类键（所有僵尸卡库都只有这一个分类）。</summary>
	private const string ZombieCategory = "Zombie";

	/// <summary>
	/// 读不到 json 时的兜底集合（按 V0.28 `Asset/Config/PacketBank/PacketBankResource.json`
	/// 的 `Include` 闭包离线算出的真实值：GeneralZombie ← TotalZombie ← Total）。
	/// ⚠️ 改这一个常量没用，改完要同步 `.cache/check_zombie_disco_pult.py` 里的核对断言。
	/// </summary>
	private static readonly string[] FallbackDerivedBankKeys = new string[3]
	{
		"GeneralZombie",
		"TotalZombie",
		"Total"
	};

	private const string PacketBankResourcePath = "res://Asset/Config/PacketBank/PacketBankResource.json";

	/// <summary>`Almanac._zombieInitialized`（**私有**）—— 判断图鉴僵尸页是否已经建过列表。</summary>
	private static FieldInfo _zombieInitializedField;
	private static bool _zombieInitializedFieldProbed;

	/// <summary>扫场景的间隔（帧）。等待中的小鬼/落地判定是**逐帧**推进的，不受这里影响。</summary>
	private const int ScanIntervalFrames = 10;

	/// <summary>
	/// 开火后等小鬼出现的超时。`ImpSpawn()` 只等一个物理帧，
	/// 700ms 足够宽；超时只是把票作废，避免残留票误伤别的鬼投掷兵投出的小鬼。
	/// </summary>
	private const ulong FireTicketTimeoutMsec = 700;

	/// <summary>落地后多久还没走起来就强推一次 `Walk()`（保险丝，正常走不到）。</summary>
	private const ulong WalkFuseExtraMsec = 3000;

	private XWModRuntimeContext _context;
	private SceneTree _tree;
	private Callable _tickCallable;
	private bool _hooked;
	private bool _connected;
	private int _frameCounter;

	// 每条出错路径**各用一个**「已报告」标志：共用会把关键日志静音掉。
	private bool _tickFaultReported;
	private bool _bankFaultReported;
	private bool _almanacFaultReported;
	private bool _hookFaultReported;
	private bool _replaceFaultReported;
	private bool _walkFaultReported;

	private readonly List<CatapultHook> _hooks = new List<CatapultHook>();
	private readonly List<FireTicket> _tickets = new List<FireTicket>();
	private readonly List<ThrownUnit> _thrown = new List<ThrownUnit>();

	/// <summary>已经挂上 `child_entered_tree` 的那个父节点（正常就是 characterNode）。</summary>
	private Node _watchTarget;
	private Callable _childEnteredCallable;
	private bool _childEnteredConnected;
	private int _watchRebinds;

	private string[] _bankKeys;
	private int _bankPatchCount;
	private int _almanacPatchCount;
	private int _replaceCount;
	private int _thrownCount;

	public void Initialize(XWModRuntimeContext context)
	{
		try
		{
			_context = context;
			_hooked = false;
			_connected = false;
			_frameCounter = 0;
			_tickFaultReported = false;
			_bankFaultReported = false;
			_almanacFaultReported = false;
			_hookFaultReported = false;
			_replaceFaultReported = false;
			_walkFaultReported = false;
			_bankKeys = null;
			_bankPatchCount = 0;
			_almanacPatchCount = 0;
			_replaceCount = 0;
			_thrownCount = 0;
			_watchTarget = null;
			_watchRebinds = 0;
			_hooks.Clear();
			_tickets.Clear();
			_thrown.Clear();

			string root = (context == null) ? "<null>" : context.PackageRoot;
			Info("运行入口已初始化；PackageRoot=" + root
				+ "；投掷单位 " + ImpPacketName + " → " + ThrownPacketName + "。");
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
				Warn("拿不到 SceneTree；投掷替换不会生效（僵尸本身仍可正常投放与攻击）。");
				return;
			}
			_tickCallable = Callable.From(new Action(OnProcessFrame));
			_tree.Connect("process_frame", _tickCallable);
			_connected = true;
			_hooked = true;
			Info("已挂载 process_frame；会把「" + CharacterConfigName + "」补进卡库「"
				+ RootZombieBankKey + "」的「" + ZombieCategory + "」分类，"
				+ "并在它投石时把 " + ImpPacketName + " 换成 " + ThrownPacketName + "。");
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
			try
			{
				UnhookAll();
			}
			catch (Exception ex)
			{
				Warn("Shutdown 取消失效：退订异常（已吞掉）：" + ex.Message);
			}
			try
			{
				UnwatchChildEntries();
			}
			catch (Exception ex)
			{
				Warn("Shutdown 取消失效：child_entered_tree 断开异常（已吞掉）：" + ex.Message);
			}
			_connected = false;
			_hooked = false;
			_tree = null;
			_hooks.Clear();
			_tickets.Clear();
			_thrown.Clear();
		}
	}

	// ---------------------------------------------------------------- 每帧

	private void OnProcessFrame()
	{
		try
		{
			_frameCounter++;

			// 这三件事必须逐帧推进（都带自己的超时/失效回收）
			AdvanceTickets();
			AdvanceThrown();

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
				Warn("逐帧推进异常（本条只报一次，仍会继续尝试）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 每 10 帧干三件事：
	///   · 把本卡补进僵尸根卡库（及派生库）→ 选卡界面 / 关卡编辑器里能选到它；
	///   · 图鉴节点 → 僵尸页兜底刷新（图鉴是独立场景，菜单里也会打开，所以不能只在战斗里扫）；
	///   · 战斗角色 → 挂投石组件。
	/// 第一件必须在场景树之外也跑（卡库是全局的），所以放在 `ScanScene` 里、递归之前。
	/// </summary>
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

		PruneInvalidHooks();
		ScanRecursive(root);
	}

	private void ScanRecursive(Node node)
	{
		if (node == null || !GodotObject.IsInstanceValid(node))
		{
			return;
		}

		if (node is Almanac almanac)
		{
			TryPatchAlmanac(almanac);
		}
		else if (node is TowerDefenseCharacter character)
		{
			TryHookCharacter(character);
		}

		Godot.Collections.Array<Node> children = node.GetChildren();
		for (int i = 0; i < children.Count; i++)
		{
			ScanRecursive(children[i]);
		}
	}

	// ---------------------------------------------------------------- 卡库

	/// <summary>
	/// 把本卡补进**僵尸根卡库** `GeneralZombie` 的 `Zombie` 分类 —— 这一步决定
	/// 「选卡界面 / 关卡编辑器里能不能选到它」。
	///
	/// 依据：`Almanac.cs:220` 图鉴僵尸页 `zombiePacketBank = GetPacketBankData("GeneralZombie")`
	/// （**同一个实例**，不像植物那样深拷贝）；`TowerDefensePacketBankData.GetCategory("Zombie")`
	/// 就是列卡用的那个数组。所以补根卡库 = 图鉴 + 选卡界面同时生效，天然同源。
	///
	/// 还补 `Include` 闭包里的派生库（实测 `TotalZombie`、`Total`）：
	///   只补 GeneralZombie 的话，`CommandManager.debugPacketOpenAll`（切到 `Total`）下又会看不到。
	///   派生集合按 `PacketBankResource.json` 的 `Include` 闭包**在运行期算**，不写死。
	///
	/// 幂等 + 可恢复：卡库是全局单例，但别的 Mod 仍可能 `provides.PacketBank` 覆盖同名卡库，
	/// 所以每次扫描都检查一遍（十几条字符串比较，开销可忽略），缺了再补、补上才打日志。
	/// </summary>
	private void TryPatchCardBanks()
	{
		try
		{
			ResourceManager manager = ResourceManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;      // 资源管理器还没起来，下次扫描再说
			}
			System.Collections.Generic.Dictionary<string, TowerDefensePacketBankData> banks =
				manager.TOWERDEFENSE_PACKETBANKS;
			if (banks == null || banks.Count == 0)
			{
				return;      // 全量资源还在加载
			}

			string[] keys = _bankKeys ?? (_bankKeys = ResolveDerivedBankKeys());
			for (int i = 0; i < keys.Length; i++)
			{
				TowerDefensePacketBankData bank;
				if (!banks.TryGetValue(keys[i], out bank) || bank == null || !GodotObject.IsInstanceValid(bank))
				{
					continue;
				}
				if (EnsureZombieCategoryContains(bank, keys[i]))
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
				Warn("补僵尸卡库「" + ZombieCategory + "」分类失败（本条只报一次；不影响投掷替换）："
					+ ex.Message);
			}
		}
	}

	/// <summary>往一个卡库的 `Zombie` 分类里追加本卡。已在里面返回 false（幂等），真的加了返回 true。</summary>
	private bool EnsureZombieCategoryContains(TowerDefensePacketBankData bank, string bankKey)
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
		for (int i = 0; i < list.Count; i++)
		{
			if (string.Equals(list[i].AsString(), CharacterConfigName, StringComparison.Ordinal))
			{
				return false;        // 已经在里面了
			}
		}
		list.Add(CharacterConfigName);
		categories[ZombieCategory] = list;      // 显式回写（Array 是引用语义，写回最稳）
		Info("已把「" + CharacterConfigName + "」补进卡库「" + bankKey + "」的「" + ZombieCategory
			+ "」分类 ⇒ 选卡界面 / 关卡编辑器里可以选到它了。");
		return true;
	}

	/// <summary>
	/// 算「要补哪些卡库」= `GeneralZombie` 自身 + 所有通过 `Include` **间接包含**它的卡库
	/// （`Include` 是递归合并语义，见 `ResourceManager.BuildExpandedPacketBank`）。
	/// json 读不到就回落到 `FallbackDerivedBankKeys`（离线算好的真实值）。
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
					|| IncludesTransitively(raw, name, RootZombieBankKey, new HashSet<string>(StringComparer.OrdinalIgnoreCase)))
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

	/// <summary>
	/// `fromBank` 的 `Include` 闭包里有没有 `target`（带 visited 防环 —— 游戏自己也防环，
	/// `ResourceManager.BuildExpandedPacketBank` 会抛 `Include cycle detected`）。
	/// </summary>
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

	/// <summary>
	/// 兜底：图鉴僵尸页的卡库**就是** `GeneralZombie` 本体（同一实例），
	/// 所以 `TryPatchCardBanks()` 已经把它补好了 —— 这里只在
	/// 「僵尸页已经建过列表」（说明列表是按补之前的卡库建的）时刷一次。
	///
	/// ⚠️ 千万**别**在没建过列表时调 `InitZombie()`：图鉴是刻意懒初始化的
	/// （`Almanac.cs:450` `if (!_zombieInitialized) InitZombie();`），提前调会在
	/// 打开图鉴的瞬间把预览节点和角色资源全加载出来，白白多一次卡顿。
	/// </summary>
	private void TryPatchAlmanac(Almanac almanac)
	{
		try
		{
			TowerDefensePacketBankData bank = almanac.zombiePacketBank;
			if (bank == null || !GodotObject.IsInstanceValid(bank))
			{
				return;
			}
			// 补的其实是同一个全局实例；这里再走一遍 check-then-add，纯幂等保险
			bool added = EnsureZombieCategoryContains(bank, "<almanac>");
			if (!added)
			{
				return;
			}
			_almanacPatchCount++;
			if (IsZombiePageInitialized(almanac))
			{
				almanac.InitZombie();
				Info("图鉴僵尸页已打开过 ⇒ 主动刷新一次列表（第 " + _almanacPatchCount + " 次）。");
			}
		}
		catch (Exception ex)
		{
			if (!_almanacFaultReported)
			{
				_almanacFaultReported = true;
				Warn("补图鉴僵尸页失败（本条只报一次；不影响投掷替换）：" + ex.Message);
			}
		}
	}

	/// <summary>读 `Almanac._zombieInitialized`（私有，反射一次后缓存 FieldInfo）。拿不到就返回 false（= 不刷新，安全降级）。</summary>
	private static bool IsZombiePageInitialized(Almanac almanac)
	{
		if (!_zombieInitializedFieldProbed)
		{
			_zombieInitializedFieldProbed = true;
			_zombieInitializedField = typeof(Almanac).GetField(
				"_zombieInitialized", BindingFlags.Instance | BindingFlags.NonPublic);
		}
		if (_zombieInitializedField == null)
		{
			return false;
		}
		return _zombieInitializedField.GetValue(almanac) is bool initialized && initialized;
	}

	// ---------------------------------------------------------------- 挂钩

	private void TryHookCharacter(TowerDefenseCharacter character)
	{
		try
		{
			TowerDefenseManager manager = TowerDefenseManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;      // 不在战斗里
			}
			TowerDefenseCharacterConfig config = character.config;
			if (config == null || !GodotObject.IsInstanceValid(config))
			{
				return;
			}
			if (!string.Equals(config.name, CharacterConfigName, StringComparison.Ordinal))
			{
				return;
			}
			if (!(character is TowerDefenseZombie shooter))
			{
				return;
			}
			// 小鬼会被 AddChild 到 shooter 的父节点（= characterNode）上，
			// 所以在这里就把父节点的 child_entered_tree 挂好。
			EnsureWatchChildEntries(shooter);

			ComponentManager components = character.componentManager;
			if (components == null)
			{
				return;
			}
			CatapultComponent catapult = components.GetRuntime<CatapultComponent>(CatapultInstanceId);
			if (!IsUsable(catapult))
			{
				return;
			}
			AddHook(catapult, shooter);
		}
		catch (Exception ex)
		{
			if (!_hookFaultReported)
			{
				_hookFaultReported = true;
				Warn("读取投石组件失败（本条只报一次；不影响僵尸正常投放）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 组件是否仍然可用。
	/// ⚠️ CharacterComponentRuntime **不是 GodotObject**（是纯 C# 抽象类），
	/// 所以既没有 GodotObject.IsInstanceValid 也没有 GetInstanceId；
	/// 只能看 IsReleased + Owner（Owner 是 TowerDefenseCharacter，是 Node）。
	/// </summary>
	private static bool IsUsable(CatapultComponent catapult)
	{
		try
		{
			return catapult != null && !catapult.IsReleased && catapult.Owner != null
				&& GodotObject.IsInstanceValid(catapult.Owner);
		}
		catch
		{
			return false;
		}
	}

	private void AddHook(CatapultComponent catapult, TowerDefenseZombie shooter)
	{
		// 引用相等即「同一个组件」：CharacterComponentRuntime 不是 GodotObject，没有 GetInstanceId。
		for (int i = 0; i < _hooks.Count; i++)
		{
			if (ReferenceEquals(_hooks[i].Component, catapult))
			{
				return;
			}
		}

		CatapultHook hook = new CatapultHook();
		hook.Component = catapult;
		hook.Shooter = shooter;
		hook.Handler = delegate { OnCatapultFired(hook); };
		try
		{
			catapult.OnFireEvent += hook.Handler;
		}
		catch (Exception ex)
		{
			Warn("订阅 OnFireEvent 失败（已跳过该组件）：" + ex.Message);
			return;
		}
		_hooks.Add(hook);
		Info("已挂上第 " + _hooks.Count + " 个「" + CharacterConfigName + "」投石组件。");
	}

	private void PruneInvalidHooks()
	{
		for (int i = _hooks.Count - 1; i >= 0; i--)
		{
			if (!IsUsable(_hooks[i].Component))
			{
				_hooks.RemoveAt(i);
			}
		}
	}

	private void UnhookAll()
	{
		for (int i = 0; i < _hooks.Count; i++)
		{
			CatapultHook hook = _hooks[i];
			if (!IsUsable(hook.Component))
			{
				continue;
			}
			try
			{
				hook.Component.OnFireEvent -= hook.Handler;
			}
			catch (Exception ex)
			{
				Warn("退订 OnFireEvent 失败（已忽略）：" + ex.Message);
			}
		}
	}

	// ---------------------------------------------------------------- 投掷替换

	/// <summary>
	/// `CatapultComponent.OnFireAnimeEvent()` 的 568 行触发本事件，
	/// **紧跟着**同一帧 `TowerDefenseZombieImppult.AnimeEvent("fire")` 才调用 `ImpSpawn()`。
	/// 所以此刻小鬼还不存在 —— 只能领一张票，等 `child_entered_tree`。
	/// </summary>
	private void OnCatapultFired(CatapultHook hook)
	{
		try
		{
			FireTicket ticket = new FireTicket();
			ticket.Shooter = hook.Shooter;
			ticket.DeadlineMsec = Time.GetTicksMsec() + FireTicketTimeoutMsec;
			_tickets.Add(ticket);
		}
		catch (Exception ex)
		{
			if (!_replaceFaultReported)
			{
				_replaceFaultReported = true;
				Warn("记录开火事件失败（本条只报一次）：" + ex.Message);
			}
		}
	}

	private void EnsureWatchChildEntries(TowerDefenseZombie shooter)
	{
		Node parent = shooter.GetParent();
		if (parent == null || !GodotObject.IsInstanceValid(parent))
		{
			return;
		}
		if (ReferenceEquals(_watchTarget, parent) && _childEnteredConnected)
		{
			return;
		}
		UnwatchChildEntries();
		_childEnteredCallable = Callable.From<Node>(new Action<Node>(OnChildEnteredTree));
		try
		{
			parent.Connect("child_entered_tree", _childEnteredCallable);
			_watchTarget = parent;
			_childEnteredConnected = true;
			_watchRebinds++;
			Info("已监听「" + parent.Name + "」的 child_entered_tree（第 " + _watchRebinds + " 次绑定）。");
		}
		catch (Exception ex)
		{
			_watchTarget = null;
			_childEnteredConnected = false;
			Warn("监听 child_entered_tree 失败（投掷替换不会生效）：" + ex.Message);
		}
	}

	private void UnwatchChildEntries()
	{
		if (_watchTarget != null && GodotObject.IsInstanceValid(_watchTarget))
		{
			try
			{
				_watchTarget.Disconnect("child_entered_tree", _childEnteredCallable);
			}
			catch (Exception ex)
			{
				Warn("断开 child_entered_tree 失败（已忽略）：" + ex.Message);
			}
		}
		_watchTarget = null;
		_childEnteredConnected = false;
	}

	/// <summary>
	/// 小鬼刚 `AddChild` 进 `characterNode` 的那一刻（**同步**回调，早于渲染）。
	/// 这里把它换掉，玩家看不到任何一帧小鬼。
	/// </summary>
	private void OnChildEnteredTree(Node child)
	{
		try
		{
			DropExpiredTickets();
			if (_tickets.Count == 0 || child == null || !GodotObject.IsInstanceValid(child))
			{
				return;
			}
			if (!(child is TowerDefenseZombie imp))
			{
				return;
			}
			TowerDefenseCharacterConfig config = imp.config;
			if (config == null || !GodotObject.IsInstanceValid(config)
				|| !string.Equals(config.name, ImpPacketName, StringComparison.Ordinal))
			{
				return;
			}

			FireTicket ticket = _tickets[0];
			_tickets.RemoveAt(0);
			TowerDefenseZombie shooter = (ticket.Shooter != null && GodotObject.IsInstanceValid(ticket.Shooter))
				? ticket.Shooter : null;

			ReplaceImpWithThrownZombie(imp, shooter);
		}
		catch (Exception ex)
		{
			if (!_replaceFaultReported)
			{
				_replaceFaultReported = true;
				Warn("替换投掷单位异常（本条只报一次，仍会继续尝试）：" + ex.Message);
			}
		}
	}

	private void ReplaceImpWithThrownZombie(TowerDefenseZombie imp, TowerDefenseZombie shooter)
	{
		TowerDefensePacketConfig packet = TowerDefenseManager.GetPacketConfig(ThrownPacketName);
		if (packet == null || !GodotObject.IsInstanceValid(packet))
		{
			Warn("找不到包「" + ThrownPacketName + "」，本次保留原小鬼。");
			return;
		}
		Node parent = TowerDefenseGroundItemBase.characterNode;
		if (parent == null || !GodotObject.IsInstanceValid(parent))
		{
			parent = imp.GetParent();
		}
		if (parent == null || !GodotObject.IsInstanceValid(parent))
		{
			Warn("找不到 characterNode，本次保留原小鬼。");
			return;
		}

		// —— 先把小鬼身上的「引擎刚算好的投掷参数」抄下来，再把它丢掉 ——
		Vector2 pos = imp.GetLogicalGlobalPosition();
		Vector2I gridPos = imp.gridPos;
		double height = imp.z - imp.groundHeight;      // 相对地面的高度（Create 的 height 形参语义）
		double ySpeed = imp.ySpeed;                    // 小鬼投石车给的是 -240（先升后落）

		// 命中判定/尺度：贴着创建者的缩放走（与 ImpSpawn 的做法一致）
		double hitpointScale = 1.0;
		Vector2 scale = Vector2.One;
		bool hypnoses = false;
		if (shooter != null)
		{
			if (GodotObject.IsInstanceValid(shooter.instance))
			{
				hitpointScale = shooter.instance.hitpointScale;
				hypnoses = shooter.instance.hypnoses;
			}
			if (shooter.transformPoint != null && GodotObject.IsInstanceValid(shooter.transformPoint))
			{
				scale = shooter.transformPoint.Scale;
			}
		}
		bool invisible = (shooter != null) && shooter.invisible;

		// 立即作废小鬼：QueueFree 在帧末生效，它这一帧都不会被画出来
		imp.QueueFree();

		TowerDefenseCharacter created = packet.Create(pos, gridPos, height);
		if (created == null || !GodotObject.IsInstanceValid(created) || !(created is TowerDefenseZombie thrown))
		{
			Warn("生成「" + ThrownPacketName + "」失败，本次投掷为空。");
			return;
		}

		thrown.ySpeed = ySpeed;
		float landX = ResolveLandingX();
		float fallTime = (float)Math.Max(0.001, thrown.GetFallTime());

		ThrownUnit unit = new ThrownUnit();
		unit.Node = thrown;
		unit.WalkDeadlineMsec = Time.GetTicksMsec() + (ulong)(fallTime * 1000.0) + WalkFuseExtraMsec;
		unit.LandHandler = delegate { unit.Landed = true; };
		thrown.OnLand += unit.LandHandler;
		_thrown.Add(unit);

		parent.AddChild(thrown, false, Node.InternalMode.Disabled);

		try
		{
			thrown.SetHitpointAndScale(hitpointScale, scale);
			thrown.SetDeferred("invisible", invisible);
			if (hypnoses)
			{
				thrown.Hypnoses();
			}
		}
		catch (Exception ex)
		{
			Warn("套用缩放/隐形/催眠失败（已忽略，不影响投掷本身）：" + ex.Message);
		}

		// 抛物线：水平位移交给 Tween（时长 = 引擎自己算的落地时间），竖直方向由基类重力接管
		try
		{
			Vector2 from = thrown.GetLogicalGlobalPosition();
			Tween tween = thrown.CreateTween();
			tween.SetEase(Tween.EaseType.Out);
			tween.SetTrans(Tween.TransitionType.Quad);
			tween.TweenMethod(Callable.From<Vector2>(thrown.SetLogicalGlobalPosition),
				from, new Vector2(landX, from.Y), fallTime);
		}
		catch (Exception ex)
		{
			Warn("创建抛物线 Tween 失败（僵尸会原地落下）：" + ex.Message);
		}

		_replaceCount++;
		_thrownCount++;
		Info("第 " + _replaceCount + " 次投掷替换：" + ImpPacketName + " → " + ThrownPacketName
			+ "，落点 x=" + landX.ToString("0.#") + "，飞行 " + fallTime.ToString("0.00") + "s。");
	}

	/// <summary>
	/// 落点列：与小鬼投石车僵尸 `ImpSpawn()` 第 168 行**完全相同的公式**
	/// （第 3~5 列之间取随机 x）。`GetMapCellPos` 返回的是逻辑全局坐标。
	/// </summary>
	private static float ResolveLandingX()
	{
		try
		{
			TowerDefenseManager manager = TowerDefenseManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return 0f;
			}
			Vector2 a = manager.GetMapCellPos(new Vector2I(LandingGridMin, 0));
			Vector2 b = manager.GetMapCellPos(new Vector2I(LandingGridMax, 0));
			double lo = Math.Min(a.X, b.X);
			double hi = Math.Max(a.X, b.X);
			return (float)GD.RandRange(lo, hi);
		}
		catch
		{
			return 0f;
		}
	}

	/// <summary>通知图鉴/统计之外，把飞行中的暴走舞王伽刚特尔推进到「落地后开始走」。</summary>
	private void AdvanceThrown()
	{
		if (_thrown.Count == 0)
		{
			return;
		}
		ulong now = Time.GetTicksMsec();
		for (int i = _thrown.Count - 1; i >= 0; i--)
		{
			ThrownUnit unit = _thrown[i];
			TowerDefenseZombie node = unit.Node;
			if (node == null || !GodotObject.IsInstanceValid(node))
			{
				_thrown.RemoveAt(i);
				continue;
			}
			bool fuse = now >= unit.WalkDeadlineMsec;
			if (!unit.Landed && !fuse)
			{
				continue;
			}
			_thrown.RemoveAt(i);
			try
			{
				node.OnLand -= unit.LandHandler;
			}
			catch
			{
				// 事件退订失败无所谓：node 会随生命周期一起释放
			}
			if (!unit.Landed)
			{
				Warn("投掷单位落地事件超时（已用保险丝强推行走）。");
			}
			try
			{
				node.CallDeferred("Walk");
			}
			catch (Exception ex)
			{
				if (!_walkFaultReported)
				{
					_walkFaultReported = true;
					Warn("让投掷单位开始行走失败（本条只报一次）：" + ex.Message);
				}
			}
		}
	}

	private void AdvanceTickets()
	{
		DropExpiredTickets();
	}

	private void DropExpiredTickets()
	{
		if (_tickets.Count == 0)
		{
			return;
		}
		ulong now = Time.GetTicksMsec();
		for (int i = _tickets.Count - 1; i >= 0; i--)
		{
			if (now >= _tickets[i].DeadlineMsec)
			{
				_tickets.RemoveAt(i);
			}
		}
	}

	// ---------------------------------------------------------------- 日志

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
