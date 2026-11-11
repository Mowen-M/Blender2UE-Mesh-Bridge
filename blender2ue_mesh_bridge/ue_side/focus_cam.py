# focus_cam.py -- point the editor viewport camera at the imported scene.
#
# The centre is read from placement.json next to this script's export folder, so it works
# for whatever you exported.  Coordinate conversion Blender -> UE: (x, -y, z) * 100.
# If placement.json is not found, the Fallback centre/size below are used - set them by
# hand if you need a fixed camera.
import json
import os
import unreal

_here = os.path.dirname(os.path.abspath(__file__))
_parent = os.path.dirname(_here)

# Fallback: centre in Blender metres and a rough radius, used only when placement.json
# cannot be found next to this script.
FALLBACK_CENTRE_M = (171.0, 87.0, 30.0)
FALLBACK_RADIUS_M = 120.0

centre_m, radius_m = FALLBACK_CENTRE_M, FALLBACK_RADIUS_M
for candidate in (os.path.join(_parent, "placement.json"), os.path.join(_here, "placement.json")):
    try:
        with open(candidate, "r", encoding="utf-8") as f:
            data = json.load(f)
        locs = [e["loc"] for e in data.get("objects", []) if len(e.get("loc", ())) == 3]
        if locs:
            mn = [min(l[i] for l in locs) for i in range(3)]
            mx = [max(l[i] for l in locs) for i in range(3)]
            centre_m = [(mn[i] + mx[i]) * 0.5 for i in range(3)]
            radius_m = max(1.0, max(mx[i] - mn[i] for i in range(3)) * 0.5)
            break
    except Exception:
        continue

cm = 100.0
center = unreal.Vector(centre_m[0] * cm, -centre_m[1] * cm, centre_m[2] * cm)
# Oblique view from the south-west, raised by roughly two scene radii.
dist = radius_m * cm * 2.2
loc = unreal.Vector(center.x - dist, center.y - dist * 1.6, center.z + dist * 0.9)
rot = unreal.MathLibrary.find_look_at_rotation(loc, center)

sub = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem)
log = ["centre_ue=%s radius_cm=%.0f" % ([round(v, 1) for v in (center.x, center.y, center.z)],
                                        radius_m * cm)]
try:
    sub.set_level_viewport_camera_info(loc, rot)
    log.append("oblique camera set")
except Exception as e:
    log.append("oblique failed: %s" % e)

# Straight top-down alternative, ready to use if the oblique view is not what you want:
# top_loc = unreal.Vector(center.x, center.y, center.z + dist * 2.0)
# top_rot = unreal.Rotator(0.0, -90.0, 0.0)
log.append("top_down alternative in comments")

unreal.log("[focus_cam] " + "; ".join(log))
try:
    with open(os.path.join(_here, "ue_cam_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log))
except Exception as e:
    unreal.log_warning("[focus_cam] could not write log: %s" % e)
