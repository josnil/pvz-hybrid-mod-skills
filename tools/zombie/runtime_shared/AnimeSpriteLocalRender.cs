// AnimeSpriteLocalRender.cs —— 让「自制 .dat 皮肤」的动画逐帧播放（植物 / 僵尸共用）
//
// ── 为什么需要它 ────────────────────────────────────────────────────────────
// 自制皮肤走 standalone `.dat`（`animeFile = "./Xxx.dat"`），**不在引擎的全局图集清单里**
// ⇒ `AdobeAnimateSprite` 的 `GpuPoseTextureRid` 无效 ⇒ `_runtimeGpuClockInterpolationActive`
// 为假 ⇒ 精灵只在 `RequestNodeRedraw`（按 ESC 暂停再恢复才会触发）时前进一帧。
// 表现出来就是「动画完全静止，只有暂停一次跳一帧」。
//
// 修法：把这类精灵切到**本地 CPU 姿态**渲染：
//     forceLocalRender   = true   (AdobeAnimateSprite.cs:1141)
//     forceCpuPoseRender = true   (AdobeAnimateSprite.cs:1166)
// 两者都是 `public bool` **属性但不带 `[Export]`** ⇒ 写不进 `.tscn` / `.tres`，
// **只能运行期由托管入口设**。引擎自己的先例：`PacketPickControl.cs:401-402`（两个一起设）。
// `Almanac.cs:1139` 只设了 `forceLocalRender` ⇒ 图鉴预览仍会走 GPU 位姿提交（也会静止），
// 所以**两个必须一起设**。
//
// ── 调用契约 ────────────────────────────────────────────────────────────────
// 调用方在**周期性的整树扫描**里对每个 `AdobeAnimateSprite` 调 `Patch()`：
//   · 返回 `Patched` 才打日志（幂等：已经设过就返回 `AlreadyLocal`，不重复打）；
//   · **不能只在初始化时做一次**：引擎会把 `forceCpuPoseRender` 放掉
//     （`ReleaseForcedCpuPoseData`），且图鉴 / 选卡 / 种植预览各自是**独立实例**，
//     所以必须反复扫（调用方通常每 N 帧扫一次整棵树）。
//
// ⚠️ 本文件是**单一真源**，两个插件工程各自 `<Compile Include>` 它（与
//    `GatlingVolleyCore.cs` 同一套做法：共用源文件，不共用程序集）。
//    现状：僵尸入口已改用本文件；植物入口仍保留一份等价的内联实现
//    （`runtime_src_plant/SuperGatlingPeaRuntimeEntry.cs` 的 `TryPatchSkinRender`），
//    下次重建植物包时应迁移过来，消除两处漂移。

using System;
using Godot;

public static class AnimeSpriteLocalRender
{
	/// <summary>
	/// 认定「自制皮肤」的字符串标记：本工坊两份自制外观都叫 `SuperGatlingPea`，
	/// 且内置资源里**不存在**这个名字（内置只有 `GatlingPea` / `GatlingPeaZ` 等）。
	/// 判据取两个稳定字符串，任一命中即认定（大小写不敏感）：
	///   · `animeFile`   —— 自制外观是相对路径 `"./SuperGatlingPea.dat"`，
	///                      内置一律是 `res://Asset/Anime/.../<Key>.dat`；
	///   · `ResourcePath` —— 运行时由 mod 挂载路径加载，含文件名。
	/// 为什么不按对象引用比对：图鉴 / 选卡预览里的精灵与战斗里的不是同一个实例，
	/// 而且用户可能根本没进战斗就开图鉴 ⇒ 没有「已见过的那一份」可以比。
	/// </summary>
	public const string SkinDataToken = "SuperGatlingPea";

	/// <summary>不是本工坊自制皮肤 —— 不要动它。</summary>
	public const int NotApplicable = 0;

	/// <summary>这一轮真的写入了两个开关（调用方打日志用）。</summary>
	public const int Patched = 1;

	/// <summary>本来就是本地 CPU 姿态（幂等，无需重复写、无需打日志）。</summary>
	public const int AlreadyLocal = 2;

	/// <summary>节点还没进树 / 没 ready —— 现在设语义不明确，**下一轮扫描再来**。</summary>
	public const int NotReady = -1;

	/// <summary>
	/// 幂等地把「本工坊自制皮肤」精灵切到本地 CPU 姿态渲染。
	/// 只读 + 可能在异常时安全降级（返回 `NotApplicable`），**绝不抛**。
	/// </summary>
	public static int Patch(AdobeAnimateSprite sprite)
	{
		try
		{
			if (sprite == null || !GodotObject.IsInstanceValid(sprite))
			{
				return NotApplicable;
			}
			// 未就绪的节点上设这两个属性会走进 `SetProcessEnabled(_canRun && …)` 分支，
			// 语义不明确 ⇒ 等它 ready 了再补。
			if (!sprite.IsInsideTree() || !sprite.IsNodeReady())
			{
				return NotReady;
			}
			AdobeAnimateData data = sprite.flashAnimeData;
			if (!IsOurSkinData(data))
			{
				return NotApplicable;
			}
			if (sprite.forceLocalRender && sprite.forceCpuPoseRender)
			{
				return AlreadyLocal;
			}
			sprite.forceLocalRender = true;
			sprite.forceCpuPoseRender = true;
			return Patched;
		}
		catch
		{
			// 读/写属性失败就当不是本工坊皮肤（安全降级：保持引擎默认行为）
			return NotApplicable;
		}
	}

	/// <summary>这份 `AdobeAnimateData` 是不是本工坊自制外观（见 `SkinDataToken` 注释）。</summary>
	public static bool IsOurSkinData(AdobeAnimateData data)
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
		}
		return false;
	}

	/// <summary>日志用的可读标识（`.tres` 的路径，读不到就退回 `animeFile`）。</summary>
	public static string Describe(AdobeAnimateData data)
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
}
