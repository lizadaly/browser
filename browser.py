import logging
from pathlib import Path
import socket
import tkinter
import tkinter.font
from typing import Any, Literal, Self
from urllib import parse, request as urllib_request
from urllib.parse import urlparse
import ssl

from css import CSSParser, cascade_priority, style
from htmlparser import Element, Node, Text, lex, tree_to_list


logging.basicConfig()

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


def request(url: str) -> str:
    req = urllib_request.Request(
        url,
        headers={
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36"
        },
    )
    with urllib_request.urlopen(req) as f:
        return f.read().decode("utf-8")


class Browser:
    SCROLL_STEP = 100

    def __init__(self, width=WIDTH, height=HEIGHT) -> None:
        self.display_list: list["DrawText | DrawRect"] = []
        self.scroll = 0
        self.width = width
        self.height = height
        self.window = tkinter.Tk()
        self.canvas = tkinter.Canvas(
            self.window, width=self.width, height=self.height, bg="white"
        )
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
        body = request(url)

        self.root = lex(body)
        rules = self.default_style_sheet.copy()
        links = [
            el.attrs["href"]
            for el in tree_to_list(self.root, [])
            if isinstance(el, Element)
            and el.tag == "link"
            and "href" in el.attrs
            and el.attrs.get("rel") == "stylesheet"
        ]
        for link in [l for l in links if l]:
            parts = parse.urlsplit(link)

            if not parts.scheme:
                link = parse.urljoin(url, parts.path)
            try:
                rules.extend(CSSParser(request(url)).parse())
            except AssertionError as e:
                logging.warning(e)
        style(self.root, sorted(rules, key=cascade_priority))
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
    size: int,
    weight: str,
    style: str,
    family: str,
) -> tkinter.font.Font:
    key = (size, weight, style, family)
    if key not in FONTS:
        font = tkinter.font.Font(
            size=size, family=family, weight=weight, slant=style  # type: ignore
        )
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

        self.line: list[tuple[float, str, tkinter.font.Font, str]] = []

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
            if tree.tag == "br":
                self.flush()
            for child in tree.children:
                self.recurse(child)

    def text(self, tok: Text):
        weight = tok.parent.style["font-weight"]
        style = tok.parent.style["font-style"]
        color = tok.parent.style["color"]
        family = tok.parent.style["font-family"].split(",")[0]
        # Normalize some junk for TK
        if style == "normal":
            style = "roman"
        if weight not in ["normal", "bold"]:
            weight = "normal"
        size = int(float(tok.parent.style["font-size"][:-2]) * 0.75)
        font = get_font(size=size, weight=weight, style=style, family=family)

        for word in tok.text.split():
            self.line.append((self.cursor_x, word, font, color))
            w = font.measure(word)
            self.cursor_x += w + font.measure(" ")
            if self.cursor_x + w > self.width:
                self.flush()

    def flush(self) -> None:
        if not self.line:
            return
        metrics = [font.metrics() for _, _, font, _ in self.line]
        max_ascent = max([metric["ascent"] for metric in metrics])
        baseline = self.cursor_y + 1.25 * max_ascent
        for rel_x, word, font, color in self.line:
            x = rel_x + self.x
            y = self.y + baseline - font.metrics("ascent")
            self.display_list.append(DrawText(x, y, word, font, color))
        self.cursor_x = 0
        self.line = []
        max_descent = max([metric["descent"] for metric in metrics])
        self.cursor_y = baseline + 1.25 * max_descent


class DrawText:
    def __init__(
        self, x1: float, y1: float, text: str, font: tkinter.font.Font, color: str
    ):
        self.top = y1
        self.left = x1
        self.text = text
        self.font = font
        self.color = color
        self.bottom = y1 + font.metrics("linespace")

    def execute(self, scroll: float, canvas: tkinter.Canvas):
        canvas.create_text(
            self.left,
            self.top - scroll,
            text=self.text,
            font=self.font,
            anchor="nw",
            fill=self.color,
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
