import sys

from interactive_argparse import PyInquirerPrompter, QuestionKind
from interactive_argparse.parse.question import Question


class TestPyInquirerPrompter:
    def test_text_like_kinds_map_to_input_type(self):
        for kind in (QuestionKind.TEXT, QuestionKind.INT, QuestionKind.FLOAT):
            question = Question(name="n", message="m", kind=kind)
            result = PyInquirerPrompter._to_pyinquirer_dict(question)
            assert result["type"] == "input"

    def test_confirm_kind_maps_to_confirm_type_with_raw_default(self):
        question = Question(name="n", message="m", kind=QuestionKind.CONFIRM, default=True)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["type"] == "confirm"
        assert result["default"] is True

    def test_single_choice_kind_maps_to_list_type(self):
        question = Question(
            name="n", message="m", kind=QuestionKind.SINGLE_CHOICE,
            default="red", choices=["red", "green"],
        )
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["type"] == "list"
        assert result["choices"] == ["red", "green"]
        assert result["default"] == "red"

    def test_multi_choice_kind_maps_to_checkbox_type_with_raw_default(self):
        question = Question(name="n", message="m", kind=QuestionKind.MULTI_CHOICE, default=["a", "b"])
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["type"] == "checkbox"
        assert result["default"] == ["a", "b"]

    def test_int_default_is_stringified_for_pyinquirer(self):
        question = Question(name="n", message="m", kind=QuestionKind.INT, default=5)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert result["default"] == "5"
        assert isinstance(result["default"], str)

    def test_no_default_omits_default_key(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert "default" not in result

    def test_no_choices_omits_choices_key(self):
        question = Question(name="n", message="m", kind=QuestionKind.TEXT)
        result = PyInquirerPrompter._to_pyinquirer_dict(question)
        assert "choices" not in result

    def test_pyinquirer_is_not_imported_until_prompter_is_used(self):
        assert "PyInquirer" not in sys.modules
        PyInquirerPrompter()
        assert "PyInquirer" not in sys.modules
