using System;
using System.Collections.Generic;
using System.Reflection;
using Godot;
using PVZHE.ModEditor.ModSystem;

/// <summary>
/// 「超级机枪射手」植物 Mod 的托管运行时入口。
///
/// ★★ 2026-09-24 齐射改版后的分工（用户需求：像狐尾草一样把一轮子弹一次性齐射出去）：
///
///   常规攻击 = **纯数据齐射，插件完全不参与**：
///     · 数据侧 7 条 <c>FireComponentFireProjectileConfig</c>（同 speed/dir=0/伤害，仅
///       <c>firePosId = 0..6</c> 不同 → 7 个 Marker2D，横向间距 32px，豌豆 28×28 ⇒ 互不重叠）；
///     · 动画 f62 的 1 个 <c>fire</c> 事件 → <c>AnimeEvent</c>（fireEventName 默认 "fire"）
///       → <c>FireConfiguredVolley()</c>（fireNumAtOnce=false ⇒ 恰好 1 次）
///       → <c>Fire()</c>（FireComponent.cs:3434）一次遍历全部 7 条 = 7 颗同一帧出膛；
///     · <c>lockProjectileGridY = true</c>（FireComponent.cs:2743 → BulletField.cs:1473/5598）
///       把每颗豌豆的行锁死在种植行 ⇒ 横向散布不改变「前方一行」的命中行为。
///     · ⚠️ 因此本插件**不得**再改写 <c>fireEventName</c> 屏蔽发射链
///       （2026-09-21 的 "modfire" 屏蔽已撤销——那时常规攻击由插件逐颗发，
///       屏蔽 vanilla 是为了防「一次攻击打两遍」；现在常规攻击恰恰要靠它）。
///
///   大招（本插件唯一剩下的玩法职责）：每次攻击 10% 概率 → 5 秒内向前方 ±15°
///   散射**恰好 300 颗**豌豆。逐颗调 <c>CreateProjectileByData()</c>
///   （FireComponent.cs:3049，狐尾草 TowerDefensePlantHWC.FireVolley 同款 API）。
///   ⚠️ **不能再调 <c>Fire()</c>**：它现在一次会打出全部 7 条齐射配置（= 7 颗）。
///
/// ─────────────────────────────────────────────────────────────────────────
/// 一、为什么大招必须写 C#（证据都在解包源码里，不是猜的）
///   · <c>FireComponentFireProjectileConfig</c> 只有 8 个字段（checkProjectileId / firePosId /
///     speed / dir / offsetLine / fireNumSkip / fireEventNeed / projectileFlip），
///     **没有任何概率或时窗字段** ⇒ 「10% 概率」「5 秒」在数据里无处安放；
///   · <c>FireComponent.AttackProcessing</c>（FireComponent.cs:3286-3307）只按 <c>fireInterval</c>
///     调 <c>sprite.timeScale</c>，最高约 4 倍速 ⇒ 5 秒最多 ~93 颗，**够不到 300 颗**；
///   · <c>EmitFireVolley()</c> 的唯一随机源是 <c>OnFireVolley(ulong randomSeed)</c>，种子是**确定性**的
///     （<c>NetworkDeterministicSeed.ForCharacterEvent</c>，为联机同步刻意禁掉真随机）
///     ⇒ 「10% 概率」也不能靠数据里的随机字段。
///
/// 二、大招为什么走 CreateProjectileByData 而不是 Fire()
///   · <c>Fire()</c>（3434 行）遍历 <c>_fireProjectileList</c> **一次全打出** ——
///     齐射改版后那里有 7 条配置，调一次 = 7 颗重叠着飞向同一方向；
///   · <c>CreateProjectileByData(posId, velocity, data, collisionFlags, camp, offset, overrides)</c>
///     （3049 行 → CreateProjectile 2684 行）与 Fire() 的弹体创建**同一段代码**：
///       - collisionFlags 传 -1 ⇒ <c>parent.instance.collisionFlags</c>，与
///         <c>Fire()</c> 的 useParentCollision 默认路径一致（FireComponentCheckConfig.cs:57-64
///         GetCollisionFlags() 对 useParentCollision=true 恒返 -1）；
///       - 速度/方向 = velocity（与配置里 speed×FromAngle(dir) 同构，本插件读齐射配置的
///         speed 作为弹速，单一真源）；
///       - 弹的行：lockProjectileGridY=true ⇒ overrides.gridYOverride = 种植行
///         （FireComponent.cs:2743）⇒ 大招散射弹同样锁行。
///   · overrides 与 <c>Fire()</c>（3490-3494 行）同口径：
///       - <c>spriteRotationOverride = DegToRad(散射角)</c>（弹体贴图随方向旋转）；
///       - <c>flipXOverride = 本体 Scale.X &lt; 0</c>（= GetProjectileBodyScaleX :713-721
///         在 projectileFlip=false 时的语义）。
///
/// 三、怎么知道「一次攻击开始了」—— 用 <c>OnFireReady</c>，不用 <c>OnFireVolley</c>
///   · <c>OnFireVolley</c> 是**每条配置**打出一颗就发一次信号（3510-3521 行）⇒
///     齐射一次会连发 7 次信号，做概率判定要再去重；
///   · <c>OnFireReady</c>（FireComponent.cs:667，委托 <c>FireReadyEventHandler()</c> 在 255 行）
///     在 <c>AttackEntered()</c>（3258 行）里**恰好调一次** ⇒ 天然就是「一次攻击开始」的精确信号。
///   · 攻击节奏仍由游戏自己掌握：IdleEntered → Refresh() 把 timer 置为
///     fireInterval ± offset（2377-2382 行），归零且有目标 ⇒ 进 Attack ⇒
///     OnFireReady ⇒ 本插件掷 10% 骰。**不需要自己维护 1.5s 计时器**，
///     天然与游戏节奏/暂停/变速一致。大招期间后续攻击照常进 Attack
///     （vanilla 齐射照常打，视觉上是「大招里还夹着正常射击」，与原作描述一致），
///     但不再重复掷骰、不再叠加新的大招。
///
/// 四、自制外观的「动画静止」修复（保留，见 TryPatchSkinRender）
///   自制 <c>AdobeAnimateData</c> 没有烘焙 GPU 位姿纹理 ⇒ GPU 位姿提交路径静默失败。
///   修法 = 引擎预览同款：<c>forceLocalRender = true</c> + <c>forceCpuPoseRender = true</c>
///   （PacketPickControl.cs:401-402 就是这两条一起设的），每 10 帧全树扫描补设。
///
/// ⚠️ 铁律：Initialize / OnAllModsLoaded / Shutdown 一律**不许抛异常**。
/// 依据 ModLoader.cs：<c>TryInitializeRuntimeEntry</c> 失败 → 667-671 行**无条件整包回滚**
/// （不受 runtimeAssemblyPolicy 保护）；<c>NotifyAllModsLoaded</c> 失败 → State = Failed。
///
/// 本入口顺带干另外两件事（都与「卡牌出现在哪里」有关）：
///   ④ **图鉴去重**：游戏自己（<c>XWModContentCatalog.WithPlants</c>，
///      只被 <c>Almanac.cs:219</c> 调用）会把所有 Mod 植物单列成 <c>ModPlants</c> 一类，
///      于是本卡在图鉴里**同时**出现在「ModPlants（只有它自己）」和「Gold」两个分类里
///      ⇒ 用户看到的「重复出现」。
///      ★ 2026-09-25 口径：把本卡从 <c>ModPlants</c> 里摘掉；摘空了就把整个键删掉
///      （「只包含该角色的独立图鉴」随之消失），**只保留金卡分类那一张**。
///   ⑤ **进共享卡库 <c>GeneralPlant</c>（及派生库）的「金卡」分类** ⇒ 选卡界面里能选到它。
///      这一步是根上的修法：图鉴本来就是从 <c>GeneralPlant</c> 拷贝出来的，所以补完共享卡库，
///      **图鉴与卡牌库天然同源一致**；④ 里「确保金卡分类含本卡」的那半只是「图鉴已经开着、
///      来不及重开」的兜底。
///   详见 <c>TryPatchCardBanks</c> 与 <c>TryPatchAlmanac</c>。
/// </summary>
public sealed class SuperGatlingPeaRuntimeEntry : IXWModRuntimeEntry
{
	private const string LogPrefix = "[SuperGatlingPea] ";

	/// <summary>识别本 Mod 植物：用场景 config 资源里的 name 字段（内置机枪射手也叫 GatlingPea，不能按类名认）。</summary>
	private const string CharacterConfigName = "SuperGatlingPea";

	/// <summary>ComponentSet 里 FireComponent 的 InstanceId。</summary>
	private const string FireInstanceId = "character.fire";

	/// <summary>
	/// 卡片分类里的「金卡」键名（本卡 `packet.type = 1 = PACKET_TYPE.GOLD`）。
	/// 图鉴的植物分类字典就是 `GeneralPlant` 卡库的 `Category`，实测（V0.28）
	/// `Asset/Config/PacketBank/PacketBankResource.json` → `GeneralPlant.Category` 只有 6 个键：
	/// **White(178) / Gold(19) / Diamond(16) / Colour(6) / Star(27) / Original(20)**。
	/// （Item / GraveStone / Zombie 在别的卡库里，不在这里；改这个常量前先核对上面的 json。）
	/// </summary>
	private const string GoldCategory = "Gold";

	/// <summary>
	/// 「只有 Mod 植物」的那个独立分类的键名（<c>XWModContentCatalog.PlantCategory</c>）。
	/// <c>XWModContentCatalog.WithPlants()</c>（addons/ModEditor/ModSystem/XWModContentCatalog.cs:107-123）
	/// 会把所有 Mod 植物**单列**成 <c>category["ModPlants"]</c>，且图鉴
	/// （<c>Almanac.cs:219</c> 是**全库唯一**调用点）就是按这份拷贝的分类翻页的
	/// （<c>Almanac.cs:311-328</c>）⇒ 本卡会同时出现在 <c>ModPlants</c> 与 <c>Gold</c>
	/// 两个分类里 = 用户在图鉴里看到的「重复出现」。
	///
	/// ★ 2026-09-25 用户口径：**删掉「只包含该角色」的独立图鉴，把它保留在已有的金卡分类里**。
	///   所以插件必须把本卡从 <c>ModPlants</c> 里摘出去；摘完若该分类**空了**就整个删键
	///   （「只含本角色」的独立分类随之消失），但**绝不能**因为别的 Mod 植物也在里面就整类删掉。
	/// </summary>
	private const string ModPlantCategory = "ModPlants";

	/// <summary>
	/// 卡库的「根」：**所有植物卡牌库**都由它派生。
	/// 依据：`TowerDefenseLevelPacketBankConfig.packetBankType` 默认就是 `"GeneralPlant"`
	/// （关卡可用 `TowerDefenseLevelConfig.packetBank` / `PacketBankName` 覆盖），
	/// 而选卡界面 `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync` 就是按
	/// `bankData.category[分类]` 列出可选卡的。
	/// 所以「把卡放进 GeneralPlant.Gold」= 既进图鉴、又进选卡界面，且两边同源 ⇒ 数据天然一致。
	/// </summary>
	private const string RootPlantBankKey = "GeneralPlant";

	/// <summary>
	/// `GeneralPlant` 卡库的 JSON 资源（`res://` 内置路径，任何构建都有）。
	/// 用它算出「哪些卡库通过 `Include` 间接包含了 GeneralPlant」——
	/// `ResourceManager.BuildExpandedPacketBank` 会沿着 `Include` 递归合并分类，
	/// 所以那些卡库（实测只有 `Total`）运行期是 GeneralPlant 的**超集**，
	/// 本卡也必须一起补进去，否则「打开全部卡」的调试开关下又会看不到。
	/// </summary>
	private const string PacketBankResourcePath = "res://Asset/Config/PacketBank/PacketBankResource.json";

	/// <summary>
	/// 读不到上面的 json 时的兜底集合（离线按 V0.28 的资源算出来的真实值）。
	/// ⚠️ 改这一个常量没用，改完要同步 `.cache/check_plant_super_gatling.py` 里那条核对断言。
	/// </summary>
	private static readonly string[] FallbackDerivedBankKeys = new string[2] { "GeneralPlant", "Total" };

	/// <summary>
	/// `Almanac._plantInitialized`（**私有**）—— 用来判断图鉴的植物页是否已经建过列表。
	/// 只有在「已经建过」时才需要主动刷新；没建过就别碰，让它按游戏原本的**懒初始化**
	/// （`PlantButtonPressed` → `if (!_plantInitialized) InitPlant()`）自己读到我们补好的分类。
	/// 反射拿不到就退化成「不刷新」（最坏情况：用户翻一次分类就能看到），绝不影响其它功能。
	/// </summary>
	private static FieldInfo _plantInitializedField;
	private static bool _plantInitializedFieldProbed;

	// ---------------------------------------------------------------- 发射/大招参数
	//
	// ★ 2026-09-24 齐射改版：常规攻击（7 颗齐射）已全部下沉到**数据侧**
	//   （ComponentSet 的 7 条配置 + 动画 fire 事件），插件不再持有
	//   「每轮颗数 / 颗间距」这类连发链参数（那是僵尸包的职责）。
	//   插件只剩「大招」一族参数，全部转发共用核心 runtime_shared/GatlingVolleyCore.cs。

	/// <summary>每次攻击触发大招的概率（10%）。</summary>
	private const double UltimateChance = GatlingVolleyParams.UltimateChance;

	/// <summary>大招持续时间（秒）。</summary>
	private const double UltimateSeconds = GatlingVolleyParams.UltimateSeconds;

	/// <summary>大招目标总颗数（恰好 300）。</summary>
	private const int UltimatePeas = GatlingVolleyParams.UltimatePeas;

	/// <summary>大招散射半角（±15°）。每颗**独立**取 U(-15, +15)。</summary>
	private const double ScatterHalfAngleDeg = GatlingVolleyParams.ScatterHalfAngleDeg;

	/// <summary>
	/// 单帧最多打几颗：防掉帧时一次性雪崩式创建几百个子弹对象。
	/// 大招 300 颗 / 5 秒 = 60 颗/秒，60fps 下 1 颗/帧，30fps 下 2 颗/帧，8 已经很宽裕。
	/// </summary>
	private const int MaxPeasPerFrame = GatlingVolleyParams.MaxPeasPerFrame;

	/// <summary>
	/// 停顿判定阈值（毫秒）。超过它说明中间发生了暂停/长卡顿（`process_frame` 停发），
	/// 这时把大招时间轴的起点整体后移、欠账作废，避免「继续」瞬间补射出几百颗。
	/// </summary>
	private const ulong StallGapMsec = GatlingVolleyParams.StallThresholdMsec;

	/// <summary>
	/// 大招弹速的**兜底值**（只在齐射配置读不到时用）。正常运行时每颗都实时读
	/// `fireProjectileList[0].speed`（= 数据侧 500，与常规齐射同源 ⇒ 速度属性不漂移）。
	/// </summary>
	private const float FallbackPeaSpeed = 500f;

	/// <summary>
	/// 扫场景找植物 / 找本 Mod 精灵的间隔（帧）。发射节拍本身是每帧推进的。
	/// </summary>
	private const int ScanIntervalFrames = 10;

	/// <summary>
	/// 本 Mod 外观数据的识别关键字：`.tres` 的资源路径与 `.dat` 的 `animeFile` 里都含它。
	/// 用于把「本 Mod 的 AdobeAnimateSprite」从场景树里挑出来（战斗内 + 图鉴/选卡预览）。
	/// </summary>
	private const string SkinDataToken = "SuperGatlingPea";

	// ---------------------------------------------------------------- 内部类型

	/// <summary>
	/// 一个已订阅的发射组件。
	/// ⚠️ 委托类型 `FireReadyEventHandler` 是**嵌在 FireComponent 里的**（源码 255 行），
	/// 所以这里必须写全 FireComponent.FireReadyEventHandler。
	/// ★ 2026-09-24 齐射改版后只剩大招一条时间轴（常规攻击 = 数据侧齐射，插件不插手）。
	/// </summary>
	private sealed class PlantHook
	{
		public FireComponent Component;
		public FireComponent.FireReadyEventHandler ReadyHandler;

		/// <summary>是否正在大招中。</summary>
		public bool BurstActive;
		public ulong BurstStartMsec;
		public int BurstEmitted;
	}

	/// <summary>
	/// 需要跟随本体同步帧的「头部」子精灵（自制外观：头为独立图层，自带独立时间轴）。
	///
	/// ★ 为什么必须同步（有源码位置，别删）：
	///   自制外观把角色拆成**两个 AdobeAnimateSprite**：根节点画 `body` 图层、
	///   `Head` 子节点画 `head` 图层，两者各自持有 `frameIndex` / `clip`。
	///   `AdobeAnimateSprite` 本身**不会**让子精灵跟随父精灵的帧
	///   （全类里没有任何 "把 child.frameIndex 设成 parent.frameIndex" 的代码，
	///    只有渲染排序用的 `insertLayerId` / `followParentSpriteLayerId`）。
	///   内置 `GatlingPeaSprite.cs:24-45 BatchPhysicsUpdate` 是**手写**的同步逻辑 ——
	///   而 Mod 不能带 `.cs` 脚本，所以只能由这里代劳。
	///
	/// 同步策略（照抄内置 GatlingPeaSprite 的语义）：
	///   · Head 在待机（clip == "HeadIdle"）时，把它的帧拖到与本体的**相对偏移**对齐
	///     （本体 clip 起点 + (head.frameIndex - head.clip 起点)），慢/快由 timeScale 追平：
	///     落后 → 2.0 倍速追、超前 → 0.5 倍速等、相等 → 1.0。
	///   · 开火时（clip == "HeadFire"）不动，让 FireComponent 自己驱动播出射击动画。
	/// </summary>
	private sealed class HeadLink
	{
		public AdobeAnimateSprite Body;
		public AdobeAnimateSprite Head;
	}

	private XWModRuntimeContext _context;
	private SceneTree _tree;
	private Callable _tickCallable;
	private RandomNumberGenerator _rng;
	private readonly List<PlantHook> _hooks = new List<PlantHook>();
	private readonly List<HeadLink> _headLinks = new List<HeadLink>();

	/// <summary>Head 待机 clip 名（与 ComponentSet 的 spliceIdleAnimeClips 一致）。</summary>
	private const string HeadIdleClip = "HeadIdle";

	/// <summary>Head 开火 clip 名（与 ComponentSet 的 fireAnimeClips 一致）。</summary>
	private const string HeadFireClip = "HeadFire";

	/// <summary>自制外观里「头部」节点的节点名（`.tscn` 里带 `unique_name_in_owner = true`）。</summary>
	private const string HeadNodeName = "Head";

	private bool _hooked;
	private bool _connected;
	private int _frameCounter;

	/// <summary>上一帧的毫秒时刻，用来识别暂停/长卡顿（只在 OnProcessFrame 里读写）。</summary>
	private ulong _lastTickMsec;

	// 每条出错路径**各用一个**「已报告」标志，不要共用一个。
	// 理由：这些互不相干，共用一个标志会「先报的那条把后报的静音掉」——
	// 比如图鉴补分类失败（只是图鉴难看）会把「大招推进失败」（= 大招真没生效）的日志吃掉，
	// 排查时就只能看到一个不相干的警告，非常难定位。
	private bool _tickFaultReported;
	private bool _almanacFaultReported;
	private bool _bankFaultReported;
	private bool _hookFaultReported;
	private bool _readyFaultReported;
	private bool _fireFaultReported;
	private bool _shapeFaultReported;
	private bool _headSyncFaultReported;
	private bool _skinPatchFaultReported;

	/// <summary>算好的「要补的卡库 key 列表」（按 Include 闭包算出，只算一次）。</summary>
	private string[] _bankKeys;
	private int _bankPatchCount;
	private int _ultimateCount;
	private int _almanacPatchCount;
	private int _skinPatchCount;

	public void Initialize(XWModRuntimeContext context)
	{
		try
		{
			_context = context;
			_hooked = false;
			_connected = false;
			_frameCounter = 0;
			_lastTickMsec = 0;
			_tickFaultReported = false;
			_almanacFaultReported = false;
			_bankFaultReported = false;
			_hookFaultReported = false;
			_readyFaultReported = false;
			_fireFaultReported = false;
			_shapeFaultReported = false;
			_headSyncFaultReported = false;
			_skinPatchFaultReported = false;
			_ultimateCount = 0;
			_almanacPatchCount = 0;
			_skinPatchCount = 0;
			_bankKeys = null;
			_bankPatchCount = 0;
			_hooks.Clear();
			_headLinks.Clear();

			_rng = new RandomNumberGenerator();
			// 用引擎随机源播种（不是确定性种子）—— 单机体验用；
			// 联机会与主机不同步，这是刻意接受的代价（见类注释第一节）。
			_rng.Randomize();

			string root = (context == null) ? "<null>" : context.PackageRoot;
			Info("运行入口已初始化；PackageRoot=" + root
				+ "；常规攻击 = 数据侧 7 颗齐射（插件不参与）；大招 " + Pct(UltimateChance)
				+ "% → " + UltimateSeconds.ToString("0.#") + "s 内散射 " + UltimatePeas
				+ " 颗 ±" + ScatterHalfAngleDeg.ToString("0.#") + "°。");
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
				Warn("拿不到 SceneTree；大招与动画修复都不会生效（植物本身仍可正常攻击）。");
				return;
			}
			_tickCallable = Callable.From(new Action(OnProcessFrame));
			_tree.Connect("process_frame", _tickCallable);
			_connected = true;
			_hooked = true;
			Info("已挂载 process_frame；常规攻击 = 数据侧 7 颗齐射（动画 fire 事件触发，插件不插手），"
				+ "本插件只订阅 OnFireReady 掷大招骰（CreateProjectileByData 逐颗散射）；"
				+ "并会把本 Mod 的精灵切到本地 CPU 位姿渲染（修复「动画静止、暂停一次跳一帧」）；"
				+ "另把「" + CharacterConfigName + "」补进卡库「" + RootPlantBankKey + "」的「"
				+ GoldCategory + "」分类，并从图鉴的「" + ModPlantCategory
				+ "」独立分类里摘掉它（去掉图鉴里「只含本角色」的重复分类）。");
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
			_connected = false;
			_hooked = false;
			_tree = null;
			_hooks.Clear();
			_headLinks.Clear();
		}
	}

	// ---------------------------------------------------------------- 每帧

	private void OnProcessFrame()
	{
		try
		{
			_frameCounter++;

			ulong now = Time.GetTicksMsec();

			// 暂停 / 长卡顿：大招时间轴整体后移，欠账作废（不补发）。
			// 依据：SceneTree 暂停时 process_frame 可能停发，恢复后 now 会一次性跳几百毫秒；
			// 不补偿的话「继续」那一帧会把欠下的几百颗豌豆全吐出来。
			// 暂停 / 长卡顿判定收在共用核心 runtime_shared/GatlingVolleyCore.cs
			// （植物 / 僵尸共用同一套阈值与算法）。
			ulong gap = GatlingVolleyJudge.StallGap(_lastTickMsec, now);
			_lastTickMsec = now;

			// 发射节拍每帧推进（内部分别有单帧上限，开销可控）
			AdvanceHooks(now, gap);

			// 头部同步每帧都要做（跟着 clip 走，不能只按扫描间隔）
			SyncHeads();

			if ((_frameCounter % ScanIntervalFrames) != 0)
			{
				return;
			}
			ScanScene();
		}
		catch (Exception ex)
		{
			// 每帧都还会再试（只是不再刷屏），所以措辞是「只报一次」而不是「已停止重试」。
			if (!_tickFaultReported)
			{
				_tickFaultReported = true;
				Warn("发射节拍推进异常（本条只报一次，仍会继续尝试）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 每 10 帧干四件事（都不依赖场景树）：
	///   · 把本卡补进共享卡库 `GeneralPlant`（及派生库）→ **选卡界面**里能选到它；
	///   · 图鉴节点 → 摘掉「只有 Mod 植物」的独立分类 `ModPlants` + 补「金卡」分类
	///     （菜单里也会打开图鉴，所以**不能**只在战斗里扫）；
	///   · 战斗角色 → 挂发射组件；
	///   · 本 Mod 的精灵 → 切到本地 CPU 位姿渲染（修动画静止）。
	/// 第一件必须在场景树之外也跑（选卡界面在战斗场景里，但卡库是全局的），
	/// 所以它放在 `ScanScene` 里、递归之前。
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
		if (node is AdobeAnimateSprite sprite)
		{
			TryPatchSkinRender(sprite);
		}

		Godot.Collections.Array<Node> children = node.GetChildren();
		for (int i = 0; i < children.Count; i++)
		{
			ScanRecursive(children[i]);
		}
	}

	// ---------------------------------------------------------------- ③ 动画修复

	/// <summary>
	/// 把「本 Mod 外观」的精灵从 GPU 位姿路径切到本地 CPU 位姿路径 —— 见类注释第六节。
	///
	/// 为什么必须**运行期**设：`forceLocalRender` / `forceCpuPoseRender` 都是
	/// `public bool` **属性但带 `[Export]` 之外的实现**（源码 1141 / 1166 行都没有 `[Export]`），
	/// `.tscn` / `.tres` 里写不进去 ⇒ 只能由托管入口代劳。
	///
	/// 幂等 + 可覆盖：先把当前值读出来，只有真的需要改才写 + 打日志
	/// （两个 setter 自己也有 `if (field != value)` 守卫，重复写不会触发重算）。
	/// 因为 `ScanRecursive` 每 10 帧重扫整棵树，所以「引擎自己把 forceCpuPoseRender 放掉」
	/// 的情况（`ReleaseForcedCpuPoseData`）下一轮扫描会被自动补回来。
	/// </summary>
	private void TryPatchSkinRender(AdobeAnimateSprite sprite)
	{
		try
		{
			if (sprite == null || !GodotObject.IsInstanceValid(sprite))
			{
				return;
			}
			// 未就绪的节点上设这两个属性会走进 `SetProcessEnabled(_canRun && …)` 的分支，
			// 语义不明确 ⇒ 等它 ready 了再补（下一轮扫描会再来）。
			if (!sprite.IsInsideTree() || !sprite.IsNodeReady())
			{
				return;
			}
			if (!IsOurSkinData(sprite.flashAnimeData))
			{
				return;
			}
			if (sprite.forceLocalRender && sprite.forceCpuPoseRender)
			{
				return;
			}
			sprite.forceLocalRender = true;
			sprite.forceCpuPoseRender = true;
			_skinPatchCount++;
			Info("已把第 " + _skinPatchCount + " 个本 Mod 精灵切到本地 CPU 位姿渲染"
				+ "（forceLocalRender + forceCpuPoseRender）⇒ 动画恢复逐帧播放。节点="
				+ sprite.Name + "，data=" + Describe(sprite.flashAnimeData));
		}
		catch (Exception ex)
		{
			if (!_skinPatchFaultReported)
			{
				_skinPatchFaultReported = true;
				Warn("切换本 Mod 精灵渲染路径失败（本条只报一次；只是动画可能仍静止，不影响攻击）："
					+ ex.Message);
			}
		}
	}

	/// <summary>
	/// 这份 AdobeAnimateData 是不是本 Mod 自制外观。
	///
	/// 为什么不按对象引用比对：图鉴/选卡预览里的精灵可能与战斗里的不是同一个实例，
	/// 而且用户可能**根本没进战斗**就直接开图鉴 ⇒ 我们没有「已见过的那一份」可比对。
	/// 改判两个稳定的字符串：
	///   · `animeFile` —— 自制外观是 standalone `.dat`，写的是相对路径 `"./SuperGatlingPea.dat"`
	///     （内置都是 `res://Asset/Anime/.../<Key>.dat`）；
	///   · `ResourcePath` —— 运行时由 mod 挂载路径加载，通常也含 key。
	/// 任一含 `SuperGatlingPea` 即认定（大小写不敏感）。
	/// </summary>
	private static bool IsOurSkinData(AdobeAnimateData data)
	{
		if (data == null || !GodotObject.IsInstanceValid(data))
		{
			return false;
		}
		try
		{
			string anime = data.animeFile;
			if (!string.IsNullOrEmpty(anime)
				&& anime.IndexOf(SkinDataToken, StringComparison.OrdinalIgnoreCase) >= 0)
			{
				return true;
			}
			string path = data.ResourcePath;
			if (!string.IsNullOrEmpty(path)
				&& path.IndexOf(SkinDataToken, StringComparison.OrdinalIgnoreCase) >= 0)
			{
				return true;
			}
		}
		catch
		{
			// 读属性失败就当不是（安全降级：这类精灵保持原样）
		}
		return false;
	}

	private static string Describe(AdobeAnimateData data)
	{
		try
		{
			string path = data.ResourcePath;
			return string.IsNullOrEmpty(path) ? data.animeFile : path;
		}
		catch
		{
			return "<?>";
		}
	}

	// ---------------------------------------------------------------- 卡库 / 图鉴

	/// <summary>
	/// 把本卡补进**共享卡库**（`ResourceManager.TOWERDEFENSE_PACKETBANKS`）的「金卡」分类
	/// —— 这一步决定「**选卡界面里能不能选到它**」。
	///
	/// 为什么是这一步（有源码位置）：
	///   · 选卡界面 `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync`
	///     直接按 `packetBankData.category[分类]` 列卡，而 `packetBankData` 来自
	///     `TowerDefenseManager.GetPacketBankData(config.packetBankType)`；
	///   · `TowerDefenseLevelPacketBankConfig.packetBankType` 的默认值就是 `"GeneralPlant"`
	///     （关卡可用 `TowerDefenseLevelConfig.packetBank` 覆盖）；
	///   · 图鉴也是从 `GeneralPlant` 拷贝出来的（`Almanac.cs:219` → `WithPlants`）。
	///   ⇒ 只要本卡进了 `GeneralPlant.Gold`，**图鉴和选卡界面就同时有它，且同源**，
	///     这就是「图鉴与卡牌库数据一致」的天然保证（不需要两边各补一份）。
	///
	/// 还补**派生库**：`ResourceManager.BuildExpandedPacketBank` 会沿 `Include` 递归合并分类，
	///   所以 `Total`（`Include: [GeneralPlant, TotalZombie]`）运行期是 GeneralPlant 的超集。
	///   只补 GeneralPlant 的话，`CommandManager.debugPacketOpenAll`（切到 `Total`）下又会看不到。
	///   派生集合按 `PacketBankResource.json` 的 `Include` 闭包**在运行期算**，不写死。
	///
	/// 幂等 + 可恢复：卡库是全局单例、只构建一次（`LoadFullGameplayRootsOnMainThreadAsync`），
	///   但别的 Mod 仍可能通过 `provides.PacketBank` 覆盖同名卡库，所以这里**每次扫描都检查一遍**
	///   （一个分类里十几条字符串比较，开销可忽略），缺了再补，补上才打日志。
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
				return;      // 全量资源还在加载（TOWERDEFENSE_PACKETBANKS 是在那一步一次性建好的）
			}

			string[] keys = _bankKeys ?? (_bankKeys = ResolveDerivedBankKeys());
			for (int i = 0; i < keys.Length; i++)
			{
				TowerDefensePacketBankData bank;
				if (!banks.TryGetValue(keys[i], out bank) || bank == null || !GodotObject.IsInstanceValid(bank))
				{
					continue;
				}
				if (EnsureGoldContains(bank, keys[i]))
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
				Warn("补共享卡库「" + GoldCategory + "」分类失败（本条只报一次；不影响大招与动画修复）："
					+ ex.Message);
			}
		}
	}

	/// <summary>
	/// 往一个卡库的 `Gold` 分类里追加本卡。已在里面返回 false（幂等），真的加了返回 true。
	/// </summary>
	private bool EnsureGoldContains(TowerDefensePacketBankData bank, string bankKey)
	{
		Godot.Collections.Dictionary categories = bank.category;
		if (categories == null || !categories.ContainsKey(GoldCategory))
		{
			return false;
		}
		Godot.Collections.Array gold = categories[GoldCategory].AsGodotArray();
		if (gold == null)
		{
			return false;
		}
		for (int i = 0; i < gold.Count; i++)
		{
			if (string.Equals(gold[i].AsString(), CharacterConfigName, StringComparison.Ordinal))
			{
				return false;        // 已经在金卡里
			}
		}
		gold.Add(CharacterConfigName);
		categories[GoldCategory] = gold;      // 显式回写（Array 是引用语义，写回最稳）
		Info("已把「" + CharacterConfigName + "」补进卡库「" + bankKey + "」的「" + GoldCategory
			+ "」分类 ⇒ 选卡界面里可以选到它了。");
		return true;
	}

	/// <summary>
	/// 算「要补哪些卡库」= `GeneralPlant` 自身 + 所有通过 `Include` **间接包含**
	/// `GeneralPlant` 的卡库（`Include` 是递归合并语义，见 `ResourceManager.BuildExpandedPacketBank`）。
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
				if (string.Equals(name, RootPlantBankKey, StringComparison.OrdinalIgnoreCase)
					|| IncludesTransitively(raw, name, RootPlantBankKey, new HashSet<string>(StringComparer.OrdinalIgnoreCase)))
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
	/// 整理**图鉴自己那份拷贝**：① 把本卡从「只有 Mod 植物」的独立分类 <c>ModPlants</c> 里摘掉
	/// （摘空了就整个删键）；② 确保「金卡」分类里有本卡。
	///
	/// 为什么必须做 ①（有源码位置，别删）：
	///   `XWModContentCatalog.WithPlants()`（addons/ModEditor/ModSystem/XWModContentCatalog.cs:107-123）
	///   把 GeneralPlant 卡库**深拷贝**一份，然后把所有 Mod 植物塞进新建的
	///   `category["ModPlants"]`（`PlantCategory = "ModPlants"`，同文件 15 行）。全仓库只有
	///   `Almanac.cs:219` 调用它，图鉴的植物列表就按这份拷贝的分类翻页
	///   （`Almanac.cs:311-328`）—— 于是本卡会**同时**出现在「ModPlants（只有它自己）」和
	///   「Gold」两个分类里，用户看到的就是「图鉴里重复出现」。
	///   ★ 2026-09-25 用户口径：删掉只包含该角色的独立分类，保留在已有的金卡分类里。
	///   ⚠️ 摘条目而不是整类删：`ModPlants` 是**所有** Mod 植物共用的分类，别的 Mod 植物还在里面时
	///      整类删掉会把它们一起藏起来。只有摘完**空了**才删键。
	///
	/// 为什么还要做 ②（兜底，不是重复劳动）：
	///   图鉴的这份拷贝在 `_Ready`（`Almanac.cs:183`）就做好了，图鉴又是**按需实例化**的
	///   （`DialogManager.DialogCreate` → `Instantiate()`，MainMenu.cs:261 /
	///   TowerDefenseControlOld.cs:122），所以**正常时序**下 `TryPatchCardBanks()` 已经先把
	///   共享卡库补好，图鉴拷贝自然就带着本卡。这一步只兜「图鉴已经开着 → 我们才补上共享卡库」
	///   （比如开着图鉴点重新应用）。两边都是幂等 check-then-add，不会重复。
	///
	/// ⚠️ 删分类会让分类数 -1 ⇒ 正在显示的那一页可能**越界**：
	///   `Almanac.InitPlant()` 开头就是 `if (… || plantCategoryId >= plantPacketBank.category.Count)`
	///   ⇒ 直接 return 出**空列表**。`ModPlants` 是附加在末尾的，所以只有「正好停在这一页」
	///   才会越界，但为了稳仍统一回落一次（`Min(plantCategoryId, Count-1)`，不动其它页）。
	///
	/// 刷新列表只在「植物页已经建过列表」时才做 —— 见 `IsPlantPageInitialized`。
	/// </summary>
	private void TryPatchAlmanac(Almanac almanac)
	{
		try
		{
			TowerDefensePacketBankData bank = almanac.plantPacketBank;
			if (bank == null || !GodotObject.IsInstanceValid(bank))
			{
				return;
			}
			Godot.Collections.Dictionary categories = bank.category;
			if (categories == null)
			{
				return;
			}

			// ① 图鉴去重：把本卡从「只有 Mod 植物」的独立分类里摘掉（用户口径：
			//    删除只包含该角色的独立图鉴）。摘空了才删键 —— 别的 Mod 植物还要靠它。
			bool changed = false;
			if (categories.ContainsKey(ModPlantCategory))
			{
				Godot.Collections.Array modPlants = categories[ModPlantCategory].AsGodotArray();
				if (modPlants != null)
				{
					int before = modPlants.Count;
					for (int i = modPlants.Count - 1; i >= 0; i--)
					{
						if (string.Equals(modPlants[i].AsString(), CharacterConfigName, StringComparison.Ordinal))
						{
							modPlants.RemoveAt(i);
						}
					}
					if (modPlants.Count != before)
					{
						changed = true;
						if (modPlants.Count == 0)
						{
							categories.Remove(ModPlantCategory);
							Info("图鉴去重：本卡是该分类里唯一的植物 ⇒ 已删除「" + ModPlantCategory
								+ "」分类本身（图鉴里不再出现只含本角色的独立分类）。");
						}
						else
						{
							categories[ModPlantCategory] = modPlants;
							Info("图鉴去重：已把「" + CharacterConfigName + "」从「" + ModPlantCategory
								+ "」分类里摘掉（该分类还剩 " + modPlants.Count
								+ " 个其它 Mod 植物，故保留分类本身）。");
						}
					}
				}
			}

			// ② 兜底：确保金卡分类里有本卡（用户口径：保留在已有的金卡类型图鉴中），
			//    并顺手去掉**多余重复项**（图鉴里「重复出现」的另一条可能路径）。
			//    ⚠️ 注意别在这里提前 return —— ① 可能已经改过分类，刷新逻辑在下面统一走。
			if (categories.ContainsKey(GoldCategory))
			{
				Godot.Collections.Array gold = categories[GoldCategory].AsGodotArray();
				if (gold != null)
				{
					int hits = 0;
					for (int i = gold.Count - 1; i >= 0; i--)
					{
						if (!string.Equals(gold[i].AsString(), CharacterConfigName, StringComparison.Ordinal))
						{
							continue;
						}
						hits++;
						if (hits > 1)
						{
							gold.RemoveAt(i);        // 从后往前删，保留下标最小的那一个
							changed = true;
							Info("图鉴去重：金卡分类里发现本卡的重复条目，已删掉多余的一份。");
						}
					}
					if (hits == 0)
					{
						gold.Add(CharacterConfigName);
						categories[GoldCategory] = gold;   // 显式回写（Array 虽是引用语义，写回最稳）
						changed = true;
						_almanacPatchCount++;
						Info("兜底：已把「" + CharacterConfigName + "」并进图鉴那份拷贝的「" + GoldCategory
							+ "」分类（第 " + _almanacPatchCount + " 次；图鉴每次打开都是新的一份卡库拷贝）。");
					}
				}
			}

			if (!changed)
			{
				return;          // 幂等：图鉴这份拷贝已经整理好了
			}

			// 分类数变了 ⇒ 正在显示的那一页可能越界，先回落再刷新。
			// （`ModPlants` 在末尾，所以只有「正好停在那一页」才会越界；统一回落一次最稳。）
			if (almanac.plantCategoryId >= categories.Count && categories.Count > 0)
			{
				almanac.plantCategoryId = categories.Count - 1;
			}

			// 只有「植物页已经建过列表」时才需要主动刷新 —— 那说明分类列表是**按改之前的卡库**建的。
			// 没建过就**千万别**调 InitPlant()：图鉴是刻意懒初始化的
			// （`PlantButtonPressed` 里 `if (!_plantInitialized) InitPlant()`，
			//   自带的 AlmanacVirtualizedResidencyRuntimeTest 还专门断言「不得提前初始化隐藏分类 /
			//   不得提前实例化预览节点」）。提前调会把这些预览节点和角色资源在**打开图鉴的瞬间**
			//   就加载出来，白白多一次卡顿，还破坏了游戏原本的懒初始化设计。
			if (IsPlantPageInitialized(almanac))
			{
				almanac.InitPlant();
				Info("植物页已打开过 ⇒ 主动刷新一次列表（否则要手动翻一次分类才看得到）。");
			}
		}
		catch (Exception ex)
		{
			if (!_almanacFaultReported)
			{
				_almanacFaultReported = true;
				Warn("整理图鉴分类失败（本条只报一次；不影响大招与动画修复）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 读 `Almanac._plantInitialized`（私有，反射一次后缓存 FieldInfo）。
	/// 拿不到字段就返回 false（= 不刷新，安全降级）。
	/// </summary>
	private static bool IsPlantPageInitialized(Almanac almanac)
	{
		if (!_plantInitializedFieldProbed)
		{
			_plantInitializedFieldProbed = true;
			_plantInitializedField = typeof(Almanac).GetField(
				"_plantInitialized", BindingFlags.Instance | BindingFlags.NonPublic);
		}
		if (_plantInitializedField == null)
		{
			return false;
		}
		return _plantInitializedField.GetValue(almanac) is bool initialized && initialized;
	}

	// ---------------------------------------------------------------- 挂发射组件

	private void TryHookCharacter(TowerDefenseCharacter character)
	{
		try
		{
			// 不在战斗里时没有角色节点，这层判断只是省下 config 访问
			TowerDefenseManager manager = TowerDefenseManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;
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
			ComponentManager components = character.componentManager;
			if (components == null)
			{
				return;
			}
			FireComponent fire = components.GetRuntime<FireComponent>(FireInstanceId);
			if (!IsUsable(fire))
			{
				return;
			}
			AddHook(fire);

			// 顺带把「本体 + 头部」配对登记，让头跟随本体同步（自制外观是双图层双精灵）。
			TryLinkHead(fire.sprite);
		}
		catch (Exception ex)
		{
			if (!_hookFaultReported)
			{
				_hookFaultReported = true;
				Warn("读取植物发射组件失败（本条只报一次；不影响植物正常攻击）：" + ex.Message);
			}
		}
	}

	/// <summary>
	/// 组件是否仍然可用。
	/// ⚠️ CharacterComponentRuntime **不是 GodotObject**（是纯 C# 抽象类），
	/// 所以既没有 GodotObject.IsInstanceValid 也没有 GetInstanceId；
	/// 只能看 IsReleased + Owner（Owner 是 TowerDefenseCharacter，是 Node）。
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

	private void AddHook(FireComponent fire)
	{
		// 引用相等即「同一个组件」：CharacterComponentRuntime 不是 GodotObject，没有
		// GetInstanceId；而植物被铲掉/重种后本来就是一个全新的组件对象。
		for (int i = 0; i < _hooks.Count; i++)
		{
			if (ReferenceEquals(_hooks[i].Component, fire))
			{
				return;
			}
		}

		PlantHook hook = new PlantHook();
		hook.Component = fire;
		// 委托签名是 ()，没有 sender —— 用闭包把组件绑进回调。
		hook.ReadyHandler = delegate { OnFireReadyFrom(hook); };
		try
		{
			fire.OnFireReady += hook.ReadyHandler;
		}
		catch (Exception ex)
		{
			Warn("订阅 OnFireReady 失败（已跳过该组件）：" + ex.Message);
			return;
		}

		// ★ 2026-09-24 齐射改版：**不再**屏蔽 vanilla 动画事件发射链——
		//   常规攻击的 7 颗齐射恰恰要靠动画里那个 "fire" 事件触发
		//   （AnimeEvent → FireConfiguredVolley → Fire() 一次打出 7 条配置）。
		//   订阅失败时也不改组件任何状态 ⇒ 「订阅失败 = 只是没有大招」，绝不影响常规齐射。

		_hooks.Add(hook);
		Info("已挂上第 " + _hooks.Count + " 个「" + CharacterConfigName + "」发射组件（只接管大招）。");
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
			PlantHook hook = _hooks[i];
			if (!IsUsable(hook.Component))
			{
				continue;
			}
			try
			{
				hook.Component.OnFireReady -= hook.ReadyHandler;
			}
			catch (Exception ex)
			{
				Warn("退订 OnFireReady 失败（已忽略）：" + ex.Message);
			}
		}
	}

	// ---------------------------------------------------------------- 掷骰 + 发射

	/// <summary>
	/// 「一次攻击开始了」——`FireComponent.AttackEntered()`（3258 行）每次都恰好调一次。
	/// ★ 2026-09-24 齐射改版：常规攻击是数据侧齐射，这里**只**掷 10% 大招骰；
	///   命中 → 开大招；不命中 → 什么都不做（vanilla 自己已经把 7 颗齐射打出去了）。
	/// </summary>
	private void OnFireReadyFrom(PlantHook hook)
	{
		try
		{
			if (hook == null || !IsUsable(hook.Component))
			{
				return;
			}
			// 大招期间：不再掷骰、不叠加新大招。
			// vanilla 的常规齐射在大招期间照常打出（每次 Attack 的 fire 事件都会触发），
			// 视觉上 = 「大招弹幕里夹着正常的 7 连齐射」，与原作「发射 7 枚，概率发射大量」一致。
			if (hook.BurstActive)
			{
				return;
			}
			ulong now = Time.GetTicksMsec();
			if (GatlingVolleyJudge.RollUltimate(_rng))
			{
				StartBurst(hook, now);
			}
		}
		catch (Exception ex)
		{
			warnOnce(ref _readyFaultReported, "判定大招时异常（本条只报一次，仍会继续尝试）：" + ex.Message);
		}
	}

	private void StartBurst(PlantHook hook, ulong now)
	{
		hook.BurstActive = true;
		hook.BurstStartMsec = now;
		hook.BurstEmitted = 0;

		_ultimateCount++;
		Info("触发大招（第 " + _ultimateCount + " 次）："
			+ UltimateSeconds.ToString("0.#") + "s 内散射 " + UltimatePeas + " 颗 ±"
			+ ScatterHalfAngleDeg.ToString("0.#") + "°，节拍 "
			+ (UltimateSeconds * 1000.0 / UltimatePeas).ToString("0.0") + "ms/颗。");
	}

	/// <summary>
	/// 每帧推进所有发射组件的大招时间轴。`gap` 是本次「暂停/长卡顿」的补偿量（毫秒，0 = 无）。
	/// </summary>
	private void AdvanceHooks(ulong now, ulong gap)
	{
		if (_hooks.Count == 0)
		{
			return;
		}
		for (int i = _hooks.Count - 1; i >= 0; i--)
		{
			PlantHook hook = _hooks[i];
			if (!IsUsable(hook.Component))
			{
				continue;
			}
			if (gap > 0)
			{
				// 植物入口只剩大招一条时间轴 ⇒ 复用共用核心的两参形态
				//（第一参是僵尸包「连发链轴」的占位，植物侧恒 0、无副作用）。
				ulong unusedChainMsec = 0;
				GatlingVolleyJudge.ShiftTimeline(ref unusedChainMsec, ref hook.BurstStartMsec, gap);
			}
			AdvanceBurst(hook, now);
		}
	}

	/// <summary>
	/// 大招：第 k 颗的计划时刻 = 起点 + k × (5000/300) ms（k 从 1 数）。
	/// 用「按颗数算时刻」而不是「每次 += 间隔」，可以完全避免浮点累加漂移，
	/// 保证**恰好 300 颗**、**恰好 5 秒**。
	/// </summary>
	private void AdvanceBurst(PlantHook hook, ulong now)
	{
		int guard = 0;
		while (hook.BurstEmitted < UltimatePeas && guard < MaxPeasPerFrame)
		{
			ulong dueMsec = GatlingVolleyJudge.BurstDueMsec(hook.BurstStartMsec, hook.BurstEmitted);
			if (now < dueMsec)
			{
				return;
			}
			float angle = GatlingVolleyJudge.ScatterAngleDeg(_rng);
			if (!FireUltimatePea(hook, angle))
			{
				hook.BurstActive = false;
				return;
			}
			hook.BurstEmitted++;
			guard++;
		}

		if (hook.BurstEmitted >= UltimatePeas)
		{
			hook.BurstActive = false;
			Info("大招结束：共散射 " + hook.BurstEmitted + " 颗，用时 "
				+ ((now - hook.BurstStartMsec) / 1000.0).ToString("0.0") + "s。");
		}
	}

	/// <summary>
	/// 打出一颗大招散射豌豆：走**游戏自己的** <c>CreateProjectileByData()</c>
	/// （FireComponent.cs:3049 → CreateProjectile :2684，狐尾草
	/// <c>TowerDefensePlantHWC.FireVolley</c> 同款 API）。
	///
	/// ⚠️ 为什么不能再调 <c>Fire()</c>：齐射改版后 <c>fireProjectileList</c> 里有
	///   7 条配置，<c>Fire()</c> 一次会把 7 颗全打出（:3449 的 for 循环）。
	///
	/// 与 vanilla <c>Fire()</c> 的行为对齐（每条都有源码位置）：
	///   · 弹种   = fireCheckList[0].GetProjectile()（与 Fire() :3467-3472 同源）
	///   · 弹速   = fireProjectileList[0].speed（与常规齐射**同一份**数据 ⇒ 速度不漂移）
	///   · 伤害等 = TowerDefenseProjectileCreateData 原值，本插件一个字段都不改
	///   · 碰撞旗 = collisionFlags 传 -1 ⇒ parent.instance.collisionFlags，
	///     与 Fire() 的 useParentCollision 默认路径一致（FireComponentCheckConfig.cs:57-64）
	///   · 朝向   = overrides.spriteRotationOverride = 散射角（Fire() :3493 同口径）
	///   · 翻转   = 本体 Scale.X &lt; 0（= GetProjectileBodyScaleX :713-721 在
	///     projectileFlip=false 时的语义，狐尾草 FireVolley 同款写法）
	///   · 行锁定 = lockProjectileGridY=true（定义里）⇒ CreateProjectile :2743 自动
	///     写 gridYOverride = 种植行，散射弹也只打本排
	/// </summary>
	private bool FireUltimatePea(PlantHook hook, float angleDeg)
	{
		try
		{
			FireComponent fire = hook.Component;
			Godot.Collections.Array<FireComponentCheckConfig> checks = fire.fireCheckList;
			if (checks == null || checks.Count == 0)
			{
				warnOnce(ref _shapeFaultReported,
					"fireCheckList 为空 ⇒ 大招打不出豌豆，请核对 ComponentSet。");
				return false;
			}
			FireComponentCheckConfig check = checks[0];
			if (check == null || !GodotObject.IsInstanceValid(check))
			{
				return false;
			}
			TowerDefenseProjectileCreateData data = check.GetProjectile();
			if (data == null)
			{
				warnOnce(ref _shapeFaultReported,
					"fireCheckList[0].GetProjectile() 为空 ⇒ 大招打不出豌豆，请核对 ComponentSet。");
				return false;
			}
			// 弹速与常规齐射同源：实时读配置（不缓存），读不到再兜底
			float speed = FallbackPeaSpeed;
			Godot.Collections.Array<FireComponentFireProjectileConfig> list = fire.fireProjectileList;
			if (list != null && list.Count > 0 && list[0] != null && GodotObject.IsInstanceValid(list[0]))
			{
				speed = list[0].speed;
			}
			Vector2 velocity = speed * Vector2.FromAngle(Mathf.DegToRad(angleDeg));
			BulletFieldSpawnOverrides overrides = new BulletFieldSpawnOverrides
			{
				flipXOverride = (fire.parent != null && GodotObject.IsInstanceValid(fire.parent)
									&& fire.parent.Scale.X < 0f),
				spriteRotationOverride = Mathf.DegToRad(angleDeg)
			};
			// collisionFlags = -1 ⇒ CreateProjectile 回落 parent.instance.collisionFlags
			//（与 Fire() 的 useParentCollision=true 路径完全一致）；camp 传 PLANT
			//⇒ CreateProjectileByData :3051-3054 换成 parent.camp。
			fire.CreateProjectileByData(0, velocity, data, -1,
				TowerDefenseEnum.CHARACTER_CAMP.PLANT, Vector2.Zero, overrides);
			return true;
		}
		catch (Exception ex)
		{
			// 发射失败不能把「整帧节拍」炸掉（否则同一帧里后续植物全被跳过）。
			warnOnce(ref _fireFaultReported,
				"调用 CreateProjectileByData 失败（本条只报一次；植物仍会正常齐射）：" + ex.Message);
			return false;
		}
	}

	// ---------------------------------------------------------------- 头部同步

	/// <summary>
	/// 找出该角色身上的「本体 + 头部」两个 AdobeAnimateSprite，登记进 _headLinks。
	///
	/// ⚠️ 传进来的 `fireSprite` **是「头」，不是精灵根** —— 这点以前搞错过，别改回去：
	///   `FireComponent.sprite` 来自 `ResolveOwnerNode&lt;AdobeAnimateSprite&gt;(Definition.spritePath)`
	///   （FireComponent.cs:1241），而本 Mod 的 ComponentSet 写的是
	///   `spritePath = NodePath("SpriteGroup/TransformPoint/GatlingPea/Head")` ⇒ 解析出来就是 Head。
	///   （内置 GatlingPea 的 Builtin ComponentSet 同样指向 `.../GatlingPea/Head`。）
	///   旧代码把 `fire.sprite` 当根、再 `GetNodeOrNull("%Head")`，结果拿到的是**它自己**
	///   ⇒ 登记成「头 ↔ 头」的自环，同步逻辑变成空转（bodyRel == headRel ⇒ 恒设 timeScale=1）。
	///
	/// 所以这里两种形状都兜住：
	///   · 传进来的是 Head（本 Mod 的实际情况）⇒ 本体 = `Head.GetParent()`；
	///   · 传进来的是根（万一以后改了 spritePath）⇒ 本体 = 它自己，头 = `%Head`。
	///
	/// 拿不到规则形状就静默跳过（不是致命错误，最多头不同步）。
	/// </summary>
	private void TryLinkHead(AdobeAnimateSprite fireSprite)
	{
		try
		{
			if (fireSprite == null || !GodotObject.IsInstanceValid(fireSprite))
			{
				return;
			}

			AdobeAnimateSprite head = fireSprite;
			AdobeAnimateSprite body;
			if (string.Equals(head.Name, HeadNodeName, StringComparison.Ordinal))
			{
				body = head.GetParent() as AdobeAnimateSprite;
			}
			else
			{
				body = head;
				head = head.GetNodeOrNull("%" + HeadNodeName) as AdobeAnimateSprite;
			}

			if (body == null || !GodotObject.IsInstanceValid(body))
			{
				return;
			}
			if (head == null || !GodotObject.IsInstanceValid(head) || ReferenceEquals(body, head))
			{
				return;      // 没有独立头部（例如旧的内置外观）—— 正常，直接跳过
			}

			for (int i = 0; i < _headLinks.Count; i++)
			{
				if (ReferenceEquals(_headLinks[i].Body, body))
				{
					return;      // 已登记，幂等
				}
			}
			HeadLink link = new HeadLink();
			link.Body = body;
			link.Head = head;
			_headLinks.Add(link);
			Info("已登记第 " + _headLinks.Count + " 组「本体+头部」精灵（本体=" + body.Name
				+ "，头=" + head.Name + "），头部将跟随本体帧同步。");
		}
		catch (Exception ex)
		{
			// 头不同步只是观感问题，绝不能影响别的功能
			Warn("登记头部精灵失败（已跳过，头部可能不同步）：" + ex.Message);
		}
	}

	/// <summary>
	/// 每帧把每个 Head 的帧拖到与本体一致的相位上 —— 见 <see cref="HeadLink"/> 的说明。
	///
	/// 帧语义（官方素材直转的 .tres；★ 2026-09-24 植物包把 HeadFire 收窄为射击段）：
	///   BodyIdle = 0..24（茎叶），HeadIdle = 25..49（头待机），HeadFire = 50..74（射击，
	///   闭合循环：f50 与 f74 位姿相同；原 75..86 的「大招抖动段」不再被任何 clip 引用，
	///   否则每轮普攻都会播它 ⇒ 「射击后抽搐」，见生成器 HEADFIRE_CLIP_PLANT 注释）
	/// ⇒ 本体待机在 BodyIdle，头待机在 HeadIdle，**三段长度都是 25 帧**，
	///     所以「相对相位」正是两者 frameIndex 相对各自 clipRange.X 的偏移量 ——
	///     新布局不再要求「帧号天然对齐」，用 `relative = frameIndex - clipRange.X`
	///     比相对量即可，天然适配任何 clip 起点。
	/// </summary>
	private void SyncHeads()
	{
		if (_headLinks.Count == 0)
		{
			return;
		}
		for (int i = _headLinks.Count - 1; i >= 0; i--)
		{
			HeadLink link = _headLinks[i];
			AdobeAnimateSprite body = link.Body;
			AdobeAnimateSprite head = link.Head;
			if (!GodotObject.IsInstanceValid(body) || !GodotObject.IsInstanceValid(head))
			{
				_headLinks.RemoveAt(i);
				continue;
			}
			try
			{
				// 暂停态跟随
				head.pause = body.pause;

				// 开火中（含大招连射）不去干扰 FireComponent 对头部动画的驱动
				if (head.clip != HeadIdleClip)
				{
					continue;
				}
				if (head.timeScale == 0.0)
				{
					continue;      // 玩家/系统刻意停表，别碰
				}

				int bodyRel = body.frameIndex - body.clipRange.X;
				int headRel = head.frameIndex - head.clipRange.X;
				if (headRel < bodyRel)
				{
					head.timeScale = 2.0;      // 落后 → 追上
				}
				else if (headRel > bodyRel)
				{
					head.timeScale = 0.5;      // 超前 → 等一等
				}
				else
				{
					head.timeScale = 1.0;
				}
			}
			catch (Exception ex)
			{
				// 单个精灵出问题不该拖垮整帧同步
				if (!_headSyncFaultReported)
				{
					_headSyncFaultReported = true;
					Warn("头部帧同步异常（本条只报一次，仍会继续尝试）：" + ex.Message);
				}
			}
		}
	}

	// ---------------------------------------------------------------- 日志

	private static string Pct(double v)
	{
		return (v * 100.0).ToString("0.#");
	}

	/// <summary>「本条只报一次」的通用实现：把标志位置起，已置起就什么都不做。</summary>
	private static void warnOnce(ref bool reported, string message)
	{
		if (reported)
		{
			return;
		}
		reported = true;
		LogWarn(LogPrefix + message);
	}

	private static void LogWarn(string message)
	{
		try
		{
			GD.PushWarning(message);
		}
		catch
		{
			// 日志本身绝不能成为异常源：入口三回调抛异常 = 无条件整包回滚。
		}
	}

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
