# Blender2UE Mesh Bridge | Blender -> Unreal Engine  (UE 5.6 - 5.8)
#
# Repository: https://github.com/Mowen-M/Blender2UE-Mesh-Bridge
# License:    GPL-3.0-or-later (inherited from CoordiKnight v1.3).  See LICENSE.
#
# Based on CoordiKnight v1.3 by Nazzareno Giannelli (github.com/NazzarenoGiannelli/coordiknight)
# Rewritten to fix what breaks in UE 5.5/5.6/5.7/5.8:
#
#   1. UE's paste gate.  UEditorEngine::CanPasteSelectedActorsFromClipboard() does
#        PasteString.StartsWith("BEGIN MAP")
#      which is case-SENSITIVE (identical from UE 4.27 through 5.6.1).  Measured on
#      5.6.1: this gate only guards the console PASTE command - the interactive Ctrl+V
#      accepts v1.3's "Begin Map" anyway.  We still emit "BEGIN MAP" because it is what
#      UE itself writes and it makes the exec path work too.
#
#   2. Local vs world transforms.  v1.3 reads object.location / rotation_euler / scale,
#      which are LOCAL values.  Any parented or constrained object lands in the wrong
#      place.  We read matrix_world.
#
#   3. Scale semantics.  v1.3 copies the Blender object scale into RelativeScale3D.
#      The placeholder is /Engine/BasicShapes/Cube, which is already 100 cm wide, while
#      an FBX-imported mesh already carries its real size.  Dropping the real mesh onto
#      the placeholder keeps the actor's scale (UE only calls SetStaticMesh - see
#      ComponentAssetBroker.cpp), so the object gets multiplied by the object scale:
#      that is the stretching.  Default mode therefore emits scale = 1.
#
#   4. A stale, hard-coded StaticMeshDerivedDataKey copied out of some old UE build.
#      It is version-specific and useless across 5.6 -> 5.8, so it is gone.
#
#   5. Every actor was named Cube19_4.  Names are now unique.
#
#   6. Numbers were serialised with str(), which can produce "1e-05"; UE's T3D float
#      parser does not accept exponent notation.  Fixed-width decimals now.
#
#   7. Double offset, measured on 5.6.1.  When a Blender FBX is imported as a StaticMesh,
#      UE bakes the object's world translation AND rotation into the mesh vertices (the
#      pivot stays at the mesh origin).  Writing the world transform onto the actor on
#      at X=5 m lands at X=10 m.  That only happens when the FBX itself carries the
#      placement, i.e. the object was left moved in the Blender scene when it was
#      exported.  The default WORLD mode writes the real world Location/Rotation with
#      Scale = 1 - verified live on 5.8.4 (Details: 201.4 / -1.58 / 152.2, Yaw 35,
#      Scale 1) and on 5.6.1 - because the usual workflow models the object around its
#      own pivot and lets the paste supply the placement.  If you export with the object
#      left moved and rotated, pick the "FBX carries position" (BAKED) mode instead:
#      it was measured to give 0.00 cm error on all axes for five objects including a
#      parented child and a rotated+scaled cylinder.
#
#   8. Placeholders are no longer all cubes.  Each object gets a BasicShape that matches
#      its proportions (cone if it narrows upward, cylinder if it is post-like, plane if
#      it is paper-thin, otherwise cube) and within one copy no two objects repeat a
#      shape, so pasting several objects at once stays readable in the viewport.
#      Match-bounds keeps the cube: it is the only BasicShape whose native bounding box
#      is exactly 100x100x100, which is what makes the blocking-out size exact.
#
#   9. 2.3.0: NEW "Export Display Parts to UE" command.  Copies UE's blockout workflow end to end:
#      every unique mesh of the selection becomes its own FBX (origin set to the geometry
#      centre, geometry baked at the world origin, material carried in the FBX) and a
#      placement.json records each object's name / mesh / world transform.  The UE side
#      script (shipped in ue_side/) imports the FBXs, names the materials after the parts,
#      creates /Game/Maps/Auto_placed_Map and spawns every StaticMeshActor back at the
#      exact transform - no manual dragging, no offset.  Coordinates: UE = (x, -y, z)*100.

bl_info = {
    "name": "Blender2UE Mesh Bridge (UE 5.6-5.8)",
    "author": "Mowen (Bowen Sun) - based on CoordiKnight v1.3 by Nazzareno Giannelli",
    "version": (1, 0, 0),
    "blender": (2, 83, 0),
    "category": "Object",
    "location": "View 3D > Object > Blender2UE Mesh Bridge",
    "description": "Bridge Blender meshes into Unreal Engine: exact position/rotation/scale via clipboard T3D, or FBX + placement.json export with materials",
    "warning": "",
    "doc_url": "https://github.com/Mowen-M/Blender2UE-Mesh-Bridge",
    "tracker_url": "https://github.com/Mowen-M/Blender2UE-Mesh-Bridge/issues",
}

import bpy
import math
import os
import re
import json
import shutil
from mathutils import Matrix, Vector

# UE's /Engine/BasicShapes/Cube is a 100 cm cube, so one Blender metre == one unit of
# placeholder scale.
CUBE_SIZE_CM = 100.0

# Y-flip between Blender's right-handed space and UE's left-handed space.
# UE_x =  B_x,  UE_y = -B_y,  UE_z =  B_z
Y_FLIP = Matrix(((1.0, 0.0, 0.0),
                 (0.0, -1.0, 0.0),
                 (0.0, 0.0, 1.0)))


def _num(value):
    """T3D-safe float: plain decimal, never exponent notation, never '-0.000000'."""
    out = f"{float(value):.6f}"
    if out.startswith("-") and float(out) == 0.0:
        out = out[1:]
    return out


def _safe_name(name):
    """Keep the ActorLabel token well-formed across UE versions."""
    return (name.replace('"', "'").replace("\\", "_")
                .replace("\r", "").replace("\n", " ").strip() or "Actor")


def _ue_loc(vec):
    return (_num(vec.x * 100.0), _num(-vec.y * 100.0), _num(vec.z * 100.0))


def _ue_rot_from_world(obj):
    """World-space rotation of the object as UE (Pitch, Yaw, Roll) in degrees.

    mathutils stores a matrix so that a point transforms as  p_world = p_local @ M.
    Read as an ordinary column-vector operator, that same rotation is therefore M^T.
    UE's actor rotation matrix is the Blender rotation conjugated by the Y-flip:

        R_ue = Y . M^T . Y          (Y = Y_FLIP, its own inverse)

    and UE builds it as Rz(Yaw) . Ry(Pitch) . Rx(Roll), which inverts to

        pitch = asin(-R[2][0])   yaw = atan2(R[1][0], R[0][0])   roll = atan2(R[2][1], R[2][2])

    Conjugating without the transpose (what v2.0 did) gives R_ue^T: for a pure yaw the
    sign flips, for a compound rotation it lands 90-150 degrees off.  Settled by
    tests/probe_blender_rot.py, which feeds real point sets through both candidates
    and asks which one reproduces the UE-space image of the Blender rotation.
    """
    rot = obj.matrix_world.to_quaternion().to_matrix()
    ue_rot = (Y_FLIP @ rot @ Y_FLIP).transposed()
    # UE builds its matrix as Rz(Yaw) * Ry(Pitch) * Rx(Roll)
    pitch = math.asin(max(-1.0, min(1.0, -ue_rot[2][0])))
    if abs(math.cos(pitch)) > 1e-6:
        yaw = math.atan2(ue_rot[1][0], ue_rot[0][0])
        roll = math.atan2(ue_rot[2][1], ue_rot[2][2])
    else:
        # Gimbal lock: at Pitch = +/-90 yaw and roll are no longer independent
        # (only their sum or difference survives), so the ordinary extraction above
        # silently produces a wrong orientation.  Pin roll to 0 and recover yaw from
        # the row that is still well conditioned.
        roll = 0.0
        if pitch > 0.0:
            yaw = math.atan2(-ue_rot[0][1], ue_rot[0][2])
        else:
            yaw = math.atan2(-ue_rot[0][1], -ue_rot[0][2])
    return _num(math.degrees(pitch)), _num(math.degrees(yaw)), _num(math.degrees(roll))


def _world_dims(obj):
    """World-space, axis-aligned size of the object in metres (what UE will show)."""
    from mathutils import Vector
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return mx - mn


def _world_center(obj):
    from mathutils import Vector
    pts = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
    mn = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    mx = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (mn + mx) * 0.5


def _ue_mesh_ref(prefix, obj_name):
    """'/Game/Foo/Bar.Bar' style reference for an already-imported UE asset."""
    prefix = (prefix or "").strip().rstrip("/")
    name = _safe_name(obj_name)
    if not prefix:
        return None
    return f"{prefix}/{name}.{name}"


# UE's own BasicShapes.  Kept as object-path strings because that is exactly the token
# the T3D parser expects after StaticMesh=/Script/Engine.StaticMesh'...'.
# All six exist in every engine installed here (4.27 / 5.3 / 5.4 / 5.5 / 5.6 / 5.7 / 5.8).
BASIC_SHAPE_REFS = (
    "/Engine/BasicShapes/Cube.Cube",
    "/Engine/BasicShapes/Cylinder.Cylinder",
    "/Engine/BasicShapes/Cone.Cone",
    "/Engine/BasicShapes/Sphere.Sphere",
    "/Engine/BasicShapes/Plane.Plane",
    "/Engine/BasicShapes/Torus.Torus",
)


def _taper_ratio(obj):
    """How much narrower the top of the object is than its bottom (1.0 = no taper).

    Used only to pick a placeholder shape: below ~0.4 a Cone reads far better than a
    Cylinder.  Vertex counts are capped because this runs per object per copy.
    """
    verts = obj.data.vertices
    n = min(len(verts), 4000)
    if n < 8:
        return 1.0
    mw = obj.matrix_world
    pts = [mw @ verts[i].co for i in range(n)]
    zs = [p.z for p in pts]
    lo, hi = min(zs), max(zs)
    span = hi - lo
    if span < 1e-6:
        return 1.0

    def extent(sel):
        xs = [p.x for p in sel]
        ys = [p.y for p in sel]
        return (max(xs) - min(xs)) + (max(ys) - min(ys))

    band = 0.15 * span
    top = [p for p in pts if p.z > hi - band]
    bot = [p for p in pts if p.z < lo + band]
    if not top or not bot:
        return 1.0
    e_bot = extent(bot)
    if e_bot <= 1e-6:
        return 1.0
    return extent(top) / e_bot


def _placeholder_shape(obj, index, used):
    """Pick one of UE's built-in BasicShapes for this object.

    Several objects pasted at once all used to arrive as identical 1 m cubes, which made
    them impossible to tell apart in the viewport.  The shape follows the object's own
    proportions, and within one batch every object gets a different shape where the list
    allows it, so the placeholders stay distinguishable.
    """
    dims = _world_dims(obj)
    short, mid, long_ = sorted((dims.x, dims.y, dims.z))
    eps = 1e-6
    if short < 0.02 * max(long_, eps):
        shape = "Plane"                       # paper-thin: a flat sheet reads correctly
    elif _taper_ratio(obj) < 0.4:
        shape = "Cone"                        # clearly narrowing upwards
    elif mid < 0.35 * max(long_, eps):
        shape = "Cylinder"                    # post / rod / tower
    else:
        shape = "Cube"

    ref = f"/Engine/BasicShapes/{shape}.{shape}"
    if ref in used:
        for alt in BASIC_SHAPE_REFS:
            if alt not in used:
                ref = alt
                break
    used.add(ref)
    return ref


def build_t3d(objects, mode="BAKED", ue_mesh_prefix="", vary_placeholders=True):
    """Return the T3D clipboard text for the given Blender objects."""
    actors = []
    used_names = set()
    used_shapes = set()

    for index, obj in enumerate(objects, start=1):
        label = _safe_name(obj.name)

        # unique T3D object name (v1.3 reused 'Cube19_4' for everything)
        base = "CK_" + "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in label)
        actor_name = f"{base}_{index}"
        while actor_name in used_names:
            actor_name += "x"
        used_names.add(actor_name)

        pitch, yaw, roll = _ue_rot_from_world(obj)

        if mode == "BOUNDS":
            # placeholder cube sized to the object's real world size, centred on the
            # object's world bounding-box centre.  Nice for blocking out a scene, but
            # dropping the real mesh on it WILL scale the mesh - that is the trade-off.
            dims = _world_dims(obj)
            scale = (_num(max(dims.x, 1e-6)), _num(max(dims.y, 1e-6)), _num(max(dims.z, 1e-6)))
            lx, ly, lz = _ue_loc(_world_center(obj))
        elif mode == "WORLD":
            # for FBX exports where the transform was applied in Blender (mesh data is
            # relative to the pivot): put the transform on the actor instead.
            scale = ("1.000000", "1.000000", "1.000000")
            lx, ly, lz = _ue_loc(obj.matrix_world.translation)
        else:
            # BAKED (default) / DIRECT.  Measured on UE 5.6.1: when Blender's FBX is
            # imported as a StaticMesh, UE bakes the object's world translation AND
            # rotation into the mesh vertices (pivot stays at the mesh origin).  So the
            # actor must sit at the origin with identity rotation/scale - writing the
            # world transform on top of it is exactly the double offset users see.
            scale = ("1.000000", "1.000000", "1.000000")
            pitch = yaw = roll = "0.000000"
            lx = ly = lz = "0.000000"

        mesh_ref = None
        if mode == "DIRECT":
            mesh_ref = _ue_mesh_ref(ue_mesh_prefix, obj.name)
        if not mesh_ref:
            if mode == "BOUNDS" or not vary_placeholders:
                # BOUNDS sizes the placeholder with RelativeScale3D, and only the cube's
                # native bounding box is exactly 100x100x100, so keeping the cube there is
                # what makes the blocking-out size correct.
                mesh_ref = BASIC_SHAPE_REFS[0]
            else:
                mesh_ref = _placeholder_shape(obj, index, used_shapes)

        actors.append(f"""
    Begin Actor Class=/Script/Engine.StaticMeshActor Name={actor_name} Archetype=/Script/Engine.StaticMeshActor'/Script/Engine.Default__StaticMeshActor'
        Begin Object Class=/Script/Engine.StaticMeshComponent Name="StaticMeshComponent0" Archetype=/Script/Engine.StaticMeshComponent'/Script/Engine.Default__StaticMeshActor:StaticMeshComponent0'
        End Object
        Begin Object Name="StaticMeshComponent0"
            StaticMesh=/Script/Engine.StaticMesh'"{mesh_ref}"'
            OverrideMaterials(0)=/Script/Engine.Material'"/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"'
            RelativeLocation=(X={lx},Y={ly},Z={lz})
            RelativeRotation=(Pitch={pitch},Yaw={yaw},Roll={roll})
            RelativeScale3D=(X={scale[0]},Y={scale[1]},Z={scale[2]})
        End Object
        StaticMeshComponent="StaticMeshComponent0"
        RootComponent="StaticMeshComponent0"
        ActorLabel="{label}"
    End Actor""")

    # UE 5.5/5.6 gate: CanPasteSelectedActorsFromClipboard() requires the text to start
    # with the upper-case token. The parser itself is case-insensitive, so the rest of
    # the document keeps UE's own mixed-case style.
    header = "BEGIN MAP\nBEGIN LEVEL"
    footer = "\nEND LEVEL\nBEGIN SURFACE\nEND SURFACE\nEND MAP"
    return header + "".join(actors) + footer


class OBJECT_OT_coordiknight(bpy.types.Operator):
    """Copy UE-ready T3D for the selected objects to the clipboard, then Ctrl+V in Unreal Engine"""
    bl_idname = "object.coordiknight"
    bl_label = "Blender2UE Mesh Bridge"
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=(
            ('WORLD', "Paste carries position (default)", "Writes the object's world Location and Rotation onto the actor and leaves Scale at 1. Verified live on UE 5.8.4 and 5.6.1: the pasted actor lands exactly where the Blender object is (Y flipped) with the right yaw/pitch/roll, and dropping your exported mesh on it keeps that position. This is the mode to use when your FBX is modelled around its own pivot, so the mesh carries size but not placement."),
            ('BAKED', "FBX already carries position", "Scale 1, actor at the origin. Only right when your FBX export keeps the object's world transform, because UE then bakes that transform into the mesh vertices (measured on UE 5.6.1) and a positioned actor would offset it a second time."),
            ('BOUNDS', "Match bounds", "Placeholder sized to the object's real world size, centred on its world bounding box. Good for blocking out; dropping the real mesh on it will scale that mesh."),
            ('DIRECT', "Use my UE meshes", "Reference the StaticMesh assets you already imported into UE (fill in the UE folder below). Paste gives the finished actors, no dragging needed."),
        ),
        default='WORLD',
        description="How the placeholder is sized and where its pivot goes",
    )
    ue_mesh_prefix: bpy.props.StringProperty(
        name="UE mesh folder",
        default="/Game/Meshes",
        description="UE folder that holds the imported StaticMeshes whose names match the Blender objects",
    )

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects) and context.mode == 'OBJECT'

    def execute(self, context):
        selected = list(context.selected_objects)
        vary = getattr(context.scene.coordiknight_settings, "vary_placeholders", True)
        text = build_t3d(selected, mode=self.mode, ue_mesh_prefix=self.ue_mesh_prefix,
                         vary_placeholders=vary)
        context.window_manager.clipboard = text

        if self.mode == 'DIRECT' and not self.ue_mesh_prefix.strip():
            self.report({'WARNING'}, "B2UE: 'Use my UE meshes' needs a UE folder, fell back to the Cube placeholder")
        elif self.mode == 'BOUNDS':
            self.report({'WARNING'}, "B2UE: Match-bounds placeholders are scaled - dropping the real mesh on them will scale it. Use 'Paste carries position' if you plan to drop meshes in.")
        self.report({'INFO'}, f"B2UE: copied {len(selected)} actor(s) [{self.mode.lower()}] to clipboard")
        return {'FINISHED'}

    def invoke(self, context, event):
        return self.execute(context)


class OBJECT_OT_coordiknight_menu(bpy.types.Operator):
    """Open the Blender2UE Mesh Bridge operator with its options"""
    bl_idname = "object.coordiknight_menu"
    bl_label = "Blender2UE Mesh Bridge"

    def execute(self, context):
        return bpy.ops.object.coordiknight('INVOKE_DEFAULT')


class VIEW3D_PT_coordiknight(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "B2UE Bridge"
    bl_label = "Blender -> UE 5.6+"

    def draw(self, context):
        layout = self.layout
        col = layout.column(align=True)
        col.operator("object.coordiknight", text="Copy (paste carries position - default)").mode = 'WORLD'
        col.operator("object.coordiknight", text="Copy (FBX carries position)").mode = 'BAKED'
        col.operator("object.coordiknight", text="Copy (match bounds)").mode = 'BOUNDS'
        layout.prop(context.scene.coordiknight_settings, "vary_placeholders",
                    text="Different placeholder per object")
        box = layout.box()
        box.label(text="Use my UE meshes:")
        box.prop(context.scene.coordiknight_settings, "ue_mesh_prefix", text="")
        box.operator("object.coordiknight", text="Copy (direct UE meshes)").mode = 'DIRECT'
        box2 = layout.box()
        box2.label(text="Auto export -> auto-place in UE:")
        box2.prop(context.scene.coordiknight_settings, "ue_export_dir", text="")
        box2.operator("object.coordiknight_export_parts", text="Export Parts to UE (FBX + Placement)", icon='EXPORT')


class CoordiKnightSettings(bpy.types.PropertyGroup):
    ue_mesh_prefix: bpy.props.StringProperty(
        name="UE mesh folder",
        default="/Game/Meshes",
        description="UE folder holding StaticMeshes named after the Blender objects",
    )
    vary_placeholders: bpy.props.BoolProperty(
        name="Different placeholder per object",
        default=True,
        description="Give each pasted actor a different BasicShape (cube / cylinder / cone / sphere / plane / torus) chosen from the object's own proportions, so several objects copied at once are easy to tell apart in the viewport. Match-bounds always uses the cube so its size stays exact",
    )
    ue_export_dir: bpy.props.StringProperty(
        name="UE Export Directory",
        subtype='DIR_PATH',
        default="//ue_parts/",
        description="Output folder for FBX / placement.json / ue_side scripts (// = next to current .blend)",
    )


# --------------------------------------------- FBX + placement table export for UE (2.3.0)

def _ue_safe_name(n):
    """Make a Blender name safe as a UE asset name.  Dots, spaces and slashes all
    break the asset path (UE reads Cube.031 as package.object)."""
    return re.sub(r'[^\w\-]', '_', n)


def _mesh_bbox_center(me):
    vs = [v.co for v in me.vertices]
    if not vs:
        return (0.0, 0.0, 0.0)
    mn = [min(v[i] for v in vs) for i in range(3)]
    mx = [max(v[i] for v in vs) for i in range(3)]
    return [(mn[i] + mx[i]) * 0.5 for i in range(3)]


UE_README = r"""Blender2UE Mesh Bridge: Blender export  ->  UE auto-import
==========================================================

In Blender (this add-on):
  1) Select the objects you want to export (a whole city, a group of buildings,
     display parts - anything).
  2) N panel  >  B2UE Bridge  >  "Export Parts to UE (FBX + Placement)"
       -> one FBX per unique mesh: origin set to the geometry centre, geometry baked at
          the world origin, materials packed into the FBX
       -> placement.json: name / mesh / world location / rotation / scale of every
          object (units: metres)
       -> ue_side\ is filled with the UE-side scripts automatically

In Unreal Engine (choose one):
  A. Run it yourself:  Tools > Execute Script...  (or the Python console:
     py "C:/<export dir>/ue_side/ue_import_parts.py" )
     The script finds placement.json and parts\ next to itself, imports every FBX into
     /Game/MeshParts, creates /Game/Maps/Auto_placed_Map, spawns one actor per object at
     the exact transform, adds Sun + SkyLight + SkyAtmosphere and saves the level.
  B. On project start: copy ue_side\init_unreal.py to
     <UE project>\Content\Python\init_unreal.py. The shipped file does nothing on
     purpose - it is a placeholder so a project does not re-import by itself.

Key points:
  - FBX import must have "Import Materials" turned on. Materials are collected into
    /Game/MeshParts/Materials/<part name>
  - While importing, UE lets the material take the plain name and renames the mesh to
    <name>1 (or the other way round). The script renames things back once the import is
    done, so do not rename assets by hand in between.
  - Coordinate conversion: UE = (x*100, -y*100, z*100) centimetres,
    quaternion = (x, -y, z, w)
  - Destination folders, the level name and whether the old City_/DisplayPart_ actors are
    cleared are constants at the top of ue_side\ue_import_parts.py
    (CONTENT / MATDIR / LEVEL / USE_ISM / CLEAR_OLD)
  - Every run writes a log: <export dir>\ue_import_log.txt
"""


class OBJECT_OT_coordiknight_export_parts(bpy.types.Operator):
    """Export one FBX per unique mesh of the selection (origin at the geometry
    centre) and write placement.json so UE can put every part back in place"""
    bl_idname = "object.coordiknight_export_parts"
    bl_label = "Export Parts to UE (FBX + Placement)"
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return bool(context.selected_objects) and context.mode == 'OBJECT'

    def execute(self, context):
        settings = context.scene.coordiknight_settings
        # Resolve the user's chosen export path. Blender's // paths are relative to
        # the current .blend file; absolute paths are preserved. Normalize Windows
        # separators and expand ~ so any chosen export directory works.
        raw_outdir = settings.ue_export_dir or "//ue_parts/"
        outdir = os.path.abspath(os.path.normpath(
            os.path.expanduser(bpy.path.abspath(raw_outdir))
        ))
        parts_dir = os.path.join(outdir, "parts")
        try:
            os.makedirs(parts_dir, exist_ok=True)
        except OSError as exc:
            self.report({'ERROR'}, "B2UE: cannot create export directory %s (%s)" % (outdir, exc))
            return {'CANCELLED'}
        objs = [o for o in context.selected_objects if o.type == 'MESH']
        if not objs:
            self.report({'ERROR'}, "B2UE: select at least one mesh object first")
            return {'CANCELLED'}

        meshes = {}
        for o in objs:
            meshes.setdefault(o.data.as_pointer(), o.data)

        prev_sel = [o for o in context.selected_objects]
        prev_active = context.view_layer.objects.active
        exported, fails = 0, []
        for me in meshes.values():
            name = _ue_safe_name(me.name)
            tmp = bpy.data.objects.new("CK_EXPORT_TMP", me)
            context.scene.collection.objects.link(tmp)
            c = _mesh_bbox_center(me)
            tmp.matrix_world = Matrix.Translation((-c[0], -c[1], -c[2]))
            bpy.ops.object.select_all(action='DESELECT')
            tmp.select_set(True)
            context.view_layer.objects.active = tmp
            fn = os.path.join(parts_dir, name + ".fbx")
            try:
                bpy.ops.export_scene.fbx(filepath=fn, use_selection=True, object_types={'MESH'},
                                         use_mesh_modifiers=True, apply_unit_scale=True,
                                         apply_scale_options='FBX_SCALE_ALL',
                                         bake_space_transform=True,
                                         path_mode='COPY', embed_textures=True,
                                         axis_forward='-Z', axis_up='Y', add_leaf_bones=False)
                exported += 1
            except Exception as e:
                fails.append((me.name, str(e)))
            bpy.data.objects.remove(tmp, do_unlink=True)

        # Placement table
        entries = []
        for o in objs:
            loc, rot, scl = o.matrix_world.decompose()
            # 2026-10-27 fix: the FBX geometry is baked at the geometry centre, so the
            # placement must use the world position of that centre, not of the object origin.
            c = _mesh_bbox_center(o.data)
            loc = o.matrix_world @ Vector((c[0], c[1], c[2]))
            entries.append({
                "obj": o.name,
                "part": _ue_safe_name(o.data.name),
                "mesh": o.data.name,
                "coll": (o.users_collection[0].name if o.users_collection else ""),
                "loc": [loc.x, loc.y, loc.z],
                "rot": [rot.x, rot.y, rot.z, rot.w],
                "scale": [scl.x, scl.y, scl.z],
            })
        with open(os.path.join(outdir, "placement.json"), "w", encoding="utf-8") as f:
            json.dump({"units": "meters", "count": len(entries), "objects": entries},
                      f, ensure_ascii=False, indent=1)

        # Ship the UE-side scripts and the instructions with the export
        src_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ue_side")
        side_dir = os.path.join(outdir, "ue_side")
        if os.path.isdir(src_dir):
            os.makedirs(side_dir, exist_ok=True)
            for fn in ("init_unreal.py", "ue_import_parts.py", "add_lights.py", "focus_cam.py"):
                src = os.path.join(src_dir, fn)
                if os.path.isfile(src):
                    shutil.copy2(src, os.path.join(side_dir, fn))
        with open(os.path.join(outdir, "README.txt"), "w", encoding="utf-8") as f:
            f.write('py "ue_import_parts.py"\n')
        with open(os.path.join(outdir, "README_UE.txt"), "w", encoding="utf-8") as f:
            f.write(UE_README)

        # Restore the original selection
        bpy.ops.object.select_all(action='DESELECT')
        for o in prev_sel:
            try:
                o.select_set(True)
            except Exception:
                pass
        context.view_layer.objects.active = prev_active

        msg = "Exported %d mesh FBX + %d placements -> %s" % (exported, len(entries), outdir)
        if fails:
            msg += " (%d failed: %s)" % (len(fails), fails[0])
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def menu_func(self, context):
    self.layout.operator(OBJECT_OT_coordiknight.bl_idname)


classes = (CoordiKnightSettings, OBJECT_OT_coordiknight, OBJECT_OT_coordiknight_menu,
           OBJECT_OT_coordiknight_export_parts, VIEW3D_PT_coordiknight)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.coordiknight_settings = bpy.props.PointerProperty(type=CoordiKnightSettings)
    bpy.types.VIEW3D_MT_object.append(menu_func)


def unregister():
    bpy.types.VIEW3D_MT_object.remove(menu_func)
    del bpy.types.Scene.coordiknight_settings
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
