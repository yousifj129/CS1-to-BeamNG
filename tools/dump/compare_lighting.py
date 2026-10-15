import json
import os
import re
import zipfile

REPO = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")

# Does a working level's ScatterSky.elevation agree with its TimeOfDay.startTime?
# If elevation is derived from time, a morning startTime must pair with a low positive elevation.
for name in sorted(os.listdir(REPO)):
    if not name.endswith(".zip"):
        continue
    path = os.path.join(REPO, name)
    try:
        archive = zipfile.ZipFile(path)
    except Exception:
        continue

    tod = sky = None
    try:
        for entry in archive.infolist():
            if not entry.filename.endswith("items.level.json") or entry.file_size == 0:
                continue
            if entry.file_size > 40_000_000:
                continue
            text = archive.read(entry).decode("utf-8", "replace")
            for line in text.splitlines():
                if tod is None and '"class": "TimeOfDay"' in line or '"class":"TimeOfDay"' in line:
                    try:
                        tod = json.loads(line)
                    except Exception:
                        pass
                if sky is None and ('"class": "ScatterSky"' in line or '"class":"ScatterSky"' in line):
                    try:
                        sky = json.loads(line)
                    except Exception:
                        pass
            if tod and sky:
                break
    except Exception:
        archive.close()
        continue
    finally:
        pass

    if tod or sky:
        print(f"{name}")
        if tod:
            print("   TimeOfDay  : startTime=%s time=%s animate=%s dayLength=%s" % (
                tod.get("startTime"), tod.get("time"), tod.get("animate"), tod.get("dayLength")))
        if sky:
            print("   ScatterSky : elevation=%s azimuth=%s ambientScale=%s exposure=%s" % (
                sky.get("elevation"), sky.get("azimuth"),
                sky.get("ambientScale"), sky.get("exposure")))
        if tod and sky:
            st = tod.get("startTime")
            el = sky.get("elevation")
            if isinstance(st, (int, float)) and isinstance(el, (int, float)):
                # Rough check: a sun above the horizon at local noonish should have elevation > 0.
                print("   -> startTime %.3f, elevation %.1f  (%s)" % (
                    st, el, "elevation positive, consistent with daytime"
                    if el > 0 else "elevation NEGATIVE despite startTime"))
        print()
    archive.close()
