import argparse
import json
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from hashlib import sha1, sha256
from pathlib import Path

REPOSITORY = "JeffSackmann/tennis_MatchChartingProject"
API = "https://api.github.com/repos/" + REPOSITORY
LICENSE = "CC-BY-NC-SA-4.0"

def request(url):
    return urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "tennis-match-lab"}),
        timeout=90,
    )

def get_json(url):
    with request(url) as response:
        return json.load(response)

def fetch_file(item, commit, folder):
    name = item["path"]
    size = item["size"]
    destination = folder / name
    if Path(name).name != name:
        raise ValueError("Expected a root-level data file")
    url = f"https://raw.githubusercontent.com/{REPOSITORY}/{commit}/{name}"
    temp = destination.with_suffix(destination.suffix + ".part")
    digest = sha256()
    git_digest = sha1()
    git_digest.update(f"blob {size}\0".encode())
    count = 0
    with request(url) as response, temp.open("wb") as stream:
        while block := response.read(1024 * 1024):
            stream.write(block)
            digest.update(block)
            git_digest.update(block)
            count += len(block)
    # Check the download before replacing the temporary file
    if count != size or git_digest.hexdigest() != item["sha"]:
        raise ValueError(f"Content verification failed for {name}")
    temp.replace(destination)
    return {"file": name, "bytes": count, "sha256": digest.hexdigest(),
            "git_blob_sha": item["sha"], "url": url}

def download(output, include_points=False, commit=None):
    if commit is not None and not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("Use a full 40-character source commit SHA")
    if commit is None:
        commit = get_json(API + "/commits/master")["sha"]
    tree = get_json(API + "/git/trees/" + commit)["tree"]
    items = []
    for item in tree:
        name = item["path"]
        is_data = name.endswith(".csv") or name in {"README.md", "data_dictionary.txt"}
        if item["type"] != "blob" or not is_data:
            continue
        if not include_points and "-points-" in name:
            continue
        items.append(item)
    folder = Path(output) / commit
    if folder.exists():
        raise ValueError("Snapshot folder already exists; use verify.py to check it")
    folder.mkdir(parents=True)
    manifest = {"repository": REPOSITORY, "commit": commit, "license": LICENSE,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "include_points": include_points, "files": [], "complete": False}
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for result in pool.map(lambda item: fetch_file(item, commit, folder), items):
                manifest["files"].append(result)
                print(result["file"], result["bytes"], flush=True)
        manifest["complete"] = True
    finally:
        (folder / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n",
                                            encoding="utf-8")
    return folder

def main():
    # Arguments
    parser = argparse.ArgumentParser(description="Download a verified Match Charting Project snapshot.")
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--include-points", action="store_true")
    parser.add_argument("--commit", help="Reproduce a specific source commit instead of latest")
    args = parser.parse_args()
    folder = download(args.output, args.include_points, args.commit)
    print("Snapshot:", folder)

if __name__ == "__main__":
    main()
