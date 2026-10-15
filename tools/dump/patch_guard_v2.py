"""
Make the stale-unpacked-level guard actually reliable.

BeamNG loads `current/levels/<name>/` in preference to the same level inside a mod.  The World
Editor recreates that directory whenever a level is opened or saved -- it writes `main.decals.json`
even for a level it did not otherwise touch -- so a single 281-byte file is enough to shadow the
entire mod.

An earlier version of this guard required `main/items.level.json` to be present before it would
delete anything, so a folder holding only `main.decals.json` slipped through.  The guard now
removes any folder for this level, and removes it whenever `--install` runs so the editor cannot
leave the mod shadowed between builds.
"""

import ast
import io
import os
import shutil

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("def remove_stale_unpacked_level(")
end = src.index("\n\n\n", src.index("return candidate", start))

NEW = '''def remove_stale_unpacked_level(level_name: str) -> Optional[str]:
    """
    Delete an unpacked level folder that would shadow this mod, and return its path.

    BeamNG resolves `current/levels/<name>/` BEFORE the same level inside a mod, so any folder
    there silently replaces everything the mod contains.  The World Editor creates one whenever a
    level is opened -- it writes `main.decals.json` even for a level it does not otherwise modify --
    and that alone is enough:

        current/levels/cannes/main.decals.json      281 bytes

    An earlier version of this guard only deleted the folder when `main/items.level.json` existed,
    so a folder holding just `main.decals.json` was left in place and continued to shadow the mod.
    Any directory for this level is now removed.
    """
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        return None

    levels_dir = os.path.join(local, "BeamNG", "BeamNG.drive", "current", "levels")
    if not os.path.isdir(levels_dir):
        return None

    removed = []
    # Match case-insensitively: the level is "Cannes" but the folder the editor writes is "cannes".
    for entry in os.listdir(levels_dir):
        if entry.lower() != level_name.lower():
            continue
        candidate = os.path.join(levels_dir, entry)
        if not os.path.isdir(candidate):
            continue
        try:
            shutil.rmtree(candidate)
            removed.append(candidate)
        except OSError:
            pass

    return removed[0] if removed else None'''

src = src[:start] + NEW + src[end:]

# Import shutil at module scope so the guard does not depend on a local import.
if "\nimport shutil\n" not in src:
    src = src.replace("import re\n", "import re\nimport shutil\n", 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("removes any folder for the level :", "entry.lower() != level_name.lower()" in src)
print("shutil at module scope           :", "\nimport shutil\n" in src)

# Remove the folder that is shadowing the mod right now.
cur = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "levels")
for entry in os.listdir(cur) if os.path.isdir(cur) else []:
    if entry.lower() == "cannes":
        target = os.path.join(cur, entry)
        print()
        print("removing the shadowing folder now:", target)
        shutil.rmtree(target, ignore_errors=True)
        print("  still exists:", os.path.isdir(target))
