"""
Add a verifier check: every scene object's __parent must name a DECLARED SimGroup.

This is the check that would have caught the empty-Roads bug: the objects parsed fine, the log
reported no error, but 1244 DecalRoads pointed at `"__parent": "Roads"`, a group that nothing
declares, so the engine dropped them.  Buildings were created despite the same mistake because
their parent string happened to match a real group; roads were not.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "verify_conversion.py")
src = io.open(TARGET, encoding="utf-8").read()

CHECK = '''

def check_parent_groups(mod_root: str, level_name: str, report) -> None:
    """
    Every object's __parent must be the name of a SimGroup declared somewhere in the level.

    An object whose parent is not declared is silently dropped by the engine: no log error, no
    visible symptom beyond the object not existing.  This caught 1244 DecalRoads pointing at a
    non-existent "Roads" group, which left the Roads folder empty in the editor scene tree.
    """
    main_root = os.path.join(mod_root, "levels", level_name, "main")
    if not os.path.isdir(main_root):
        return

    items_files = []
    for current, _dirs, names in os.walk(main_root):
        if "items.level.json" in names:
            items_files.append(os.path.join(current, "items.level.json"))

    declared = set()
    for path in items_files:
        for obj in _iter_json_objects(io.open(path, encoding="utf-8").read()):
            if isinstance(obj, dict) and obj.get("class") == "SimGroup" and obj.get("name"):
                declared.add(obj["name"])

    report.check(bool(declared), "no SimGroup is declared anywhere in the level")

    orphans = {}
    for path in items_files:
        for obj in _iter_json_objects(io.open(path, encoding="utf-8").read()):
            if not isinstance(obj, dict) or obj.get("class") == "SimGroup":
                continue
            parent = obj.get("__parent")
            if parent and parent not in declared:
                orphans.setdefault(parent, []).append(obj.get("class"))

    for parent, classes in sorted(orphans.items()):
        counts = {}
        for name in classes:
            counts[name] = counts.get(name, 0) + 1
        summary = ", ".join(f"{v}x {k}" for k, v in sorted(counts.items()))
        report.check(
            False,
            f"{len(classes)} object(s) ({summary}) reference undeclared parent group "
            f"'{parent}'; the engine will silently drop them",
        )
'''

anchor = "def verify_level("
if anchor not in src:
    raise SystemExit("verify_level anchor not found")
src = src.replace(anchor, CHECK.strip("\n") + "\n\n\n" + anchor, 1)

# io is needed for the new check.
if "\nimport io\n" not in src:
    src = src.replace("\nimport json\n", "\nimport io\nimport json\n", 1)

# Call it: find the existing group-declaration check and append the call after it.
CALL_ANCHOR = "report.check("
if "check_parent_groups" in src and "check_parent_groups(" not in src.split("def verify_level(")[1]:
    # Insert the call just before verify_level returns, using the last known report statement.
    marker = "\n    return report"
    idx = src.find(marker, src.index("def verify_level("))
    if idx == -1:
        raise SystemExit("could not find verify_level return")
    src = src[:idx] + (
        "\n\n    # An object whose __parent is not a declared SimGroup is silently dropped.\n"
        "    check_parent_groups(mod_root, level_name, report)"
    ) + src[idx:]

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("check defined :", "def check_parent_groups(" in src)
print("check called  :", src.split("def verify_level(")[1].count("check_parent_groups(mod_root"))
