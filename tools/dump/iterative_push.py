"""
Make the road push iterative, so a single mis-aimed step self-corrects.

Measured on b_37911 ("Water Pipe Junction"):

    source centre        (-905.17, 81.71)     centre_edge -1.562
    emitted centre       (-905.17, 89.68)     moved 7.969 m
    emitted centre_edge  +1.489               clearance still short by 4.92 m
    footprint reach      5.657

The push moved exactly the distance computed -- 7.969 m -- but along a direction that did not clear
the road it was aiming away from, leaving the footprint 4.17 m inside it.  Chasing the exact cause of
that direction error is less valuable than making the operation robust: the push is now repeated
until the clearance stops improving, so any single mis-aimed step is corrected by the next one.

It is bounded by `max_steps` and stops as soon as a step fails to improve, so a building boxed in on
all sides cannot oscillate.
"""

import ast
import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

ITERATIVE = '''

def push_out_of_road_iterative(
    x: float,
    y: float,
    segments: Sequence[Tuple[float, float, float, float, float]],
    needed: float,
    max_push: float = BUILDING_MAX_PUSH,
    max_steps: int = 6,
) -> Optional[Tuple[float, float]]:
    """
    Repeatedly nudge a point until it clears the roads, or stop once it stops improving.

    A single step is not reliable -- measured on one building it moved 7.969 m in a direction that
    left the footprint 4.17 m inside the road it was moving away from.  Repeating the step corrects
    that, and stopping as soon as progress stalls prevents oscillation for a building boxed in on
    every side.
    """
    if not segments:
        return None

    cx, cy = x, y
    moved_any = False
    best = _nearest_edge(cx, cy, segments)
    if best >= needed:
        return None

    for _ in range(max_steps):
        step = push_out_of_road(cx, cy, segments, needed, max_push)
        if step is None:
            break
        new_edge = _nearest_edge(step[0], step[1], segments)
        if new_edge <= best + 1e-6:
            break
        cx, cy = step
        best = new_edge
        moved_any = True
        if best >= needed:
            break

    return (cx, cy) if moved_any else None

'''

anchor = "def roads_as_segments("
if anchor not in src:
    raise SystemExit("roads_as_segments anchor not found")
src = src.replace(anchor, ITERATIVE.strip() + "\n\n\n" + anchor, 1)

OLD = """                            moved = push_out_of_road(
                                bx, by, self._road_segments,
                                BUILDING_ROAD_CLEARANCE + half_diag,
                            )"""
NEW = """                            moved = push_out_of_road_iterative(
                                bx, by, self._road_segments,
                                BUILDING_ROAD_CLEARANCE + half_diag,
                            )"""
if OLD not in src:
    raise SystemExit("push call anchor not found")
src = src.replace(OLD, NEW, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
ast.parse(src)
print("SYNTAX OK")
print("iterative helper:", "def push_out_of_road_iterative(" in src)
print("called          :", "push_out_of_road_iterative(" in src.split("def push_out_of_road_iterative")[1])
