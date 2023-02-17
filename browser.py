import logging
import socket
import tkinter
import tkinter.font
from typing import Any, Literal, Optional
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
        self.display_list: list[tuple[float, float, str, tkinter.font.Font]] = []
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
        root = lex(body)
        self.display_list = Layout(root).display_list
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for x, y, c, font in self.display_list:
            if y > self.scroll + HEIGHT:
                continue
            if y + VSTEP < self.scroll:
                continue
            self.canvas.create_text(x, y - self.scroll, text=c, anchor="nw", font=font)


class Node:
    def __init__(self, parent: Optional["Node"] | None):
        self.parent: Node | None = parent
        self.children: list[Node] = []


class Text(Node):
    def __init__(self, text: str, parent: Node):
        super().__init__(parent)
        self.text = text

    def __str__(self):
        return f"[text] {self.text}"


class Element(Node):
    def __init__(self, tag: str, attrs: list, parent: Node | None = None):
        super().__init__(parent)
        self.tag = tag
        self.attrs = attrs

    def __str__(self):
        return f"<{self.tag}>"


FONTS: dict[tuple, tkinter.font.Font] = {}


def get_font(
    size: int, weight: Literal["normal", "bold"], style: Literal["roman", "italic"]
) -> tkinter.font.Font:
    key = (size, weight, style)
    if key not in FONTS:
        font = get_font(size=size, weight=weight, style=style)
        FONTS[key] = font
    return FONTS[key]


class Layout:
    sizes = {"h1": 24, "h2": 20, "h3": 18, "h4": 16}

    def __init__(self, root: Element):
        self.display_list: list[tuple[float, float, str, tkinter.font.Font]] = []
        self.cursor_x: float = HSTEP
        self.cursor_y: float = VSTEP
        self.weight: Literal["normal", "bold"] = "normal"
        self.style: Literal["roman", "italic"] = "roman"
        self.size = 16
        self.family = "Georgia"
        self.line: list[tuple[float, str, tkinter.font.Font]] = []

        self.recurse(root)

        self.flush()

    def recurse(self, tree: Node):
        if isinstance(tree, Text):
            self.text(tree)

        elif isinstance(tree, Element):
            self.open_tag(tree.tag)
            for child in tree.children:
                self.recurse(child)
            self.close_tag(tree.tag)

    def open_tag(self, tag: str):
        if tag in ("b", "strong"):
            self.weight = "bold"
        elif tag in ("i", "em"):
            self.style = "italic"
        elif tag in ("h1", "h2", "h3", "h4"):
            self.size = self.sizes[tag]
            self.weight = "bold"
        elif tag in ("div", "p", "nav"):
            self.flush()

    def close_tag(self, tag: str):
        if tag in ("b", "strong"):
            self.weight = "normal"
        elif tag in ("i", "em"):
            self.style = "roman"
        elif tag in ("h1", "h2", "h3", "h4"):
            self.size = 16
            self.weight = "normal"
        elif tag == "br":
            self.flush()
        elif tag in ("div", "p", "nav"):
            self.flush()
            self.cursor_y += VSTEP

    def text(self, tok: Text):
        font = tkinter.font.Font(
            size=self.size, family=self.family, weight=self.weight, slant=self.style
        )
        for word in tok.text.split():
            self.line.append((self.cursor_x, word, font))
            w = font.measure(word)
            self.cursor_x += w + font.measure(" ")
            if self.cursor_x + w > WIDTH - HSTEP:
                self.flush()

    def flush(self) -> None:
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for x, word, font in self.line:
            y = baseline - font.metrics("ascent")
            self.display_list.append((x, y, word, font))
        self.cursor_x = HSTEP
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent


def lex(body: str) -> Element:
    class BrowserParser(HTMLParser):
        root: Element | None
        open: list[Node]

        def __init__(self) -> None:
            super().__init__()
            self.open = []
            self.root = None

        def handle_starttag(self, tag: str, attrs: list):
            el = Element(tag, attrs)
            if not self.root:
                self.root = el

            if self.open:
                el.parent = self.open[-1]
                el.parent.children.append(el)
            print(f"Opening {el}")
            self.open.append(el)

        def handle_endtag(self, tag: str) -> None:
            self.open.pop()

        def handle_data(self, data: str) -> None:
            if self.root:
                parent = self.open[-1]
                text = Text(data, parent=parent)
                parent.children.append(text)

    parser = BrowserParser()
    parser.feed(body)
    if not parser.root:
        raise Exception("Did not get a root node")
    return parser.root


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    Browser().load(args.url)
    tkinter.mainloop()
