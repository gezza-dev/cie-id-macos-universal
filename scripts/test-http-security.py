#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Exercise the production HTTP helper against local HTTP and untrusted TLS.

Pass one or more --trusted-url arguments to also test macOS's native CA store.
No test certificate is installed into any trust store.
"""
import argparse
import http.server
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable', type=Path, help='cie_security_tests binary')
    parser.add_argument('--trusted-url', action='append', default=[])
    args = parser.parse_args()
    def probe(url, accepted, label):
        result = subprocess.run([str(args.executable.resolve()), '--http', url], capture_output=True, text=True, timeout=30)
        if (result.returncode == 0) != accepted or result.returncode not in (0, 2):
            raise RuntimeError(label + ': ' + result.stdout + result.stderr)
        print('PASS ' + label + ': ' + result.stdout.strip(), flush=True)
    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(b'local security fixture\x00\xff')
        def log_message(self, *args):
            pass
    with tempfile.TemporaryDirectory(prefix='cie-tls-test-') as temp:
        directory = Path(temp)
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-keyout', str(directory/'key.pem'), '-out', str(directory/'cert.pem')],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        plain = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        secure = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(directory/'cert.pem', directory/'key.pem')
        secure.socket = context.wrap_socket(secure.socket, server_side=True)
        servers = (plain, secure)
        for server in servers:
            threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            probe('http://127.0.0.1:' + str(plain.server_port), True, 'binary HTTP response')
            probe('https://127.0.0.1:' + str(secure.server_port), False, 'reject self-signed HTTPS certificate')
            probe('file:///etc/hosts', False, 'reject non-HTTP protocol')
            probe('http://user:password@127.0.0.1:' + str(plain.server_port), False, 'reject credentials in URL')
            for url in args.trusted_url:
                probe(url, True, 'accept trusted HTTPS')
        finally:
            for server in servers:
                server.shutdown()
                server.server_close()


if __name__ == '__main__':
    main()
