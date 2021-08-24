import argparse
from typing import List

from interactive_argparse import InteractiveArgumentParser


class FakePrompter:
    def __init__(self, mapping: dict):
        self.questions = None
        self.mapping = mapping

    def __call__(self, questions: List[dict]):
        self.questions = questions
        result = {}
        for q in questions:
            name = q.get("name")
            val = self.mapping.get(name, q.get("default"))
            # if q.get("filter", None) is not None:
            #     val = q.get("filter")(val)
            result[name] = val

        return result


class TestInteractiveParser:
    def test_interactive_parser_proxy_add_argument(self):
        parser = InteractiveArgumentParser(argparse.ArgumentParser(), prompter=FakePrompter({
            "string": "not_default"
        }))
        parser.add_argument("-s", "--string", help="A basic string", default="default")
        namespace = parser.parse_args()
        assert namespace.string == "not_default"

    def test_interactive_parser_basic_string(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-s", "--string", help="A basic string", default="default")

        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({
            "string": "not_default"
        }))
        namespace = iparser.parse_args()
        assert namespace.string == "not_default"

    def test_interactive_parser_primitive_types(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-i", "--int", help="A basic int")
        parser.add_argument("-f", "--float", help="A basic int")
        parser.add_argument("-b", "--bool", help="A bool flag", action="store_true")
        parser.add_argument("-l", "--list", help="A basic list", nargs="+")

        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({
            "int": 4,
            "float": 3.0,
            "bool": False,
            "list": ["hello", "world"]
        }))
        namespace = iparser.parse_args()
        assert namespace.int == 4
        assert namespace.float == 3.0
        assert not namespace.bool
        assert namespace.list == ["hello", "world"]


