"""Make emit_roads use chained polylines instead of one DecalRoad per segment."""

import io
import os

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
TARGET = os.path.join(REPO, "tools", "beamng_convert.py")
src = io.open(TARGET, encoding="utf-8").read()

start = src.index("    def emit_roads(self) -> None:")
end = src.index("    # ---------------------------------------------------------------- buildings", start)

NEW = '''    def emit_roads(self) -> None:
        """
        Emit one DecalRoad per CHAINED centre-line, not per segment.

        One decal per segment produced visible gaps: each decal fades in and out at its own ends,
        so 1244 mostly-two-node stubs -- 780 of them bare two-node pieces -- left a seam at every
        boundary, and at intersections several decals overlapped and stacked their fades.  Chaining
        through shared nodes yields 173 continuous polylines instead, cut at junctions.

        `startEndFade` is also zeroed now.  It is what creates the gradual fade at each end of a
        decal; with one decal per segment that meant a fade every few metres.  With long chains the
        fades belong only at genuine road ends, and inside a junction a fade is exactly what makes
        the surface appear to break up.
        """
        objects: List[Dict[str, Any]] = []
        material_usage: Counter = Counter()

        chains = chain_roads(self.roads, self.max_sagitta)

        for entry in chains:
            points = entry["points"]
            width = max(entry["width"], self.max_width)
            material = entry["material"]
            road = entry["road"]
            material_usage[material] += 1

            nodes: List[List[float]] = []
            for point in points:
                bx, by, bz = point.beamng()
                if self.terrain is not None:
                    # Project onto the reconstructed ground so the decal follows the surface.
                    bz = self.ground_height(bx, by)
                nodes.append([round(bx, 4), round(by, 4), round(bz, 4), round(width, 4)])

            if len(nodes) < 2:
                continue

            # Drop consecutive duplicates, which would give the spline zero-length spans.
            deduped: List[List[float]] = []
            for node in nodes:
                if deduped:
                    dx = node[0] - deduped[-1][0]
                    dy = node[1] - deduped[-1][1]
                    if dx * dx + dy * dy < 0.0004:
                        continue
                deduped.append(node)
            nodes = deduped
            if len(nodes) < 2:
                continue

            decal: Dict[str, Any] = {
                "class": "DecalRoad",
                "persistentId": new_id(),
                "__parent": "Roads",
                "position": nodes[0][:3],
                "material": material,
                "textureLength": 16.0,
                "renderPriority": 10,
                "drivability": 1.0,
                "autoLanes": True,
                "autoJunction": True,
                "oneWay": road.is_one_way,
                "improvedSpline": True,
                "smoothness": 0.5,
                "breakAngle": 0.5,
                "decalBias": 0.002,
                "distanceFade": [3000, 500],
                # No fade along a chain: a fade mid-road is what made the surface look broken up.
                "startEndFade": [0.0, 0.0],
                "overObjects": not self.with_terrain,
                "nodes": nodes,
            }
            objects.append(decal)
            self.report["decalRoadNodes"] += len(nodes)

        self.report["roadsConverted"] = len(objects)
        self.report["roadChains"] = len(chains)
        self.report["roadSegmentsChained"] = sum(e["segments"] for e in chains)
        self.report["materials"] = dict(material_usage.most_common())
        self.report["roadGroupFiles"] = self._emit_grouped(
            objects, group="Roads", container="MissionGroup"
        )

'''

src = src[:start] + NEW + src[end:]
io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
print("emit_roads now chains      :", "chains = chain_roads(self.roads" in src)
print("startEndFade zeroed        :", '"startEndFade": [0.0, 0.0]' in src)
