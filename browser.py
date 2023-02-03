import logging
import socket
from urllib.parse import urlparse
from html.parser import HTMLParser
import ssl

def request(url: str) -> tuple((dict, str)):
    o = urlparse(url)
    s = socket.socket(family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP)
    port = o.port
    if not port:
        port = 80 if o.scheme == "http" else 443
    s.connect((o.hostname, port))
    if o.scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=o.hostname)

    s.send((f"GET {o.path or '/'} HTTP/1.1\r\n"
            "Connection: close\r\n"
            f"Host: {o.hostname}\r\n\r\n".encode('utf8')))
    response = s.makefile("r", encoding="utf8", newline="\r\n")
    statusline = response.readline()
    version, status, explanation = statusline.split(" ", 2)
    assert status == "200", f"{status}: {explanation}"
    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n": break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()
    assert "transfer-encoding" not in headers
    assert "content-encoding" not in headers
    body = response.read()
    s.close()

    return headers, body


def show(body: str) -> str:

    class BrowserParser(HTMLParser):
        def handle_data(self, data: str) -> None:
            print(data)
    parser = BrowserParser()
    parser.feed(body)

def load(url: str):
    headers, body = request(url)
    show(body)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()
    load(args.url)

