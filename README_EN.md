# PvZ Hybrid Mod Authoring Skills (WorkBuddy Agent Skills)

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows-blue)]()
[![Game](https://img.shields.io/badge/game-PvZ%20Hybrid%20V0.28%20(Godot%204%20%2B%20C%23)-orange)]()

> 🤖 **These skills run inside [WorkBuddy](https://www.workbuddy.cn).**
> **Invitation link for new users:** <https://www.workbuddy.cn/events/invite?inviteCode=ryoc35nu7pi1nq>
> This link is the **new-user invitation/registration portal of WorkBuddy**, the AI agent workbench that hosts and drives these three skills (conversational mod authoring, automatic skill loading, automated offline gates). Register through the link and you can install and use the skills from this repo right away.

A **WorkBuddy Agent Skills** collection for modding *Plants vs. Zombies Hybrid Edition* (Godot 4 + C#). It consists of three interlocking skills: a universal `.pmod` package-format encyclopedia, plus two end-to-end pipelines — one for plants, one for zombies. Everything here comes from repeated, real-project testing: every "iron rule" corresponds to an actual pitfall, and every pitfall includes its root cause with engine-source-level evidence.

> 🚀 **First time here? Start with [GETTING_STARTED.md](GETTING_STARTED.md)** — build your first in-game stat mod in about 30 minutes, no unpacking and no code required.

> 🇨🇳 Chinese documentation: [README.md](README.md)

---

## Table of Contents

- [🚀 Quick Start (for beginners)](GETTING_STARTED.md)
- [What Is This](#what-is-this)
- [The Three Skills at a Glance](#the-three-skills-at-a-glance)
- [Repository Layout](#repository-layout)
- [Installation & Configuration](#installation--configuration)
- [Skill Details](#skill-details)
  - [pvz-hybrid-mod-authoring (universal base)](#1-pvz-hybrid-mod-authoring-universal-base)
  - [pvz-hybrid-plant-authoring (plant pipeline)](#2-pvz-hybrid-plant-authoring-plant-pipeline)
  - [pvz-hybrid-zombie-authoring (zombie pipeline)](#3-pvz-hybrid-zombie-authoring-zombie-pipeline)
- [Environment & Dependencies](#environment--dependencies)
- [Standard Workflow (How the Skills Fit Together)](#standard-workflow-how-the-skills-fit-together)
- [Important Notes](#important-notes)
- [FAQ](#faq)
- [License](#license)

---

## What Is This

A mod for *PvZ Hybrid Edition* is a `.pmod` file (essentially `zip + root mod.json`). The game ships with an F3 in-game GUI mod editor, but it **cannot be driven by AI**; a `.pmod`, however, can be generated purely by scripts — and that is the foundation of this whole skill set.

The three skills turn "from a one-sentence requirement to an installable, playable mod" into operational manuals an AI can execute precisely:

- **Knowledge documents + reusable tools**: the skills deliver validated **methodology and hard constraints** (package format, field semantics, firing pipeline, render pipeline, offline gate design); the generators, gate scripts and the GUI editor they reference are published in this repo under [`tools/`](tools/README.md), ready to reuse or adapt.
- **Why trust it?** Every conclusion defers to engine source code (`addons/ModEditor/ModSystem/`, `Script/Component/`) as the final arbiter, and the verification methodology includes negative tests that prove the gates themselves are not "fake green".

## The Three Skills at a Glance

| Skill | Role | One-liner | Size |
|---|---|---|---|
| **pvz-hybrid-mod-authoring** | Universal base (encyclopedia) | Hand-write/generate `.pmod` of any category: projectiles, maps, characters, shop, audio, atlases…; includes the `mod_editor.py` GUI-editor workflow and a "single screenshot → character sprite" pipeline | Single SKILL.md, ~159 KB |
| **pvz-hybrid-plant-authoring** | Plant-specific pipeline | Build a plant mod from scratch: stats, cards, almanac, firing (rate/count/spread), skins, managed C# plugins (probability/burst/true-random) | SKILL.md + 7 references + 1 checklist |
| **pvz-hybrid-zombie-authoring** | Zombie-specific pipeline | Build a zombie mod from scratch: armor set, three-node head swap, giving zombies firing, muzzle-aligned bullet spawn, almanac dedup | SKILL.md + 3 references |

Relationship: **mod-authoring is the dictionary; plant/zombie are two construction blueprints**. Both pipeline skills declare their boundary up front — package-format details go back to the base skill; sequence and hard constraints follow the pipeline skill.

## Repository Layout

```
pvz-hybrid-mod-skills/
├── README.md                       # Chinese documentation
├── README_EN.md                    # This file
├── GETTING_STARTED.md              # 🚀 Beginner quick start (first mod in ~30 min)
├── LICENSE                         # MIT
├── skills/                         # Three skill modules; each folder installs independently
    ├── pvz-hybrid-mod-authoring/
    │   └── SKILL.md                # Main skill doc (all iron rules + package-format details)
    ├── pvz-hybrid-plant-authoring/
    │   ├── SKILL.md                # 12-step flow + Top-15 pitfalls
    │   ├── assets/
    │   │   └── 新建植物清单.md      # Pre-flight requirement checklist (Chinese)
    │   └── references/
    │       ├── plant-package-and-gates.md   # Packaging & 8 hard gates
    │       ├── plant-data-fields.md         # Stat fields / card bank / direct planting
    │       ├── plant-fire-pipeline.md       # Firing pipeline & animation event table
    │       ├── plant-skin.md                # Skin "three-piece set"
    │       ├── plant-runtime-plugin.md      # Managed C# plugin recipes
    │       ├── plant-verification.md        # Offline gates & acceptance
    │       └── plant-pmod-hotpatch.md       # Hot-patching stats when only .pmod remains
    └── pvz-hybrid-zombie-authoring/
        ├── SKILL.md                # 12-step flow + Top-10 pitfalls
        └── references/
            ├── zombie-package-and-gates.md  # 13-file package / armor / card bank
            ├── zombie-fire-and-marker.md    # Firing system / muzzle-aligned spawn point
            └── zombie-skin-and-head.md      # Skins / three-node head swap / head-fit quantification
└── tools/                          # Companion toolchain & template generators (see tools/README.md)
    ├── pmod-toolchain/             # .pmod build/verify/hot-patch + GUI editor + pure-resource sample mod
    ├── plant/                      # Plant pipeline template generator + plugin source + offline gates
    ├── zombie/                     # Zombie templates ×3 + shared sources + gates + head-fit tools
    ├── map/                        # Map pipeline template + gates
    ├── skin/                       # Classic reanim → .dat/.tres/atlas conversion pipeline
    └── case-docs/                  # Five full case-study delivery documents
```

## Installation & Configuration

### Prerequisites

1. **WorkBuddy** (recommended — register via the invitation link at the top): skills are auto-loaded and executed by the WorkBuddy AI agent.
2. An unpacked copy of *PvZ Hybrid Edition* **V0.28** (the skills constantly consult engine source `.cs` files and the `Asset/` structure as ground truth).
3. See [Environment & Dependencies](#environment--dependencies).

### Steps

1. Clone the repo (or download and extract the ZIP):

   ```bash
   git clone https://github.com/<your-account>/pvz-hybrid-mod-skills.git
   ```

2. Copy the skill folders you need into a skills directory (**each folder installs independently**):

   - **User-level** (available in all projects): `C:\Users\<you>\.workbuddy\skills\`
   - **Project-level** (current project only): `<your-workspace>\.workbuddy\skills\`

   ```bash
   # Example: install all three skills at user level
   cp -r skills/pvz-hybrid-mod-authoring   ~/.workbuddy/skills/
   cp -r skills/pvz-hybrid-plant-authoring ~/.workbuddy/skills/
   cp -r skills/pvz-hybrid-zombie-authoring ~/.workbuddy/skills/
   ```

3. Restart your WorkBuddy session, then just talk to the agent, e.g.:
   - "Make a plant mod with double fire rate" → plant skill triggers;
   - "Give the zombie a sunflower-queen head" → zombie skill triggers;
   - "Change the projectile damage in this .pmod" → mod-authoring triggers.

> Not using WorkBuddy? The skills are structured Markdown knowledge bases and read perfectly well as developer handbooks — start from each SKILL.md's "standard flow" section.

## Skill Details

### 1. pvz-hybrid-mod-authoring (universal base)

**What it does**: the complete encyclopedia of the `.pmod` format. Covers overriding built-in resources (projectiles / maps / characters / levels / shop / collectibles / shovel / lawnmowers / survival / tutorial / NPC dialogue / BGM / audio / textures / atlases) and managed-code mods (C# DLL). Includes the out-of-game GUI editor `mod_editor.py` workflow (edit stats / package / validate without writing code) and a "single character screenshot → character sprite with animation" (matting + frame-by-frame) pipeline.

**Key contents**:

- **Prerequisite mental model**: the in-game F3 editor is a GUI that AI cannot drive; `.pmod = zip + root mod.json` can be script-generated.
- **Package structure**: `mod.json` must be at the root and unique (≤ 1 MiB); categories derive from `Resources/<category>/<file>.tres` path prefixes; packaging exclusion list (`.uid` `.import` `.cs` `.csproj` `.sln` …).
- **Two forms**: `.pmod` (loaded by game) vs project folder (opened by editor) — the classic time-waster.
- **Path-prefix → (category, key) full table** + **iron rules** (violations fail loading).
- **Map deep-dive**: `TowerDefenseMapConfig` coordinates (1-based, closed interval), row-addition geometry, background replacement.
- **Plant / zombie deep-dives**: 6-file plant package, firing pipeline (`ComponentSet`), `FireMarker` muzzle, skin "three-piece set" (`.tscn` + `.tres` + `.dat`), HP & direct-plant-on-empty-ground, the four key zombie-vs-plant differences.
- **Managed-code mods**: four hard constraints, `Runtime/` may contain exactly one `ModAssembly.dll`, entry-class discipline, verifying without launching the game.
- **Character sprite authoring**: matting (including the soft-moss-background failure boundary), part-layered animation, quantified delivery checks.

**How to use**: auto-triggered by WorkBuddy from the description; can also be named explicitly. Use its iron rules and lookup tables as the dictionary for the other two skills.

**Main dependencies**: see [Environment & Dependencies](#environment--dependencies); the GUI editor and matting scripts need Python + Pillow.

### 2. pvz-hybrid-plant-authoring (plant pipeline)

**What it does**: a 12-step end-to-end flow for a plant mod, centered on four decisions: reuse a built-in plant or build fresh; whether a managed C# plugin is required; skin via official-asset conversion or hand-made; whether the card enters the seed-selection UI and almanac.

**Key contents**:

- **12-step standard flow**: gather requirements → clone the generator and edit constants (`CHAR_KEY` must match in four places) → 6-file package → explicitly declare `ComponentSet` (missing = no bullets, zero logs) → data-side firing (salvo vs per-shot hard constraints) → skin → card into selection/almanac (with side effects) → HP / direct-plant → plugin → offline gates → install → in-game acceptance.
- **Top-15 pitfalls**, each with root-cause source references — including the famous "child sprites are always drawn by the parent" (⇒ head swaps require three nodes), `>` silently swallowing `.tscn` node headers, and "assertion wrong the same way as the code = fake green".
- **Gate overview**: layered design of `self_check()`, on-disk assertions, negative tests, offline replication of ModLoader gates, idempotency checks.

**How to use**: ask the agent to "make a plant mod / change fire rate / put my card in the almanac / swap the skin". Before building, the agent opens `assets/新建植物清单.md` (Chinese checklist) to tick off requirements. Details are one lookup away via the reference index at the end of SKILL.md.

**Main dependencies**: Python 3.13+ (generator), .NET SDK (plugin builds), Pillow (official-skin conversion / hand-made skins), unpacked game tree.

### 3. pvz-hybrid-zombie-authoring (zombie pipeline)

**What it does**: the 12-step end-to-end flow for zombie mods — only the zombie path and **every difference from plants**. Zombies have no firing component by default, face left (horizontal flip), and head-follow rendering is special — all made explicit.

**Key contents**:

- **13-file package layout**: card / body config / packet entry / scene / component set / fire definition / sprite scene / armor data / armor slots / skin set / managed plugin — item by item, with hard path constraints (exactly 6 segments, `Zombies` category directory).
- **Armor system**: the Armor three-piece set, near-death rage state machine (newspaper-zombie template).
- **Three-node head swap**: `HeadShadow` + `HeadHolder` + `Head` — why naively swapping a child sprite's texture always yields "fragments of other characters" (parent-draws-child mechanism), and why pushing a child *behind* the parent only works via `insertLayerId`.
- **Giving zombies firing**: add `FireComponent` to the component set, keep exactly 1 entry in `fireProjectileList`, negative `speed` (left-facing = forward), plugin-driven cadence, `CanFireCheckOnceByData` instead of `CanFire`, **bullet spawn point realigned to the muzzle every frame**.
- **Almanac dedup**: the almanac zombie page has two non-deduplicated sources ⇒ runtime reflection dedup.
- **Quantified sizing/positioning discipline** (iron rule 30 in full): "make the head a bit bigger / nudge it up" must never be eyeballed — flood-fill segmentation on the reference image, offline composited rendering to sweep candidate scales, rigid anchors (face/crown, not the frame-animated flame petals).

**How to use**: ask the agent to "make a zombie mod / swap the head / make it shoot / add armor"; references are indexed at the end of SKILL.md.

**Main dependencies**: same as the plant pipeline, plus the `dotnet` CLI for `ModAssembly.dll`.

## Environment & Dependencies

### Hard requirements

| Dependency | Purpose | Notes |
|---|---|---|
| **WorkBuddy** (recommended) | Runtime host for the skills | Register via the [invitation link](https://www.workbuddy.cn/events/invite?inviteCode=ryoc35nu7pi1nq); works as plain docs without it |
| **PvZ Hybrid Edition V0.28 (unpacked)** | Ground-truth source | Skills read `addons/ModEditor/ModSystem/` (`ModLoader.cs`, `XWModManifest.cs`, …) and the `Asset/` structure |
| **Python ≥ 3.13** | Generators / gates / validators | Pure-math scripts need no third-party packages |
| **Pillow (PIL)** | Skin conversion, matting, offline rendering, comparison images | `pip install pillow` |

### As needed

| Dependency | When |
|---|---|
| **.NET SDK (`dotnet` CLI)** | Managed C# plugins (probability / burst / true-random / fix-frozen-animation / zombie firing cadence) to build `ModAssembly.dll` |
| **Node.js (optional)** | A few tool scripts |
| **Classic PvZ assets (reanim)** | For the "official-asset conversion" skin route (conversion scripts are not bundled; build your own per the documented pipeline) |

### Companion tools & templates (tools/)

The tools referenced by the skills **are now shipped in this repo** — see [tools/README.md](tools/README.md): the `.pmod` toolchain (`build_pmod.py` / `verify_pmod.py` / stat hot-patch / GUI editor `mod_editor.py`), template generators and managed C# plugin sources for all four pipelines, offline gate & head-fit quantification scripts, the official-asset conversion pipeline (reanim → `.dat`/`.tres`/atlas), and five full case-study delivery documents.

⚠️ These scripts come from the author's Windows environment and **some paths are hardcoded** (unpacked game tree, dual game builds). Replace them with your own paths per the "environment adaptation" section in `tools/README.md`. Version baseline is V0.28; after engine updates, defer to `addons/ModEditor/ModSystem/` source as the final arbiter.

## Standard Workflow (How the Skills Fit Together)

```
Requirement ("a sunflower-queen zombie that shoots")
   │
   ├─ ① mod-authoring: look up format & iron rules (mod.json fields, path→category table, plugin constraints)
   │
   ├─ ② zombie-authoring: walk the 12 steps
   │      Step 0 gather requirements → clone generator → 13-file package → three-node head swap
   │      → add FireComponent → managed plugin (cadence / can-fire / head pose / spawn point)
   │      → card-bank registration & almanac dedup
   │
   ├─ ③ Offline gates (gate overviews in both pipeline skills): self-check + on-disk assertions
   │      + negative tests + offline-replicated ModLoader validation + idempotency (3 runs, byte-stable)
   │
   └─ ④ Install & in-game acceptance: drop .pmod into
          %APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\Mods\
          → confirm via [ModLoader] lines in PVZHE_Logs → verify visual items in game
```

For plant mods, swap ② for the plant-authoring 12 steps.

## Important Notes

1. **Absolute paths inside the skills are the author's environment examples** (`D:\zzz\pvzHE\...`, `C:\Users\...`). They describe *where each kind of information lives* (unpacked tree, logs, mod install dir); replace them with your own equivalents. The game's user-data dir is fixed: `%APPDATA%\Godot\app_userdata\植物大战僵尸杂交版\`.
2. **Version baseline is V0.28**. Engine updates may change fields, gates, or behavior — always defer to `addons/ModEditor/ModSystem/` and `Script/Component/` source; the skills teach exactly how to arbitrate with source.
3. **Never manually delete `ModsCache`**. Restart the game after changing a package; the cache is managed automatically.
4. **No `.cs` files inside the package, ever** (same for `.exe`/`.bat`/`.cmd`/`.ps1` and other executables); `Runtime/` may contain exactly one `ModAssembly.dll`, otherwise the whole package is rejected.
5. **The in-game F3 editor cannot be automated** (GUI); all automation goes through "generate `.pmod` purely by script".
6. **Self-checks must be paired with negative tests**. Memory-text-only self-checks go "fake green" (assertion wrong the same way as the code); the skills insist every assertion be tamper-tested.
7. **Entering the card bank/almanac has side effects** (gold-card shard drops, random card draws) — the skills require informing the player; keep that step.
8. **Dual-build setups run gates twice**: the author's machine keeps remake/console builds; a single-build user runs each gate once.
9. **Respect the community rules**: mods are for personal, non-commercial use; respect the copyright and work of the original game and Hybrid Edition authors.

## FAQ

**Q1: My plant's animation plays but no bullets spawn, and nothing is logged?**
The two most common causes: ① the character scene does **not explicitly declare `ComponentSet`** (it inherits the base one without FireComponent — completely silent); ② the animation `events` table has **no `fire` entry** — normal firing is 100% animation-event driven; setting `fireAnimeClips` alone is not enough. See plant skill Step 4 / Step 5.

**Q2: Custom-skin animation is fully frozen and only advances one frame per ESC pause?**
A self-made `.dat` is not in the global atlas list ⇒ GPU pose texture invalid ⇒ frozen. Fix: a managed plugin sets `forceLocalRender = true` + `forceCpuPoseRender = true` at runtime. ⚠️ Only works if the sprite is not drawn by a parent — for child sprites it silently does nothing; use the three-node structure.

**Q3: After a head swap the head renders as fragments of other characters?**
The engine collects "direct child sprites of a sprite" by node type and **draws them in the parent's batch**, sampling the parent's shared all-characters atlas ⇒ a cross-`.tres` child sprite is always wrong. The only fix is the three-node structure (shadow consumes positioning, plain container breaks parent-drawing, visible head renders independently). See zombie skill Step 5.

**Q4: My `.pmod` is rejected outright / rolled back on load?**
Check the four hard constraints: `runtimeAssembly` must literally be `Runtime/ModAssembly.dll`; `runtimeApiVersion = 1`; callbacks must never throw; `provides`/`overrides` must declare every recognized file in the package. Also: one extra file in `Runtime/` (even `.pdb`) triggers rejection. Search `[ModLoader]` lines in `PVZHE_Logs` for keywords.

**Q5: I changed the C# source but behavior didn't change?**
Generators **never rebuild the DLL automatically** — after editing `.cs` run a separate build (two compiles compared by sha256), otherwise the package still carries the old DLL.

**Q6: "Make the head bigger / nudge it up" — guessed numbers keep being wrong?**
Iron rule: **never eyeball size/position**. With a reference image, measure it (flood-fill segmentation + offline render scale sweep + rigid anchors). Without one, take a conservative value from project precedent. And **changing `head_scale` always requires re-solving `head_offset`**. See zombie skill pitfall 11 and references §10.

**Q7: Do I need a managed plugin?**
Only for what pure data cannot do: probability triggers, timed/mode-switching fire, true randomness, per-shot firing, projectile replacement, unfreezing custom skins. Rate/count/spread/damage/cost/cooldown/card type are all pure data — don't add plugins "just to be safe".

**Q8: `Animation/LayerVisible` won't hide a layer (e.g. an extra head appears)?**
Quotes must wrap the **entire** property name: `"Animation/LayerVisible/图层_1" = false`. Quoting only the tail (`Animation/LayerVisible/"图层_1"`) makes the line **completely ineffective**, silently, and the layer stays visible.

**Q9: Should I ship translations.csv in the package?**
No. Write the Chinese name directly in the `translate` field; `translations.csv` is editor-only and merely adds a harmless diagnostic.

**Q10: Can these skills work with other AI tools?**
They are plain Markdown (frontmatter + body), so the content is portable; the "auto-trigger by description, auto-run gates" experience depends on WorkBuddy. Any AI tool with custom system prompts / knowledge bases can consume them manually.

---

## License

Released under the [MIT License](LICENSE). *Plants vs. Zombies Hybrid Edition* is copyrighted by its original authors; this repository contains only original mod-development methodology documents.
