from abc import ABCMeta, abstractmethod
from typing import Any, Dict, List, Optional, Type

from .question import Question


class PrompterMeta(ABCMeta):
    """Metaclass that auto-registers concrete `Prompter` subclasses by their
    `name` class attribute, so `@interactive("name")` (or `Prompter.registry`
    directly) can resolve a prompter without every caller needing to import
    and construct it by hand.
    """
    registry: Dict[str, Type["Prompter"]] = {}

    def __new__(mcs, class_name, bases, namespace, **kwargs):
        cls = super().__new__(mcs, class_name, bases, namespace, **kwargs)
        prompter_name = namespace.get("name")
        if prompter_name is not None:
            mcs.registry[prompter_name] = cls
        return cls


class Prompter(metaclass=PrompterMeta):
    """Base class for prompters: a callable that turns a list of `Question`s
    into a `{name: raw_answer}` dict.

    A concrete subclass sets a `name` class attribute to register itself in
    `Prompter.registry`, e.g.::

        class MyPrompter(Prompter):
            name = "mine"
            def __call__(self, questions): ...

        @interactive("mine")
        def build_parser(): ...
    """
    name: Optional[str] = None

    @abstractmethod
    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        raise NotImplementedError
