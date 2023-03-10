from abc import ABC, abstractmethod
import logging
from typing import Self, Type, TypeVar
from htmlparser import Element, Node

logging.basicConfig()
logger = logging.getLogger(__name__)


INHERITED_PROPERTIES = {
    "font-size": "16px",
    "font-style": "normal",
    "font-weight": "normal",
    "color": "black",
    "font-family": "Georgia",
}


class Selector(ABC):
    priority: int

    @abstractmethod
    def matches(self, node: Node) -> bool:
        pass


SelectorType = TypeVar("SelectorType", bound=Selector)


class TagSelector(Selector):
    def __init__(self, tag: str):
        self.tag = tag
        self.priority = 1

    def matches(self, node: Node) -> bool:
        return isinstance(node, Element) and self.tag == node.tag

    def __str__(self):
        return f"tag: {self.tag}"

    def __repr__(self):
        return self.__str__()


class ClassSelector(Selector):
    def __init__(self, klass: str):
        self.klass = klass[1:]
        self.priority = 10

    def matches(self, node: Node) -> bool:
        if isinstance(node, Element):
            if cls := node.attrs.get("class"):
                return cls == self.klass
        return False

    def __str__(self):
        return f"class: {self.klass}"

    def __repr__(self):
        return self.__str__()


class DescendentSelector(Selector):
    def __init__(self, ancestor: SelectorType, descendant: SelectorType):
        self.ancestor = ancestor
        self.descendant = descendant
        self.priority = ancestor.priority + descendant.priority

    def matches(self, node: Node) -> bool:
        if not self.descendant.matches(node):
            return False
        while node.parent:
            if self.ancestor.matches(node.parent):
                return True
            node = node.parent
        return False

    def __str__(self):
        return f"{self.ancestor} {self.descendant}"

    def __repr__(self):
        return self.__str__()


SelectorRule = tuple[TagSelector | DescendentSelector | ClassSelector, dict[str, str]]


def cascade_priority(rule: SelectorRule) -> int:
    selector, _ = rule
    return selector.priority


class CSSParser:
    def __init__(self, s: str):
        self.s: str = s
        self.i: int = 0

    def whitespace(self) -> None:
        while self.i < len(self.s) and self.s[self.i].isspace():
            self.i += 1

    def word(self) -> str:
        start = self.i
        while self.i < len(self.s):
            if self.s[self.i].isalnum() or self.s[self.i] in "'\"#-.%":
                self.i += 1
            else:
                break
        assert self.i > start
        return self.s[start : self.i]

    def literal(self, literal: str):
        assert self.i < len(self.s) and self.s[self.i] == literal
        self.i += 1

    def pair(self) -> tuple[str, str]:
        prop = self.word()
        self.whitespace()
        self.literal(":")
        self.whitespace()
        val = self.word()
        return prop.lower(), val

    def ignore_until(self, chars: str) -> str | None:
        while self.i < len(self.s):
            if self.s[self.i] in chars:
                return self.s[self.i]
            else:
                self.i += 1
        return None

    def body(self) -> dict[str, str]:
        pairs: dict[str, str] = {}
        while self.i < len(self.s) and self.s[self.i] != "}":
            try:
                prop, val = self.pair()
                # print(prop, val)
                pairs[prop.lower()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except AssertionError:
                why = self.ignore_until(";}")
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs

    def selector(self):
        sel = self.word().lower()
        if sel.startswith("."):
            out = ClassSelector(sel)
        else:
            out = TagSelector(sel)
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != "{":
            tag = self.word()
            descendent = TagSelector(tag.lower())
            out = DescendentSelector(out, descendent)
            self.whitespace()
        return out

    def parse(self) -> list[SelectorRule]:
        rules: list[SelectorRule] = []
        while self.i < len(self.s):
            try:
                self.whitespace()
                selector = self.selector()
                self.literal("{")
                self.whitespace()
                body = self.body()
                self.literal("}")
                rules.append((selector, body))
            except AssertionError:
                why = self.ignore_until("}")
                if why == "}":
                    self.literal("}")
                    self.whitespace()
                else:
                    break
        return rules


def compute_style(node: Node, property: str, value: str):
    if property == "font-size":
        if value.endswith("px"):
            return value
        elif value.endswith("%"):
            if node.parent:
                parent_font_size = node.parent.style["font-size"]
            else:
                parent_font_size = INHERITED_PROPERTIES["font-size"]
            node_pct = float(value[:-1]) / 100
            parent_px = float(parent_font_size[:-2])
            return str(node_pct * parent_px) + "px"
        return None
    return value


def style(node: Element, rules: list[SelectorRule]):
    for property, default_value in INHERITED_PROPERTIES.items():
        if node.parent:
            node.style[property] = node.parent.style[property]
        else:
            node.style[property] = default_value

    for selector, body in rules:
        if not selector.matches(node):
            continue
        # print(f"Matched {selector} with {node}")
        for property, value in body.items():
            computed_value = compute_style(node, property, value)
            if not computed_value:
                continue
            node.style[property] = computed_value

    if val := node.attrs.get("style"):
        pairs = CSSParser(val).body()
        for property, value in pairs.items():
            computed_value = compute_style(node, property, value)
            if not computed_value:
                continue
            node.style[property] = computed_value
    for child in node.children:
        if isinstance(child, Element):
            style(child, rules)
