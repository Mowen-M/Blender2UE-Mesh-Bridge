# Changelog

All notable versions of Blender2UE Mesh Bridge.

## v1.0.0 — 2026-11-10

First public release. Code is the private English build 3.0.0, renumbered to 1.0.0 for
publication; every user-facing string, exported file and UE-side script is English, no
machine-specific paths anywhere, and the fallback-colour keyword list is English-only.

- **Clipboard workflow** — four explicit transform conventions (`WORLD` default, `BAKED`,
  `BOUNDS`, `DIRECT`), transforms read from `matrix_world`, `BEGIN MAP` written in upper case
  so the console `PASTE` path is accepted too, unique actor names, fixed-width decimals
  (UE's T3D parser rejects `1e-05`), no stale hard-coded `StaticMeshDerivedDataKey`.
- **Placeholders** — shape chosen from the object's proportions and never repeated inside one
  paste; match-bounds always uses the cube (its native bounds are exactly 100×100×100).
- **Export workflow** — one FBX per unique mesh (origin at geometry centre, geometry baked at
  the world origin, materials embedded) + `placement.json` + UE-side Python that imports,
  names materials after the parts, creates `/Game/Maps/Auto_placed_Map`, spawns one actor per
  part at the exact transform, adds Sun / SkyLight / SkyAtmosphere and saves the level.
- **Materials** — materials carried by the FBX are kept; only meshes with no material get a
  generated flat colour from the built-in palette.
- **Export path** — the folder picked in the panel is authoritative, `//` resolves against the
  `.blend`, and the UE-side script finds everything from its own location.

### Pre-release history (private builds, same feature set)

- **3.0.0** — English build of 2.4.1: all strings translated, `README_UE.txt` replaces the
  Chinese instruction file, `bl_info` carries the version, logs are written next to the
  scripts, `focus_cam.py` frames the scene from `placement.json`.
- **2.4.1** — UE-side material fix: materials that the FBX brought in are kept; only
  material-less meshes get a fallback colour.
- **2.3.3** — export path fix: panel folder is authoritative, `//` paths resolve against the
  `.blend`, no hard-coded drive letters.
- **2.3.0** — new “Export Parts to UE (FBX + Placement)” pipeline.
- **2.2.0** — default mode `WORLD`, fixed a missing matrix transpose that broke rotation.
- **2.1.0** — `WORLD`/`BAKED` modes, `matrix_world`, unique actor names, fixed-width floats.
- **1.3** — upstream CoordiKnight (Nazzareno Giannelli), used as the starting point.
