import argparse
import pathlib

from interactive_argparse import QuestionKind
from interactive_argparse.parse.question import _argparse_action_to_question, _subparsers_action_to_question


class TestArgparseActionToQuestion:
    def test_store_true_action_is_confirm_kind(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--should_greet", action="store_true")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.CONFIRM
        assert question.default is False

    def test_choices_without_nargs_is_single_choice_kind(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--color", choices=["red", "green", "blue"], default="red")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.SINGLE_CHOICE
        assert question.choices == ["red", "green", "blue"]
        assert question.default == "red"

    def test_nargs_plus_is_multi_choice_kind(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--list", nargs="+")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.MULTI_CHOICE

    def test_nargs_int_greater_than_one_is_multi_choice_kind(self):
        # Regression test: action.nargs can be a plain int (e.g. nargs=2),
        # which previously crashed on `action.nargs.isnumeric()`.
        parser = argparse.ArgumentParser()
        parser.add_argument("--pair", nargs=2)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.MULTI_CHOICE

    def test_multi_choice_default_is_a_raw_list(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--tags", nargs="+", default=["a", "b"])
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.MULTI_CHOICE
        assert question.default == ["a", "b"]

    def test_positional_without_default_has_no_cast_or_default(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("name")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.TEXT
        assert question.default is None
        assert question.cast is None

    def test_help_is_the_raw_help_string(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name", help="The user's name.")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.help == "The user's name."

    def test_help_is_none_when_not_provided(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--name")
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.help is None

    def test_type_int_without_default_gets_int_cast(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.INT
        assert question.cast("5") == 5

    def test_int_default_is_raw_not_stringified(self):
        # Stringifying for text-based prompts (e.g. PyInquirer's "input"
        # question) is a prompter concern now, not a Question concern - see
        # TestPyInquirerPrompter for that translation.
        parser = argparse.ArgumentParser()
        parser.add_argument("--count", type=int, default=5)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.INT
        assert question.default == 5
        assert isinstance(question.default, int)

    def test_custom_type_outside_known_set_has_no_cast(self):
        # Documents current behavior: custom `type=` callables that aren't
        # int/str/bool/float are not applied as a cast, so the answer stays
        # as the raw (usually string) value from the prompter.
        parser = argparse.ArgumentParser()
        parser.add_argument("--path", type=pathlib.Path)
        question = _argparse_action_to_question(parser._actions[-1])
        assert question.cast is None

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


class TestSubparsersActionToQuestion:
    def test_builds_single_choice_question_over_subcommand_names(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        subparsers.add_parser("stop")
        question = _subparsers_action_to_question(parser._actions[-1])
        assert question.kind == QuestionKind.SINGLE_CHOICE
        assert question.name == "command"
        assert question.choices == ["run", "stop"]

    def test_default_falls_back_to_first_choice_when_unset(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        subparsers.add_parser("stop")
        question = _subparsers_action_to_question(parser._actions[-1])
        assert question.default == "run"

    def test_default_is_honored_when_it_is_a_valid_choice(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        subparsers.add_parser("run")
        subparsers.add_parser("stop")
        action = parser._actions[-1]
        action.default = "stop"
        question = _subparsers_action_to_question(action)
        assert question.default == "stop"

    def test_uses_synthetic_name_when_dest_is_suppressed(self):
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers()
        subparsers.add_parser("run")
        action = parser._actions[-1]
        assert action.dest == argparse.SUPPRESS
        question = _subparsers_action_to_question(action)
        assert question.name == "_subcommand"

    def test_returns_none_when_no_subcommands_registered(self):
        parser = argparse.ArgumentParser()
        parser.add_subparsers(dest="command")
        action = parser._actions[-1]
        assert _subparsers_action_to_question(action) is None
