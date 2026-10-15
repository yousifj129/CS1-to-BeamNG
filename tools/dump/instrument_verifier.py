"""Instrument the verifier to count checks per phase, so lost coverage is visible."""

import io
import os
import re
import sys

REPO = r"D:\Developer\open source projects\cities-skylines-to-beamng-map"
sys.path.insert(0, os.path.join(REPO, "tools"))

# Wrap Report.check to log a per-section tally.
import verify_conversion as v


class CountingReport:
    def __init__(self):
        self.total = 0
        self.failures = []
        self.marks = []
        self._label = "start"

    def label(self, text):
        self.marks.append((text, self.total))

    def check(self, cond, msg=""):
        self.total += 1
        if not cond:
            self.failures.append(msg)
        return bool(cond)

    def note(self, msg=""):
        pass


# Find the real Report class and monkeypatch its check.
real_report = None
for name in dir(v):
    obj = getattr(v, name)
    if isinstance(obj, type) and name.lower().startswith("report"):
        real_report = obj
        break
print("Report class:", real_report)

counter = CountingReport()
orig_check = real_report.check


def counting_check(self, cond, msg=""):
    counter.total += 1
    if not cond:
        counter.failures.append(msg)
    return bool(cond)


real_report.check = counting_check

layout = os.path.join(REPO, "exports", "Cannes_city_layout.json")
mod_root = os.path.join(REPO, "dist", "cs1_cannes")
try:
    v.verify(layout, mod_root)
except SystemExit:
    pass
except Exception as exc:
    print("verify raised:", type(exc).__name__, exc)

real_report.check = orig_check
print(f"\ntotal checks executed: {counter.total}")
print(f"failures: {len(counter.failures)}")
for f in counter.failures[:5]:
    print("   ", f)

# Now report how many statics were seen.
main = os.path.join(mod_root, "levels", "Cannes", "main")
objs = list(v.walk_all_objects(main))
from collections import Counter

print("\nobject classes seen by walk_all_objects:")
for cls, n in Counter(str(o.get("class")) for o in objs).most_common():
    print(f"   {n:>6}  {cls}")

statics = [o for o in objs if o.get("class") == "TSStatic"]
print(f"\nTSStatic objects: {len(statics)}")
if statics:
    s = statics[0]
    print("first TSStatic keys:", sorted(s.keys()))
    print("  shapeName:", s.get("shapeName"))
