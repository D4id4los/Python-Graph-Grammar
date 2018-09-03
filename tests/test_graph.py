import pytest
from model_gen import graph
from model_gen.exceptions import ModelGenArgumentError


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
        result = e.to_yaml()
        assert result['attr'] == attrs
        assert result['id'] == id(e)


class TestVertex:

    def test_deepcopy_no_edges(self):
        """
        A deepcopy of a Vertex should make a copy of the vertex and save the
        old id to new object mapping into the memodict and if the mapping
        argument is supplied also save a mapping from old object to new object
        in the provided dictionary.


        """
        memodict = {}
        mapping = {}
        v = graph.Vertex()
        copy = v.__deepcopy__(memodict, mapping)
        assert id(v) != id(copy)
        assert memodict[id(v)] == copy
        assert mapping[v] == copy

    def test_deepcopy_with_edges(self):
        """
        Makes a copy of the Vertex where connections remain unchanged,
        i.e. uncopied, even if it exists in the memodict.
        """
        v = graph.Vertex()
        v2 = graph.Vertex()
        e = graph.Edge(v, v2)
        e2 = graph.Edge(v, v2)
        v.edges.add(e)
        memodict = {id(e): e2}
        mapping = {}
        assert e in v.edges
        assert e2 not in v.edges
        copy = v.__deepcopy__(memodict, mapping)
        assert e in copy.edges
        assert len(copy.edges) == 1
        memodict = {}
        copy = v.__deepcopy__(memodict, mapping)
        assert e in copy.edges
        assert len(copy.edges) == 1

    def test_recursive_copy(self):
        """
        Recursive copy should make a copy of all referenced elements
        and reference those in the copy of the original vertex.

        A mapping between the original referenced element and its copy
        shall be saved in a dict if it is provided as an argument.
        """
        mapping = {}
        vertex = graph.Vertex()
        edge = graph.Edge(vertex, None)
        vertex.edges.add(edge)
        copy = vertex.recursive_copy(mapping)
        copy_edge = copy.edges.pop()
        assert id(copy) != id(vertex)
        assert id(copy_edge) != id(edge)
        assert mapping[vertex] == copy
        assert mapping[edge] == copy_edge
        assert len(mapping) == 2

    def test_matches_wrong_arg(self):
        """
        If called with a non GraphElement argument then an error is to be
        thrown.
        """
        v = graph.Vertex()
        with pytest.raises(ModelGenArgumentError):
            v.matches('')

    def test_matches_non_vertex(self):
        v = graph.Vertex()
        v2 = graph.Vertex()
        e = graph.Edge(v, v2)
        assert v.matches(e) is False

    @pytest.mark.parametrize('attr1,attr2,result', [
        ({}, {}, True),
        ({'a': 1}, {}, True),
        ({'a': 1, 'b': 2}, {'a': 1}, True),
        ({}, {'a': 1}, False),
        ({'a': 1}, {'a': 2}, False)
    ])
    def test_matches_vertex(self, attr1, attr2, result):
        v = graph.Vertex()
        v.attr = attr1
        v2 = graph.Vertex()
        v2.attr = attr2
        assert v.matches(v2) is result

    def test_replace_connection_valid_calls(self):
        """
        If the replacement function returns an element it is to be a
        replacement for the connected element, if the function returns None
        then no change is to be made.
        """
        v = graph.Vertex()
        e1 = graph.Edge()
        e2 = graph.Edge()
        v.edges = {e1}

        def func(x):
            if x == e1:
                return e2
            else:
                return None
        v.replace_connection(func)
        assert v.edges == {e2}
        v.replace_connection(func)
        assert v.edges == {e2}

    def test_replace_connection_invalid_func(self):
        """
        If the replacement function does not return a object of a fitting
        class, e.g. returning a Vertex instead of an edge, then an error
        is to be thrown.
        """
        v = graph.Vertex()
        e = graph.Edge()
        v.edges = {e}

        def func(_):
            return ''
        with pytest.raises(ValueError):
            v.replace_connection(func)

        def func2(_):
            return graph.Vertex()
        with pytest.raises(ValueError):
            v.replace_connection(func2)

    def test_from_yaml_not_created(self):
        """
        If the Vertex object has not yet been instantiated (identified by
        the id field in the yaml data) then it should be created and
        returned.
        """
        data = {'id': 1,
                'attr': {'a': 1, 3: 'test'}}
        mapping = {}
        result = graph.Vertex.from_yaml(data, mapping)
        assert result.attr == data['attr']
        assert len(mapping) == 1
        assert data['id'] in mapping

    def test_from_yaml_already_created(self):
        """
        If the Vertex object has already been created (it being present
        in mapping) then that existing object should be returned and no
        new instance created.
        """
        vertex = graph.Vertex()
        data = {'id': 1,
                'attr': {'a': 1, 3: 'test'}}
        mapping = {1: vertex}
        result = graph.Vertex.from_yaml(data, mapping)
        assert id(vertex) == id(result)
        assert len(mapping) == 1


class TestEdge:

    def test_deepcopy_no_connections(self):
        memodict = {}
        mapping = {}
        edge = graph.Edge()
        copy = edge.__deepcopy__(memodict, mapping)
        assert id(copy) != id(edge)
        assert memodict[id(edge)] == copy
        assert mapping[edge] == copy

    def test_deepcopy_with_connections(self):
        """
        Connections to other graph elements should be left untouched by
        the deepcopy.
        """
        mapping = {}
        vertex1 = graph.Vertex()
        vertex2 = graph.Vertex()
        vertex3 = graph.Vertex()
        memodict = {id(vertex1): vertex3}
        edge = graph.Edge(vertex1, vertex2)
        copy = edge.__deepcopy__(memodict, mapping)
        assert id(copy) != id(edge)
        assert id(copy.vertex1) == id(edge.vertex1)
        assert id(copy.vertex2) == id(copy.vertex2)
        assert memodict[id(edge)] == copy
        assert len(mapping) == 1
        assert mapping[edge] == copy

    def test_recursive_copy(self):
        """
        References to other graph elements should lead to copies of
        these elements being made and then referenced in the new object.

        A link betwenn the old and new references should be saved in the
        mapping dict, if such is provided.
        """
        mapping = {}
        vertex1 = graph.Vertex()
        vertex2 = graph.Vertex()
        edge = graph.Edge(vertex1, vertex2)
        copy = edge.recursive_copy(mapping)
        assert id(copy) != id(edge)
        assert id(copy.vertex1) != id(edge.vertex1)
        assert id(copy.vertex2) != id(edge.vertex2)
        assert mapping[edge] == copy
        assert mapping[vertex1] == copy.vertex1
        assert mapping[vertex2] == copy.vertex2
        assert len(mapping) == 3

    def test_matches_wrong_arg(self):
        edge = graph.Edge()
        with pytest.raises(ModelGenArgumentError):
            edge.matches('')

    @pytest.mark.parametrize('attr1,attr2,expected', [
        ({}, {}, True),
        ({'a': 1}, {}, True),
        ({'a': 1}, {'a': 1}, True),
        ({'a': 1}, {'a': 2}, False),
        ({'a': 1}, {'b': 1}, False)
    ])
    def test_matches_edge(self, attr1, attr2, expected):
        edge1 = graph.Edge()
        edge1.attr = attr1
        edge2 = graph.Edge()
        edge2.attr = attr2
        assert edge1.matches(edge2) is expected

    def test_matches_vertex(self):
        edge = graph.Edge()
        vertex = graph.Vertex()
        edge.attr = {'a': 1}
        vertex.attr = {'a': 1}
        assert edge.matches(vertex) is False

    def test_replace_connection_valid_replacements(self):
        edge = graph.Edge()
        vertex1 = graph.Vertex()
        vertex2 = graph.Vertex()
        vertex3 = graph.Vertex()
        edge.vertex1 = vertex1
        edge.vertex2 = vertex2

        def func(x):
            if x == vertex1:
                return vertex3
            else:
                return None
        edge.replace_connection(func)
        assert edge.vertex1 == vertex3
        assert edge.vertex2 == vertex2

    def test_replace_connection_invalid(self):
        edge = graph.Edge()
        vertex1 = graph.Vertex()
        vertex2 = graph.Vertex()
        edge.vertex1 = vertex1
        edge.vertex2 = vertex2

        def func(_):
            return ''
        with pytest.raises(ValueError):
            edge.replace_connection(func)

        def func(_):
            return graph.Edge()
        with pytest.raises(ValueError):
            edge.replace_connection(func)

