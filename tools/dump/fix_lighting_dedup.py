"""
Fix two defects in the lighting emitter, both found by the conformance report.

1. DUPLICATES.  The emitter scanned every `items.level.json` in `levels/template.zip` and collected
   all matching objects.  The template holds the same five lighting objects in two different files,
   so the level ended up with TWO LevelInfo, TWO TimeOfDay, TWO ScatterSky and TWO CloudLayer -- 10
   objects where polish_roads_v2 has exactly five.  Measured there: every core atmosphere object
   appears EXACTLY ONCE, all five in a single file.

   The emitter now keeps the first occurrence of each class only.

2. `globalEnviromentMap`.  polish_roads_v2's LevelInfo sets it to a cubemap name, under that exact
   spelling -- missing the `n` in "Environment".  The engine complains
   `LevelInfo dont have defined globalEnviromentMap for vehicle's static reflections` when it is
   absent, which our logs have shown repeatedly.  It is now set.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

OLD_COLLECT = """        objects: List[Dict[str, Any]] = []
        template = None

        game = find_beamng_install()
        if game:
            archive = os.path.join(game, "content", "levels", "template.zip")
            if os.path.isfile(archive):
                template = archive

        if template:
            with zipfile.ZipFile(template) as source:
                for entry in source.infolist():
                    if not entry.filename.lower().endswith("items.level.json"):
                        continue
                    try:
                        text = source.read(entry).decode("utf-8", "replace")
                    except Exception:
                        continue
                    decoder = json.JSONDecoder()
                    index = 0
                    while index < len(text):
                        while index < len(text) and text[index].isspace():
                            index += 1
                        if index >= len(text):
                            break
                        try:
                            obj, index = decoder.raw_decode(text, index)
                        except json.JSONDecodeError:
                            break
                        if not isinstance(obj, dict):
                            continue
                        if obj.get("class") in (
                            "LevelInfo", "TimeOfDay", "ScatterSky", "CloudLayer",
                            "Precipitation", "ForestWindEmitter",
                        ):
                            clone = dict(obj)
                            clone["persistentId"] = new_id()
                            clone["__parent"] = "sky_and_sun"
                            clone.pop("name", None)
                            clone["name"] = clone.get("name", obj.get("class"))
                            objects.append(clone)
"""

NEW_COLLECT = """        objects: List[Dict[str, Any]] = []
        seen: set = set()
        template = None

        game = find_beamng_install()
        if game:
            archive = os.path.join(game, "content", "levels", "template.zip")
            if os.path.isfile(archive):
                template = archive

        if template:
            with zipfile.ZipFile(template) as source:
                for entry in source.infolist():
                    if not entry.filename.lower().endswith("items.level.json"):
                        continue
                    try:
                        text = source.read(entry).decode("utf-8", "replace")
                    except Exception:
                        continue
                    decoder = json.JSONDecoder()
                    index = 0
                    while index < len(text):
                        while index < len(text) and text[index].isspace():
                            index += 1
                        if index >= len(text):
                            break
                        try:
                            obj, index = decoder.raw_decode(text, index)
                        except json.JSONDecodeError:
                            break
                        if not isinstance(obj, dict):
                            continue
                        cls = obj.get("class")
                        if cls not in (
                            "LevelInfo", "TimeOfDay", "ScatterSky", "CloudLayer",
                            "Precipitation", "ForestWindEmitter",
                        ):
                            continue
                        # Keep the FIRST of each class only.  The template holds the same five
                        # objects in two different files; collecting every match produced ten
                        # objects and two of each class.  polish_roads_v2 has exactly one of each.
                        if cls in seen:
                            continue
                        seen.add(cls)

                        clone = dict(obj)
                        clone["persistentId"] = new_id()
                        clone["__parent"] = "sky_and_sun"
                        clone["name"] = obj.get("name", cls)

                        # The engine expects a cubemap here, under this exact spelling (missing the
                        # `n` in "Environment").  Its absence is what produces
                        # "LevelInfo dont have defined globalEnviromentMap for vehicle's static
                        # reflections" in the log.
                        if cls == "LevelInfo" and not clone.get("globalEnviromentMap"):
                            clone["globalEnviromentMap"] = "BNG_Sky_02_cubemap"

                        objects.append(clone)
"""

if OLD_COLLECT not in src:
    raise SystemExit("lighting collection anchor not found")
src = src.replace(OLD_COLLECT, NEW_COLLECT, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("dedup by class      :", "if cls in seen:" in src)
print("globalEnviromentMap :", "BNG_Sky_02_cubemap" in src)
