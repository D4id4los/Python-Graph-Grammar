import pytest
from model_gen import graph
from model_gen.exceptions import ModelGenArgumentError
from pytest_mock import mocker


class TestGraphElement:

    def test_matches_wrong_arg(self, mocker):
        """
        On a Non-GraphElement argument an ArgumentException should be thrown.
        """
        mocker.patch.object(graph.GraphElement, '__abstractmethods__', set())
        e = graph.GraphElement()
        with pytest.raises(ModelGenArgumentError):
            e.matches('')

    @pytest.mark.parametrize('attr1,attr2', [
        ({'a': 1}, {'a': 1}),
        ({'a': 1, 'b': 1}, {'a': 1}),
        ({'a': 1}, {})
    ])
    def test_matches_matching(self, attr1, attr2, mocker):
        """
        If all attrs of the element passed as argument are equal to those of
        the host element then the test returns true.
        """
        mocker.patch.object(graph.GraphElement, '__abstractmethods__', set())
        host_elem = graph.GraphElement()
        test_elem = graph.GraphElement()
        host_elem.attr = attr1
        test_elem.attr = attr2
        assert host_elem.matches(test_elem) is True

    @pytest.mark.parametrize('attr1,attr2', [
        ({}, {'a': 1}),
        ({'a': 1}, {'a': 2}),
        ({'a': 1}, {'a': 1, 'b': 1})
    ])
    def test_matches_missmatching(self, attr1, attr2, mocker):
        """
        If some members of attr in the test element are not present or of
        different value in the host element then matches must return True.
        """
        mocker.patch.object(graph.GraphElement, '__abstractmethods__', set())
        host_elem = graph.GraphElement()
        test_elem = graph.GraphElement()
        host_elem.attr = attr1
        test_elem.attr = attr2
        assert host_elem.matches(test_elem) is False

    @pytest.mark.parametrize('attrs', [
        {},
        {'a': 1}
    ])
    def test_to_yaml(self, attrs, mocker):
        mocker.patch.object(graph.GraphElement, '__abstractmethods__', set())
        e = graph.GraphElement()
        e.attr = attrs
        dict = e.to_yaml()
        assert dict['attr'] == attrs
        assert dict['id'] == id(e)