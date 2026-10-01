import http.client
import json
from http.server import ThreadingHTTPServer
from threading import Thread
import unittest

from travel_agent.api import TravelAgentAPIHandler


class TravelAgentAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), TravelAgentAPIHandler)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_address[1]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def request(self, method: str, path: str, body: dict | None = None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port)
        encoded = json.dumps(body) if body is not None else None
        headers = {"Content-Type": "application/json"} if encoded else {}
        connection.request(method, path, body=encoded, headers=headers)
        response = connection.getresponse()
        response_body = response.read()
        headers = dict(response.getheaders())
        connection.close()
        return response.status, headers, response_body

    def test_post_delay_returns_serialized_workflow_result_with_cors(self) -> None:
        status, headers, body = self.request("POST", "/api/replan", {"delay_hours": 4})

        self.assertEqual(status, 200)
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        result = json.loads(body)
        self.assertEqual(result["disruption"]["new_arrival"], "2026-10-20T16:00:00")
        self.assertTrue(result["affected"])
        self.assertEqual(
            result["updated_itinerary"]["events"][0]["kind"], "flight"
        )

    def test_options_preflight_allows_cross_origin_post(self) -> None:
        status, headers, body = self.request("OPTIONS", "/api/replan")

        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("POST", headers["Access-Control-Allow-Methods"])

    def test_invalid_delay_returns_json_client_error(self) -> None:
        status, headers, body = self.request(
            "POST", "/api/replan", {"delay_hours": -1}
        )

        self.assertEqual(status, 400)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertIn("delay_hours", json.loads(body)["error"])


if __name__ == "__main__":
    unittest.main()