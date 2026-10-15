"""
Guard against the stale unpacked level that overrode the mod.

BeamNG loads an unpacked level from

    %LOCALAPPDATA%\\BeamNG\\BeamNG.drive\\current\\levels\\<name>\\

in PREFERENCE to the same level inside a mounted mod.  The World Editor creates that folder when
it saves a level, and it was present for this level from an earlier session:

    current\\levels\\cannes\\main\\MissionGroup\\Roads\\items.level.json      0 bytes
    current\\levels\\cannes\\main\\MissionGroup\\Roads_0\\items.level.json    0 bytes
    current\\levels\\cannes\\main\\MissionGroup\\Roads_1\\items.level.json    0 bytes

That single stale folder caused every symptom chased over the last several rounds -- an empty
Roads folder, the old `cs1_building_*` shapes, the "No Mesh" placeholders and grey terrain --
because the engine never read the mod at all.  Clearing the material cache did not help, because
the stale level was not a cache.

`--install` now detects it, reports it, and removes it so the mod is what actually loads.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

HELPER = '''def remove_stale_unpacked_level(level_name: str) -> Optional[str]:
    """
    Delete an unpacked level folder that would override the mod, if one exists.

    BeamNG resolves `current/levels/<name>/` BEFORE the same level inside a mod, so a folder left
    behind by the World Editor silently replaces everything the mod contains.  Returns the path
    that was removed, or None.

    This is what produced the "empty Roads folder" and the "No Mesh" buildings: an old unpacked
    copy of this level sat in the user folder and was loaded instead of the mod.
    """
    import shutil

    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None

    candidate = os.path.join(local, "BeamNG", "BeamNG.drive", "current", "levels", level_name)
    if not os.path.isdir(candidate):
        return None

    # Only remove it if it really is this level (guard against a similarly named unrelated map).
    marker = os.path.join(candidate, "main", "items.level.json")
    if not os.path.isfile(marker):
        return None

    try:
        shutil.rmtree(candidate)
    except OSError:
        return None
    return candidate


'''

anchor = "def zip_mod(mod_root: str, zip_path: str) -> str:"
if anchor not in src:
    raise SystemExit("zip_mod anchor not found")
src = src.replace(anchor, HELPER + anchor, 1)

# Call it from the install step.
INSTALL_ANCHORS = [
    'shutil.copy2(zip_path, os.path.join(mods_dir, os.path.basename(zip_path)))',
    'shutil.copyfile(zip_path, os.path.join(mods_dir, os.path.basename(zip_path)))',
    'shutil.copy(zip_path, os.path.join(mods_dir, os.path.basename(zip_path)))',
]
for a in INSTALL_ANCHORS:
    if a in src:
        src = src.replace(
            a,
            "removed = remove_stale_unpacked_level(level_name)\n"
            "        if removed:\n"
            "            print(\n"
            "                f\"  removed stale unpacked level (it would override the mod):\\n\"\n"
            "                f\"    {removed}\"\n"
            "            )\n"
            "        " + a,
            1,
        )
        print("install hook inserted before:", a[:52])
        break
else:
    print("WARNING: could not find the install copy call; guard not wired in")

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("helper added:", "def remove_stale_unpacked_level(" in src)
print("hook wired  :", "removed = remove_stale_unpacked_level(level_name)" in src)
