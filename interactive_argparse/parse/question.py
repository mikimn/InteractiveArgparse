from argparse import Action, SUPPRESS, _SubParsersAction
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, List, Optional


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

    `message` is a fully-formatted, terminal-ready prompt string (name,
    help text and default all combined) - `help` is the raw, unformatted
    help text alone, for prompters that want to lay out the label and
    description separately (e.g. as a form field label plus a caption)
    instead of using `message` as-is.

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
    help: Optional[str] = None


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
        help=action.help or None,
    )


def not_none(x: Optional[Any]):
    return x is not None
