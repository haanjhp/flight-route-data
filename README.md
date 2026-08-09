# Flight Route Data

Offline callsign-to-route data for ConnectCrew. The published database contains flight identifiers and airport pairs only. It never contains user IDs, names, crew data, aircraft registrations, or exact operation timestamps.

## Updates

- `update-public-routes`: weekly public-data refresh without Firestore access.
- `aggregate-user-routes`: monthly 31-day anonymous Firestore aggregation using the `FIREBASE_SERVICE_ACCOUNT` repository secret.
- Both workflows can be run manually and publish only when normalized route data changes.

Public inputs are the CC0 Virtual Radar Server standing-data project and its ADSB.lol distribution. Generated artifacts are `dist/routes.sqlite` and `dist/meta.json`.

## Local build

```bash
python scripts/fetch_public.py --force
python scripts/build_routes.py \
  --routes cache/public/routes.csv \
  --airports cache/public/airports.csv \
  --airlines cache/public/airlines.csv
```
