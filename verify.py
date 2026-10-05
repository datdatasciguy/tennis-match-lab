import argparse
from hashlib import sha256
import json
from pathlib import Path


def verify(folder):
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if not manifest["complete"]:
        raise ValueError("Snapshot is incomplete")
    for row in manifest["files"]:
        path = folder / row["file"]
        if Path(row["file"]).name != row["file"]:
            raise ValueError("Manifest contains an invalid file path")
        digest = sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        if path.stat().st_size != row["bytes"] or digest.hexdigest() != row["sha256"]:
            raise ValueError("Snapshot file changed: " + row["file"])
    return len(manifest["files"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check a downloaded snapshot against its manifest.")
    parser.add_argument("folder", type=Path)
    print("Verified files:", verify(parser.parse_args().folder))
