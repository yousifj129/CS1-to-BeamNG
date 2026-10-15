"""Add the undeclared-parent check to verify_conversion.py, using its real helpers."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "verify_conversion.py")
src = io.open(TARGET, encoding="utf-8").read()

CHECK = '''def check_declared_parents(main_root: str, report) -> None:
    """
    Every non-group object's `__parent` must name a SimGroup that is actually declared.

    An object whose parent is not declared is dropped by the engine with no log error and no
    visible symptom other than the object not existing.  This is exactly what happened to 1244
    DecalRoads, which pointed at a group called "Roads" that nothing declares -- the objects
    parsed cleanly, the level loaded, and the Roads folder in the scene tree was empty.
    """
    if not os.path.isdir(main_root):
        return

    objects = list(walk_all_objects(main_root))
    declared = {
        obj.get("name")
        for obj in objects
        if obj.get("class") == "SimGroup" and obj.get("name")
    }

    report.check(bool(declared), "no SimGroup is declared anywhere in the level")

    orphans: Dict[str, Dict[str, int]] = {}
    for obj in objects:
        if obj.get("class") == "SimGroup":
            continue
        parent = obj.get("__parent")
        if parent and parent not in declared:
            counts = orphans.setdefault(parent, {})
            key = str(obj.get("class"))
            counts[key] = counts.get(key, 0) + 1

    for parent, counts in sorted(orphans.items()):
        total = sum(counts.values())
        summary = ", ".join(f"{v}x {k}" for k, v in sorted(counts.items()))
        report.check(
            False,
            f"{total} object(s) ({summary}) reference undeclared parent group '{parent}'; "
            f"the engine drops these silently",
        )


'''

anchor = "def walk_all_objects(root: str) -> Iterable[Dict[str, Any]]:"
if anchor not in src:
    raise SystemExit("walk_all_objects anchor not found")
src = src.replace(anchor, CHECK + anchor, 1)

# Call it from verify(): append just before the function's return.
start = src.index("def verify(")
marker = "\n    return report"
pos = src.find(marker, start)
if pos == -1:
    # Fall back to the last line of verify() before the next top-level def.
    nxt = src.index("\ndef to_beamng(", start)
    body = src[start:nxt]
    src = src[:nxt] + (
        "\n    # Objects whose __parent is not a declared SimGroup are silently dropped.\n"
        "    check_declared_parents(os.path.join(mod_root, \"levels\", LEVEL_NAME, \"main\"), report)\n"
    ) + src[nxt:]
else:
    src = src[:pos] + (
        "\n\n    # Objects whose __parent is not a declared SimGroup are silently dropped.\n"
        "    check_declared_parents(os.path.join(mod_root, \"levels\", LEVEL_NAME, \"main\"), report)"
    ) + src[pos:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("check defined :", "def check_declared_parents(" in src)
print("check called  :", "check_declared_parents(" in src.split("def check_declared_parents(")[1])
