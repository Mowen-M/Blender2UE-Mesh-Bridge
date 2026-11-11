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
| Size | 24 394 bytes |
| SHA-256 | `52458f972bc0953f15da1bdd627c1d971d4835a06ca00445bd1ac3fb036b3868` |

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
- `build_t3d()` on a cube at (1.5, 2.5, 0.75) m emits
  `RelativeLocation=(X=150.000000,Y=-250.000000,Z=75.000000)` — the expected y-flip,
  centimetres, Scale = 1.
- All six Python files pass `py_compile`; the package is pure ASCII (English UI).

Rebuild the same ZIP from the repo root with `python build_zip.py`.
