from abc import ABC, abstractmethod
from typing import Self, Type, TypeVar
from htmlparser import Element, Node


class Selector(ABC):
    @abstractmethod
    def matches(self, node: Node) -> bool:
        pass

SelectorType = TypeVar('SelectorType', bound=Selector)

class TagSelector(Selector):
    def __init__(self, tag: str):
        self.tag = tag 


    def matches(self, node: Node) -> bool:
        return isinstance(node, Element) and self.tag == node.tag
    
class DescendentSelector(Selector):
    def __init__(self, ancestor: SelectorType, descendant: SelectorType):
        self.ancestor = ancestor
        self.descendent = descendant

    def matches(self, node: Node) -> bool:
        if not self.descendent.matches(node):
            return False 
        while node.parent:
            if self.ancestor.matches(node.parent):
                return True
            node = node.parent 
        return False 

SelectorRule = tuple[TagSelector | DescendentSelector, dict[str, str]]


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
            if self.s[self.i].isalnum() or self.s[self.i] in "#-.%":
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
                pairs[prop.lower()] = val
                self.whitespace()
                self.literal(";")
                self.whitespace()
            except AssertionError as e:
                print(e)
                why = self.ignore_until(";}")
                if why == ";":
                    self.literal(";")
                    self.whitespace()
                else:
                    break
        return pairs


    def selector(self):
        out = TagSelector(self.word().lower())
        self.whitespace()
        while self.i < len(self.s) and self.s[self.i] != '{}':
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

    

def style(node: Element, rules: list[SelectorRule]):
    for selector, body in rules:
        if not selector.matches(node):
            continue

        for property, value in body.items():
            node.style[property] = value

    if val := node.attrs.get("style"):
        pairs = CSSParser(val).body()
        for property, value in pairs.items():
            node.style[property] = value
    for child in node.children:
        if isinstance(child, Element):
            style(child, rules)

