# init_unreal.py -- startup hook for UE's plugin system.
#
# It intentionally does NOTHING: running an import every time a project is opened or
# created is never what you want.
#
# To import right now: open Window > Output Log and type
#     py "C:/<your export folder>/ue_side/ue_import_parts.py"
#
# If you really want the import to run automatically on project start, replace this file
# with a copy of ue_import_parts.py (or ask and it can be generated as init_unreal_auto.py).
