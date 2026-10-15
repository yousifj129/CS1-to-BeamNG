"""
Chain road segments into continuous polylines, and use the chains when emitting DecalRoads.

Problem: the export has one DecalRoad per CS1 segment, and CS1 splits the network finely -- 780 of
1244 segments are bare two-node stubs.  Each decal fades in and out at its own ends, so consecutive
segments leave visible gaps, and at intersections several decals overlap and stack their fades.

Fix: walk the segment graph and join segments that share a node into long polylines, cutting the
chains at junctions (nodes where 3+ segments meet) so each road ends cleanly at the junction
instead of piling up.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

HELPER = '''def chain_roads(
    roads: Sequence["Road"], max_sagitta: float = 0.5
) -> List[Dict[str, Any]]:
    """
    Join road segments that share a node into long continuous centre-lines.

    Returns dicts of {points, width, material, road} where `points` is the whole polyline in CS1
    space and `width` is the widest segment in the chain (so a junction is not pinched).

    Why: the export contains one segment per CS1 road piece and CS1 splits the network finely --
    780 of 1244 segments are bare two-node stubs.  Emitting one DecalRoad each leaves a gap at
    every boundary, because each decal fades in and out at its own ends.

    Junction handling: a node touched by three or more segments is a junction, and chains are cut
    there.  Each incoming road then ends cleanly at the junction rather than several overlapping
    and stacking their fades, which is what tears intersections apart.

    Every segment is consumed exactly once, so no stretch of road is drawn twice.
    """
    if not roads:
        return []

    incident: Dict[int, List[Tuple[int, str]]] = {}
    for index, road in enumerate(roads):
        incident.setdefault(road.start_node_id, []).append((index, "start"))
        incident.setdefault(road.end_node_id, []).append((index, "end"))

    junction_nodes = {node for node, uses in incident.items() if len(uses) >= 3}
    used = [False] * len(roads)

    def polyline_of(road: "Road") -> List[Vec3]:
        return list(road.surface_polyline(max_sagitta))

    # Build chains starting at junctions and dead ends first, so open chains are formed before any
    # closed loop is walked.
    def priority(index: int) -> Tuple[int, int]:
        road = roads[index]
        ends_at_junction = (
            road.start_node_id in junction_nodes or road.end_node_id in junction_nodes
        )
        return (0 if ends_at_junction else 1, index)

    chains: List[Dict[str, Any]] = []

    for seed in sorted(range(len(roads)), key=priority):
        if used[seed]:
            continue
        seed_road = roads[seed]
        used[seed] = True
        members = [seed]
        chain = polyline_of(seed_road)

        # Grow forward from the seed's end node, then backward from its start node.
        for direction in ("end", "start"):
            node_id = seed_road.end_node_id if direction == "end" else seed_road.start_node_id
            while node_id not in junction_nodes:
                candidates = [
                    (idx, end) for idx, end in incident.get(node_id, []) if not used[idx]
                ]
                if len(candidates) != 1:
                    # 0 means a dead end; more than one is ambiguous, so stop rather than guess.
                    break
                idx, entered_by = candidates[0]
                nxt = roads[idx]
                used[idx] = True
                members.append(idx)

                pts = polyline_of(nxt)
                # `entered_by` is the end of `nxt` that touches node_id, so traverse away from it.
                if entered_by == "start":
                    oriented = pts
                    node_id = nxt.end_node_id
                else:
                    oriented = list(reversed(pts))
                    node_id = nxt.start_node_id

                if direction == "end":
                    if chain and oriented and oriented[0].distance_to(chain[-1]) < 0.05:
                        oriented = oriented[1:]
                    chain.extend(oriented)
                else:
                    if chain and oriented and oriented[-1].distance_to(chain[0]) < 0.05:
                        oriented = oriented[:-1]
                    chain = oriented + chain

        if len(chain) < 2:
            continue

        widths = [roads[i].measured_width for i in members]
        widest = max(widths)
        representative = roads[max(members, key=lambda i: roads[i].measured_width)]
        chains.append(
            {
                "points": chain,
                "width": widest,
                "material": material_for(representative),
                "road": representative,
                "segments": len(members),
            }
        )

    return chains


'''

anchor = "class BeamNGLevelBuilder:"
if anchor not in src:
    raise SystemExit("builder class anchor not found")
src = src.replace(anchor, HELPER + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("chain_roads added:", "def chain_roads(" in src)
print("returns dicts    :", '"segments": len(members)' in src)
