"""Snapshot the Mosquito Atlas taxon list into the dashboard.

The dashboard deploys on its own, so it can't read the Atlas repository at
runtime. This script copies the fields the dashboard needs (ids, names,
complex/group membership and identification notes) into
``vdamkc/reference/atlas_taxa.json``. Re-run it whenever the Atlas taxa change:

    python scripts/sync_atlas_taxa.py [path/to/Anopheles_Atlas]
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ATLAS = ROOT.parent / "Anopheles_Atlas"
OUT = ROOT / "vdamkc" / "reference" / "atlas_taxa.json"


def main(atlas_dir: Path) -> None:
    taxa = []
    for path in sorted((atlas_dir / "data" / "taxa").glob("*.json")):
        for t in json.loads(path.read_text(encoding="utf-8")):
            group = t.get("group") or {}
            taxa.append({
                "id": t["id"],
                "name": t["name"],
                "display": t.get("display", t["name"]),
                "genus": t["genus"],
                "group": group.get("name"),
                "group_kind": group.get("kind"),
                "group_members": group.get("members", []),
                "group_note": group.get("note"),
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "source": "Mosquito Atlas data/taxa/*.json",
        "synced": date.today().isoformat(),
        "taxa": taxa,
    }, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(taxa)} taxa to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_ATLAS)
