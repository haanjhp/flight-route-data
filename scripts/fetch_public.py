#!/usr/bin/env python3
import argparse, json, pathlib, urllib.error, urllib.request

SOURCES = {
    "routes.csv": "https://vrs-standing-data.adsb.lol/routes.csv",
    "airports.csv": "https://vrs-standing-data.adsb.lol/airports.csv",
    "airlines.csv": "https://raw.githubusercontent.com/vradarserver/standing-data/main/airlines/schema-01/airlines.csv",
}

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("cache/public")); parser.add_argument("--force", action="store_true"); args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True); meta_path = args.output.parent / "source_meta.json"
    old = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    changed = args.force or not old or any(not (args.output / name).exists() for name in SOURCES)
    if not changed:
        request = urllib.request.Request(SOURCES["routes.csv"], method="HEAD", headers={"If-None-Match": old.get("routes.csv", {}).get("etag", ""), "If-Modified-Since": old.get("routes.csv", {}).get("lastModified", "")})
        try:
            with urllib.request.urlopen(request) as response:
                changed = response.status != 304
        except urllib.error.HTTPError as error:
            changed = error.code != 304
    if not changed:
        print("Public sources unchanged"); return
    new = {}
    for name, url in SOURCES.items():
        request = urllib.request.Request(url, headers={"User-Agent": "flight-route-data/1.0"})
        with urllib.request.urlopen(request) as response:
            (args.output / name).write_bytes(response.read())
            new[name] = {"url": url, "etag": response.headers.get("ETag", ""), "lastModified": response.headers.get("Last-Modified", "")}
    meta_path.write_text(json.dumps(new, indent=2) + "\n")

if __name__ == "__main__": main()
