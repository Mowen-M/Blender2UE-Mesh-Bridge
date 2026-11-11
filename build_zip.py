import hashlib, os, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "blender2ue_mesh_bridge")
OUT = os.path.join(ROOT, "V1", "Blender2UE_Mesh_Bridge_v1.0.0.zip")

files = []
for dirpath, dirnames, filenames in os.walk(PKG):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    for fn in sorted(filenames):
        if fn.endswith(".pyc"):
            continue
        full = os.path.join(dirpath, fn)
        rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
        files.append((full, rel))
files.sort(key=lambda x: x[1])

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as z:
    for full, rel in files:
        z.write(full, rel)

data = open(OUT, "rb").read()
print("zip:", OUT)
print("entries:", len(files))
for _, rel in files:
    print("  ", rel)
print("bytes:", len(data))
print("sha256:", hashlib.sha256(data).hexdigest())
