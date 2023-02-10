import logging
import socket
import tkinter
from typing import Any
from urllib.parse import urlparse
from html.parser import HTMLParser
import ssl

def request(url: str) -> tuple[(dict, str)]:
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

WIDTH = 800
HEIGHT = 600

def layout(text: str) -> list:
    HSTEP, VSTEP = 13, 18
    cursor_x, cursor_y = HSTEP, VSTEP

    display_list: list[tuple[int, int, str]] = []
    for c in text:
        display_list.append((cursor_x, cursor_y, c))
        cursor_x += HSTEP    
        if cursor_x >= WIDTH - HSTEP:
            cursor_y += VSTEP
            cursor_x = HSTEP
    return display_list
class Browser:

    SCROLL_STEP = 100

    def __init__(self, width=WIDTH, height=HEIGHT) -> None:
        self.display_list: list[tuple[int, int, str]] = []
        self.scroll = 0
        self.width = width
        self.height = height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=self.width, height=self.height)
        self.canvas.pack()
        self.window.bind("<Down>", self.scrolldown)

    def scrolldown(self, e):
        self.scroll += self.SCROLL_STEP
        self.draw()

    def load(self, url: str):

        headers, body = request(url)
        text = lex(body)
        self.display_list = layout(text)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c in self.display_list:
            self.canvas.create_text(x, y - self.scroll, text=c)


def lex(body: str) -> str:
    class BrowserParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.text: list[str] = []
            self.capture = False

        def handle_starttag(self, tag: str, attrs: Any):
            if tag == "body":
                self.capture = True

        def handle_endtag(self, tag: str) -> None:
            if tag == "body":
                self.capture = False

        def handle_data(self, data: str) -> None:
            if self.capture:
                self.text.append(data)

    parser = BrowserParser()
    parser.feed(body)
    return "".join(parser.text )



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('url')
    args = parser.parse_args()
    Browser().load(args.url)
    tkinter.mainloop()

