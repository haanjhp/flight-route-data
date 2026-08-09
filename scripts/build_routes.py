#!/usr/bin/env python3
import argparse, csv, datetime as dt, hashlib, json, pathlib, re, sqlite3
from collections import defaultdict

SCHEMA = 1

def clean(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())

def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)

def first(row, *keys):
    lowered = {k.lower(): (v or "") for k, v in row.items()}
    return next((lowered[k.lower()] for k in keys if lowered.get(k.lower())), "")

def load_airlines(path):
    result = {}
    for row in read_csv(path):
        icao, iata = clean(first(row, "ICAO", "Code")), clean(first(row, "IATA"))
        if len(icao) == 3:
            result[icao] = (icao, iata)
        if len(iata) == 2:
            result[iata] = (icao, iata)
    return result

def load_airports(path):
    result = {}
    for row in read_csv(path):
        icao = clean(first(row, "ICAO", "Code", "Ident", "gps_code"))
        iata = clean(first(row, "IATA", "iata_code"))
        if 3 <= len(icao) <= 4:
            result[icao] = iata
    return result

def parse_public(path, airlines, airports):
    for row in read_csv(path):
        callsign = clean(first(row, "Callsign"))
        number = clean(first(row, "Number")) or "".join(re.findall(r"\d+", callsign))
        carrier = clean(first(row, "AirlineCode", "Code")) or callsign[:3]
        route = first(row, "AirportCodes", "Route")
        points = [clean(p) for p in re.split(r"[- /,]+", route) if clean(p)]
        if len(points) < 2 or not number.isdigit(): continue
        airline_icao, airline_iata = airlines.get(carrier, (carrier if len(carrier) == 3 else "", carrier if len(carrier) == 2 else ""))
        callsign_icao = f"{airline_icao}{number}" if airline_icao else callsign
        route_icao = f"{points[0]}-{points[-1]}"
        route_iata = f"{airports.get(points[0], points[0])}-{airports.get(points[-1], points[-1])}"
        yield (callsign_icao, airline_icao, airline_iata, number, int(number), route_iata, route_icao, "public", 10, 0, "")

def parse_users(path, airlines):
    if not path.exists(): return
    for row in json.loads(path.read_text(encoding="utf-8")):
        flight = clean(row.get("flightNumber")); number = "".join(re.findall(r"\d+", flight))
        prefix = flight[:-len(number)] if number else ""
        airline_icao, airline_iata = airlines.get(prefix, (prefix if len(prefix) == 3 else "", prefix if len(prefix) == 2 else ""))
        if not number or not airline_icao: continue
        departure, arrival = clean(row.get("from")), clean(row.get("to"))
        if not departure or not arrival: continue
        route = f"{departure}-{arrival}"
        yield (f"{airline_icao}{number}", airline_icao, airline_iata, number, int(number), route, route, "user_roster", 100, int(row.get("observationCount", 1)), row.get("lastSeenMonth", ""))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", required=True, type=pathlib.Path)
    parser.add_argument("--airports", required=True, type=pathlib.Path)
    parser.add_argument("--airlines", required=True, type=pathlib.Path)
    parser.add_argument("--users", type=pathlib.Path, default=pathlib.Path("data/user_routes.json"))
    parser.add_argument("--output", type=pathlib.Path, default=pathlib.Path("dist"))
    parser.add_argument("--base-url", default="https://raw.githubusercontent.com/haanjhp/flight-route-data/main/dist")
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    airlines, airports = load_airlines(args.airlines), load_airports(args.airports)
    merged = {}
    for record in list(parse_public(args.routes, airlines, airports)) + list(parse_users(args.users, airlines) or []):
        key = (record[0], record[6], record[7]); previous = merged.get(key)
        if not previous or record[8:] > previous[8:]: merged[key] = record
    records = sorted(merged.values())
    normalized = "\n".join("|".join(map(str, row)) for row in records).encode()
    data_version = hashlib.sha256(normalized).hexdigest()[:16]
    db_path = args.output / "routes.sqlite"; db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE routes(callsign_icao TEXT, airline_icao TEXT, airline_iata TEXT, flight_number TEXT, number_key INTEGER, route_iata TEXT, route_icao TEXT, source TEXT, source_rank INTEGER, observation_count INTEGER, last_seen_month TEXT)")
    db.executemany("INSERT INTO routes VALUES(?,?,?,?,?,?,?,?,?,?,?)", records)
    db.execute("CREATE INDEX routes_number ON routes(number_key, source_rank DESC, observation_count DESC)")
    db.execute("CREATE INDEX routes_callsign ON routes(callsign_icao)"); db.commit(); db.execute("VACUUM"); db.close()
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    old_meta_path = args.output / "meta.json"
    old_meta = json.loads(old_meta_path.read_text()) if old_meta_path.exists() else {}
    generated_at = old_meta.get("generatedAt") if old_meta.get("dataVersion") == data_version else None
    meta = {"schemaVersion": SCHEMA, "dataVersion": data_version, "generatedAt": generated_at or dt.datetime.now(dt.timezone.utc).isoformat(), "sha256": digest, "byteSize": db_path.stat().st_size, "recordCount": len(records), "sqliteURL": f"{args.base_url}/routes.sqlite"}
    (args.output / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta))

if __name__ == "__main__": main()
