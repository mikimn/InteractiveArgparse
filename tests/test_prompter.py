import pytest

from interactive_argparse import Prompter, PyInquirerPrompter


class TestPrompterRegistry:
    def test_subclass_with_name_is_registered(self):
        class _TempNamedPrompter(Prompter):
            name = "temp_registry_test"

            def __call__(self, questions):
                return {}

        assert Prompter.registry["temp_registry_test"] is _TempNamedPrompter

    def test_subclass_without_name_is_not_registered(self):
        before = dict(Prompter.registry)

        class _TempUnnamedPrompter(Prompter):
            def __call__(self, questions):
                return {}

        assert Prompter.registry == before

    def test_prompter_cannot_be_instantiated_directly(self):
        with pytest.raises(TypeError):
            Prompter()

    def test_pyinquirer_prompter_is_registered(self):
        assert Prompter.registry["pyinquirer"] is PyInquirerPrompter
