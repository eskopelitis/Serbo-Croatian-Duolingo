"""Offline startup checks; no learner database or model/speech calls."""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace

import startup


class LanStartupTests(unittest.TestCase):
    def test_windows_physical_adapters_precede_vpn_with_gateway(self):
        rows = [
            {"Name": "A VPN", "Address": "10.2.0.2", "Physical": False},
            {"Name": "Z Wi-Fi", "Address": ["192.168.1.237"], "Physical": True},
            {"Name": "Ethernet", "Address": "192.168.2.10", "Physical": True},
            {"Name": "Unknown", "Address": "10.3.0.2"},
            {"Name": "Z Wi-Fi", "Address": "192.168.1.237", "Physical": True},
        ]
        with patch.object(startup.os, "name", "nt"), patch.object(
                startup.subprocess, "CREATE_NO_WINDOW", 0, create=True), patch.object(
                startup.subprocess, "run", return_value=SimpleNamespace(stdout=json.dumps(rows))), patch.object(
                startup.socket, "getaddrinfo") as fallback:
            self.assertEqual(startup.lan_addresses(), [
                ("Ethernet", "192.168.2.10"), ("Z Wi-Fi", "192.168.1.237"),
                ("A VPN", "10.2.0.2"), ("Unknown", "10.3.0.2")])
            fallback.assert_not_called()

    def test_defaults_and_localhost_override(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(startup.server_settings(), ("0.0.0.0", 5000))
        with patch.dict(os.environ, {"SONGTOLEARN_HOST": "127.0.0.1", "SONGTOLEARN_PORT": "5001"}):
            self.assertEqual(startup.server_settings(), ("127.0.0.1", 5001))
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch.object(startup, "lan_addresses") as discovery:
                startup.print_urls(*startup.server_settings())
            discovery.assert_not_called()
            self.assertIn("http://127.0.0.1:5001", output.getvalue())
            self.assertIn("phone access is disabled", output.getvalue())

    def test_discovery_failure_still_explains_phone_address(self):
        with patch.object(startup.socket, "getaddrinfo", side_effect=OSError), patch.object(
                startup.subprocess, "run", side_effect=OSError):
            self.assertEqual(startup.lan_addresses(), [])
        self.assertFalse(startup._is_lan("127.0.0.1"))
        self.assertFalse(startup._is_lan("169.254.1.2"))
        self.assertFalse(startup._is_lan("100.90.220.66"))
        self.assertFalse(startup._is_lan("8.8.8.8"))
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(startup, "lan_addresses", return_value=[]):
            startup.print_urls("0.0.0.0", 5000)
        self.assertIn("ipconfig", output.getvalue())

    def test_main_binds_lan_without_debugger_even_with_flask_debug_env(self):
        import db
        import stt
        import sc_piper
        from flask import Flask

        with tempfile.TemporaryDirectory(prefix="songtolearn-lan-") as directory, contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(db, "DB_PATH", str(Path(directory) / "test.sqlite3")))
            # The app may keep connections alive until GC; track and close them
            # before TemporaryDirectory cleanup on Windows.
            connections = []
            original = db.get_conn

            def get_conn():
                conn = original()
                connections.append(conn)
                return conn

            stack.enter_context(patch.object(db, "get_conn", side_effect=get_conn))
            stack.callback(lambda: [conn.close() for conn in connections])
            stack.enter_context(patch.object(stt, "warm"))
            stack.enter_context(patch.object(sc_piper, "start_warmup"))
            stack.enter_context(patch.dict(os.environ, {
                "SONGTOLEARN_HOST": "0.0.0.0", "SONGTOLEARN_PORT": "5000", "FLASK_DEBUG": "1",
                "SONGTOLEARN_HTTPS": "0"}))
            stack.enter_context(patch.object(startup, "lan_addresses", return_value=[("Wi-Fi", "192.168.1.237")]))
            run = stack.enter_context(patch.object(Flask, "run"))
            output = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            runpy.run_path(str(Path(__file__).with_name("app.py")), run_name="__main__")
            run.assert_called_once_with(host="0.0.0.0", port=5000, debug=False,
                                        use_debugger=False, use_reloader=False, ssl_context=None)
            self.assertIn("Phone on same Wi-Fi (Wi-Fi): http://192.168.1.237:5000", output.getvalue())


if __name__ == "__main__":
    unittest.main()
