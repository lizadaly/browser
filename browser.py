import logging
import socket
import tkinter
import tkinter.font
from typing import Any, Literal
from urllib.parse import urlparse
from html.parser import HTMLParser
import ssl


def request(url: str) -> tuple[(dict, str)]:
    o = urlparse(url)
    s = socket.socket(
        family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    port = o.port
    if not port:
        port = 80 if o.scheme == "http" else 443
    s.connect((o.hostname, port))
    if o.scheme == "https":
        ctx = ssl.create_default_context()
        s = ctx.wrap_socket(s, server_hostname=o.hostname)

    s.send(
        (
            f"GET {o.path or '/'} HTTP/1.1\r\n"
            "Connection: close\r\n"
            f"Host: {o.hostname}\r\n\r\n".encode("utf8")
        )
    )
    response = s.makefile("r", encoding="utf8", newline="\r\n")
    statusline = response.readline()
    version, status, explanation = statusline.split(" ", 2)
    assert status == "200", f"{status}: {explanation}"
    headers = {}
    while True:
        line = response.readline()
        if line == "\r\n":
            break
        header, value = line.split(":", 1)
        headers[header.lower()] = value.strip()
    assert "transfer-encoding" not in headers
    assert "content-encoding" not in headers
    body = response.read()
    s.close()

    return headers, body


WIDTH = 800
HEIGHT = 600
HSTEP, VSTEP = 13, 18


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
        self.window.bind("<Up>", self.scrollup)

    def scrolldown(self, e):
        self.scroll += self.SCROLL_STEP
        self.draw()

    def scrollup(self, e):
        self.scroll -= self.SCROLL_STEP
        self.draw()

    def load(self, url: str):
        headers, body = request(url)
        tokens = lex(body)
        self.display_list = layout(tokens)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c, font in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c, anchor="nw", font=font)


class Text:
    def __init__(self, text: str):
        self.text = text


class Tag:
    def __init__(self, tag: str, mode: str):
        self.tag = tag
        self.mode = mode


def layout(tokens: list[Tag | Text]) -> list:
    display_list: list[tuple[float, float, str, tkinter.font.Font]] = []
    cursor_x: float = HSTEP
    cursor_y: float = VSTEP

    for tok in tokens:
        weight: Literal["normal", "bold"] = "normal"
        slant: Literal["roman", "italic"] = "roman"
        if isinstance(tok, Tag):
            if tok.tag in ("b", "strong"):
                if tok.mode == "start":
                    weight = "bold"
                else:
                    weight = "normal"
            if tok.tag in ("i", "em"):
                if tok.mode == "start":
                    slant = "italic"
                else:
                    slant = "roman"

        font = tkinter.font.Font(family="Helvetica", size=16, weight=weight, slant=slant)

        if isinstance(tok, Text):
            for word in tok.text.split():
                w = font.measure(word)
                if cursor_x + w > WIDTH - HSTEP:
                    cursor_y += font.metrics("linespace") * 1.25
                    cursor_x = HSTEP
                display_list.append((cursor_x, cursor_y, word, font))
                cursor_x += w + font.measure(" ")
    return display_list


def lex(body: str) -> list[Tag | Text]:
    class BrowserParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.text: list[str] = []
            self.tokens: list[Tag | Text] = []
            self.capture = False

        def handle_starttag(self, tag: str, attrs: Any):
            if tag == "body":
                self.capture = True
            if self.capture:
                if tag in ("script", "style"):
                    self.capture = False
                self.tokens.append(Tag(tag, mode="start"))

        def handle_endtag(self, tag: str) -> None:
            if tag == "body":
                self.capture = False
            if self.capture:
                self.tokens.append(Tag(tag, mode="end"))
            if tag in ("script", "style"):
                self.capture = True

        def handle_data(self, data: str) -> None:
            if self.capture:
                self.tokens.append(Text(data))

    parser = BrowserParser()
    parser.feed(body)
    return parser.tokens


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    Browser().load(args.url)
    tkinter.mainloop()
