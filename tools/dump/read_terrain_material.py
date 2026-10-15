import json
import os
import zipfile
import re

REPO = os.path.join(os.environ["LOCALAPPDATA"], "BeamNG", "BeamNG.drive", "current", "mods", "repo")
CANDIDATES = [
    "Bob_City_Map_Alpha_Patreon_Preview.zip",
    "Altitude.zip",
    "autobahnvawriss.zip",
    "americanroad.zip",
]

for name in CANDIDATES:
    path = os.path.join(REPO, name)
    if not os.path.isfile(path):
        continue
    print("=" * 78)
    print(name)
    print("=" * 78)
    with zipfile.ZipFile(path) as archive:
        entries = [
            e for e in archive.infolist()
            if re.search(r"terrain", e.filename, re.I)
            and e.filename.endswith(".json")
            and 0 < e.file_size < 3_000_000
        ]
        for entry in entries[:3]:
            print(f"--- {entry.filename} ({entry.file_size} bytes)")
            text = archive.read(entry).decode("utf-8", "replace")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                print("    (not valid JSON:", exc, ")")
                continue

            items = list(data.items())[:2]
            for key, value in items:
                print(f"    key: {key}")
                if isinstance(value, dict):
                    for field, field_value in value.items():
                        rendered = json.dumps(field_value)
                        if len(rendered) > 110:
                            rendered = rendered[:110] + "..."
                        print(f"      {field}: {rendered}")
                print()
    print()
