import functools
import os
import sys
from argparse import ArgumentParser, Namespace, SUPPRESS
from dataclasses import replace
from typing import Any, Callable, Dict, List, Optional, Union

from .prompter import Prompter
from .pyinquirer_prompter import PyInquirerPrompter
from .question import Question, _argparse_action_to_question, not_none

#: If set, `InteractiveArgumentParser`'s default prompter (used whenever no
#: `prompter=` is passed explicitly) is looked up by this name in
#: `Prompter.registry` instead of always being `PyInquirerPrompter`.
PROMPTER_ENV_VAR = "INTERACTIVE_ARGPARSE_PROMPTER"


def _resolve_prompter(name: str, source: str = "prompter") -> Prompter:
    try:
        prompter_cls = Prompter.registry[name]
    except KeyError:
        raise ValueError(
            f"Unknown {source} {name!r}; registered prompters: {sorted(Prompter.registry)}"
        )
    return prompter_cls()


class InteractiveArgumentParser:
    #: How many times a single question is re-asked after its answer fails
    #: to `cast` (e.g. typing "abc" for an int-typed argument), before giving
    #: up and reporting a usage error instead of crashing with a raw
    #: ValueError/TypeError traceback.
    _MAX_CAST_ATTEMPTS = 3

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
        self._prompter = prompter if prompter is not None else self._build_default_prompter()
        self._interactive_flag = interactive_flag.replace("--", "")
        self._enable_by_default = enable_by_default
        self._flag_dest = f"no_{self._interactive_flag}" if enable_by_default else self._interactive_flag
        self._flag_option = f"--{self._flag_dest}"
        self._init_interactive_parser()

    @staticmethod
    def _build_default_prompter() -> Prompter:
        prompter_name = (os.environ.get(PROMPTER_ENV_VAR) or "").strip()
        if not prompter_name:
            return PyInquirerPrompter()
        return _resolve_prompter(prompter_name, source=f"{PROMPTER_ENV_VAR} value")

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

        questions_by_name = {question.name: question for question in questions}
        for key, value in answers.items():
            question = questions_by_name.get(key)
            if question is not None and question.cast is not None:
                value = self._cast_answer(question, value)
            setattr(namespace, key, value)
        self._namespace = Namespace(**namespace.__dict__.copy())
        return namespace, []

    def _cast_answer(self, question: Question, value: Any) -> Any:
        """Applies `question.cast` to `value`, re-prompting just this one
        question (up to `_MAX_CAST_ATTEMPTS` times total) if casting fails -
        e.g. a plain-text prompter letting someone type "abc" for an
        int-typed argument. Gives up with a normal argparse usage error
        (via `self._base_parser.error`, same as an invalid value passed on
        the real command line) rather than letting the raw ValueError/
        TypeError crash the program.
        """
        last_error: Optional[Exception] = None
        for attempt in range(self._MAX_CAST_ATTEMPTS):
            try:
                return question.cast(value)
            except (TypeError, ValueError) as exc:
                last_error = exc
                if attempt == self._MAX_CAST_ATTEMPTS - 1:
                    break
                retry_question = replace(
                    question,
                    message=f"Invalid value {value!r} for {question.name} ({exc}) - please try again. {question.message}",
                )
                retry_answers = self._prompter([retry_question])
                if not retry_answers:
                    # Cancelled by user
                    exit()
                if question.name not in retry_answers:
                    # Malformed prompter response (missing the one key we
                    # asked for) - stop retrying and fall through to the
                    # same usage-error path as exhausted attempts, instead
                    # of a raw KeyError.
                    break
                value = retry_answers[question.name]
        self._base_parser.error(
            f"invalid value {value!r} for {question.name!r} after {self._MAX_CAST_ATTEMPTS} attempts: {last_error}"
        )


def interactive(prompter: Union[Callable[..., ArgumentParser], str, None] = None):
    """Decorate a function that builds and returns an `ArgumentParser` so it
    returns an `InteractiveArgumentParser` wrapping it instead.

        @interactive
        def build_parser():
            parser = argparse.ArgumentParser()
            parser.add_argument("--name")
            return parser

        args = build_parser().parse_args()

    Can also be called with the registered name of a `Prompter` subclass
    (see `Prompter.registry`) to use that prompter instead of the default::

        @interactive("web")
        def build_parser(): ...

    For anything beyond picking a registered prompter by name (a custom
    `prompter` instance, `interactive_flag`, `enable_by_default`, ...),
    construct `InteractiveArgumentParser` directly instead.
    """
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            resolved_prompter = _resolve_prompter(prompter) if isinstance(prompter, str) else None
            return InteractiveArgumentParser(fn(*args, **kwargs), prompter=resolved_prompter)
        return wrapper

    if callable(prompter):
        # Bare `@interactive` - `prompter` is actually the decorated function.
        fn, prompter = prompter, None
        return decorator(fn)
    return decorator
