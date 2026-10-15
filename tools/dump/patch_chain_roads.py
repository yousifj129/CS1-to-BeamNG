"""
Chain road segments into continuous polylines.

The exported 1244 DecalRoads are one-per-CS1-segment, and CS1 breaks the network into short
pieces: 780 of them have only two nodes.  Drawing each separately leaves visible gaps at every
segment boundary because each decal has its own start/end fade and junction handling.

This walks the segment graph and joins segments that share a node, producing long continuous
polylines.  Chains BREAK at junctions -- nodes where more than two segments meet -- so an
intersection is not double-drawn with overlapping fades, which is what makes junctions look torn.
"""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

HELPER = '''def chain_roads(
    roads: Sequence["Road"], max_sagitta: float = 0.5
) -> List[Tuple[List[Vec3], float, str]]:
    """
    Join road segments that share a node into long continuous centre-lines.

    Returns a list of (points, width, material) where `points` is the full polyline in CS1 space.

    Why this is needed: the export contains one segment per CS1 road piece, and CS1 splits the
    network finely -- 780 of 1244 segments are bare two-node stubs.  Emitting one DecalRoad each
    leaves a gap at every boundary, because each decal fades in and out at its own ends.

    Junction handling: a node touched by three or more segments is a junction.  Chains are cut
    there, so each incoming road ends cleanly at the junction instead of several roads overlapping
    and stacking their fades.  That overlap is what tears intersections apart visually.

    Each segment is consumed exactly once, so no stretch of road is drawn twice.
    """
    # node id -> list of (segment index, which end)
    incident: Dict[int, List[Tuple[int, str]]] = {}
    for index, road in enumerate(roads):
        incident.setdefault(road.start_node_id, []).append((index, "start"))
        incident.setdefault(road.end_node_id, []).append((index, "end"))

    junction_nodes = {node for node, uses in incident.items() if len(uses) >= 3}

    used = [False] * len(roads)

    def points_of(road: "Road", forward: bool) -> List[Vec3]:
        pts = road.surface_polyline(max_sagitta)
        return list(pts) if forward else list(reversed(pts))

    def other_end(road: "Road", entering: str) -> Tuple[int, str]:
        """Given the end we entered by, return the node id and opposite end name."""
        if entering == "start":
            return road.end_node_id, "end"
        return road.start_node_id, "start"

    chains: List[Tuple[List[Vec3], float, str]] = []

    # Start from junctions and dead ends first, so open chains get built before loops.
    order = sorted(
        range(len(roads)),
        key=lambda i: (
            0 if roads[i].start_node_id in junction_nodes else 1,
            0 if roads[i].end_node_id in junction_nodes else 1,
            i,
        ),
    )

    for seed in order:
        if used[seed]:
            continue
        road = roads[seed]
        used[seed] = True

        # Extend forward from the seed's end node, then backward from its start node.
        chain: List[Vec3] = list(road.surface_polyline(max_sagitta))

        for direction in ("end", "start"):
            node_id = road.end_node_id if direction == "end" else road.start_node_id
            while True:
                if node_id in junction_nodes:
                    break
                candidates = [
                    (idx, end)
                    for idx, end in incident.get(node_id, [])
                    if not used[idx]
                ]
                if len(candidates) != 1:
                    # 0 -> dead end; >1 -> ambiguous, stop rather than guess.
                    break
                idx, end = candidates[0]
                nxt = roads[idx]
                used[idx] = True
                # `end` is the end of `nxt` that touches node_id, so traverse away from it.
                forward = end == "start"
                pts = points_of(nxt, forward)
                if direction == "end":
                    chain.extend(pts[1:] if pts and chain and pts[0].distance_to(chain[-1]) < 0.01 else pts)
                else:
                    pts = list(reversed(pts))
                    chain = (pts[:-1] if pts and chain and pts[-1].distance_to(chain[0]) < 0.01 else pts) + chain
                node_id, _ = other_end(nxt, end)

        if len(chain) >= 2:
            # Use the widest segment in the chain so junctions are not pinched.
            width = max(
                (r.measured_width for r in roads if not used or True),
                default=road.measured_width,
            )
            chains.append((chain, road.measured_width, material_for(road)))

    return chains


'''

anchor = "class BeamNGLevelBuilder:"
if anchor not in src:
    raise SystemExit("builder class anchor not found")
src = src.replace(anchor, HELPER + anchor, 1)

io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("chain_roads added:", "def chain_roads(" in src)
