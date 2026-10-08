#!/usr/bin/env python3
import argparse, csv, datetime as dt, hashlib, json, pathlib, re, sqlite3
from collections import defaultdict

SCHEMA = 2

# Historical IATA aliases in standing data must not override current roster carriers.
ROSTER_CARRIERS = {
    "7C": ("JJA", "7C", "Jeju Air"),
    "ZE": ("ESR", "ZE", "Eastar Jet"),
    "TW": ("TWB", "TW", "T'Way Air"),
    "KE": ("KAL", "KE", "Korean Air"),
    "OZ": ("AAR", "OZ", "Asiana Airlines"),
    "LJ": ("JNA", "LJ", "Jin Air"),
    "BX": ("ABL", "BX", "Air Busan"),
    "RS": ("ASV", "RS", "Air Seoul"),
    "RF": ("EOK", "RF", "Aero K"),
    "YP": ("APZ", "YP", "Air Premia"),
    "KJ": ("AIH", "KJ", "Air Incheon"),
}

def parse_roster_flight(value):
    aliases = {**ROSTER_CARRIERS, **{row[0]: row for row in ROSTER_CARRIERS.values()}}
    flight = re.sub(r"\s+", "", (value or "").upper())
    if flight.startswith("DH"):
        flight = flight[2:]
    for prefix in sorted(aliases, key=len, reverse=True):
        if not flight.startswith(prefix): continue
        match = re.fullmatch(r"([0-9]{1,4})([A-Z])?", flight[len(prefix):])
        if match and int(match[1]) > 0:
            return aliases[prefix], str(int(match[1]))
    return None

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
        name = first(row, "Name").strip()
        if len(icao) == 3:
            result[icao] = (icao, iata, name)
        if len(iata) == 2:
            # The standing data contains a few reused historical IATA codes.
            # Keep the first active mapping instead of letting a later alias replace it.
            result.setdefault(iata, (icao, iata, name))
    for iata, carrier in ROSTER_CARRIERS.items():
        result[iata] = carrier
        result[carrier[0]] = carrier
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
        number = str(int(number))
        airline_icao, airline_iata, airline_name = airlines.get(carrier, (carrier if len(carrier) == 3 else "", carrier if len(carrier) == 2 else "", carrier))
        callsign_icao = f"{airline_icao}{number}" if airline_icao else callsign
        route_icao = f"{points[0]}-{points[-1]}"
        route_iata = f"{airports.get(points[0], points[0])}-{airports.get(points[-1], points[-1])}"
        yield (callsign_icao, airline_icao, airline_iata, airline_name, number, int(number), route_iata, route_icao, "public", 10, 0, "")

def parse_users(path, airlines):
    if not path.exists(): return
    for row in json.loads(path.read_text(encoding="utf-8")):
        parsed = parse_roster_flight(row.get("flightNumber"))
        if parsed is None: continue
        (airline_icao, airline_iata, airline_name), number = parsed
        departure, arrival = clean(row.get("from")), clean(row.get("to"))
        if not re.fullmatch(r"[A-Z]{3,4}", departure) or not re.fullmatch(r"[A-Z]{3,4}", arrival) or departure == arrival: continue
        route = f"{departure}-{arrival}"
        yield (f"{airline_icao}{number}", airline_icao, airline_iata, airline_name, number, int(number), route, route, "user_roster", 100, int(row.get("observationCount", 1)), row.get("lastSeenMonth", ""))

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
        key = (record[0], record[6]); previous = merged.get(key)
        if previous and record[8] == previous[8] == "user_roster":
            record = (*record[:10], previous[10] + record[10], max(previous[11], record[11]))
        if not previous or record[9:] > previous[9:]: merged[key] = record
    records = sorted(merged.values())
    normalized = "\n".join("|".join(map(str, row)) for row in records).encode()
    data_version = hashlib.sha256(normalized).hexdigest()[:16]
    db_path = args.output / "routes.sqlite"; db_path.unlink(missing_ok=True)
    db = sqlite3.connect(db_path)
    db.execute("CREATE TABLE routes(callsign_icao TEXT, airline_icao TEXT, airline_iata TEXT, airline_name TEXT, flight_number TEXT, number_key INTEGER, route_iata TEXT, route_icao TEXT, source TEXT, source_rank INTEGER, observation_count INTEGER, last_seen_month TEXT)")
    db.executemany("INSERT INTO routes VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", records)
    db.execute("CREATE INDEX routes_number ON routes(number_key, source_rank DESC, observation_count DESC)")
    db.execute("CREATE INDEX routes_callsign ON routes(callsign_icao)")
    db.execute(f"PRAGMA user_version = {SCHEMA}"); db.commit(); db.execute("VACUUM"); db.close()
    digest = hashlib.sha256(db_path.read_bytes()).hexdigest()
    old_meta_path = args.output / "meta.json"
    old_meta = json.loads(old_meta_path.read_text()) if old_meta_path.exists() else {}
    generated_at = old_meta.get("generatedAt") if old_meta.get("dataVersion") == data_version else None
    meta = {"schemaVersion": SCHEMA, "dataVersion": data_version, "generatedAt": generated_at or dt.datetime.now(dt.timezone.utc).isoformat(), "sha256": digest, "byteSize": db_path.stat().st_size, "recordCount": len(records), "sqliteURL": f"{args.base_url}/routes.sqlite"}
    (args.output / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(meta))

if __name__ == "__main__": main()
