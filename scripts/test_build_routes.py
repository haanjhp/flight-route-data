import pathlib
import tempfile
import unittest
import json
from build_routes import load_airlines, parse_roster_flight, parse_users


class RouteTests(unittest.TestCase):
    def test_current_carriers_override_historical_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "airlines.csv"
            path.write_text("ICAO,IATA,Name\nAZE,ZE,Arcus\nCOY,7C,Coyne\nESR,ZE,Eastar\n")
            airlines = load_airlines(path)
            self.assertEqual(airlines["ZE"][0], "ESR")
            self.assertEqual(airlines["7C"][0], "JJA")

    def test_number_and_suffix(self):
        for flight in ["7C0101", "JJA101", "7C0101A"]:
            self.assertEqual(parse_roster_flight(flight), (("JJA", "7C", "Jeju Air"), "101"))
        self.assertEqual(parse_roster_flight("ZE0136")[0][0], "ESR")
        self.assertEqual(parse_roster_flight("DHBX8045")[0][0], "ABL")

    def test_reject_activity_codes_and_unknown_carriers(self):
        for flight in ["C2113B", "F8401A", "DHVAN206", "VANVAN715", "ZE0", "ZE0136/0137"]:
            self.assertIsNone(parse_roster_flight(flight))

    def test_user_route(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "users.json"
            path.write_text(json.dumps([
                {"flightNumber": "ZE0136", "from": "ALA", "to": "ICN", "observationCount": 3},
                {"flightNumber": "C2113B", "from": "ICN", "to": "CEB"},
                {"flightNumber": "7C0101", "from": "ICN", "to": "ICN"},
            ]))
            rows = list(parse_users(path, {}))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][0], "ESR136")
            self.assertEqual(rows[0][10], 3)


if __name__ == "__main__":
    unittest.main()
