"""Exercise the offline waterfall viewer over its actual loopback HTTP API."""
from html.parser import HTMLParser
import http.client
import json
import threading
import unittest
from unittest import mock
from urllib.parse import urlsplit

import mne
import numpy as np

from analysis.waterfall_browser import create_waterfall_server, serve_waterfall


class AssetReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.sources = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in {"script", "img", "iframe", "audio", "video", "source"} and "src" in attrs:
            self.sources.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.sources.append(attrs["href"])


class WaterfallServerTest(unittest.TestCase):
    def setUp(self):
        times = np.arange(1500) / 250
        values_uv = np.array([100 + 10 * np.sin(2 * np.pi * 10 * times),
                              -50 + 20 * np.cos(2 * np.pi * 20 * times),
                              5 * np.sin(2 * np.pi * 6 * times)])
        self.raw = mne.io.RawArray(
            values_uv * 1e-6,
            mne.create_info(["EEG 1", "Cz", "unmapped"], 250, "eeg"),
            first_samp=1000, verbose="ERROR")
        self.raw.set_annotations(mne.Annotations([1, 3], [0, .25], ["Task", "BAD_motion"]))
        self.server = create_waterfall_server(
            self.raw, start=1.25, duration=3, scale_uv=35,
            title="Messung <A> · EEG", filter_label="Unfiltered")
        address = urlsplit(self.server.url)
        self.prefix = address.path
        self.thread = threading.Thread(target=self.server.serve_forever,
                                       kwargs={"poll_interval": .01}, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)

    def close_server(self):
        self.server.shutdown()
        self.thread.join(timeout=2)
        self.server.server_close()
        self.assertFalse(self.thread.is_alive(), "The HTTP serving thread did not stop.")

    def request(self, resource="", *, path=None, method="GET"):
        connection = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            connection.request(method, self.prefix + resource if path is None else path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def json_request(self, resource="data"):
        status, headers, body = self.request(resource)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        # Reject JS's non-standard numeric constants, including on error routes.
        value = json.loads(body, parse_constant=lambda value: self.fail("Nonfinite JSON: " + value))
        return status, value

    def test_binds_only_to_loopback_and_reports_recording_metadata(self):
        self.assertEqual(self.server.server_address[0], "127.0.0.1")
        self.assertGreater(self.server.server_port, 0)
        code, metadata = self.json_request("meta")
        self.assertEqual(code, 200)
        self.assertEqual(metadata["title"], "Messung <A> · EEG")
        self.assertEqual(metadata["sfreq"], 250)
        self.assertEqual(metadata["total_duration"], 6)
        self.assertEqual((metadata["start"], metadata["duration"], metadata["scale_uv"]),
                         (1.25, 3, 35))
        self.assertEqual(metadata["filter_label"], "Unfiltered")
        self.assertEqual(metadata["channels"], [
            {"index": 0, "name": "EEG 1", "label": "Fz", "mapped": True},
            {"index": 1, "name": "Cz", "label": "Cz", "mapped": True},
            {"index": 2, "name": "unmapped", "label": "unmapped", "mapped": False}])

    def test_html_and_plotly_are_bundled_with_local_only_asset_references(self):
        code, headers, body = self.request()
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/html; charset=utf-8")
        parser = AssetReferences()
        parser.feed(body.decode("utf-8"))
        self.assertIn("plotly.min.js", parser.sources)
        for source in parser.sources:
            self.assertFalse(urlsplit(source).netloc, source)
            self.assertFalse(urlsplit(source).scheme, source)
        self.assertIn("connect-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("frame-ancestors 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        code, headers, script = self.request("plotly.min.js")
        self.assertEqual(code, 200)
        self.assertEqual(headers["Content-Type"], "text/javascript; charset=utf-8")
        self.assertGreater(len(script), 1_000_000)
        self.assertIn(b"plotly.js", script[:1000].lower())
        self.assertEqual(int(headers["Content-Length"]), len(script))

    def test_recording_end_clipping_channel_order_and_display_centering(self):
        code, uncentered = self.json_request(
            "data?start=4.5&duration=10&channels=2,0&center=0&low=8&high=13&window=2&hop=0.25")
        self.assertEqual(code, 200)
        self.assertEqual((uncentered["start"], uncentered["stop"]), (4.5, 6))
        self.assertEqual([channel["index"] for channel in uncentered["channels"]], [2, 0])
        self.assertEqual(uncentered["band"], [8, 13])
        self.assertEqual(uncentered["window_seconds"], 2)
        self.assertEqual(uncentered["hop_seconds"], .248)
        channel = uncentered["channels"][1]
        self.assertEqual(channel["offset_uv"], 0)
        np.testing.assert_allclose(channel["bandpower"], 50, rtol=1e-10)
        code, centered = self.json_request("data?start=4.5&duration=10&channels=0&center=1")
        self.assertEqual(code, 200)
        self.assertAlmostEqual(centered["channels"][0]["offset_uv"], 100, places=8)
        self.assertEqual(centered["channels"][0]["bandpower"], channel["bandpower"])
        np.testing.assert_allclose(np.array(channel["amplitude"])
                                   - centered["channels"][0]["amplitude"], 100)

    def test_default_request_preserves_annotation_origin_and_raw_state(self):
        samples = self.raw.get_data().copy()
        annotations = self.raw.annotations.copy()
        info = (self.raw.first_samp, self.raw.info["highpass"], self.raw.info["lowpass"],
                self.raw.info["sfreq"], list(self.raw.ch_names))
        code, result = self.json_request()
        self.assertEqual(code, 200)
        self.assertEqual((result["start"], result["stop"]), (1.25, 4.25))
        self.assertEqual(result["events"], [{"onset": 1, "description": "Task"},
                                            {"onset": 3, "description": "BAD_motion"}])
        self.assertIn(None, result["channels"][0]["bandpower"])
        self.json_request("data?start=0&duration=2&channels=2,1&center=0&low=4&high=8")
        self.json_request("data?start=5&duration=1&channels=0")
        np.testing.assert_array_equal(samples, self.raw.get_data())
        for name in ("onset", "duration", "description"):
            np.testing.assert_array_equal(getattr(annotations, name), getattr(self.raw.annotations, name))
        self.assertEqual(info, (self.raw.first_samp, self.raw.info["highpass"],
                                self.raw.info["lowpass"], self.raw.info["sfreq"], list(self.raw.ch_names)))

    def test_nonfinite_samples_are_serialized_as_null_gaps(self):
        self.raw._data[0, 600] = np.nan
        self.raw._data[0, 750] = np.inf
        code, result = self.json_request("data?start=1&duration=4&channels=0")
        self.assertEqual(code, 200)
        self.assertIn(None, result["channels"][0]["amplitude"])
        self.assertIn(None, result["channels"][0]["bandpower"])
        self.assertTrue(any("nichtendliche" in warning.casefold() for warning in result["warnings"]))

    def test_bad_parameters_return_json_errors_and_keep_server_available(self):
        invalid = ["start=nan", "duration=inf", "low=-inf", "high=nan", "window=nan", "hop=inf",
                   "start=-1", "start=6", "duration=0", "low=13&high=8", "high=126",
                   "channels=", "channels=NaN", "channels=-1", "channels=3", "channels=0,0",
                   "channels=0.0", "channels=0,1,", "center=2", "center=true", "window=0.1",
                   "window=31", "hop=0.01", "window=1&hop=2", "unknown=1", "start=1&start=2",
                   "channels=0&channels=1", "start", "start="]
        for query in invalid:
            with self.subTest(query=query):
                code, result = self.json_request("data?" + query)
                self.assertEqual(code, 400)
                self.assertIsInstance(result["error"], str)
                self.assertTrue(result["error"])
        self.assertEqual(self.json_request("meta")[0], 200)
        self.assertEqual(self.json_request()[0], 200)

    def test_token_is_required_for_every_route_and_routes_cannot_write(self):
        self.assertRegex(self.prefix, r"^/[A-Za-z0-9_-]{32}/$")
        paths = ["/", "/meta", "/data", "/plotly.min.js", "/wrong-token/meta",
                 self.prefix[:-1] + "-extra/meta", self.prefix + "../meta", self.prefix + "missing"]
        for path in paths:
            with self.subTest(path=path):
                code, _, body = self.request(path=path)
                self.assertEqual(code, 404)
                self.assertIn("error", json.loads(body))
        original = self.raw.get_data().copy()
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self.request("data", method=method)[0], 501)
        np.testing.assert_array_equal(original, self.raw.get_data())

    def test_large_request_and_internal_errors_are_contained(self):
        code, result = self.json_request("data?start=" + "1" * 8200)
        self.assertEqual(code, 400)
        self.assertIn("lang", result["error"])
        with mock.patch("analysis.waterfall_browser.build_waterfall_data",
                        side_effect=RuntimeError("/private/path/secret-recording.csv")):
            code, result = self.json_request()
        self.assertEqual(code, 500)
        self.assertEqual(set(result), {"error"})
        self.assertNotIn("private", result["error"])
        self.assertNotIn("secret", result["error"])
        self.assertEqual(self.json_request()[0], 200)

    def test_invalid_server_settings_fail_before_browser_launch(self):
        invalid = [{"start": -1}, {"start": 6}, {"start": np.nan}, {"duration": 0},
                   {"duration": np.inf}, {"scale_uv": 0}, {"scale_uv": np.nan},
                   {"port": -1}, {"port": 65536}, {"port": 2.5}]
        with mock.patch("analysis.waterfall_browser.webbrowser.open") as browser:
            for kwargs in invalid:
                with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                    create_waterfall_server(self.raw, **kwargs)
            browser.assert_not_called()

    def test_shutdown_releases_the_socket_and_serve_wrapper_closes_on_interrupt(self):
        address = self.server.server_address
        self.close_server()
        # Cleanup remains valid after explicit shutdown/close.
        connection = http.client.HTTPConnection(*address, timeout=.5)
        try:
            with self.assertRaises(OSError):
                connection.request("GET", self.prefix + "meta")
        finally:
            connection.close()
        fake = mock.Mock(url="http://127.0.0.1:12345/token/")
        fake.serve_forever.side_effect = KeyboardInterrupt
        with mock.patch("analysis.waterfall_browser.create_waterfall_server", return_value=fake), \
             mock.patch("analysis.waterfall_browser.webbrowser.open") as browser, \
             mock.patch("builtins.print"):
            serve_waterfall(self.raw, open_browser=False)
        fake.serve_forever.assert_called_once_with(poll_interval=.25)
        fake.server_close.assert_called_once_with()
        browser.assert_not_called()


if __name__ == "__main__":
    unittest.main()
