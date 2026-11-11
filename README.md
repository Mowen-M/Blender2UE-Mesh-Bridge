# Blender2UE Mesh Bridge

**Move meshes from Blender into Unreal Engine 5.6–5.8 with the right position, rotation, scale — and the right material.**

A Blender add-on built for scene assembly: block out a city / a set / a prop group in Blender,
then land every object in UE as an individual actor at its exact world transform, with one
material per mesh, collected into a `Materials/` folder.

*Currently published: **v1.0.0*** — install ZIP in [Releases](https://github.com/Mowen-M/Blender2UE-Mesh-Bridge/releases).

---

## What it does

Two independent workflows, both verified in a real UE editor (not just unit tests):

| Workflow | What you get |
|---|---|
| **A. Copy → paste (T3D clipboard)** | Select objects in Blender, press a Copy button, `Ctrl+V` in the UE viewport. UE receives `StaticMeshActor` placeholders (BasicShapes) carrying the real transform; drop your imported mesh on them. No files, no scripts. |
| **B. Export Parts → auto-place** | One FBX per unique mesh + `placement.json` + a UE-side Python script. Running the script imports every mesh into `/Game/MeshParts`, gives each mesh its own material in `/Game/MeshParts/Materials/<part>`, creates the level, spawns one actor per part at the exact transform, adds Sun + SkyLight + SkyAtmosphere, and saves. |

Workflow B keeps the materials that came inside the FBX. Only meshes that arrive with **no**
material at all get a generated flat colour from a small built-in palette, so you never lose
a real material to a fallback.

---

## Install

1. Download `Blender2UE_Mesh_Bridge_v1.0.0.zip` from [Releases](https://github.com/Mowen-M/Blender2UE-Mesh-Bridge/releases).
2. Blender → *Edit → Preferences → Add-ons → Install from Disk…* → pick the ZIP.
3. Enable **“Blender2UE Mesh Bridge (UE 5.6-5.8)”**.
4. In the 3D Viewport press `N` → tab **“B2UE Bridge”**.

Requirements:

- Blender **2.83+** (developed and tested on 4.5 LTS; installs on Blender 5.x too, verified on 5.0.1).
- Unreal Engine **5.6 – 5.8** for workflow B. Workflow A’s clipboard path also works on 4.27–5.5.
- UE project needs the **Python Editor Script Plugin** enabled (Edit → Plugins → “Python Editor Script Plugin”, restart).

---

## Workflow A — copy transforms, paste in UE

Select your objects (Object mode) and use one of the four Copy buttons. They differ only in
how transforms are encoded; pick according to how your FBX was exported.

| Button | Mode | Use when |
|---|---|---|
| **Copy (paste carries position)** | `WORLD` *(default)* | The mesh was modelled around its own pivot. Actor gets the real world Location + Rotation, Scale = 1. Verified live on UE 5.6.1 and 5.8.4. |
| **Copy (FBX carries position)** | `BAKED` | The object was left moved/rotated in the Blender scene at export time, so UE bakes that transform into the mesh vertices. Actor sits at the origin (Scale = 1) to avoid applying the offset twice. |
| **Copy (match bounds)** | `BOUNDS` | Blockout: placeholder is sized and centred on the object’s real world bounds. Dropping your own mesh on it will scale that mesh. |
| **Copy (direct UE meshes)** | `DIRECT` | You already imported the StaticMeshes into UE; fill in the UE folder (e.g. `/Game/Meshes`) and paste finished actors. |

Optional: **“Different placeholder per object”** gives every pasted actor a different
BasicShape (cube / cylinder / cone / sphere / plane / torus) chosen from the object’s own
proportions, so a multi-object paste stays readable in the viewport. Match-bounds always uses
the cube, because it is the only BasicShape whose native bounds are exactly 100×100×100.

---

## Workflow B — export parts, place them automatically

1. In the panel, set **UE Export Directory** — anything writable; `//ue_parts/` means “next to
   the current .blend file”.
2. Select the objects → **Export Parts to UE (FBX + Placement)**.
3. In UE, the usual way — copy the script into the project:

   1. copy `ue_side/ue_import_parts.py` **and** `ue_side/b2ue_export_dir.txt` into
      `<UE project>\Content\Python\` (create that folder if it is missing — the txt holds
      this export folder’s path so the script can find `placement.json`),
   2. restart the UE editor (files under `Content\Python` are picked up at startup),
   3. run:
      ```
      py "ue_import_parts.py"
      ```
      (Tools → Execute Script…, or the Output Log console).

   If you re-export into a different folder later, copy `b2ue_export_dir.txt` again.

   The script finds the export folder by itself: an explicit `EXPORT_DIR` at the top, the
   `B2UE_EXPORT_DIR` environment variable, the one-line `b2ue_export_dir.txt` next to the
   script, the path remembered in `<UE project>\Saved\B2UE\last_export_dir.txt` after the
   first run, or a bounded scan of the UE project for the newest `placement.json` +
   `parts/`. Running it in place also works:
   `py "<export folder>/ue_side/ue_import_parts.py"`.

### Importing is slow — expect it

A full scene easily takes **5–30 minutes**, and one heavy mesh can sit there for minutes
without printing anything. UE imports FBX single-threaded; this is normal. Every batch prints
a line with the **elapsed seconds**, and the whole list is written to
`<export folder>/ue_import_log.txt`, so you can always check that it is still moving. Don’t
close the editor and don’t run the script twice — a second run re-imports the same meshes on
top of the first one.

What the export folder contains:

```
parts/*.fbx        one FBX per unique mesh: origin at the geometry centre, geometry baked at
                   the world origin, textures embedded / copied
placement.json     per object: name / part / mesh / collection / world location / rotation
                   quaternion / scale (metres)
ue_side/           ue_import_parts.py, init_unreal.py, add_lights.py, focus_cam.py
README_UE.txt      the same instructions, printed for the UE side
```

What `ue_import_parts.py` does: imports the FBX in size-aware batches (≤10 MB six at a time,
≤50 MB two at a time, heavier meshes alone, each with a retry), saves the content folder after
each batch, resolves the mesh/material same-name clash UE creates on import, moves materials
into `/Game/MeshParts/Materials/<part>`, opens or creates `/Game/Maps/Auto_placed_Map`, spawns
one labelled `StaticMeshActor` per entry, adds the sky actors, and writes
`ue_import_log.txt` next to the export.

Destination folders, level name, batching and whether old `City_`/`DisplayPart_` actors are
cleared are constants at the top of `ue_import_parts.py` (`CONTENT`, `MATDIR`, `LEVEL`,
`USE_ISM`, `CLEAR_OLD`).

---

## Coordinate mapping

```
UE location (cm) = (  Blender.x * 100,  -Blender.y * 100,  Blender.z * 100 )
UE rotation     =  Blender world rotation conjugated by the Y mirror → Pitch / Yaw / Roll
placement.json  =  quaternion written as (x, -y, z, w)
1 Blender metre  =  100 UE units  =  the edge of UE's 1 m BasicShape cube
```

---

## Known pitfalls

- **Everything is twice as far away** → your FBX already carries the placement. Use
  *Copy (FBX carries position)* / `BAKED`.
- **Pasted object is huge or stretched** → the placeholder already has the real size; Scale = 1
  is correct. Don’t use *match bounds* if you plan to drop your own mesh on the placeholder.
- **Paste does nothing** → UE’s clipboard gate wants text starting with the upper-case token
  `BEGIN MAP` (this add-on writes it). Interactive `Ctrl+V` is more forgiving than the console
  `PASTE` command; click the viewport first so the Outliner search field doesn’t swallow the
  text.
- **Everything is grey / one flat colour** → turn on *Import Materials* for the FBX import.
  A flat `M_Stone` means the mesh arrived with no material slot; check the `materials:` line in
  `ue_import_log.txt`.
- **“Cannot locate the Blender export folder”** → the script needs the folder holding
  `placement.json` + `parts/`. It remembers it in `<UE project>\Saved\B2UE\last_export_dir.txt`
  after the first run. For a fresh export that sits outside the UE project, do one of these
  once: copy `b2ue_export_dir.txt` next to the script, set `EXPORT_DIR` at the top of the
  script, or set the environment variable `B2UE_EXPORT_DIR`.
- **The import looks frozen** → it is just slow. Watch the elapsed-seconds column, or open
  `ue_import_log.txt`; never start a second run while the first is still going.
- **Blender refuses the ZIP** → the folder inside must be a valid Python module name; this
  package uses `blender2ue_mesh_bridge`.

---

## Repository layout

```
blender2ue_mesh_bridge/   the add-on (drop this folder into Blender, or install the ZIP)
  __init__.py             the whole Blender side
  README.txt              user manual shipped inside the add-on
  ue_side/                UE-side Python (import / placement / lights / camera)
V1/                       v1.0.0 release archive (ZIP + notes)
LICENSE                   GPL-3.0
CHANGELOG.md              version history
```

---

## Chinese / 中文说明

**Blender2UE Mesh Bridge** 是一个 Blender 插件，把 Blender 里的物体按**真实位置 / 旋转 / 尺寸**
搬进 Unreal Engine 5.6–5.8，并让每个 mesh 各自带自己的材质。

两条互相独立的流程：

1. **复制 → 粘贴**：Blender 里选中物体，点 Copy，在 UE 视口 `Ctrl+V`。UE 里得到带正确变换的
   占位 Actor（BasicShape），再把你的 mesh 拖上去。不需要任何文件。
2. **导出 Parts → 自动摆位**：每个唯一 mesh 导一个 FBX，外加 `placement.json` 和 UE 端 Python
   脚本。在 UE 里跑一次脚本：自动导入到 `/Game/MeshParts`、材质按 mesh 名收进
   `Materials/`、建好关卡、按原变换生成每个 Actor、补灯光并保存。

FBX 里带进来的材质会保留，只有确实没有材质的 mesh 才用内置纯色兜底。

**安装**：Blender → 编辑 → 偏好设置 → 插件 → 从磁盘安装 → 选
`Blender2UE_Mesh_Bridge_v1.0.0.zip` → 启用 → 3D 视图按 `N`，在 **B2UE Bridge** 标签里用。

**坐标**：UE 位置 = (x\*100, −y\*100, z\*100) cm；1 米 = 100 UE 单位。

常见坑：位置翻倍 → 用「FBX carries position」；物体被放大 → 占位本身已带真实尺寸，Scale 保持 1；
粘不进去 → 先点一下 UE 视口再 `Ctrl+V`。

---

## Credits & license

Based on **[CoordiKnight v1.3](https://github.com/NazzarenoGiannelli/coordiknight)** by
Nazzareno Giannelli — the original clipboard-actor workflow. This build rewrites the transform
handling, adds the FBX + placement export pipeline, keeps materials from the FBX, and adapts
everything to UE 5.6–5.8.

The inherited internal identifiers (`object.coordiknight`, `object.coordiknight_export_parts`,
`coordiknight_settings`) are kept on purpose so the add-on stays compatible with the upstream
operator IDs.

Licensed under **GPL-3.0-or-later**, inherited from CoordiKnight. See [LICENSE](LICENSE).

By **Mowen (Bowen Sun)**.
