#!/usr/bin/env python3
import collections, datetime as dt, json, os, pathlib
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

def main():
    firebase_admin.initialize_app(credentials.Certificate(json.loads(os.environ["FIREBASE_SERVICE_ACCOUNT"])))
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=31); counts = collections.Counter(); latest = {}
    query = firestore.client().collection_group("roster").where(filter=FieldFilter("date", ">=", cutoff))
    for snapshot in query.stream():
        document = snapshot.to_dict() or {}
        date = document.get("date")
        month = date.strftime("%Y-%m") if date else ""
        for leg in document.get("flightLegs") or []:
            if not isinstance(leg, dict):
                continue
            key = (str(leg.get("flightNumber", "")).upper(), str(leg.get("from", "")).upper(), str(leg.get("to", "")).upper())
            if all(key): counts[key] += 1; latest[key] = max(latest.get(key, ""), month)
    rows = [{"flightNumber": key[0], "from": key[1], "to": key[2], "observationCount": count, "lastSeenMonth": latest[key]} for key, count in sorted(counts.items())]
    output = pathlib.Path("data/user_routes.json"); output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(rows, indent=2) + "\n")
    print(f"Wrote {len(rows)} anonymous routes")

if __name__ == "__main__": main()
