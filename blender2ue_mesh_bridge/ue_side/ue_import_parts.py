# ue_import_parts.py - robust version: imports FBX parts of any size into UE and
# places them back exactly where they were in Blender.
#   Flow: scan existing assets -> batched import (small / medium / large, big meshes
#   one at a time and saved right away) -> assign materials -> spawn actors
#   (one actor per object, sharing the mesh asset).
#   The level is saved automatically at the end of run().
import unreal, json, os, time, traceback

# ---------- Paths ----------
# Where the Blender export lives (placement.json + parts/).
#
# YOU CAN COPY THIS FILE INTO <UEProject>/Content/Python/ AND RUN
#     py "ue_import_parts.py"
# The export folder is found in this order:
#   1. EXPORT_DIR below, if you fill it in (absolute path)
#   2. environment variable  B2UE_EXPORT_DIR
#   3. one-line file  b2ue_export_dir.txt  next to this script
#   4. the folder remembered from the previous run
#      (<UEProject>/Saved/B2UE/last_export_dir.txt)
#   5. next to / one level above this script (script left in <export_dir>/ue_side)
#   6. newest placement.json found inside the UE project (bounded scan)
# Once found, the folder is remembered in Saved/, so later runs need no setup.
EXPORT_DIR = ""          # optional absolute path, e.g. r"I:\...\ue_parts"; "" = auto
MARKER = "placement.json"

_here = os.path.dirname(os.path.abspath(__file__))


def _is_export_dir(p):
    if not p:
        return False
    try:
        return (os.path.isfile(os.path.join(p, MARKER))
                and os.path.isdir(os.path.join(p, "parts")))
    except Exception:
        return False


def _project_dir():
    try:
        return os.path.abspath(unreal.Paths.project_dir())
    except Exception:
        return ""


def _read_pointer(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            first = f.readline().strip()
        return first.strip('"').strip()
    except Exception:
        return ""


def _cache_file():
    proj = _project_dir()
    if not proj:
        return ""
    return os.path.join(proj, "Saved", "B2UE", "last_export_dir.txt")


def _write_cache(folder):
    cf = _cache_file()
    if not cf:
        return
    try:
        os.makedirs(os.path.dirname(cf), exist_ok=True)
        with open(cf, "w", encoding="utf-8") as f:
            f.write(folder)
    except Exception:
        pass


def _scan_project(proj):
    """Newest placement.json inside the UE project; skips the heavy folders."""
    skip = set(["Intermediate", "DerivedDataCache", "Binaries", "Saved", "Build",
                ".git", "node_modules", "__pycache__"])
    best = None
    for root, dirs, files in os.walk(proj):
        dirs[:] = [d for d in dirs if d not in skip]
        if MARKER in files and os.path.isdir(os.path.join(root, "parts")):
            try:
                t = os.path.getmtime(os.path.join(root, MARKER))
            except Exception:
                continue
            if best is None or t > best[0]:
                best = (t, root)
    return best[1] if best else None


_candidates = []
if EXPORT_DIR.strip():
    _candidates.append(EXPORT_DIR.strip())
_candidates.append(os.environ.get("B2UE_EXPORT_DIR", "").strip())
_candidates.append(_read_pointer(os.path.join(_here, "b2ue_export_dir.txt")))
_cf = _cache_file()
if _cf:
    _candidates.append(_read_pointer(_cf))
_candidates.extend([os.path.dirname(_here), _here])

EXPORT_DIR = next((os.path.abspath(p) for p in _candidates if _is_export_dir(p)), None)

if EXPORT_DIR is None:
    _proj = _project_dir()
    if _proj:
        EXPORT_DIR = _scan_project(_proj)

if EXPORT_DIR is None:
    raise FileNotFoundError(
        "Cannot locate the Blender export folder (needs placement.json + parts/).\n"
        "Pick one of these (all are remembered after the first run):\n"
        "  - set EXPORT_DIR at the top of this file to the absolute export path\n"
        "  - set the environment variable B2UE_EXPORT_DIR\n"
        "  - put the export path on one line into b2ue_export_dir.txt next to this script\n"
        "  - leave this script inside <export_dir>/ue_side and run it from there"
    )

EXPORT_DIR = os.path.abspath(EXPORT_DIR)
_write_cache(EXPORT_DIR)
PLACEMENT_FILE = os.path.join(EXPORT_DIR, "placement.json")
PARTS_DIR = os.path.join(EXPORT_DIR, "parts")
print("[UE Import] Export directory:", EXPORT_DIR)

# Unreal project asset destinations and import batching settings.
# These constants were present in the original script but were accidentally
# omitted from the auto-path version.
CONTENT = "/Game/MeshParts"
MATDIR = "/Game/MeshParts/Materials"
LEVEL = "/Game/Maps/Auto_placed_Map"
USE_ISM = False          # False = one actor per object (individually movable)
CLEAR_OLD = True         # Clear previously generated City_/DisplayPart_ actors
SMALL_MB, MID_MB = 10.0, 50.0

# Initialize the log state before say() is called.
LOG = os.path.join(EXPORT_DIR, "ue_import_log.txt")
lines = []

_T0 = time.time()


def say(m):
    stamp = "[%7.1fs] " % (time.time() - _T0)
    m = stamp + str(m)
    lines.append(m)
    try:
        with open(LOG, "w", encoding="utf-8") as _log_file:
            _log_file.write("\n".join(lines))
    except Exception:
        pass
    print(m)


def akey(p):
    return str(p).rsplit("/", 1)[-1].split(".")[0]


def scan_meshes():
    out = {}
    try:
        reg = unreal.AssetRegistryHelpers.get_asset_registry()
        try:
            reg.scan_paths_synchronous([CONTENT, MATDIR], True)
        except Exception:
            pass
        for p in unreal.EditorAssetLibrary.list_assets(CONTENT, recursive=True, include_folder=False):
            try:
                a = unreal.load_asset(p)
            except Exception:
                a = None
            if isinstance(a, unreal.StaticMesh):
                out[akey(p)] = a
    except Exception:
        say("scan fail:\n" + traceback.format_exc())
    return out


def find_mesh(meshes, part):
    if part in meshes:
        return meshes[part]
    for k in meshes:
        if k == part or k.startswith(part + "_") or k.startswith(part + "1") or k.startswith(part + "("):
            return meshes[k]
    return None


def do_import(batch, pdir):
    tasks = []
    for fn, nm in batch:
        ui = unreal.FbxImportUI()
        ui.static_mesh_import_data.import_uniform_scale = 1.0
        ui.static_mesh_import_data.auto_generate_collision = False
        ui.import_materials = True
        ui.import_animations = False
        t = unreal.AssetImportTask()
        t.filename = os.path.join(pdir, fn)
        t.destination_path = CONTENT
        t.destination_name = nm
        t.automated = True
        t.replace_existing = True
        t.options = ui
        tasks.append(t)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
    unreal.EditorAssetLibrary.save_directory(CONTENT, only_if_is_dirty=False, recursive=True)


def import_all(parts):
    """Import small -> medium -> large, one heavy mesh at a time; save after each batch."""
    pdir = PARTS_DIR
    have = scan_meshes()
    todo = []
    for fn in sorted(os.listdir(pdir)):
        if not fn.lower().endswith(".fbx"):
            continue
        nm = os.path.splitext(fn)[0]
        # Reimport existing meshes too: this refreshes FBX material slots when
        # an earlier run assigned fallback materials such as M_Stone.
        sz = os.path.getsize(os.path.join(pdir, fn)) / (1024.0 * 1024.0)
        todo.append((fn, nm, sz))
    smalls = [(f, n) for f, n, s in todo if s <= SMALL_MB]
    mids = [(f, n) for f, n, s in todo if SMALL_MB < s <= MID_MB]
    heavies = [(f, n) for f, n, s in todo if s > MID_MB]
    say("import plan: small=%d mid=%d heavy=%d" % (len(smalls), len(mids), len(heavies)))

    for batch_name, lst, step in (("small", smalls, 6), ("mid", mids, 2)):
        for i in range(0, len(lst), step):
            try:
                do_import(lst[i:i + step], pdir)
                say("import %s %d/%d" % (batch_name, min(i + step, len(lst)), len(lst)))
            except Exception:
                say("import %s chunk fail:\n%s" % (batch_name, traceback.format_exc()))
                # Retry the items of this chunk one by one
                for one in lst[i:i + step]:
                    try:
                        do_import([one], pdir)
                        say("retry ok %s" % one[1])
                    except Exception:
                        say("retry fail %s:\n%s" % (one[1], traceback.format_exc()))
    for one in heavies:
        try:
            say("import heavy start: %s (%.0f MB)" % (one[1], os.path.getsize(os.path.join(pdir, one[0])) / (1024.0 * 1024.0)))
            do_import([one], pdir)
            say("import heavy done: %s" % one[1])
        except Exception:
            say("HEAVY IMPORT FAILED %s:\n%s" % (one[1], traceback.format_exc()))
    meshes = scan_meshes()
    say("meshes available: %d / %d parts" % (len(meshes), len(parts)))
    return meshes


PALETTE = {
    "M_Stone": (0.78, 0.74, 0.64), "M_Mud": (0.72, 0.60, 0.44), "M_Roof": (0.55, 0.36, 0.27),
    "M_Wood": (0.42, 0.30, 0.20), "M_Water": (0.16, 0.42, 0.55), "M_Plaza": (0.80, 0.78, 0.72),
    "M_Brick": (0.62, 0.44, 0.34), "M_Green": (0.34, 0.42, 0.26), "M_Metal": (0.50, 0.48, 0.45),
}


def color_for(name):
    """Fallback flat colour picked from English keywords in the part name.
    Only reached for meshes that arrived with no material of their own."""
    low = name.lower()
    if "water" in low:
        return "M_Water"
    if any(k in low for k in ("tree", "cypress", "olive", "barley", "fallow")):
        return "M_Green"
    if any(k in low for k in ("wood", "bridge")):
        return "M_Wood"
    if "roof" in low:
        return "M_Roof"
    if "brick" in low:
        return "M_Brick"
    if "tower" in low:
        return "M_Metal"
    if "plaza" in low:
        return "M_Plaza"
    if any(k in low for k in ("building", "house")):
        return "M_Mud"
    return "M_Stone"


def _paint_material(mat, rgba):
    """Wire a BaseColor constant into a material (UE 5.8 compatible, step by step)."""
    mel = unreal.MaterialEditingLibrary
    ex = None
    try:
        ex = mel.create_material_expression(mat, unreal.MaterialExpressionConstant3Vector, -400, 0)
    except Exception:
        say("expr create fail: " + traceback.format_exc())
    if ex is None:
        return False
    try:
        ex.set_editor_property("constant", unreal.LinearColor(rgba[0], rgba[1], rgba[2], 1.0))
    except Exception:
        try:
            ex.set_editor_property("constant", unreal.Color(int(rgba[0] * 255), int(rgba[1] * 255), int(rgba[2] * 255), 255))
        except Exception:
            say("expr color fail: " + traceback.format_exc())
    try:
        mel.connect_material_property(ex, "", unreal.MaterialProperty.MP_BASE_COLOR)
    except Exception:
        say("connect fail: " + traceback.format_exc())
    try:
        mel.recompile_material(mat)
    except Exception:
        pass
    return True


def ensure_materials():
    out = {}
    for nm, rgba in PALETTE.items():
        path = MATDIR + "/" + nm
        mat = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
        if mat is None:
            try:
                mat = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                    nm, MATDIR, unreal.Material, unreal.MaterialFactoryNew())
            except Exception:
                say("mat create fail %s:\n%s" % (nm, traceback.format_exc()))
                mat = None
        if mat is not None:
            _paint_material(mat, rgba)
            out[nm] = mat
    try:
        unreal.EditorAssetLibrary.save_directory(MATDIR, only_if_is_dirty=False, recursive=True)
    except Exception:
        pass
    return out


def run():
    try:
        with open(PLACEMENT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        say("placement.json load FAIL: %s" % traceback.format_exc())
        return
    entries = data.get("objects", [])
    parts = sorted(set(data.get("parts") or [e["part"] for e in entries]))
    say("START objects=%d parts=%d dir=%s" % (len(entries), len(parts), EXPORT_DIR))
    say("NOTE: FBX import is SLOW - big meshes can take minutes each, a whole scene "
        "easily 5-30 min. Do not close the editor and do not run the script twice; "
        "this list updates after every batch, and the full log is " + LOG)

    meshes = import_all(parts)

    # ---- Materials: when an FBX mesh and its material share a name they fight over
    #   it (the mesh keeps the plain name, the material gets a "1" suffix, or the other
    #   way round) ----
    #   1) Move the materials sitting in the MeshParts root into Materials/ and rename
    #      each one after the mesh it belongs to
    #   2) Give every mesh its own material (keeps the baked textures); only meshes with
    #      no material of their own get a flat-colour fallback
    mats_color = ensure_materials()

    # Collect every material asset in the content folder
    mat_assets = {}
    for p in unreal.EditorAssetLibrary.list_assets(CONTENT, recursive=True, include_folder=False):
        try:
            a = unreal.load_asset(p)
        except Exception:
            a = None
        if isinstance(a, unreal.MaterialInterface):
            mat_assets[akey(p)] = str(p)

    moved = 0
    mat_for_mesh = {}
    real_mat_for_mesh = {}
    for mname, mpath in mat_assets.items():
        # Find the mesh key this material belongs to (UE adds a "1" suffix to one of
        # the two, so the plain name can be either the mesh or the material)
        base = None
        if mname in meshes:
            base = mname
        else:
            for k in meshes:
                if k == mname or k.startswith(mname) or mname.startswith(k):
                    base = k
                    break
        if base is None:
            continue
        target = MATDIR + "/" + base
        if mpath.startswith(MATDIR + "/"):
            mat_for_mesh[base] = mpath
        elif unreal.EditorAssetLibrary.does_asset_exist(target):
            mat_for_mesh[base] = target
        else:
            try:
                unreal.EditorAssetLibrary.rename_asset(mpath, target)
                moved += 1
                mat_for_mesh[base] = target
            except Exception:
                mat_for_mesh[base] = mpath
        # If the name lines up with a mesh, treat it as that mesh's material
        # (a MaterialInstance created by the FBX import counts too)
        try:
            a = unreal.load_asset(mat_for_mesh[base])
            if isinstance(a, unreal.MaterialInterface):
                real_mat_for_mesh[base] = mat_for_mesh[base]
        except Exception:
            pass
    say("fbx material assets found=%d moved_to_Materials=%d usable_material=%d" % (
        len(mat_assets), moved, len(real_mat_for_mesh)))

    kept = 0
    assigned = 0
    for b, sm in meshes.items():
        # First trust the material slot imported directly from this FBX. Blender
        # material names usually do NOT match the mesh name, so guessing by asset
        # name here incorrectly replaces them with M_Stone.
        imported_slots = []
        try:
            imported_slots = list(sm.get_editor_property("static_materials") or [])
        except Exception:
            imported_slots = []
        imported_materials = []
        for slot in imported_slots:
            try:
                candidate = slot.get_editor_property("material_interface")
            except Exception:
                candidate = None
            if isinstance(candidate, unreal.MaterialInterface):
                candidate_name = akey(candidate.get_path_name())
                if candidate_name not in PALETTE:
                    imported_materials.append(candidate)
        if imported_materials:
            # Keep all imported slots (including multi-material meshes) unchanged.
            kept += 1
            continue

        # Secondary fallback: a real FBX material asset associated by name.
        mp = real_mat_for_mesh.get(b)
        mt = None
        if mp:
            try:
                mt = unreal.load_asset(mp)
            except Exception:
                mt = None
        if isinstance(mt, unreal.MaterialInterface) and akey(mt.get_path_name()) not in PALETTE:
            try:
                smat = unreal.StaticMaterial()
                smat.material_interface = mt
                sm.set_editor_property("static_materials", [smat])
                kept += 1
                continue
            except Exception:
                pass

        # Only meshes with no imported Blender material get a generated fallback.
        mt = mats_color.get(color_for(b))
        if mt is None:
            continue
        try:
            smat = unreal.StaticMaterial()
            smat.material_interface = mt
            sm.set_editor_property("static_materials", [smat])
            assigned += 1
        except Exception:
            pass
    try:
        unreal.EditorAssetLibrary.save_directory(MATDIR, only_if_is_dirty=False, recursive=True)
    except Exception:
        pass
    say("materials: per_mesh_fbx=%d fallback_color=%d" % (kept, assigned))

    les = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
    try:
        if unreal.EditorAssetLibrary.does_asset_exist(LEVEL):
            les.load_level(LEVEL)
        else:
            les.new_level(LEVEL, False)
        say("level ok")
    except Exception:
        say("level fail:\n" + traceback.format_exc())
    act = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    if CLEAR_OLD:
        cleared = 0
        try:
            for a in act.get_all_level_actors():
                try:
                    lbl = a.get_actor_label()
                    if lbl.startswith(("City_", "DisplayPart_")):
                        act.destroy_actor(a)
                        cleared += 1
                except Exception:
                    pass
        except Exception:
            pass
        say("cleared old: %d" % cleared)

    cm = 100.0
    spawned = 0
    miss = {}
    placed = []
    if USE_ISM:
        root_actor = act.spawn_actor_from_class(unreal.Actor, unreal.Vector(0, 0, 0))
        root_actor.set_actor_label("City_Instances")
        root = None
        by_part = {}
        for e in entries:
            by_part.setdefault(e["part"], []).append(e)
        for part, plist in by_part.items():
            sm = find_mesh(meshes, part)
            if sm is None:
                miss[part] = len(plist)
                continue
            comp = unreal.new_object(unreal.InstancedStaticMeshComponent, root_actor)
            comp.set_static_mesh(sm)
            if root is None:
                try:
                    root_actor.set_editor_property("root_component", comp)
                except Exception:
                    pass
                root = comp
            else:
                try:
                    comp.attach_to_component(root, unreal.AttachmentRule.KEEP_RELATIVE,
                                             unreal.AttachmentRule.KEEP_RELATIVE,
                                             unreal.AttachmentRule.KEEP_RELATIVE, False)
                except Exception:
                    pass
            try:
                comp.register_component()
            except Exception:
                pass
            for e in plist:
                x, y, z = e["loc"]
                qx, qy, qz, qw = e["rot"]
                loc = unreal.Vector(x * cm, -y * cm, z * cm)
                q = unreal.Quat(qx, -qy, -qz, qw)  # mirror the Y axis: yaw changes sign
                try:
                    rot = q.rotator()
                except Exception:
                    rot = unreal.MathLibrary.quat_rotator(q)
                s = e["scale"]
                tr = unreal.Transform(location=loc, rotation=rot, scale=unreal.Vector(s[0], s[1], s[2]))
                comp.add_instance(tr, True)
                spawned += 1
    else:
        for e in entries:
            sm = find_mesh(meshes, e["part"])
            if sm is None:
                miss[e["part"]] = miss.get(e["part"], 0) + 1
                continue
            x, y, z = e["loc"]
            qx, qy, qz, qw = e["rot"]
            loc = unreal.Vector(x * cm, -y * cm, z * cm)
            q = unreal.Quat(qx, -qy, -qz, qw)  # mirror the Y axis: yaw changes sign
            try:
                rot = q.rotator()
            except Exception:
                rot = unreal.MathLibrary.quat_rotator(q)
            a = act.spawn_actor_from_class(unreal.StaticMeshActor, loc, rot)
            if a is None:
                continue
            try:
                a.set_actor_label("City_" + e["obj"][:40])
            except Exception:
                pass
            s = e["scale"]
            a.set_actor_scale3d(unreal.Vector(s[0], s[1], s[2]))
            try:
                a.static_mesh_component.set_static_mesh(sm)
            except Exception:
                pass
            spawned += 1
    # Debug: log the real UE transform of the first three actors so it can be
    # compared against Blender
    try:
        dbg = []
        for e in entries[:3]:
            sm = find_mesh(meshes, e["part"])
            if sm is None:
                continue
            x, y, z = e["loc"]
            qx, qy, qz, qw = e["rot"]
            loc_expect = (x * 100.0, -y * 100.0, z * 100.0)
            dbg.append("%s | part=%s | expect_loc=%s | blender_rot=%s" % (
                e["obj"], e["part"], [round(v, 1) for v in loc_expect],
                [round(qx, 3), round(qy, 3), round(qz, 3), round(qw, 3)]))
        say("DEBUG_SAMPLES: " + " || ".join(dbg))
    except Exception:
        pass
    say("spawned=%d missing=%s" % (spawned, str(sorted(miss.items(), key=lambda kv: -kv[1])[:6])))

    try:
        sun = act.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0, 0, 12000), unreal.Rotator(0, -42, 35))
        sun.set_actor_label("City_Sun")
        sun.light_component.set_intensity(5.0)
        sky = act.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0, 0, 6000))
        sky.set_actor_label("City_SkyLight")
        atm = act.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0, 0, 0))
        atm.set_actor_label("City_Atmo")
        say("lights ok")
    except Exception:
        say("lights fail:\n" + traceback.format_exc())

    try:
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
        say("level saved")
    except Exception:
        say("level save fail: " + traceback.format_exc())

    say("DONE")


run()
