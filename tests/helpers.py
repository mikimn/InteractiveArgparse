from typing import Any, Dict, List

from interactive_argparse import Prompter
from interactive_argparse.parse.question import Question


class FakePrompter(Prompter):
    def __init__(self, mapping: dict):
        self.questions = None
        self.mapping = mapping
        self.call_count = 0

    def __call__(self, questions: List[Question]) -> Dict[str, Any]:
        self.call_count += 1
        self.questions = questions
        return {q.name: self.mapping.get(q.name, q.default) for q in questions}
