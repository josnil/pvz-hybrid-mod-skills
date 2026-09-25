// ---------------------------------------------------------------------------
//   「超级机枪」系列（植物 SuperGatlingPea / 僵尸 ZombieSuperGatlingPaper）
//   **共用**的射击判定核心 —— 单一真源（single source of truth）。
// ---------------------------------------------------------------------------
//
//   用户需求（2026-09-22）：植物与僵尸共用同一套「射击判定逻辑」。
//
//   为什么是「共享源文件」而不是「共享程序集」：
//     两个 .pmod 必须各自带一份路径恰好为 `Runtime/ModAssembly.dll` 的程序集，
//     且 runtimeEntryType 不同 ⇒ 没法共享程序集。但两个 csproj 可以
//     `<Compile Include="../runtime_shared/GatlingVolleyCore.cs" Link="..." />`
//     编译**同一份源文件** ⇒ 判定逻辑只有一个真源，改一处两边同时生效，
//     永远不会出现「植物改了、僵尸忘了」这种漂移。
//
//   本文件刻意**不引用任何游戏类型**（只用 Godot 的 RandomNumberGenerator
//   和 System 的 Math）⇒ 两个工程都能原样编译，也便于单独推理。
//
//   参数值的语义与出处：
//     · 普攻 1.5s / 7 颗 / 间距 0.1s、大招 10% / 5s / 300 颗 / ±15°
//       —— 两条 Mod 的用户需求逐字相同；
//     · 250ms 卡顿阈值 —— `SceneTree` 暂停时 `process_frame` 照常发信号，
//       不抹掉欠账的话「继续」那一帧会一口气喷出几百颗豌豆；
//     · 单帧 12 颗上限 —— 防掉帧时雪崩式创建子弹对象。
// ---------------------------------------------------------------------------

using System;
using Godot;

/// <summary>
/// 共用参数。两版插件里同名的 <c>private const</c> 全部改成引用这里
/// （`const X = GatlingVolleyParams.X;` 仍是**编译期常量**，取值处零开销）。
/// </summary>
internal static class GatlingVolleyParams
{
	/// <summary>普攻周期（秒）：每 1.5 秒一轮。</summary>
	public const double AttackIntervalSeconds = 1.5;

	/// <summary>
	/// 普攻周期（毫秒）= <see cref="AttackIntervalSeconds"/> × 1000。
	/// ⚠️ 写成字面量才是编译期常量（`(ulong)Math.Round(...)` 不是）。
	/// </summary>
	public const ulong AttackIntervalMsec = 1500;

	/// <summary>一轮常规攻击的颗数：7 颗，仅直线（不散射）。</summary>
	public const int PeasPerAttack = 7;

	/// <summary>常规连发链的颗间距（秒）：7 颗排成一条直线向前飞。</summary>
	public const double PeaSpacingSeconds = 0.1;

	/// <summary>常规连发链的颗间距（毫秒）= <see cref="PeaSpacingSeconds"/> × 1000。</summary>
	public const ulong PeaSpacingMsec = 100;

	/// <summary>每次攻击触发大招的概率：10%。</summary>
	public const double UltimateChance = 0.10;

	/// <summary>大招持续时间（秒）。</summary>
	public const double UltimateSeconds = 5.0;

	/// <summary>大招总颗数：逐颗发射 ⇒ 能做到**恰好** 300。</summary>
	public const int UltimatePeas = 300;

	/// <summary>大招散射半角（度）：±15°。</summary>
	public const double ScatterHalfAngleDeg = 15.0;

	/// <summary>大招颗间距（毫秒）= 5000 / 300 ≈ 16.667。</summary>
	public const double BurstIntervalMsec = UltimateSeconds * 1000.0 / UltimatePeas;

	/// <summary>单帧最多发射几颗：防掉帧时一次性创建几百个子弹对象。</summary>
	public const int MaxPeasPerFrame = 12;

	/// <summary>两帧间隔超过它就认为「暂停 / 长卡顿」，把各条时间轴整体后移。</summary>
	public const ulong StallThresholdMsec = 250;
}

/// <summary>
/// 共用判定函数。两版插件各自的「节拍外壳」不同（植物由引擎
/// <c>FireComponent.OnFireReady</c> 触发、僵尸自建毫秒计时器），
/// 但**判定内容**完全一样 —— 全部收在这里，只此一份。
/// </summary>
internal static class GatlingVolleyJudge
{
	/// <summary>
	/// 掷大招骰：命中 ⇒ 本轮从「7 颗直线」变成「5 秒 300 颗 ±15° 散射」。
	/// 用引擎随机源（真随机）；联机会与主机不同步，这是刻意接受的代价。
	/// </summary>
	public static bool RollUltimate(RandomNumberGenerator rng)
	{
		return rng != null && (double)rng.Randf() < GatlingVolleyParams.UltimateChance;
	}

	/// <summary>大招第 index 颗的散射角：均匀落在 ±<see cref="GatlingVolleyParams.ScatterHalfAngleDeg"/> 内。</summary>
	public static float ScatterAngleDeg(RandomNumberGenerator rng)
	{
		float half = (float)GatlingVolleyParams.ScatterHalfAngleDeg;
		return rng == null ? 0f : rng.RandfRange(-half, half);
	}

	/// <summary>
	/// 大招第 index 颗（0 基）的计划时刻 = 起点 + (index+1) × 颗间距。
	/// 用「按颗数算时刻」而不是「每次 += 间隔」⇒ 完全避免浮点累加漂移，
	/// 从而保证恰好 <see cref="GatlingVolleyParams.UltimatePeas"/> 颗、恰好 5 秒。
	/// </summary>
	public static ulong BurstDueMsec(ulong burstStartMsec, int index)
	{
		return burstStartMsec
			+ (ulong)Math.Round((index + 1) * GatlingVolleyParams.BurstIntervalMsec);
	}

	/// <summary>
	/// 暂停 / 长卡顿：把三条时间轴整体后移，欠账作废（**不补发**）。
	/// 僵尸版形态：普攻轴 + 连发链轴 + 大招轴。
	/// </summary>
	public static void ShiftTimeline(ref ulong nextAttackMsec, ref ulong nextChainMsec,
		ref ulong burstStartMsec, ulong gapMsec)
	{
		if (gapMsec == 0)
		{
			return;
		}
		nextAttackMsec += gapMsec;
		nextChainMsec += gapMsec;
		burstStartMsec += gapMsec;
	}

	/// <summary>
	/// 暂停 / 长卡顿：植物版形态 —— 只有「连发链」与「大招」两条轴
	/// （没有自计时普攻轴，普攻由 `OnFireReady` 外部触发）。
	/// </summary>
	public static void ShiftTimeline(ref ulong nextPeaMsec, ref ulong burstStartMsec, ulong gapMsec)
	{
		if (gapMsec == 0)
		{
			return;
		}
		nextPeaMsec += gapMsec;
		burstStartMsec += gapMsec;
	}

	/// <summary>
	/// 本帧相对上一帧的「暂停 / 长卡顿」补偿量（毫秒）。
	/// 返回 0 = 首帧 / 正常帧；&gt; 0 = 该值就是需要补偿的间隔。
	/// </summary>
	public static ulong StallGap(ulong lastMsec, ulong now)
	{
		if (lastMsec == 0 || now <= lastMsec)
		{
			return 0;
		}
		ulong gap = now - lastMsec;
		return gap > GatlingVolleyParams.StallThresholdMsec ? gap : 0;
	}
}
