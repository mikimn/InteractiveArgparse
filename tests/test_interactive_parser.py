import argparse
import pathlib
from typing import List

import pytest

from interactive_argparse import InteractiveArgumentParser
from interactive_argparse.parse.interactive_parser import _argparse_action_to_question


class FakePrompter:
    def __init__(self, mapping: dict):
        self.questions = None
        self.mapping = mapping
        self.call_count = 0

    def __call__(self, questions: List[dict]):
        self.call_count += 1
        self.questions = questions
        result = {}
        for q in questions:
            name = q.get("name")
            val = self.mapping.get(name, q.get("default"))
            filter_fn = q.get("filter")
            if filter_fn is not None:
                val = filter_fn(val)
            result[name] = val

        return result


class TestInteractiveParser:
    def test_interactive_parser_proxy_add_argument(self):
        parser = InteractiveArgumentParser(argparse.ArgumentParser(), prompter=FakePrompter({
            "string": "not_default"
        }))
        parser.add_argument("-s", "--string", help="A basic string", default="default")
        namespace = parser.parse_args([])
        assert namespace.string == "not_default"

    def test_interactive_parser_basic_string(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("-s", "--string", help="A basic string", default="default")

        iparser = InteractiveArgumentParser(parser, prompter=FakePrompter({
            "string": "not_default"
        }))
        namespace = iparser.parse_args([])
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
        namespace = iparser.parse_args([])
        assert namespace.int == 4
        assert namespace.float == 3.0
        assert not namespace.bool
        assert namespace.list == ["hello", "world"]


class TestArgparseActionToQuestion:
    def test_store_true_action_is_confirm_type(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--should_greet", action="store_true")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "confirm"
        assert question["default"] is False

    def test_choices_without_nargs_is_list_type(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--color", choices=["red", "green", "blue"], default="red")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "list"
        assert question["choices"] == ["red", "green", "blue"]
        # "list" defaults are passed through as-is, not stringified
        assert question["default"] == "red"

    def test_nargs_plus_is_checkbox_type(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--list", nargs="+")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "checkbox"

    def test_nargs_int_greater_than_one_is_checkbox_type(self):
        # Regression test: action.nargs can be a plain int (e.g. nargs=2),
        # which previously crashed on `action.nargs.isnumeric()`.
        parser = argparse.ArgumentParser()
        parser.add_argument("--pair", nargs=2)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "checkbox"

    def test_checkbox_default_is_not_stringified(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--tags", nargs="+", default=["a", "b"])
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "checkbox"
        assert question["default"] == ["a", "b"]

    def test_positional_without_default_has_no_filter_or_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("name")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "input"
        assert "default" not in question
        assert "filter" not in question

    def test_type_int_without_default_gets_int_filter(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["filter"]("5") == 5

    def test_input_default_is_stringified(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int, default=5)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question["type"] == "input"
        assert question["default"] == "5"
        assert isinstance(question["default"], str)

    def test_custom_type_outside_known_set_has_no_filter(self):
        # Documents current behavior: custom `type=` callables that aren't
        # int/str/bool/float are not applied as a filter, so the answer
        # stays as the raw (usually string) value from the prompter.
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathlib.Path)
        question = _argparse_action_to_question(parser._actions[-1])
        assert "filter" not in question

    def test_suppress_default_returns_none(self):
        parser = argparse.ArgumentParser()
        help_action = parser._actions[0]
        assert help_action.default == argparse.SUPPRESS
        assert _argparse_action_to_question(help_action) is None

    def test_subparsers_action_returns_none(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        assert _argparse_action_to_question(parser._actions[-1]) is None


class TestInteractiveParserEndToEnd:
    @staticmethod
    def _build_parser():
        parser = argparse.ArgumentParser()
        parser.add_argument("-s", "--string", help="A basic string", default="default")
        parser.add_argument("-i", "--int", help="A basic int", type=int, default=1)
        parser.add_argument("-f", "--float", help="A basic float", type=float, default=1.0)
        parser.add_argument("-b", "--bool", help="A bool flag", action="store_true")
        parser.add_argument("-l", "--list", help="A basic list", nargs="+", default=["x"])
        parser.add_argument("-c", "--color", help="A choice", choices=["red", "green", "blue"], default="red")
        parser.add_argument("name", help="A positional")
        return parser

    def test_full_parser_happy_path(self):
        parser = self._build_parser()
        prompter = FakePrompter({
            "string": "hello",
            "int": 5,
            "float": 2.5,
            "bool": True,
            "list": ["a", "b"],
            "color": "green",
            "name": "alice",
        })
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args([])
        assert namespace.string == "hello"
        assert namespace.int == 5
        assert namespace.float == 2.5
        assert namespace.bool is True
        assert namespace.list == ["a", "b"]
        assert namespace.color == "green"
        assert namespace.name == "alice"

    def test_defaults_are_prepopulated_and_preserved(self):
        parser = self._build_parser()
        # Only answer the positional; everything else should fall back to
        # its declared default, correctly typed.
        prompter = FakePrompter({"name": "alice"})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args([])
        assert namespace.string == "default"
        assert namespace.int == 1
        assert namespace.float == 1.0
        assert namespace.bool is False
        assert namespace.list == ["x"]
        assert namespace.color == "red"

    def test_second_call_does_not_reprompt(self):
        parser = self._build_parser()
        prompter = FakePrompter({"name": "alice"})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        first = iparser.parse_args([])
        second_namespace, extras = iparser.parse_known_args([])
        assert prompter.call_count == 1
        assert extras == []
        assert second_namespace.name == first.name

    def test_cancel_raises_system_exit(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name")
        iparser = InteractiveArgumentParser(parser, prompter=lambda questions: {})
        with pytest.raises(SystemExit):
            iparser.parse_args([])

    def test_proxy_passthrough_to_base_parser(self):
        base = argparse.ArgumentParser(description="desc", prog="myprog")
        iparser = InteractiveArgumentParser(base, prompter=FakePrompter({}))
        assert iparser.description == "desc"
        assert iparser.prog == "myprog"
        assert iparser.add_mutually_exclusive_group() is not None

    def test_real_args_skip_prompting(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name")
        parser.add_argument("--should_greet", action="store_true")
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args(["--name", "Alice", "--should_greet"])
        assert namespace.name == "Alice"
        assert namespace.should_greet is True
        assert prompter.call_count == 0

    def test_no_interactive_flag_skips_prompting(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name", default="bob")
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args(["--no_interactive"])
        assert namespace.name == "bob"
        assert prompter.call_count == 0

    def test_no_interactive_flag_with_missing_required_arg_errors(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name", required=True)
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        with pytest.raises(SystemExit):
            iparser.parse_known_args(["--no_interactive"])

    def test_subparsers_does_not_crash_during_prompting(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        parser.add_argument("--name", default="bob")
        prompter = FakePrompter({})
        iparser = InteractiveArgumentParser(parser, prompter=prompter)
        namespace = iparser.parse_args([])
        assert namespace.name == "bob"
