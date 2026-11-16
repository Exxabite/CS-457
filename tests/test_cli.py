import argparse
import contextlib
import io
import socket
import unittest
from unittest.mock import patch

from code.client import connect_to_server, main as client_main, parse_args as parse_client_args
from code.client import parse_port as parse_client_port
from code.server import parse_args as parse_server_args
from code.server import parse_port as parse_server_port


class CommandLineTests(unittest.TestCase):
    def test_client_requires_host_and_port(self):
        args = parse_client_args(["-i", "localhost", "-p", "5000"])
        self.assertEqual(args.host, "localhost")
        self.assertEqual(args.port, 5000)
        with self.assertRaises(SystemExit):
            parse_client_args([])

    def test_server_requires_port(self):
        self.assertEqual(parse_server_args(["-p", "5000"]).port, 5000)
        with self.assertRaises(SystemExit):
            parse_server_args([])

    def test_both_clis_validate_port_range(self):
        for parse_port in (parse_client_port, parse_server_port):
            self.assertEqual(parse_port("1024"), 1024)
            self.assertEqual(parse_port("65535"), 65535)
            for value in ("abc", "1023", "65536"):
                with self.assertRaises(argparse.ArgumentTypeError):
                    parse_port(value)

    def test_client_connects_using_localhost_dns(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            client_socket = connect_to_server("localhost", port)
            accepted_socket, _ = listener.accept()
            client_socket.close()
            accepted_socket.close()

    def test_client_reports_dns_failure_cleanly(self):
        output = io.StringIO()
        with patch("code.client.socket.getaddrinfo", side_effect=socket.gaierror("not found")):
            with contextlib.redirect_stdout(output):
                result = client_main(["-i", "bad-host", "-p", "5000"])

        self.assertEqual(result, 1)
        self.assertIn("Could not resolve server hostname: bad-host", output.getvalue())


if __name__ == "__main__":
    unittest.main()