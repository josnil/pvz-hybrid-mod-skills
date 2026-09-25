using System;
using System.Collections.Generic;
using System.Reflection;
using Godot;
using PVZHE.ModEditor.ModSystem;

/// <summary>
/// 「奶龙僵尸」Mod 的托管运行时入口。
///
/// ════════════════════════════════════════════════════════════════════════
/// 〇、这个包为什么需要插件（纯数据做不到的部分）
/// ════════════════════════════════════════════════════════════════════════
///   1. **自制 .dat 皮肤会静止** —— `Assets/Animations/NaiLong.dat` 是 standalone `.dat`，
///      不在引擎的全局图集清单里 ⇒ `AdobeAnimateSprite` 的 GPU 位姿时钟不生效 ⇒ 动画不动。
///      修法只能运行期写 `forceLocalRender` / `forceCpuPoseRender`（无 `[Export]`，写不进 `.tscn`），
///      且引擎会 `ReleaseForcedCpuPoseData` 放掉 ⇒ 必须**周期性整树扫描**反复补。
///      见 `NaiLongLocalRender.cs`。
///   2. **每 10 秒一次大笑（出场首次不触发）** —— 节拍是墙钟语义，数据侧没有通道。
///   3. **大笑时全场植物停止发射 1 秒** —— 这一条修过一次，记下来免得再走回头路：
///      *旧做法*是把每株植物的 `timeScaleInit` 压成 0。它对「动画/移动」有效，但对
///      **发射**无效，因为引擎里凡是有独立发射计时器的组件都按
///      `GetTimerRunScale()` 推进（`FireComponent.cs:1683`）：
///          `parent.timeScale * timeScale * parent.buff.GetAttackSpeedMultiplier()`
///      而其中至少两条路径**绕开了 timeScale**：
///        · `FireComponent.cs:1687`（IZM 模式）只取 `buff.GetAttackSpeedMultiplier()`；
///        · `CannonComponent.cs:1344` 写的是 `flag ? 1.0 : parent.timeScale`。
///      ⇒ 只要走这两条路径，`timeScale = 0` 也照打不误。
///      **唯一被所有发射路径共同乘进去的量，是 `buff.GetAttackSpeedMultiplier()`**
///      （`FireComponent:1687/1693/3298`、`CannonComponent:943/1344`、
///      `CatapultComponent:538`）。而它只认一个 buff：
///          `BuffComponent.GetAttackSpeedMultiplier()` → `BuffGet("AttackSpeedDown")`
///          → `Math.Max(0.0, timeScaleValue)`
///      ⇒ 所以本插件在控场期间给每株植物挂一个
///        `TowerDefenseCharacterBuffAttackSpeedDown { timeScaleValue = 0, time = 1 }`，
///        **倍率 = 0 ⇒ 发射计时器永不推进 ⇒ 全组件、全模式一律打不出子弹**；
///        到期把 buff 摘掉即恢复。`timeScaleInit=0` 同时保留，用于「暂停行动」的观感。
///        用法与引擎自带的先例一致（`TowerDefenseZombieBossEdgarII.ResolvePulse` 就是这么
///        给全场植物挂 `AttackSpeedDown` 的，只是倍率是 0.5 / 15s）。
///        ⚠️ 只为**我们加上的**植物摘 buff：若某株植物本来就被游戏挂着
///        `AttackSpeedDown`（例如埃德加二世的火球），碰它会把原本的效果弄丢。
///   4. **大笑音效** —— Mod 音频进 `ResourceManager.AUDIOS`（键 = 文件名去扩展名，
///      `ModLoader.InferRuntimeEntry` 的 `Assets/Audio/` 分支），而 `AudioManager` 对 SFX
///      **没有事件总线**（只能 `AudioManager.Instance.AudioPlay(key)`）⇒ 由插件在触发时叫一次。
///   5. **补进共享卡库 + 图鉴去重** —— 见 `TryPatchCardBanks` / `TryDedupeAlmanacZombie`。
///
/// ════════════════════════════════════════════════════════════════════════
/// 一、大笑的时序口径（严格按需求）
/// ════════════════════════════════════════════════════════════════════════
///   · 接管一只僵尸时把 `NextLaughMsec = now + 10s` ⇒ **出场那一次不触发**（需求 2）。
///   · 触发时：`sprite` 切到 `LaughWalk` clip（大笑立绘 + 正常步态，3 秒 = 36 帧
///     = 3 个完整步态周期）+ 播 `nailong_laugh` 音效
///     + 把全场植物 `timeScaleInit = 0`（暂停行动）**并挂上攻速为 0 的 buff**（停止发射）。
///   · `PlantFreezeSec = 3.0` 与 `LaughHoldSec = 3.0` 对齐：到点同时摘 buff、
///     恢复 timeScaleInit、把 clip 换回去。
///   · `NextLaughMsec = now + 10s`（从上一次触发算起，与姿态长短无关）。
///
/// ════════════════════════════════════════════════════════════════════════
/// 一·B、僵尸「怎么才能往前走」（皮肤侧，勿删）
/// ════════════════════════════════════════════════════════════════════════
///   僵尸的前进**只**由 `GroundMoveComponent` 驱动（全仓只有它调用
///   `TranslateForPhysicsFrame`），而它按名找动画里的 **`_ground` 层**，
///   读该层逐帧位姿差当作位移：
///       `vector2 = 上一层位姿 - 这一帧位姿`  →  `TranslateParent(vector2 * _moveScale)`
///   ⇒ 皮肤里**没有 `_ground` 层就一步都走不了**（初版就漏了这层）。
///   该层必须 **alpha=0**（只做根运动、不可见），且**每个剪辑只放一条完整锯齿**：
///   锯齿回跳落在剪辑边界上才会被 `if (sprite.pause || sprite.blend) ResetGroundTracking()`
///   吃掉；放在剪辑中间会看到明显的倒跳。
///   ⚠️ `walkSpeedScale` 不影响移速（基类不读它），移速 = 本层位移速率，
///      在 nailong_skin.py 的 `GROUND_PX_PER_FRAME` 一处可调。
///
/// ════════════════════════════════════════════════════════════════════════
/// 二、纪律（与同工坊其余入口一致）
/// ════════════════════════════════════════════════════════════════════════
///   `Initialize` / `OnAllModsLoaded` / `Shutdown` **一律不许抛**（抛 = 无条件整包回滚），
///   三个回调整体 try/catch；其余每条功能路径**各自**一个「已报告」标志；
///   所有反射调用都包在 try/catch 里。`Shutdown` 必须把冻结的植物恢复回原值。
/// </summary>
public sealed class NaiLongRuntimeEntry : IXWModRuntimeEntry
{
	private const string LogPrefix = "[NaiLong] ";

	// ---------------------------------------------------------------- 角色身份
	//
	// 身份标识 = `TowerDefenseZombieConfig.name`（== 角色包 Key）。卡库与图鉴都靠它认人。

	private const string ConfigName = "ZombieNaiLong";

	// ---------------------------------------------------------------- 大笑（需求 2）

	/// <summary>大笑周期（秒）。</summary>
	private const float LaughIntervalSec = 10.0f;

	/// <summary>大笑姿态持续时间（秒）。= 控场时长，让「边笑边走」的 36 帧走完。</summary>
	private const float LaughHoldSec = 3.0f;

	/// <summary>全场植物控场时长（秒）—— 期间暂停行动且停止发射子弹。</summary>
	private const float PlantFreezeSec = 3.0f;

	/// <summary>
	/// 控场用的 buff key。**必须**是 "AttackSpeedDown"：
	/// `BuffComponent.GetAttackSpeedMultiplier()` 只按这个字面量去查表。
	/// </summary>
	private const string PlantHoldBuffKey = "AttackSpeedDown";

	/// <summary>控场期间的攻速倍率。0 ⇒ 发射计时器完全不推进 ⇒ 一颗子弹也打不出来。</summary>
	private const double PlantHoldTimeScale = 0.0;

	/// <summary>
	/// 大笑 clip 名。用 `LaughWalk`（大笑立绘 + 正常步态）而不是 `Laugh`：
	/// 3 秒里僵尸要**一边笑一边正常往前走**，所以必须用带根运动的那个剪辑
	/// （`_ground` 层，见 nailong_skin.py 的根运动注释）。
	/// </summary>
	private const string LaughClipName = "LaughWalk";

	/// <summary>没有 LaughWalk 时退回的旧大笑剪辑（只有笑、不走）。</summary>
	private const string LaughClipFallback = "Laugh";

	/// <summary>大笑音效在 `ResourceManager.AUDIOS` 里的键 = 文件名去扩展名。</summary>
	private const string LaughAudioKey = "nailong_laugh";

	/// <summary>恢复动画时的兜底 clip（存档点读不到时用）。</summary>
	private const string FallbackClip = "Walk1";

	private static readonly ulong LaughIntervalMsec = (ulong)(LaughIntervalSec * 1000f);
	private static readonly ulong LaughHoldMsec = (ulong)(LaughHoldSec * 1000f);
	private static readonly ulong PlantFreezeMsec = (ulong)(PlantFreezeSec * 1000f);

	// ---------------------------------------------------------------- 调度

	/// <summary>扫场景的间隔（帧）。大笑节拍不受它限制（每帧推进）。</summary>
	private const int ScanIntervalFrames = 10;

	/// <summary>两帧间隔超过它就认为「暂停 / 长卡顿」，把节拍整体后移，不补发欠账。</summary>
	private const ulong StallThresholdMsec = 250;

	// ---------------------------------------------------------------- 卡库

	private const string RootZombieBankKey = "GeneralZombie";
	private const string ZombieCategory = "Zombie";
	private const string PacketBankResourcePath = "res://Asset/Config/PacketBank/PacketBankResource.json";
	private static readonly string[] FallbackDerivedBankKeys =
		new string[] { "GeneralZombie", "TotalZombie", "Total" };

	// ---------------------------------------------------------------- 内部类型

	/// <summary>一只已被接管的奶龙僵尸。</summary>
	private sealed class ZombieHook
	{
		public TowerDefenseCharacter Character;

		/// <summary>下一次大笑的时刻（ms 墙钟）；接管时 = now + 10s ⇒ 出场不触发。</summary>
		public ulong NextLaughMsec;

		/// <summary>正在大笑中。</summary>
		public bool Laughing;

		/// <summary>本次大笑姿态结束的时刻。</summary>
		public ulong LaughEndMsec;

		/// <summary>大笑前的 clip（结束时换回去）。</summary>
		public string PrevClip;

		/// <summary>本次实际使用的大笑 clip（优先 LaughWalk，退化时用 Laugh）。</summary>
		public string ActiveLaughClip;
	}

	// ---------------------------------------------------------------- 状态

	private XWModRuntimeContext _context;
	private SceneTree _tree;
	private Callable _tickCallable;
	private readonly List<ZombieHook> _hooks = new List<ZombieHook>();

	/// <summary>
	/// 本次控场里**由我们**挂上攻速 buff 的植物。
	/// 只回收自己挂的 —— 若某株植物本来就被游戏挂着 AttackSpeedDown（埃德加二世的火球
	/// 就是 0.5×/15s），碰它会把它原本的效果一起弄丢。
	/// </summary>
	private readonly List<TowerDefenseCharacter> _holdTargets =
		new List<TowerDefenseCharacter>();

	/// <summary>控场前各植物 `timeScaleInit` 的原值（窗口结束原样写回）。</summary>
	private readonly Dictionary<TowerDefenseCharacter, double> _holdTimeScale =
		new Dictionary<TowerDefenseCharacter, double>();

	/// <summary>控场窗口的截止时刻（ms 墙钟）。</summary>
	private ulong _holdEndMsec;
	private bool _hooked;
	private bool _connected;
	private int _frameCounter;
	private ulong _lastFrameMsec;

	// 每条出错路径**各用一个**「已报告」标志（共用会把先报的把后报的静音掉）
	private bool _tickFaultReported;
	private bool _bankFaultReported;
	private bool _hookFaultReported;
	private bool _laughFaultReported;
	private bool _audioFaultReported;
	private bool _freezeFaultReported;
	private bool _dedupeFaultReported;
	private bool _skinFaultReported;

	private string[] _bankKeys;
	private int _bankPatchCount;
	private int _almanacDedupeCount;
	private int _laughCount;
	private int _freezeCount;
	private int _holdBuffCount;
	private int _skinPatchCount;

	private static FieldInfo _zombieLogicalField;
	private static bool _zombieLogicalFieldProbed;

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
			_laughFaultReported = false;
			_audioFaultReported = false;
			_freezeFaultReported = false;
			_dedupeFaultReported = false;
			_skinFaultReported = false;
			_bankKeys = null;
			_bankPatchCount = 0;
			_almanacDedupeCount = 0;
			_laughCount = 0;
			_freezeCount = 0;
			_skinPatchCount = 0;
			_hooks.Clear();
			_holdTargets.Clear();
			_holdTimeScale.Clear();
			_holdEndMsec = 0UL;
			_holdBuffCount = 0;

			string root = (context == null) ? "<null>" : context.PackageRoot;
			Info("运行入口已初始化；PackageRoot=" + root
				+ "；角色 = " + ConfigName
				+ "；每 " + LaughIntervalSec.ToString("0.#") + "s 大笑一次（出场首次不触发）"
				+ "，姿态 " + LaughHoldSec.ToString("0.#") + "s、音效 " + LaughAudioKey
				+ "、全场植物控场 " + PlantFreezeSec.ToString("0.#") + "s"
				+ "（buff " + PlantHoldBuffKey + "=" + PlantHoldTimeScale.ToString("0.#")
				+ " ⇒ 暂停行动且停止发射）。");
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
				Warn("拿不到 SceneTree；大笑节拍与植物冻结不会生效（角色本身仍可正常行走/啃食/死亡）。");
				return;
			}
			_tickCallable = Callable.From(new Action(OnProcessFrame));
			_tree.Connect("process_frame", _tickCallable);
			_connected = true;
			_hooked = true;
			_lastFrameMsec = Time.GetTicksMsec();
			Info("已挂载 process_frame；并会把「" + ConfigName + "」补进卡库「" + RootZombieBankKey
				+ "」的「" + ZombieCategory + "」分类。");
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
			// ★ 一定要把控场 buff 摘掉并恢复 timeScaleInit，否则关掉 Mod 后植物会永远开不了火。
			ReleasePlantFire();
			_connected = false;
			_hooked = false;
			_tree = null;
			_hooks.Clear();
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
			AdvanceHold(now);

			if ((_frameCounter % ScanIntervalFrames) != 0)
			{
				return;
			}
			ScanScene();
			// 控场窗口内再铺一遍：把窗口里刚种下的植物也带上（不改窗口截止时刻）。
			if (_holdTargets.Count > 0)
			{
				HoldPlantFire(now, keepDeadline: true);
			}
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
			// ★ 自制 .dat 皮肤的「动画静止」修法：周期性地反复补这两个开关。
			TryPatchSkinRender(animeSprite);
		}
		Godot.Collections.Array<Node> children = node.GetChildren();
		for (int i = 0; i < children.Count; i++)
		{
			ScanRecursive(children[i]);
		}
	}

	/// <summary>幂等地把「奶龙」自制皮肤精灵切到本地 CPU 姿态渲染。绝不抛。</summary>
	private void TryPatchSkinRender(AdobeAnimateSprite sprite)
	{
		try
		{
			int result = NaiLongLocalRender.Patch(sprite);
			if (result != NaiLongLocalRender.Patched)
			{
				return;
			}
			_skinPatchCount++;
			if (_skinPatchCount <= 3)
			{
				AdobeAnimateData data = sprite.flashAnimeData;
				Info("自制皮肤转本地 CPU 姿态（第 " + _skinPatchCount + " 个精灵）："
					+ NaiLongLocalRender.Describe(data) + "；节点=" + sprite.Name
					+ "。不加这两个开关时动画会完全静止。");
			}
		}
		catch (Exception ex)
		{
			if (!_skinFaultReported)
			{
				_skinFaultReported = true;
				Warn("自制皮肤渲染兜底失败（本条只报一次；最坏情况=动画静止，不影响战斗逻辑）：" + ex.Message);
			}
		}
	}

	// ================================================================ 大笑节拍

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
				// 暂停 / 长卡顿：两条时间轴整体后移，欠账作废（不补发）。
				hook.NextLaughMsec += gap;
				hook.LaughEndMsec += gap;
			}

			if (hook.Laughing)
			{
				EnsureLaughClip(hook);
				if (now >= hook.LaughEndMsec)
				{
					EndLaugh(hook);
				}
				continue;
			}

			if (now >= hook.NextLaughMsec)
			{
				BeginLaugh(hook, now);
			}
		}
	}

	/// <summary>
	/// 开始大笑：切立绘 + 播音效 + 冻结全场植物 0.5s。
	/// 「出场首次不触发」由接管时的 `NextLaughMsec = now + 10s` 保证。
	/// </summary>
	private void BeginLaugh(ZombieHook hook, ulong now)
	{
		hook.NextLaughMsec = now + LaughIntervalMsec;
		hook.LaughEndMsec = now + LaughHoldMsec;
		hook.Laughing = true;
		hook.PrevClip = ReadClip(hook.Character);

		try
		{
			AdobeAnimateSprite sprite = GetSprite(hook.Character);
			if (sprite != null)
			{
				// 优先 LaughWalk（笑 + 走），没有就退到 Laugh（只有笑）。
				string want = null;
				if (sprite.HasClip(LaughClipName))
				{
					want = LaughClipName;
				}
				else if (sprite.HasClip(LaughClipFallback))
				{
					want = LaughClipFallback;
					Warn("皮肤里没有 clip「" + LaughClipName + "」⇒ 退回「" + LaughClipFallback
						+ "」（只笑不走）。请重跑 build_zombie_nailong.py 补上带根运动的剪辑。");
				}
				hook.ActiveLaughClip = want;
				if (want != null)
				{
					// blendTime 0.1 与引擎自己的攻击/啃食切换同量级；
					// 混合期间 GroundMoveComponent 不推进，所以越小越不打断走路。
					sprite.SetAnimation(want, loop: true, blendTime: 0.1);
				}
				else
				{
					Warn("皮肤里既没有「" + LaughClipName + "」也没有「" + LaughClipFallback
						+ "」⇒ 只播音效与控场，不换立绘。");
				}
			}
		}
		catch (Exception ex)
		{
			if (!_laughFaultReported)
			{
				_laughFaultReported = true;
				Warn("切大笑立绘失败（本条只报一次）：" + ex.Message);
			}
		}

		PlayLaughAudio();

		// 每一次大笑都重新铺一遍控场窗口（多只同时大笑时窗口自然叠加，不叠加速度）。
		HoldPlantFire(now, keepDeadline: false);
		_freezeCount++;
		if (_freezeCount <= 3)
		{
			Info("第 " + _freezeCount + " 次全场植物控场 " + PlantFreezeSec.ToString("0.#")
				+ "s：挂 " + PlantHoldBuffKey + " 倍率 " + PlantHoldTimeScale.ToString("0.#")
				+ "（停止发射）+ timeScaleInit=0（暂停行动）。");
		}
		_laughCount++;
		if (_laughCount <= 3)
		{
			Info("第 " + _laughCount + " 次大笑（间隔 " + LaughIntervalSec.ToString("0.#")
				+ "s；姿态 " + LaughHoldSec.ToString("0.#") + "s）。");
		}
	}

	/// <summary>大笑期间每帧兜底：万一被状态机改回别的 clip（如重新入走），就再切回来。
	/// 用 SetClip（直接赋值）而不是 SetAnimation —— 后者会置 `sprite.blend`，
	/// 而 `GroundMoveComponent` 在 blend 期间会把位移整段丢掉 ⇒ 每帧都切会走不动。</summary>
	private void EnsureLaughClip(ZombieHook hook)
	{
		try
		{
			if (string.IsNullOrEmpty(hook.ActiveLaughClip))
			{
				return;
			}
			AdobeAnimateSprite sprite = GetSprite(hook.Character);
			if (sprite == null)
			{
				return;
			}
			if (!string.Equals(sprite.clip, hook.ActiveLaughClip, StringComparison.Ordinal))
			{
				sprite.SetClip(hook.ActiveLaughClip);
			}
		}
		catch
		{
			// 视觉兜底失败不影响逻辑：静默放弃，下一帧还会再来。
		}
	}

	/// <summary>结束大笑：把 clip 换回大笑前那一个（僵尸已死则不动，交给死亡动画）。</summary>
	private void EndLaugh(ZombieHook hook)
	{
		hook.Laughing = false;
		try
		{
			if (hook.Character != null && GodotObject.IsInstanceValid(hook.Character) && hook.Character.die)
			{
				return;
			}
			AdobeAnimateSprite sprite = GetSprite(hook.Character);
			if (sprite == null)
			{
				return;
			}
			string want = hook.PrevClip;
			if (string.IsNullOrEmpty(want) || !sprite.HasClip(want))
			{
				want = FallbackClip;
			}
			if (sprite.HasClip(want) && !string.Equals(sprite.clip, want, StringComparison.Ordinal))
			{
				sprite.SetAnimation(want, loop: true, blendTime: 0.1);
			}
		}
		catch (Exception ex)
		{
			if (!_laughFaultReported)
			{
				_laughFaultReported = true;
				Warn("恢复大笑前的动画失败（本条只报一次；下一次状态切换会自然纠正）：" + ex.Message);
			}
		}
	}

	private void PlayLaughAudio()
	{
		try
		{
			AudioManager manager = AudioManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;
			}
			// 键 = Assets/Audio/Sfx/nailong_laugh.wav 去扩展名；不在 AUDIOS 里就返回 null（不抛）。
			manager.AudioPlay(LaughAudioKey, AudioManagerEnum.TYPE.SFX, 0.0, true, false);
		}
		catch (Exception ex)
		{
			if (!_audioFaultReported)
			{
				_audioFaultReported = true;
				Warn("播放大笑音效失败（本条只报一次；大笑立绘与植物冻结不受影响）：" + ex.Message);
			}
		}
	}

	// ================================================================ 植物控场（停止发射）

	/// <summary>
	/// 让全场植物在大笑期间停止发射子弹。
	///
	/// 两件事同时做：
	///   ① **攻速 buff**（真正的修复）—— 给每株植物挂
	///      `TowerDefenseCharacterBuffAttackSpeedDown { timeScaleValue = 0, time = 1 }`。
	///      `BuffComponent.GetAttackSpeedMultiplier()` 会返回 `Math.Max(0, 0)` = 0，
	///      而**所有**发射组件都把这一项乘进自己的发射计时器：
	///        `FireComponent.cs:1683/1687/1693/3298`、
	///        `CannonComponent.cs:943/1344`、`CatapultComponent.cs:538`
	///      ⇒ 计时器推进量恒为 0 ⇒ 一颗子弹都打不出来，且不挑组件、不挑模式。
	///      （这正是旧做法失效的原因：`timeScale=0` 会被
	///       `FireComponent:1687` 的 IZM 分支与 `CannonComponent:1344` 的
	///       `flag ? 1.0 : ...` 绕过，而 buff 倍率绕不过去。）
	///      到期由 buff 自己的 `Step()` 自动过期（`time` 秒），这里也显式摘一次。
	///   ② **`timeScaleInit = 0`**（观感）—— 让植物整株僵住、动画停住，
	///      兑现需求里的「暂停行动」。它不负责发射，只负责动作。
	///
	/// **只碰自己挂的 buff**：若某株植物本来就有 `AttackSpeedDown`（埃德加二世的火球
	/// 会挂 0.5×/15s），直接跳过它，既不覆盖也不回收。
	/// </summary>
	private void HoldPlantFire(ulong now, bool keepDeadline)
	{
		try
		{
			if (_tree == null || !GodotObject.IsInstanceValid(_tree))
			{
				return;
			}
			Godot.Collections.Array<Node> plants = _tree.GetNodesInGroup("Plant");
			if (plants != null)
			{
				for (int i = 0; i < plants.Count; i++)
				{
					TowerDefenseCharacter plant = plants[i] as TowerDefenseCharacter;
					if (plant == null || !GodotObject.IsInstanceValid(plant))
					{
						continue;
					}
					BuffComponent buff = plant.buff;
					// BuffComponent 不是 GodotObject（CharacterComponentRuntime 是纯 C# 类），
					// 所以不能用 GodotObject.IsInstanceValid —— 用组件自己的 IsReleased。
					if (buff == null || buff.IsReleased)
					{
						continue;
					}

					bool ours = _holdTargets.Contains(plant);
					// 已经有 AttackSpeedDown 且不是我们挂的 ⇒ 是游戏自己的减速，别动。
					if (!ours && buff.BuffGet(PlantHoldBuffKey) != null)
					{
						continue;
					}
					if (!ours)
					{
						_holdTargets.Add(plant);
					}
					// 每次都给一份**新实例**：EnterBuff 是直接存进字典（不克隆），
					// 共用一份会让 buff.character / currentTime 被后一株植物冲掉。
					// 同一株上重复 AddBuff 会走 Refresh 分支，把 currentTime 归零（延长窗口）。
					buff.AddBuff(new TowerDefenseCharacterBuffAttackSpeedDown
					{
						timeScaleValue = PlantHoldTimeScale,
						time = PlantFreezeSec
					});
					_holdBuffCount++;
					if (_holdBuffCount <= 3)
					{
						Info("已给植物挂 " + PlantHoldBuffKey + "（倍率 "
							+ PlantHoldTimeScale.ToString("0.#") + "、"
							+ PlantFreezeSec.ToString("0.#") + "s）⇒ 停止发射。节点="
							+ plant.Name + "。");
					}
					// ② 观感：整株僵住。原值先记下来，窗口结束原样写回。
					if (!_holdTimeScale.ContainsKey(plant))
					{
						_holdTimeScale[plant] = plant.timeScaleInit;
					}
					plant.timeScaleInit = 0.0;
				}
			}
			if (!keepDeadline)
			{
				_holdEndMsec = now + PlantFreezeMsec;
			}
		}
		catch (Exception ex)
		{
			if (!_freezeFaultReported)
			{
				_freezeFaultReported = true;
				Warn("植物控场失败（本条只报一次；大笑立绘与音效不受影响）：" + ex.Message);
			}
		}
	}

	private void AdvanceHold(ulong now)
	{
		if (_holdTargets.Count == 0)
		{
			return;
		}
		if (now < _holdEndMsec)
		{
			return;
		}
		ReleasePlantFire();
	}

	/// <summary>结束控场：摘掉**我们挂的** buff，并把 timeScaleInit 写回原值。绝不抛。</summary>
	private void ReleasePlantFire()
	{
		if (_holdTargets.Count == 0 && _holdTimeScale.Count == 0)
		{
			return;
		}
		try
		{
			for (int i = 0; i < _holdTargets.Count; i++)
			{
				TowerDefenseCharacter plant = _holdTargets[i];
				if (plant == null || !GodotObject.IsInstanceValid(plant)
					|| !plant.IsInsideTree())
				{
					continue;
				}
				BuffComponent buff = plant.buff;
				if (buff != null && !buff.IsReleased)
				{
					buff.DeleteBuff(PlantHoldBuffKey);
				}
			}
		}
		catch (Exception ex)
		{
			if (!_freezeFaultReported)
			{
				_freezeFaultReported = true;
				Warn("摘除攻速 buff 失败（本条只报一次）：" + ex.Message);
			}
		}
		try
		{
			foreach (KeyValuePair<TowerDefenseCharacter, double> pair in _holdTimeScale)
			{
				TowerDefenseCharacter plant = pair.Key;
				if (plant != null && GodotObject.IsInstanceValid(plant)
					&& plant.IsInsideTree())
				{
					plant.timeScaleInit = pair.Value;
				}
			}
		}
		catch (Exception ex)
		{
			if (!_freezeFaultReported)
			{
				_freezeFaultReported = true;
				Warn("恢复植物 timeScaleInit 失败（本条只报一次）：" + ex.Message);
			}
		}
		finally
		{
			_holdTargets.Clear();
			_holdTimeScale.Clear();
			_holdEndMsec = 0UL;
		}
	}

	// ================================================================ 取节点

	private static AdobeAnimateSprite GetSprite(TowerDefenseCharacter character)
	{
		try
		{
			if (character == null || !GodotObject.IsInstanceValid(character))
			{
				return null;
			}
			AdobeAnimateSprite sprite = character.sprite;
			if (sprite == null || !GodotObject.IsInstanceValid(sprite))
			{
				return null;
			}
			return sprite;
		}
		catch
		{
			return null;
		}
	}

	private static string ReadClip(TowerDefenseCharacter character)
	{
		try
		{
			AdobeAnimateSprite sprite = GetSprite(character);
			return (sprite == null) ? null : sprite.clip;
		}
		catch
		{
			return null;
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
			if (!string.Equals(config.name, ConfigName, StringComparison.Ordinal))
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
			hook.Laughing = false;
			hook.PrevClip = null;
			hook.ActiveLaughClip = null;
			// ★★ 需求 2 的「出场时首次不触发」：接管这一刻起算 10 秒后的第一次才是首次。
			hook.NextLaughMsec = Time.GetTicksMsec() + LaughIntervalMsec;
			hook.LaughEndMsec = 0UL;

			_hooks.Add(hook);
			if (_hooks.Count <= 3)
			{
				Info("已接管第 " + _hooks.Count + " 只「" + ConfigName + "」；首次大笑在 "
					+ LaughIntervalSec.ToString("0.#") + "s 后。");
			}
		}
		catch (Exception ex)
		{
			if (!_hookFaultReported)
			{
				_hookFaultReported = true;
				Warn("读取角色配置失败（本条只报一次；不影响正常行走/啃食）：" + ex.Message);
			}
		}
	}

	// ================================================================ 卡库

	/// <summary>
	/// 把卡补进共享卡库 `GeneralZombie` 的 `Zombie` 分类 —— 决定「选卡界面 / 关卡编辑器里能不能选到它」。
	/// 依据：`Almanac.cs:220` `zombiePacketBank = GetPacketBankData("GeneralZombie")` 是**同一实例**，
	/// `Almanac.InitZombie()` 读 `GetCategory("Zombie")`，
	/// `TowerDefenseBattleFeaturePacketBank.CategoryChooseAsync` 也按 `packetBankData.category[分类]` 列卡
	/// ⇒ 补一处 = 三处同时生效。幂等：每次扫描都检查，缺了再补，补上才打日志。
	/// </summary>
	private void TryPatchCardBanks()
	{
		try
		{
			ResourceManager manager = ResourceManager.Instance;
			if (manager == null || !GodotObject.IsInstanceValid(manager))
			{
				return;
			}
			Dictionary<string, TowerDefensePacketBankData> banks = manager.TOWERDEFENSE_PACKETBANKS;
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
		bool present = false;
		for (int i = 0; i < list.Count; i++)
		{
			if (string.Equals(list[i].AsString(), ConfigName, StringComparison.Ordinal))
			{
				present = true;
				break;
			}
		}
		if (present)
		{
			return false;
		}
		list.Add(ConfigName);
		categories[ZombieCategory] = list;   // 显式回写（Array 是引用语义，写回最稳）
		Info("已把「" + ConfigName + "」补进卡库「" + bankKey + "」的「" + ZombieCategory
			+ "」分类 ⇒ 选卡界面/关卡编辑器里可以选到它了。");
		return true;
	}

	/// <summary>
	/// 图鉴僵尸页**运行时去重**。
	///
	/// 根因（`Prefab/GUI/DialogBox/Almanac/Almanac.cs`）：`InitZombie()` 有**两条独立来源**
	/// 且**都不去重** —— 共享卡库的 `Zombie` 分类（本插件补进去的那条）与
	/// `XWModContentCatalog.GetPackets(plants: false)`（引擎把 `Resources/Cards/` 注册成
	/// `Packet` 类别后自动收录）⇒ 同一张卡在图鉴僵尸页出现**两条**。
	///
	/// 两条都不能删（卡库那条删了选卡界面选不到；`Resources/Cards/` 那条删了
	/// `TOWERDEFENSE_PACKETS` 里就没有 config 了）⇒ 只能「在图鉴侧就地抹掉重复项」。
	/// 做法：反射取 `Almanac._zombieLogicalConfigs` 的**列表引用**，把 `saveKey == ZombieNaiLong`
	/// 的重复项（保留最靠前的一条）原地 `RemoveAt`，再用**公开**的
	/// `Almanac.QueueZombieVirtualRefresh()` 重建虚拟列表。幂等、绝不抛。
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
			int removed = DedupeSaveKey(list, ConfigName);
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
				Warn("图鉴僵尸页去重失败（本条只报一次；不影响角色本体、大笑与选卡）：" + ex.Message);
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

	/// <summary>`GeneralZombie` 自身 + 所有通过 `Include` 间接包含它的卡库（递归合并语义）。</summary>
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
