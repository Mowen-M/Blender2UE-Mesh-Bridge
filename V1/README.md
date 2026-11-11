# V1 — v1.0.0 release archive

This folder keeps the released, installable build of **Blender2UE Mesh Bridge v1.0.0**.
The live source lives one level up in [`blender2ue_mesh_bridge/`](../blender2ue_mesh_bridge);
this folder is the frozen artifact that matches the GitHub release.

| | |
|---|---|
| File | `Blender2UE_Mesh_Bridge_v1.0.0.zip` |
| Version (`bl_info`) | `1.0.0` |
| Add-on name | `Blender2UE Mesh Bridge (UE 5.6-5.8)` |
| Blender panel tab | `B2UE Bridge` |
| Built | 2026-11-10 |
| Size | 26 577 bytes |
| SHA-256 | `dce94afd4a2a115089d77f06ce744262d85fa2170df3b71cfc615b8777f15374` |

Archive contents (6 files):

```
blender2ue_mesh_bridge/__init__.py
blender2ue_mesh_bridge/README.txt
blender2ue_mesh_bridge/ue_side/add_lights.py
blender2ue_mesh_bridge/ue_side/focus_cam.py
blender2ue_mesh_bridge/ue_side/init_unreal.py
blender2ue_mesh_bridge/ue_side/ue_import_parts.py
```

## Verified

- Installed through Blender's own **Install from Disk** path on **Blender 4.5.4 LTS** with a
  throw-away user config: `Modules Installed (blender2ue_mesh_bridge)` → enabled →
  `bl_info.version == (1, 0, 0)`, both operators and the N-panel registered, panel tab
  `B2UE Bridge`.
- End-to-end export from Blender headless: 2 objects → `parts/Cube.fbx`,
  `parts/Cylinder.fbx`, `placement.json` (2 entries), `README.txt`, `README_UE.txt`,
  `b2ue_export_dir.txt` (in the export root and in `ue_side/`), `ue_side/` with all four
  scripts.
- `ue_import_parts.py` export-folder lookup, tested by executing the real block with a stub
  `unreal` module: export inside the UE project (project scan), pointer file, remembered
  path in `Saved/B2UE`, `B2UE_EXPORT_DIR`, script left in `<export>/ue_side`, and
  newest-of-two exports — all resolve to the right folder.
- Cube at (1.5, 2.5, 0.75) m → `RelativeLocation=(X=150.000000,Y=-250.000000,Z=75.000000)`,
  Scale 1 — the expected centimetre conversion with the Y flip.

Rebuild the same ZIP from the repo root with `python build_zip.py`.
