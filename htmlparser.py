from html.parser import HTMLParser
from typing import Any, Optional, Self, cast


class Node:
    def __init__(self) -> None:
        self.parent: Any
        self.children: list[Node] = []
        self.style: dict[str, str] = {}


class Text(Node):
    def __init__(self, text: str, parent: Node):
        super().__init__() 
        self.parent: Node = parent
        self.text = text

    def __str__(self):
        return f"[text] {self.text}"


class Element(Node):
    def __init__(
        self, tag: str, attrs: list[tuple[str, None | str]], parent: Self | None = None
    ):
        super().__init__()
        self.parent: None | Element = parent
        self.tag = tag
        self.attrs: dict[str, None | str] = {}
        for n, v in attrs:
            self.attrs[n] = v

    def __str__(self):
        return f"<{self.tag} {self.attrs}>"


def lex(body: str) -> Element:
    class BrowserParser(HTMLParser):
        root: Element | None
        open: list[Node]
        VOID_ELEMENT_TAGS = frozenset(
            [
                "area",
                "base",
                "br",
                "col",
                "embed",
                "hr",
                "img",
                "input",
                "keygen",
                "link",
                "meta",
                "param",
                "source",
                "track",
                "wbr",
            ]
        )

        def __init__(self) -> None:
            super().__init__()
            self.open = []
            self.root = None

        def handle_starttag(self, tag: str, attrs: list[tuple[str, None | str]]):
            el = Element(tag, attrs)
            if not self.root:
                self.root = el
            # print(f"<{el.tag}>")

            if self.open:
                el.parent = cast(Element, self.open[-1])
                # print(f"{el.parent} -> {el.tag}")
                el.parent.children.append(el)

            if el.tag not in self.VOID_ELEMENT_TAGS:
                self.open.append(el)

        def handle_endtag(self, tag: str) -> None:
            # print(f"</{tag}>")
            if tag not in self.VOID_ELEMENT_TAGS:
                self.open.pop()

        def handle_data(self, data: str) -> None:
            if self.root and self.open:
                parent = self.open[-1]
                text = Text(data, parent=parent)
                parent.children.append(text)

    parser = BrowserParser()
    parser.feed(body)
    if not parser.root:
        raise Exception("Did not get a root node")
    return parser.root


def tree_to_list(node: Node, list: list[Node]) -> list[Node]:
    list.append(node)
    for child in node.children:
        tree_to_list(child, list)
    return list
