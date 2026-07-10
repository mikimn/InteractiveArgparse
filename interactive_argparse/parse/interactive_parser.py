import functools
import sys
from argparse import ArgumentParser, Action, Namespace, SUPPRESS, _SubParsersAction
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any, Callable, Dict, List


class QuestionKind(Enum):
    TEXT = "text"
    INT = "int"
    FLOAT = "float"
    CONFIRM = "confirm"
    SINGLE_CHOICE = "single_choice"
    MULTI_CHOICE = "multi_choice"


@dataclass
class Question:
    """A prompter-agnostic description of a single argument to ask about.

    `default` and `choices` hold raw, correctly-typed values (never
    stringified) - it's up to each prompter to format them however its UI
    needs. `cast`, if set, is applied by `InteractiveArgumentParser` itself
    to whatever raw value a prompter returns; prompters never need to call
    it themselves.
    """
    name: str
    message: str
    kind: QuestionKind
    default: Any = None
    choices: Optional[List[Any]] = None
    cast: Optional[Callable[[Any], Any]] = None


def format_question(action_name: str, action_help: str, default=None):
    if action_help is None or action_help == '':
        if default is None:
            return f"{action_name}:"
        return f"{action_name} [default = {default}]:"

    if default is None:
        return f"{action_name} ({action_help}):"
    return f"{action_name} ({action_help}) [default = {default}]:"


def _argparse_action_to_question(action: Action) -> Optional[Question]:
    if action.default == SUPPRESS:
        return None
    if isinstance(action, _SubParsersAction):
        # Subparsers expose `choices` as a dict of sub-parsers, which isn't a
        # valid choice list. Not supported yet, so skip them.
        # TODO: track proper subparser support in a follow-up issue.
        return None
    guessed_type = type(action.default)
    if action.default is None:
        if action.type in [int, str, bool, float]:
            guessed_type = action.type

    if action.nargs and (action.nargs == "+" or (isinstance(action.nargs, int) and action.nargs > 1)):
        kind = QuestionKind.MULTI_CHOICE
    elif (not action.nargs or action.nargs == 1) and action.choices is not None:
        kind = QuestionKind.SINGLE_CHOICE
    else:
        kind = {
            int: QuestionKind.INT,
            str: QuestionKind.TEXT,
            float: QuestionKind.FLOAT,
            bool: QuestionKind.CONFIRM,
        }.get(guessed_type, QuestionKind.TEXT)

    cast = guessed_type if not isinstance(None, guessed_type) else None
    return Question(
        name=action.dest,
        message=format_question(action.dest, action.help, action.default),
        kind=kind,
        default=action.default,
        choices=list(action.choices) if action.choices else None,
        cast=cast,
    )


def not_none(x: Optional[Any]):
    return x is not None


class PyInquirerPrompter:
    """Default prompter: renders `Question`s as a terminal prompt via
    PyInquirer. PyInquirer is only imported the first time this prompter is
    actually invoked, so constructing (or not using) it costs nothing for
    callers who plug in a different prompter.
    """

    _TYPE_MAP = {
        QuestionKind.TEXT: "input",
        QuestionKind.INT: "input",
        QuestionKind.FLOAT: "input",
        QuestionKind.CONFIRM: "confirm",
        QuestionKind.SINGLE_CHOICE: "list",
        QuestionKind.MULTI_CHOICE: "checkbox",
    }

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        prompt = self._load_prompt()
        return prompt([self._to_pyinquirer_dict(q) for q in questions])

    @staticmethod
    def _load_prompt():
        import collections
        import collections.abc
        # PyInquirer's pinned `prompt_toolkit<2.0` imports ABCs from
        # `collections`, which were removed in Python 3.10. Restore them
        # before importing PyInquirer.
        if not hasattr(collections, "Mapping"):
            collections.Mapping = collections.abc.Mapping
        from PyInquirer import prompt
        return prompt

    @classmethod
    def _to_pyinquirer_dict(cls, question: Question) -> dict:
        result = {
            "type": cls._TYPE_MAP[question.kind],
            "name": question.name,
            "message": question.message,
        }
        if question.default is not None:
            # PyInquirer's "input" prompt renders the default as text, so it
            # must be a string; "confirm"/"list"/"checkbox" expect the raw
            # value.
            is_text_like = question.kind in (QuestionKind.TEXT, QuestionKind.INT, QuestionKind.FLOAT)
            result["default"] = str(question.default) if is_text_like else question.default
        if question.choices:
            result["choices"] = question.choices
        return result


class InteractiveArgumentParser:
    def __init__(
            self,
            base_parser: ArgumentParser,
            prompter: Optional[Callable[[List[Question]], Dict[str, Any]]] = None,
            interactive_flag: str = "interactive",
            enable_by_default=True,
    ) -> None:
        super().__init__()
        if base_parser is None:
            raise ValueError("base_parser cannot be None")
        self._base_parser = base_parser
        self._base_parser.parse_known_args = self.parse_known_args
        self._namespace = None
        self._args = None
        self._prompter = prompter if prompter is not None else PyInquirerPrompter()
        self._interactive_flag = interactive_flag.replace("--", "")
        self._enable_by_default = enable_by_default
        self._flag_dest = f"no_{self._interactive_flag}" if enable_by_default else self._interactive_flag
        self._flag_option = f"--{self._flag_dest}"
        self._init_interactive_parser()

    # Proxy
    def __getattr__(self, attr):
        return getattr(self._base_parser, attr)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._base_parser.__repr__()})"

    def _init_interactive_parser(self):
        if self._enable_by_default:
            help_text = f"Disables the {self.__class__.__name__} prompt"
        else:
            help_text = f"Enables the {self.__class__.__name__} prompt"
        self._base_parser.add_argument(
            self._flag_option, dest=self._flag_dest, action="store_true", help=help_text,
        )

    def _should_prompt(self, args: List[str]) -> bool:
        flag_present = self._flag_option in args
        remaining_args = [a for a in args if a != self._flag_option]
        if self._enable_by_default:
            return not flag_present and not remaining_args
        return flag_present and not remaining_args

    def parse_known_args(self, args=None, namespace=None):
        if args is None:
            # args default to the system args
            args = sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        if self._namespace:
            return Namespace(**self._namespace.__dict__.copy()), []

        if not self._should_prompt(args):
            # Real arguments (or an explicit opt-out flag) were supplied:
            # defer to the base parser's normal, non-interactive parsing.
            return ArgumentParser.parse_known_args(self._base_parser, args, namespace)

        # default Namespace built from parser defaults
        if namespace is None:
            namespace = Namespace()

        # add any action defaults that aren't present
        actions = self._base_parser._actions
        for action in actions:
            if action.dest is not SUPPRESS:
                if not hasattr(namespace, action.dest):
                    if action.default is not SUPPRESS:
                        setattr(namespace, action.dest, action.default)

        # add any parser defaults that aren't present
        for dest in self._defaults:
            if not hasattr(namespace, dest):
                setattr(namespace, dest, self._defaults[dest])

        questions = [
            _argparse_action_to_question(action)
            for action in actions
            if action.dest != self._flag_dest
        ]
        questions = list(filter(not_none, questions))
        answers = self._prompter(questions)

        if len(answers) == 0 and len(questions) > 0:
            # Cancelled by user
            exit()

        casts = {question.name: question.cast for question in questions}
        for key, value in answers.items():
            cast = casts.get(key)
            if cast is not None:
                value = cast(value)
            setattr(namespace, key, value)
        self._namespace = Namespace(**namespace.__dict__.copy())
        return namespace, []


def interactive(fn: Callable[..., ArgumentParser]) -> Callable[..., InteractiveArgumentParser]:
    """Decorate a function that builds and returns an `ArgumentParser` so it
    returns an `InteractiveArgumentParser` wrapping it instead, using
    `InteractiveArgumentParser`'s defaults.

        @interactive
        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--name")
            return parser

        args = build_parser().parse_args()

    For custom configuration (prompter, interactive_flag, enable_by_default),
    construct `InteractiveArgumentParser` directly instead.
    """
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return InteractiveArgumentParser(fn(*args, **kwargs))
    return wrapper
