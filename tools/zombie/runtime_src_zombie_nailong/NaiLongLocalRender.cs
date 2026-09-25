// NaiLongLocalRender.cs —— 让「奶龙僵尸」自制 .dat 皮肤逐帧播放
//
// 与 runtime_shared/AnimeSpriteLocalRender.cs 是**同一套做法、不同的皮肤标识**。
// 为什么不复用那一份：那里的 SkinDataToken 是常量 "SuperGatlingPea"
// ⇒ 换皮肤就得换 token，而 token 是 const ⇒ 只能各自一份（两包各自自带 ModAssembly.dll，
//    程序集互不干扰）。逻辑逐行等价，只是 token 改成 "NaiLong"。
//
// ── 为什么需要它 ────────────────────────────────────────────────────────────
// 自制皮肤走 standalone `.dat`（`animeFile = "./NaiLong.dat"`），不在引擎的全局图集清单里
// ⇒ `AdobeAnimateSprite.GpuPoseTextureRid` 无效 ⇒ `_runtimeGpuClockInterpolationActive` 为假
// ⇒ 精灵只在 `RequestNodeRedraw` 时才前进一帧 ⇒ 表现为「动画完全静止」。
// 修法：`forceLocalRender = true` + `forceCpuPoseRender = true`
// （两者都是 public bool 属性、**不带 [Export]** ⇒ 只能运行期设，且引擎会
//  `ReleaseForcedCpuPoseData` 放掉 ⇒ 必须**周期性整树扫描**反复补）。
// 调用契约与幂等语义详见 runtime_shared 那份的同名注释。

using System;
using Godot;

public static class NaiLongLocalRender
{
	/// <summary>认定「本 Mod 自制皮肤」的字符串标记（`animeFile` 或 `ResourcePath` 命中即可）。</summary>
	public const string SkinDataToken = "NaiLong";

	/// <summary>不是本 Mod 自制皮肤 —— 不要动它。</summary>
	public const int NotApplicable = 0;

	/// <summary>这一轮真的写入了两个开关（调用方打日志用）。</summary>
	public const int Patched = 1;

	/// <summary>本来就是本地 CPU 姿态（幂等，无需重复写、无需打日志）。</summary>
	public const int AlreadyLocal = 2;

	/// <summary>节点还没进树 / 没 ready —— 现在设语义不明确，**下一轮扫描再来**。</summary>
	public const int NotReady = -1;

	/// <summary>幂等地把「本 Mod 自制皮肤」精灵切到本地 CPU 姿态渲染。绝不抛。</summary>
	public static int Patch(AdobeAnimateSprite sprite)
	{
		try
		{
			if (sprite == null || !GodotObject.IsInstanceValid(sprite))
			{
				return NotApplicable;
			}
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
			// 读/写属性失败就当不是本 Mod 皮肤（安全降级：保持引擎默认行为）
			return NotApplicable;
		}
	}

	/// <summary>这份 `AdobeAnimateData` 是不是本 Mod 自制外观。</summary>
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

	/// <summary>日志用的可读标识。</summary>
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
