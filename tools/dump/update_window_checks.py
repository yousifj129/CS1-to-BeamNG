"""
Update the window-material checks.

The old rule asserted the alias entries author no stages, from the assumption that `mapTo` inherits
a built-in material.  That assumption was wrong -- `mapTo` names a mesh slot, not a parent, and no
material in the install uses a `parent` field at all.  The window materials are therefore defined in
full, which is what makes them render.  The checks now assert that instead.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
PATH = os.path.join(REPO, "tools", "dump", "conformance.py")
src = io.open(PATH, encoding="utf-8").read()

OLD = '''    check(all("Stages" not in v for v in aliases.values()),
          "aliases author no stages (nothing new is created)")'''

NEW = '''    # `mapTo` is a mesh slot name, NOT inheritance: no material in the install declares a `parent`.
    # An entry with no stages therefore renders nothing, which is why the window materials are
    # defined in full rather than aliased.
    check(all(v.get("Stages") for v in aliases.values()),
          "window materials define stages (an entry without stages renders nothing)")

    # Every texture they reference must exist, or the window falls back to a warning material.
    WINDOW_GAME = r"D:\\SteamLibrary\\steamapps\\common\\BeamNG.drive"
    if os.path.isdir(WINDOW_GAME):
        install = set()
        for root, _dirs, files in os.walk(os.path.join(WINDOW_GAME, "content")):
            for fname in files:
                if not fname.endswith(".zip"):
                    continue
                try:
                    arch = zipfile.ZipFile(os.path.join(root, fname))
                except Exception:
                    continue
                for entry in arch.namelist():
                    install.add(entry.lower())
                arch.close()

        unresolved = []
        for v in aliases.values():
            for stage in v.get("Stages") or []:
                for value in (stage or {}).values():
                    if isinstance(value, str) and value.startswith("/"):
                        if value.lstrip("/").lower() not in install:
                            unresolved.append(value)
        check(not unresolved,
              "every window material texture resolves in the install",
              f"{len(unresolved)} unresolved: {unresolved[:3]}" if unresolved else "all resolve")'''

if OLD not in src:
    raise SystemExit("alias stage check anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(PATH, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("updated window checks; syntax OK")
