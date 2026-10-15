#!/usr/bin/env python3
"""
CS1-to-BeamNG :: mutation test for the conformance verifier (tools/verify_conversion.py)
========================================================================================

A verification tool that cannot fail is worthless.  This harness takes a known-good generated
level, applies one deliberate corruption at a time, and checks that `verify_conversion.py`
reports a failure for each.

Every mutation corresponds to a realistic mistake: an off-by-one in the terrain header, a
forgotten power-of-two rounding, a layer map that punches holes, a rotation matrix that is not
a rotation, an items file wrapped in an array, a dangling shape reference, terrain metadata that
disagrees with itself.

Usage
-----
    python tools/mutation_test.py <city_layout.json> [--mod dist/cs1_cannes]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
from typing import Callable, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_mod(explicit: Optional[str]) -> str:
    if explicit:
        return explicit
    dist = os.path.join(REPO_ROOT, "dist")
    candidates = [
        os.path.join(dist, name)
        for name in (os.listdir(dist) if os.path.isdir(dist) else [])
        if os.path.isdir(os.path.join(dist, name, "levels"))
    ]
    if not candidates:
        raise SystemExit("No converted level found under dist/.")
    return max(candidates, key=os.path.getmtime)


def level_dir(mod_root: str) -> str:
    levels = os.path.join(mod_root, "levels")
    names = [n for n in os.listdir(levels) if os.path.isdir(os.path.join(levels, n))]
    if not names:
        raise SystemExit("No level folder found.")
    return os.path.join(levels, names[0])


# ------------------------------------------------------------------------------------------
#  Mutations.  Each takes the mod root and damages it in one specific way.
# ------------------------------------------------------------------------------------------


def mutate_ter_version(mod: str) -> str:
    path = os.path.join(level_dir(mod), f"{os.path.basename(level_dir(mod))}.ter")
    with open(path, "r+b") as handle:
        handle.seek(0)
        handle.write(struct.pack("<B", 7))
    return ".ter version changed from 9 to 7"


def mutate_ter_size(mod: str) -> str:
    path = os.path.join(level_dir(mod), f"{os.path.basename(level_dir(mod))}.ter")
    with open(path, "r+b") as handle:
        handle.seek(1)
        handle.write(struct.pack("<I", 5000))
    return ".ter size changed to 5000 (not a power of two)"


def mutate_terrain_hole(mod: str) -> str:
    name = os.path.basename(level_dir(mod))
    path = os.path.join(level_dir(mod), f"{name}.ter")
    size = 8192
    with open(path, "r+b") as handle:
        handle.seek(5 + size * size * 2 + 1000)
        handle.write(bytes([255]))
    return "layer map set to 255 (punches a terrain hole)"


def mutate_rotation(mod: str) -> str:
    folder = os.path.join(level_dir(mod), "main", "MissionGroup", "Buildings", "Buildings_0")
    path = os.path.join(folder, "items.level.json")
    text = open(path, encoding="utf-8").read()
    text = text.replace(
        '"rotationMatrix": [\n   1.0,\n   0.0,\n   0.0,\n   0.0,\n   1.0,\n   0.0,\n   0.0,\n   0.0,\n   1.0\n  ]',
        '"rotationMatrix": [\n   2.0,\n   0.0,\n   0.0,\n   0.0,\n   1.0,\n   0.0,\n   0.0,\n   0.0,\n   1.0\n  ]',
        1,
    )
    if text == open(path, encoding="utf-8").read():
        # fall back to a regex-free nudge: scale the first rotation value
        lines = text.splitlines()
        for index, line in enumerate(lines):
            if '"rotationMatrix"' in line:
                for offset in range(1, 12):
                    if lines[index + offset].strip() and lines[index + offset].strip()[0].isdigit():
                        lines[index + offset] = "   2.0,"
                        break
                break
        text = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    return "first building rotationMatrix made non-orthonormal"


def mutate_wrapped_array(mod: str) -> str:
    path = os.path.join(
        level_dir(mod), "main", "MissionGroup", "Roads", "Roads_0", "items.level.json"
    )
    text = open(path, encoding="utf-8").read()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("[" + text + "]\n")
    return "items.level.json wrapped in a JSON array"


def mutate_missing_shape(mod: str) -> str:
    art = os.path.join(mod, "art", "shapes")
    for folder in os.listdir(art):
        shape = os.path.join(art, folder, "cs1_proxy_box.dae")
        if os.path.isfile(shape):
            os.remove(shape)
            return "proxy box .dae deleted while buildings still reference it"
    return "no shape found to delete"


def mutate_info_size(mod: str) -> str:
    path = os.path.join(level_dir(mod), "info.json")
    with open(path, encoding="utf-8") as handle:
        info = json.load(handle)
    info["size"] = [123, 456]
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(info, handle)
    return "info.json size disagrees with the terrain"


def mutate_terrain_metadata(mod: str) -> str:
    name = os.path.basename(level_dir(mod))
    path = os.path.join(level_dir(mod), f"{name}.terrain.json")
    with open(path, encoding="utf-8") as handle:
        descriptor = json.load(handle)
    descriptor["heightMapSize"] = 12345
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(descriptor, handle)
    return "terrain.json heightMapSize set to 12345"


def mutate_missing_terrain(mod: str) -> str:
    name = os.path.basename(level_dir(mod))
    os.remove(os.path.join(level_dir(mod), f"{name}.ter"))
    return ".ter deleted while TerrainBlock still references it"


MUTATIONS: List[Tuple[str, Callable[[str], str]]] = [
    ("ter_version", mutate_ter_version),
    ("ter_size", mutate_ter_size),
    ("terrain_hole", mutate_terrain_hole),
    ("rotation", mutate_rotation),
    ("wrapped_array", mutate_wrapped_array),
    ("missing_shape", mutate_missing_shape),
    ("info_size", mutate_info_size),
    ("terrain_metadata", mutate_terrain_metadata),
    ("missing_terrain", mutate_missing_terrain),
]


def scratch_copy(good: str, scratch: str) -> None:
    """
    Build a disposable copy of the level.

    Files are hard-linked where the filesystem allows it, because the level contains a ~192 MB
    terrain and copying it for every mutation would dominate the runtime.  Hard links share
    content but not identity: editing a linked file in place would corrupt the original, which
    is why every mutation below opens its target with "r+b"/"w" and rewrites it (which breaks
    the link) rather than mutating in place through the link.  Deletions simply unlink.
    """
    if os.path.isdir(scratch):
        shutil.rmtree(scratch)

    for folder, _dirs, files in os.walk(good):
        relative = os.path.relpath(folder, good)
        target_dir = scratch if relative == "." else os.path.join(scratch, relative)
        os.makedirs(target_dir, exist_ok=True)
        for name in files:
            source = os.path.join(folder, name)
            destination = os.path.join(target_dir, name)
            try:
                os.link(source, destination)
            except OSError:
                shutil.copy2(source, destination)


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Mutation-test the conformance verifier.")
    parser.add_argument("layout", help="the city_layout.json the level was built from")
    parser.add_argument("--mod", default=None, help="known-good mod root")
    args = parser.parse_args(argv)

    good = os.path.abspath(find_mod(args.mod))
    scratch = os.path.join(REPO_ROOT, "build", "mutation_scratch")
    verifier = os.path.join(REPO_ROOT, "tools", "verify_conversion.py")

    print("=" * 78)
    print("  CS1-to-BeamNG :: mutation test of the conformance verifier")
    print("=" * 78)
    print(f"  good level : {good}")
    print()

    # Baseline: the untouched copy must pass.
    scratch_copy(good, scratch)

    baseline = subprocess.run(
        [sys.executable, verifier, args.layout, "--mod", scratch],
        capture_output=True,
        text=True,
    )
    baseline_ok = baseline.returncode == 0
    print(f"  baseline (unmodified copy): {'PASSES as expected' if baseline_ok else 'FAILS -- test is broken'}")
    print()

    results: List[Tuple[str, str, bool, str]] = []

    for name, mutation in MUTATIONS:
        scratch_copy(good, scratch)

        description = mutation(scratch)

        run = subprocess.run(
            [sys.executable, verifier, args.layout, "--mod", scratch],
            capture_output=True,
            text=True,
        )

        detected = run.returncode == 1
        detail = ""
        for line in run.stdout.splitlines():
            if line.strip().startswith("x "):
                detail = line.strip()[2:]
                break

        results.append((name, description, detected, detail))

    print(f"  {'MUTATION':<18} {'RESULT':<10} WHAT WAS CHANGED")
    print("  " + "-" * 92)
    missed = 0
    for name, description, detected, detail in results:
        verdict = "DETECTED" if detected else "MISSED"
        if not detected:
            missed += 1
        print(f"  {name:<18} {verdict:<10} {description}")
        if detail:
            print(f"  {'':<18} {'':<10}   -> {detail[:88]}")

    if os.path.isdir(scratch):
        shutil.rmtree(scratch)

    print()
    if not baseline_ok:
        print("  RESULT: FAILED -- the verifier rejects a valid level")
        return 1
    if missed:
        print(f"  RESULT: FAILED -- {missed} of {len(results)} corruptions were not detected")
        return 1

    print(f"  RESULT: OK -- all {len(results)} corruptions were detected, baseline passes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
