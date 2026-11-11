Blender2UE Mesh Bridge  |  Blender -> Unreal Engine 5.6+  (English)
==================================================================

Version 1.0.0  -  add-on name "Blender2UE Mesh Bridge (UE 5.6-5.8)"
                   Blender panel tab: "B2UE Bridge"


WHAT THIS ADD-ON DOES
---------------------
It moves objects from Blender into Unreal Engine with the right position, rotation and
size.  There are two independent workflows:

  A. Copy T3D to the clipboard, Ctrl+V in UE.
     Fast, no files.  UE gets StaticMeshActor placeholders (BasicShapes) with the real
     transform; you drop your imported mesh on them.

  B. "Export Parts to UE (FBX + Placement)".
     Writes one FBX per unique mesh plus a placement.json, plus a Python script that
     imports everything into UE and spawns every actor back at its exact transform.
     This is the one for whole scenes (city blocks, building groups, display parts).

Both workflows have been re-checked for the problems that break upstream CoordiKnight v1.3
in UE 5.5-5.8: see "WHAT WAS FIXED" at the bottom.


REQUIREMENTS
------------
- Blender 2.83 or newer (developed and tested on 4.5 LTS; installs on Blender 5.x too).
- Unreal Engine 5.6 - 5.8 for workflow B's Python script.  The clipboard workflow (A)
  also works on 4.27 through 5.5.
- Workflow B needs the Python Editor Script Plugin enabled in your UE project
  (Edit > Plugins > "Python Editor Script Plugin" > restart editor).


INSTALL
-------
1. Blender > Edit > Preferences > Add-ons > Install from Disk...
2. Pick this ZIP and enable "Blender2UE Mesh Bridge (UE 5.6-5.8)".
   Blender 5.x note: the folder inside the ZIP must be a legal Python module name.
   This package uses "blender2ue_mesh_bridge" (no dots, no version suffix), which installs
   cleanly.  If your Blender still refuses the ZIP, unzip it and install
   blender2ue_mesh_bridge/__init__.py directly.
3. In the 3D Viewport press N, open the "B2UE Bridge" tab.


WORKFLOW A - COPY T3D, PASTE IN UE
----------------------------------
Select the objects (Object mode), press one of the Copy buttons, then in UE press Ctrl+V
in the level viewport (or run the console command PASTE).

Four buttons, four transform conventions.  Pick by how your FBX was exported:

  Copy (paste carries position - default)                [WORLD]
     The actor carries the real Location + Rotation, Scale = 1.
     Use this when the mesh was modelled around its own pivot (the usual case): the mesh
     carries size, the paste carries placement.  Verified live on UE 5.8.4 and 5.6.1.

  Copy (FBX carries position)                            [BAKED]
     Actor at the origin with identity rotation, Scale = 1.
     Use this when the object was left moved/rotated in the Blender scene when exported:
     UE then bakes that transform into the mesh vertices, and a positioned actor would
     offset it a second time (measured: an object at X = 5 m landed at X = 10 m).

  Copy (match bounds)                                    [BOUNDS]
     Placeholder sized to the object's real world size and centred on its bounding box.
     Good for blocking out a scene quickly.  Warning: dropping your real mesh on such a
     placeholder scales the mesh.

  Copy (direct UE meshes)                                [DIRECT]
     References StaticMesh assets you already imported into UE (fill in the UE folder,
     e.g. /Game/Meshes) and pastes finished actors - no dragging.

"Different placeholder per object" gives each pasted actor a different BasicShape (cube /
cylinder / cone / sphere / plane / torus) chosen from the object's own proportions, so a
batch of pasted objects is still readable in the viewport.  Match-bounds always uses the
cube, because it is the only BasicShape whose native bounds are exactly 100x100x100.


WORKFLOW B - EXPORT PARTS, AUTO-PLACE IN UE
-------------------------------------------
1. In the add-on panel set "UE Export Directory" to any writable folder.
   "//ue_parts/" means: next to the current .blend file.  Absolute paths work too.
2. Select the objects, click "Export Parts to UE (FBX + Placement)".
   You get, inside the export folder:
       parts/*.fbx          one file per unique mesh.  Origin moved to the geometry
                            centre, geometry baked at the world origin, textures packed
                            into the FBX (path_mode=COPY, embed_textures).
       placement.json       every object: name / part / mesh / collection / world
                            location / rotation quaternion / scale, in metres.
       ue_side/             ue_import_parts.py, init_unreal.py, add_lights.py,
                            focus_cam.py
       README_UE.txt        short instructions for the UE side
       README.txt           the commands below, for copy-paste
       b2ue_export_dir.txt  one line: this export folder's absolute path
3. UE side - the usual way (script copied into the project):
     1) copy  ue_side/ue_import_parts.py  AND  ue_side/b2ue_export_dir.txt  into
        <UE project>\Content\Python\  (create that folder if it is missing; the txt holds
        this export folder's path so the script can find placement.json)
     2) restart the UE editor (Python files under Content\Python load at startup)
     3) run:   py "ue_import_parts.py"
        (Tools > Execute Script..., or the Output Log console)
   If you re-export into a DIFFERENT folder later, copy b2ue_export_dir.txt again.
   The script finds this export folder by itself:
        - from b2ue_export_dir.txt next to the script (copy it with the script),
        - or from <UE project>\Saved\B2UE\last_export_dir.txt (written automatically
          after the first successful run),
        - or by scanning the UE project folder for the newest placement.json + parts/.
   You can also skip the copying and run it straight out of the export folder:
        py "C:/path/to/<export folder>/ue_side/ue_import_parts.py"

IMPORTING IS SLOW - EXPECT IT
-----------------------------
A full city / display set easily takes 5-30 minutes, and one heavy mesh can sit there for
minutes without printing anything.  Do not close the editor and do not run the script a
second time (a second run re-imports the same meshes on top of the first one).  Every
batch prints a line with the elapsed seconds, and the whole list is written to
<export folder>/ue_import_log.txt, so you can check at any moment that it is still going.

What ue_import_parts.py does, in order:
   - imports every FBX into /Game/MeshParts in size batches (<= 10 MB six at a time,
     <= 50 MB two at a time, heavier meshes one at a time, each with a retry), saving the
     content folder after every batch;
   - sorts out the name clash UE creates when a mesh and its material share a name (one
     of them ends up with a "1" suffix), and moves the imported materials into
     /Game/MeshParts/Materials/<part name>;
   - keeps the materials that came from the FBX.  Only meshes that arrive with no material
     of their own get a generated flat colour from the built-in palette
     (M_Stone / M_Mud / M_Roof / M_Wood / M_Water / M_Plaza / M_Brick / M_Green / M_Metal,
     chosen by matching English keywords in the part name case-insensitively: water /
     tree, cypress, olive, barley, fallow / wood, bridge / roof / brick / tower / plaza /
     building, house - everything else falls back to M_Stone);
   - opens or creates /Game/Maps/Auto_placed_Map, optionally clears previous
     City_/DisplayPart_ actors, spawns one StaticMeshActor per placement entry
     (label City_<object name>), adds Sun + SkyLight + SkyAtmosphere, saves the level.
   - writes a log: <export folder>/ue_import_log.txt

Constants at the top of ue_import_parts.py you may want to change:

   CONTENT   = "/Game/MeshParts"           where meshes land
   MATDIR    = "/Game/MeshParts/Materials" where materials are collected
   LEVEL     = "/Game/Maps/Auto_placed_Map" level to create / reuse
   USE_ISM   = False   True spawns one InstancedStaticMeshComponent per part (cheaper for
                       thousands of copies, but instances are not individually movable)
   CLEAR_OLD = True    delete actors labelled City_ / DisplayPart_ before spawning
   SMALL_MB, MID_MB = 10.0, 50.0          the import batch thresholds

Helper scripts (run them the same way as ue_import_parts.py):
   add_lights.py  adds Sun / SkyLight / SkyAtmosphere to the current level if missing.
                  Does not save the level - Ctrl+S yourself.
   focus_cam.py   moves the viewport camera to frame whatever is in placement.json.
   init_unreal.py a deliberately empty UE startup hook (see its comments).


COORDINATE MAPPING
------------------
   UE location (cm) = ( Blender x * 100, -Blender y * 100, Blender z * 100 )
   UE rotation      = Blender world rotation conjugated by the Y mirror, exported as
                      Pitch / Yaw / Roll; the quaternion in placement.json is written as
                      (x, -y, z, w).
   One Blender metre == 100 UE units == the edge of UE's 1 m BasicShape cube.


TROUBLESHOOTING
---------------
"Cannot locate the Blender export folder"
   The script needs the folder holding placement.json + parts/.  It remembers that folder
   after the first run (<UE project>\Saved\B2UE\last_export_dir.txt).  When a fresh export
   sits outside the UE project, do one of these once:
     - copy b2ue_export_dir.txt from the export folder next to ue_import_parts.py, or
     - set EXPORT_DIR at the top of ue_import_parts.py to the export folder, or
     - set the environment variable B2UE_EXPORT_DIR.

"The import looks frozen"
   It is not - UE imports FBX single-threaded and a heavy mesh can take minutes.  Watch the
   elapsed-seconds column of the per-batch lines, or open ue_import_log.txt in the export
   folder.  Never start a second run while the first one is still going.

"Object lands twice as far as it should"
   Your FBX already carries the placement.  Use "Copy (FBX carries position)".

"Object is huge / stretched"
   The placeholder already has the real size baked in; Scale = 1 is correct.  Do not use
   Match-bounds if you plan to drop your own mesh onto the placeholder.

"Paste does nothing in UE"
   UE's clipboard gate only accepts text starting with the upper-case token "BEGIN MAP",
   which this add-on writes.  The interactive Ctrl+V is more forgiving than the console
   PASTE command; if Ctrl+V fails, check that the clipboard really holds the text.

"Blender refuses to install the ZIP / No module named ..."
   The add-on folder name must be a valid Python module name: no dots, no version suffix.
   Install blender2ue_mesh_bridge/__init__.py from an unzipped copy instead.

"Materials are all grey / one flat colour"
   Enable "Import Materials" for the FBX import.  A flat M_Stone and friends means the mesh
   came in without a material slot, so the palette fallback was used.  Check the "materials:"
   line in ue_import_log.txt: per_mesh_fbx counts meshes that kept their own material.

"Some parts missing"
   Look at the "spawned=... missing=..." line and the "HEAVY IMPORT FAILED" entries in
   ue_import_log.txt; re-run the script, it re-imports what is missing and re-places
   everything (CLEAR_OLD = True avoids duplicates).


WHAT WAS FIXED COMPARED WITH UPSTREAM CoordiKnight v1.3
------------------------------------------------------
 1. "BEGIN MAP" upper-case token so the console PASTE path works too.
 2. Transforms are read from matrix_world, not the local location/rotation_euler/scale,
    so parented and constrained objects land correctly.
 3. Scale semantics: the placeholder is already 100 cm wide and an imported FBX already
    carries its real size, so the default emits Scale = 1 instead of copying the Blender
    object scale (that was the stretching).
 4. Removed a stale hard-coded StaticMeshDerivedDataKey that only meant something in the
    UE build it was copied out of.
 5. Unique actor names instead of every actor being Cube19_4.
 6. Numbers serialised as fixed-width decimals: UE's T3D float parser rejects "1e-05".
 7. Double offset eliminated, with two explicit modes (WORLD / BAKED) for the two FBX
    conventions, instead of guessing.
 8. Placeholders vary in shape instead of being identical cubes.
 9. New export pipeline: FBX per unique mesh + placement.json + UE-side Python that
    imports, names materials, creates the level and spawns everything back in place.
10. No machine-specific paths anywhere: the export folder is chosen in the panel and the
    UE-side script locates it from its own location.


VERSIONS
--------
  1.0.0  First public release, published as "Blender2UE Mesh Bridge".  The code is the
         private English build 3.0.0 re-numbered to 1.0.0 for the public release:
         every string in the add-on, in the files it exports and in the shipped UE-side
         scripts is English (the export folder gets README_UE.txt instead of a
         Chinese-named instructions file), bl_info carries the version, the UE-side
         scripts contain no machine-specific absolute paths and write their logs next to
         themselves, the fallback-colour keyword list is English-only, and focus_cam.py
         frames the scene from placement.json instead of hard-coded coordinates.
         UE side: the "copy ue_import_parts.py into <UE project>\Content\Python, restart,
         run py \"ue_import_parts.py\"" workflow is the documented default; the script
         locates the export folder through EXPORT_DIR / B2UE_EXPORT_DIR / a
         b2ue_export_dir.txt pointer / <UE project>\Saved\B2UE\last_export_dir.txt /
         a bounded scan of the UE project (no more recursive scan of the whole home
         folder).  Every progress line carries elapsed seconds and the run starts with an
         "importing is slow" note, so a 5-30 minute import is visibly alive.

Pre-release history (private builds, same feature set as 1.0.0):
  3.0.0  English build of the 2.4.1 package: every string in the add-on, in the files it
         exports and in the shipped UE-side scripts is English (the export folder now gets
         README_UE.txt instead of a Chinese-named instructions file), bl_info carries the
         version, the UE-side scripts contain no machine-specific absolute paths and write
         their logs next to themselves, the fallback-colour keyword list is English-only,
         and focus_cam.py frames the scene from placement.json instead of hard-coded
         coordinates.
  2.4.1  material fix on the UE side: materials that the FBX brought in are kept (a mesh
         whose material has a different name was previously being repainted with M_Stone),
         and only meshes that arrive with no material get a generated fallback colour.
  2.3.3  auto export path fix: the export folder chosen in the panel is authoritative,
         "//" relative paths resolve against the .blend file, and the UE-side script finds
         the export folder from its own location instead of hard-coded drive letters.

Based on CoordiKnight v1.3 by Nazzareno Giannelli
(https://github.com/NazzarenoGiannelli/coordiknight), rewritten and extended by Mowen.
