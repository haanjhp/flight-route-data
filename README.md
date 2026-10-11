# Flight Route Data

Offline callsign-to-route data for ConnectCrew. The published database contains flight identifiers and airport pairs only. It never contains user IDs, names, crew data, aircraft registrations, or exact operation timestamps.

## Updates

- `update-public-routes`: monthly public-data refresh on the first day of the month, without Firestore access. All three public inputs are fetched so airline-only changes are detected even when routes are unchanged.
- `aggregate-user-routes`: monthly 31-day anonymous Firestore aggregation using the `FIREBASE_SERVICE_ACCOUNT` repository secret.
- Both workflows can be run manually and publish only when normalized route data changes.

Public inputs are the CC0 Virtual Radar Server standing-data project and its ADSB.lol distribution. Generated artifacts are `dist/routes.sqlite` and `dist/meta.json`.

Carrier codes use explicit current mappings to avoid reused historical IATA aliases. Names follow the exact ICAO entry in standing data. TWB/TW uses `Trinity Airways` while the external source still reports the legacy T'Way name; future non-legacy source names are adopted in both public and observed routes.

## Local build

```bash
python scripts/fetch_public.py --force
python scripts/build_routes.py \
  --routes cache/public/routes.csv \
  --airports cache/public/airports.csv \
  --airlines cache/public/airlines.csv
```
