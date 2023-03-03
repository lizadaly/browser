import logging
from pathlib import Path
import socket
import tkinter
import tkinter.font
from typing import Any, Literal, Self
from urllib.parse import urlparse
import ssl

from css import CSSParser, style
from htmlparser import Element, Node, Text, lex


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
FONTS: dict[tuple, tkinter.font.Font] = {}

BLOCK_ELEMENTS = [
    "html",
    "body",
    "article",
    "section",
    "nav",
    "aside",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hgroup",
    "header",
    "footer",
    "address",
    "p",
    "hr",
    "pre",
    "blockquote",
    "ol",
    "ul",
    "menu",
    "li",
    "dl",
    "dt",
    "dd",
    "figure",
    "figcaption",
    "main",
    "div",
    "table",
    "form",
    "fieldset",
    "legend",
    "details",
    "summary",
]


class Browser:
    SCROLL_STEP = 100

    def __init__(self, width=WIDTH, height=HEIGHT) -> None:
        self.display_list: list["DrawText | DrawRect"] = []
        self.scroll = 0
        self.width = width
        self.height = height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(self.window, width=self.width, height=self.height)
        self.canvas.pack()
        self.window.bind("<Down>", self.scrolldown)
        self.window.bind("<Up>", self.scrollup)

        self.default_style_sheet = CSSParser(Path("browser.css").read_text()).parse()


    def scrolldown(self, e):
        max_y = self.document.height - HEIGHT
        self.scroll = min(self.scroll + self.SCROLL_STEP, max_y)
        self.draw()

    def scrollup(self, e):
        self.scroll = max(self.scroll - self.SCROLL_STEP, 0)
        self.draw()

    def load(self, url: str):
        headers, body = request(url)
        self.root = lex(body)
        style(self.root, self.default_style_sheet.copy())
        self.document = DocumentLayout(self.root)
        self.document.layout()
        self.document.paint(self.display_list)
        self.draw()

    def draw(self):
        self.canvas.delete("all")
        for cmd in self.display_list:
            if cmd.top > self.scroll + HEIGHT:
                continue
            if cmd.bottom < self.scroll:
                continue
            cmd.execute(self.scroll, self.canvas)





def layout_mode(node: Node) -> Literal["block", "inline"]:
    if isinstance(node, Text):
        return "inline"
    elif node.children:
        if any(
            [
                isinstance(child, Element) and child.tag in BLOCK_ELEMENTS
                for child in node.children
            ]
        ):
            return "block"
        return "inline"
    return "block"


def get_font(
    size: int, weight: Literal["normal", "bold"], style: Literal["roman", "italic"]
) -> tkinter.font.Font:
    key = (size, weight, style)
    if key not in FONTS:
        font = get_font(size=size, weight=weight, style=style)
        FONTS[key] = font
    return FONTS[key]


class DocumentLayout:
    def __init__(self, node: Element):
        self.node = node
        self.children: list[BlockLayout] = []
        self.display_list: list["DrawText | DrawRect"] = []
        self.width: float = 0
        self.x: float = 0
        self.y: float = 0

    def layout(self):
        child = BlockLayout(self.node, self, None)
        self.children.append(child)
        self.width = WIDTH - 2 * HSTEP
        self.x = HSTEP
        self.y = VSTEP
        child.layout()
        self.height = child.height + 2 * VSTEP

    def paint(self, display_list: list["DrawText | DrawRect"]):
        self.children[0].paint(display_list)


class BlockLayout:
    sizes = {"h1": 24, "h2": 20, "h3": 18, "h4": 16}

    def __init__(
        self,
        node: Node,
        parent: Self | DocumentLayout,
        previous: None | Self,
    ):
        self.node = node
        self.parent: BlockLayout | DocumentLayout = parent
        self.previous: BlockLayout | None = previous
        self.children: list[BlockLayout] = []

        self.display_list: list["DrawText | DrawRect"] = []
        self.cursor_x: float = 0
        self.cursor_y: float = 0
        self.x: float = 0
        self.y: float = 0
        self.width: float = 0
        self.height: float = 0
        self.weight: Literal["normal", "bold"] = "normal"
        self.style: Literal["roman", "italic"] = "roman"
        self.size = 16
        self.family = "Georgia"
        self.line: list[tuple[float, str, tkinter.font.Font]] = []

    def paint(self, display_list: list["DrawText | DrawRect"]):
        bgcolor = self.node.style.get("background-color", "transparent")
        if bgcolor != "transparent":
            x2, y2 = self.x + self.width, self.y + self.height
            rect = DrawRect(self.x, self.y, x2, y2, bgcolor)
            display_list.append(rect)

        for child in self.children:
            child.paint(display_list)

        display_list.extend(self.display_list)

    def layout(self) -> None:
        self.x = self.parent.x
        self.y = (
            self.previous.y + self.previous.height if self.previous else self.parent.y
        )
        self.width = self.parent.width

        mode = layout_mode(self.node)

        if mode == "block":
            previous: BlockLayout | None = None
            for child in self.node.children:
                next = BlockLayout(child, self, previous)
                self.children.append(next)
                previous = next

            for bl in self.children:
                bl.layout()

            self.height = sum([child.height for child in self.children])

        else:
            self.recurse(self.node)
            self.flush()
            self.height = self.cursor_y

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
            if self.cursor_x + w > self.width:
                self.flush()

    def flush(self) -> None:
        if not self.line:
            return
        metrics = [font.metrics() for x, word, font in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for rel_x, word, font in self.line:
            x = rel_x + self.x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append(DrawText(x, y, word, font))
        self.cursor_x = 0
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent


class DrawText:
    def __init__(self, x1: float, y1: float, text: str, font: tkinter.font.Font):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll: float, canvas: tkinter.Canvas):
        canvas.create_text(
            self.left,
            self.top - scroll,
            text=self.text,
            font=self.font,
            anchor="nw",
        )


class DrawRect:
    def __init__(self, x1: float, y1: float, x2: float, y2: float, color: str):
        self.top = y1
        self.left = x1
        self.bottom = y2
        self.right = x2
        self.color = color

    def execute(self, scroll: float, canvas: tkinter.Canvas):
        canvas.create_rectangle(
            self.left,
            self.top - scroll,
            self.right,
            self.bottom - scroll,
            width=0,
            fill=self.color,
        )



if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    args = parser.parse_args()
    Browser().load(args.url)
    tkinter.mainloop()
