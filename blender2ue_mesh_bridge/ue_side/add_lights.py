# add_lights.py -- add the missing default lighting to the current level
# (DirectionalLight / SkyLight / SkyAtmosphere) and report what it did.
# Safe to run several times: anything that already exists is left alone.
import os
import unreal

_here = os.path.dirname(os.path.abspath(__file__))
sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
existing = list(sub.get_all_level_actors())
has_sun = any(isinstance(a, unreal.DirectionalLight) for a in existing)
log = []

if not has_sun:
    sun = sub.spawn_actor_from_class(unreal.DirectionalLight, unreal.Vector(0.0, 0.0, 20000.0),
                                     unreal.Rotator(0.0, -48.0, 35.0))
    if sun:
        try:
            sun.set_actor_label("Sun")
        except Exception:
            pass
    log.append("sun spawned")
else:
    log.append("sun exists")

if not any(isinstance(a, unreal.SkyLight) for a in existing):
    try:
        sky = sub.spawn_actor_from_class(unreal.SkyLight, unreal.Vector(0.0, 0.0, 10000.0),
                                         unreal.Rotator(0.0, 0.0, 0.0))
        log.append("skylight spawned")
    except Exception as e:
        log.append("skylight failed: %s" % e)

if not any(isinstance(a, unreal.SkyAtmosphere) for a in existing):
    try:
        atm = sub.spawn_actor_from_class(unreal.SkyAtmosphere, unreal.Vector(0.0, 0.0, 0.0),
                                         unreal.Rotator(0.0, 0.0, 0.0))
        log.append("skyatmosphere spawned")
    except Exception as e:
        log.append("atmosphere failed: %s" % e)

# The level is NOT saved here on purpose - save it yourself with Ctrl+S when you are happy
# with the result.
log.append("level not saved (save it with Ctrl+S)")

unreal.log("[add_lights] " + "; ".join(log))
try:
    with open(os.path.join(_here, "ue_lights_log.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(log))
except Exception as e:
    unreal.log_warning("[add_lights] could not write log: %s" % e)
