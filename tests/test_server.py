import http.client
import json
import threading
import unittest

from smart_home.controller import CommandError, Home
from smart_home.server import make_server


class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.home = Home()
        cls.server = make_server(cls.home, port=0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)

    def call(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.request(method, path, body, headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def test_dashboard_and_all_local_assets_load(self):
        for path in ["/", "/app.js", "/style.css"]:
            status, headers, body = self.call("GET", path)
            self.assertEqual(status, 200)
            self.assertGreater(len(body), 100)
            self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])

    def test_text_to_state_end_to_end(self):
        status, _, body = self.call("POST", "/api/command", json.dumps({"text": "turn on lights"}),
                                    {"Content-Type": "application/json"})
        data = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(data["result"]["ok"])
        self.assertTrue(all(d["state"] == "on" for d in data["state"]["devices"] if d["type"] == "light"))

    def test_device_and_scene_api(self):
        for path, payload in [("/api/device", {"device_id": "curtain_1", "command": "open"}),
                              ("/api/scene", {"name": "night_mode"})]:
            status, _, body = self.call("POST", path, json.dumps(payload), {"Content-Type": "application/json"})
            self.assertEqual(status, 200)
            self.assertTrue(json.loads(body)["result"]["ok"])

    def test_malformed_json_and_wrong_types_are_errors(self):
        for payload in ["{", "[]", json.dumps({"text": None}), json.dumps({"code": []})]:
            status, _, body = self.call("POST", "/api/command", payload, {"Content-Type": "application/json"})
            data = json.loads(body)
            self.assertIn(status, [200, 400])
            self.assertFalse(data.get("result", data)["ok"])

    def test_cross_origin_invalid_host_and_simple_form_rejected(self):
        for headers, expected in [({"Content-Type": "application/json", "Origin": "https://evil.example"}, 403),
                                  ({"Content-Type": "application/json", "Host": "evil.example"}, 403),
                                  ({"Content-Type": "text/plain"}, 415)]:
            status, _, _ = self.call("POST", "/api/command", '{"text":"turn on lights"}', headers)
            self.assertEqual(status, expected)

    def test_no_arbitrary_file_serving(self):
        for path in ["/../../pyproject.toml", "/.env", "/api/missing"]:
            self.assertEqual(self.call("GET", path)[0], 404)

    def test_remote_bind_is_not_supported(self):
        with self.assertRaises(CommandError):
            make_server(self.home, host="0.0.0.0", port=0)


if __name__ == "__main__":
    unittest.main()
