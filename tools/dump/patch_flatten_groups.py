"""
Flatten road/building groups, the way working maps do it.

Studied polish_roads_v2 (a large working third-party map).  Its road group is:

    main/MissionGroup/Dworzec_traffic/items.level.json
        declares: nothing nested
        contains: 38x DecalRoad, all "__parent": "Dworzec_traffic"

So objects live DIRECTLY in the folder named after their group, and `__parent` is that group's
name.  There is no intermediate `_0` sub-group.  Every group in that map follows this:

    main/MissionGroup/DynamicLights/items.level.json   declares ['lampy'], 1201 lights __parent DynamicLights
    main/MissionGroup/BarierkiDrogowe/items.level.json declares ['guardrails_l'], 1233 TSStatic __parent BarierkiDrogowe

Our earlier structure invented a `Roads_0` / `Roads_1` split, which the engine did not follow.
The objects are now written directly into `MissionGroup/Roads/items.level.json` and
`MissionGroup/Buildings/items.level.json`, with `__parent` naming that same group.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

START = "    def _emit_grouped("
END = "    # ---------------------------------------------------------------- level metadata"
start = src.index(START)
end = src.index(END, start)

NEW = '''    def _emit_grouped(
        self, objects: List[Dict[str, Any]], group: str, container: str
    ) -> List[str]:
        """
        Write every object of `group` into <container>/<group>/items.level.json.

        Objects go DIRECTLY in the folder named after their group, with `__parent` set to that
        same group name.  This matches how working maps are laid out -- polish_roads_v2 keeps 38
        DecalRoads in `MissionGroup/Dworzec_traffic/items.level.json` all parented to
        `Dworzec_traffic`, and its 1201 dynamic lights in `MissionGroup/DynamicLights/` all
        parented to `DynamicLights`.

        An earlier revision split the objects into invented `_0` / `_1` sub-groups.  Those
        sub-groups are declared nowhere else in the level, and the engine followed the level's own
        structure instead, so the objects were dropped -- the Roads folder came up empty in the
        scene tree while the geometry parsed cleanly and the log reported no error.
        """
        written: List[str] = []
        if not objects:
            return written

        group_root = os.path.join(self.main_root, container, group)
        os.makedirs(group_root, exist_ok=True)

        # One flat file, each object parented to the group that owns the folder.
        for obj in objects:
            obj["__parent"] = group

        path = os.path.join(group_root, "items.level.json")
        self.write_lines(path, objects)
        written.append(os.path.relpath(path, self.mod_root))

        # Remove any stale chunk folders from a previous build, so an old `Roads_0/` cannot
        # linger and confuse the loader.
        for name in os.listdir(group_root):
            candidate = os.path.join(group_root, name)
            if os.path.isdir(candidate) and name.startswith(f"{group}_"):
                import shutil

                shutil.rmtree(candidate, ignore_errors=True)

        return written

'''

src = src[:start] + NEW + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("flattened _emit_grouped :", "One flat file, each object parented" in src)
print("stale chunk cleanup     :", "shutil.rmtree(candidate" in src)
