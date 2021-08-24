import json
import sys
from argparse import ArgumentParser, Action, Namespace, SUPPRESS
from typing import Optional, Any, Callable, List

from PyInquirer import prompt as pyinquierer_prompt

_UNRECOGNIZED_ARGS_ATTR = '_unrecognized_args'


def format_question(action_name: str, action_help: str, default=None):
    if action_help is None or action_help == '':
        if default is None:
            return f"{action_name}:"
        return f"{action_name} [default = {default}]:"

    if default is None:
        return f"{action_name} ({action_help}):"
    return f"{action_name} ({action_help}) [default = {default}]:"


def _argparse_action_to_question(action: Action) -> Optional[dict]:
    if action.default == SUPPRESS:
        return None
    guessed_type = type(action.default)
    guessed_filter = None
    if action.default is None:
        if action.type in [int, str, bool, float]:
            guessed_type = action.type
            guessed_filter = lambda x: guessed_type(x)

    if action.nargs and (action.nargs == "+" or action.nargs.isnumeric() and int(action.nargs) > 1):
        q_type = "checkbox"
    elif (not action.nargs or action.nargs == 1) and action.choices is not None:
        q_type = "list"
    else:
        q_type = {
            int: 'input',
            str: 'input',
            float: 'input',
            bool: 'confirm',
        }.get(guessed_type, "input")
    result = {
        "type": q_type,
        "name": action.dest,
        "message": format_question(action.dest, action.help, action.default),
    }
    if action.default is not None:
        # result["default"] = str(action.default)
        result["default"] = action.default
    if not isinstance(None, guessed_type):
        result["filter"] = lambda x: guessed_type(x)
    if action.choices:
        result["choices"] = action.choices
    return result


def _format_action_dict(action: Action):
    return {
        "strings": action.option_strings,
        "name": action.dest,
        "nargs": action.nargs,
        "const": action.const,
        "default": action.default,
        "type": action.type.__name__ if action.type is not None else None,
        "choices": action.choices,
        "help": action.help
    }


def not_none(x: Optional[Any]):
    return x is not None


class InteractiveArgumentParser:
    def __init__(
            self,
            base_parser: ArgumentParser,
            prompter: Callable[[List[dict]], Any] = pyinquierer_prompt,
            interactive_flag: str = "interactive",
            enable_by_default=True,
    ) -> None:
        super().__init__()
        assert base_parser, "base_parser cannot be None"
        self._base_parser = base_parser
        self._base_parser.parse_known_args = self.parse_known_args
        self._namespace = None
        self._args = None
        self._prompter = prompter
        self._interactive_flag = interactive_flag.replace("--", "")
        self._enable_by_default = enable_by_default
        self._init_interactive_parser()

    # Proxy
    def __getattr__(self, attr):
        return getattr(self._base_parser, attr)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._base_parser.__repr__()})"

    def _init_interactive_parser(self):
        if self._enable_by_default:
            self._base_parser.add_argument(f"--no_{self._interactive_flag}",
                                           help=f"Disables the {self.__class__.__name__} prompt")
        else:
            self._base_parser.add_argument(f"--{self._interactive_flag}",
                                           help=f"Enables the {self.__class__.__name__} prompt")

    def parse_known_args(self, args=None, namespace=None):
        # TODO Add as overwrites
        if args is None:
            # args default to the system args
            args = sys.argv[1:]
        else:
            # make sure that args are mutable
            args = list(args)

        if self._namespace:
            return Namespace(**self._namespace.__dict__.copy()), args

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
            _argparse_action_to_question(action) for action in actions
        ]
        questions = list(filter(not_none, questions))
        answers = self._prompter(questions)
        print(questions)
        print(answers)

        if len(answers) == 0 and len(questions) > 0:
            # Cancelled by user
            exit()
        for key, value in answers.items():
            setattr(namespace, key, value)
        self._namespace = Namespace(**namespace.__dict__.copy())
        return namespace, []
