import abc
import itertools
import copy
from typing import MutableSet, Dict, Any, AnyStr, Sequence, Iterable
from typing import MutableSequence, Tuple, Callable, Sized
from model_gen.exceptions import ModelGenArgumentError
from model_gen.utils import get_logger

log = get_logger('model_gen.' + __name__)


class GraphElement(abc.ABC):
    """
    Base class from which all elements of a graph derive.

    It contains basic functionality that all graph elements share, such as a
    list of attributes.
    """

    def __init__(self):
        self.attr: Dict[AnyStr, Any] = {}

    @abc.abstractmethod
    def matches(self, graph_element) -> bool:
        """
        Test if the two graph elements match based on their attributes.

        In this test the graph_element is considered to be the mother graph, or
        left-hand-side, of a production. This means that all attributes of the
        graph_element must also be present and matching in this element for the
        function to return true.

        :param graph_element: The graph element to test for matching
        attributes.
        :return: True if the attributes of the two elements are matching.
        """
        if not isinstance(graph_element, GraphElement):
            raise ModelGenArgumentError()
        try:
            for attr_key in graph_element.attr.keys():
                if self.attr[attr_key] != graph_element.attr[attr_key]:
                    return False
        except KeyError:
            return False
        return True

    @abc.abstractmethod
    def add_to(self, graph: 'Graph') -> None:
        """
        Add this element to the graph passed as argument.

        :param graph: The graph to add this element to.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_from(self, graph: 'Graph') -> None:
        """
        Remove this element from the graph passed as argument.

        :param graph: The graph to remove this elemnt from.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def neighbours(self) -> Iterable['GraphElement']:
        """
        Return all a list of all neighbouring elements of this element.

        :return: A list of all neighbouring elements.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']) -> None:
        """
        Replace all connected elements with results returned by replacement
        function.

        If the function returns None, no replacement is performed.

        :param get_replacement: The function deciding if and by what a
        GraphElement is to be replaced.
        """
        raise NotImplementedError()

    def to_yaml(self) -> Dict:
        """
        Serialize the GraphElement into a list or dict which can be used to
        create a yaml export.

        :return: A list or dict representing the GraphElement.
        """
        fields = {
            'attr': self.attr,
            'id': id(self)
        }

        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        """
        Create a GraphElement for the serialized list or dict from a yaml
        import.

        :return: A GraphElement corresponding to the list or dict.
        """
        raise NotImplementedError


class Vertex(GraphElement):
    """
    Represents a vertex inside a graph.
    """

    def __init__(self):
        super().__init__()
        self.edges: MutableSet['Edge'] = set()

    # noinspection PyDefaultArgument
    def __deepcopy__(self, memodict={}, mapping=None):
        """
        Return a deep copy of the Vertex where connecting edges are only
        present if they have a corresponding deepcopy in memodict.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memodict[id(self)] = result
        if mapping is not None:
            mapping[self] = result
        for key, value in self.__dict__.items():
            if key == 'edges':
                # Do not copy connected edges
                setattr(result, key, value)
            else:
                # noinspection PyArgumentList
                setattr(result, key, copy.deepcopy(value, memodict))
        return result

    # noinspection PyDefaultArgument
    def recursive_copy(self,
                       mapping: Dict['GraphElement', 'GraphElement'] = {}
                       ) -> 'Vertex':
        """
        Like deepcopy, but will also create copies for connected graph
        elements.

        :arg mapping: A dict mapping original elements to already
                      created copies of them.
        :return: A copy of this graph element
        """
        if self in mapping:
            # noinspection PyTypeChecker
            return mapping[self]
        cls = self.__class__
        result = cls.__new__(cls)
        mapping[self] = result
        for key, value in self.__dict__.items():
            if key == 'edges':
                new_edges = set()
                for old_edge in value:
                    new_edges.add(old_edge.recursive_copy(mapping))
                setattr(result, key, new_edges)
            else:
                setattr(result, key, copy.deepcopy(value))
        return result

    def matches(self, graph_element):
        if not isinstance(graph_element, GraphElement):
            raise ModelGenArgumentError()
        if not isinstance(graph_element, Vertex):
            return False
        return super().matches(graph_element)

    def add_to(self, graph: 'Graph'):
        graph.vertices.append(self)

    def delete_from(self, graph: 'Graph'):
        graph.vertices.remove(self)
        for edge in self.edges:
            if edge.vertex1 == self:
                edge.vertex1 = None
            if edge.vertex2 == self:
                edge.vertex2 = None

    def neighbours(self):
        return self.edges

    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']):
        to_add = []
        to_remove = []
        for edge in self.edges:
            result = get_replacement(edge)
            if result is not None and not isinstance(result, Edge):
                raise ValueError()
            if result is not None:
                to_add.append(result)
                to_remove.append(edge)
        for edge in to_remove:
            self.edges.remove(edge)
        for edge in to_add:
            self.edges.add(edge)

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Vertex()
        result.attr = data['attr']
        mapping[data['id']] = result
        return result


class Edge(GraphElement):
    """
    Represents an edge inside a graph.
    """

    def __init__(self, vertex1: Vertex = None, vertex2: Vertex = None):
        super().__init__()
        self.vertex1 = vertex1
        self.vertex2 = vertex2

    # noinspection PyDefaultArgument
    def __deepcopy__(self, memodict={}, mapping=None):
        """
        Return a deepcopy of the edge where the vertices are only present if
        they have a corresponding deepcopy in memodict.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memodict[id(self)] = result
        if mapping is not None:
            mapping[self] = result
        for key, value in self.__dict__.items():
            if key == 'vertex1' or key == 'vertex2':
                # Do not create copies of connected vertices
                setattr(result, key, value)
            else:
                # noinspection PyArgumentList
                setattr(result, key, copy.deepcopy(value, memodict))
        return result

    # noinspection PyDefaultArgument
    def recursive_copy(self,
                       mapping: Dict['GraphElement', 'GraphElement'] = {}
                       ) -> 'Edge':
        """
        Like deepcopy, but will also create copies for connected graph
        elements.

        :arg mapping: A dict mapping original elements to already created
                      copies of them.
        :return: A copy of this graph element
        """
        if self in mapping:
            return mapping[self]
        cls = self.__class__
        result = cls.__new__(cls)
        mapping[self] = result
        for key, value in self.__dict__.items():
            if (key == 'vertex1' or key == 'vertex2') and value is not None:
                setattr(result, key, value.recursive_copy(mapping))
            else:
                setattr(result, key, copy.deepcopy(value))
        return result

    def matches(self, graph_element):
        if not isinstance(graph_element, GraphElement):
            raise ModelGenArgumentError
        if not isinstance(graph_element, Edge):
            return False
        return super().matches(graph_element)

    def add_to(self, graph: 'Graph'):
        graph.edges.append(self)
        for vertex in (self.vertex1, self.vertex2):
            if vertex is not None:
                vertex.edges.add(self)

    def delete_from(self, graph: 'Graph'):
        graph.edges.remove(self)
        for vertex in (self.vertex1, self.vertex2):
            if vertex is not None and self in vertex.edges:
                vertex.edges.remove(self)

    def neighbours(self):
        result = []
        if self.vertex1 is not None:
            result.append(self.vertex1)
        if self.vertex2 is not None:
            result.append(self.vertex2)
        return result

    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']):
        result = get_replacement(self.vertex1)
        if result is not None:
            if not isinstance(result, Vertex):
                raise ValueError()
            self.vertex1 = result
        result = get_replacement(self.vertex2)
        if result is not None:
            if not isinstance(result, Vertex):
                raise ValueError()
            self.vertex2 = result

    def to_yaml(self):
        fields = super().to_yaml()
        fields['vertex1'] = id(self.vertex1)
        fields['vertex2'] = id(self.vertex2)
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        if data['id'] in mapping:
            return mapping[data['id']]
        vertex1 = mapping[data['vertex1']]
        vertex2 = mapping[data['vertex2']]
        result = Edge(vertex1, vertex2)
        result.attr = data['attr']
        mapping[data['id']] = result
        return result

    def get_other_vertex(self, vertex: Vertex) -> Vertex:
        """
        Given one of the two vertices the edge connects to, return the
        second one.

        :param vertex: One of the two vertices the edge connects to.
        :return: The second vertex this edge connects to.
        """
        if vertex == self.vertex1:
            return self.vertex2
        elif vertex == self.vertex2:
            return self.vertex1
        else:
            raise ValueError


class Face(GraphElement):
    """
    Represents a face inside a graph.
    """

    def __init__(self, vertices: MutableSet[Vertex], edges: MutableSet[Edge]):
        super().__init__()
        self._vertices: MutableSet[Vertex] = vertices
        self._edges: MutableSet[Vertex] = edges

    def matches(self, graph_element):
        if not isinstance(graph_element, Face):
            return False
        return super().matches(graph_element)

    def add_to(self, graph: 'Graph'):
        graph.faces.append(self)

    def delete_from(self, graph: 'Graph'):
        graph.faces.remove(self)

    def neighbours(self):
        return list(self._vertices) + list(self._edges)


class Graph(MutableSet):
    """
    Represents a graph made out of vertices, edges and faces.

    Saves lists of all elements contained inside the graph.
    """

    def __init__(self, graph: 'Graph' = None,
                 vertices: Iterable[Vertex] = None,
                 edges: Iterable[Edge] = None,
                 faces: Iterable[Face] = None,
                 elements: Iterable[GraphElement] = None):
        """
        Initialises the graph, can take no arguments, a graph, all three
        of vertices, edges and faces or a list of elements. No other
        combination is allowed.

        :param graph:
        :param vertices:
        :param edges:
        :param faces:
        :param elements:
        """
        if graph is not None:
            if vertices is not None or edges is not None or faces is not None or elements is not None:
                raise TypeError()
            self.vertices = list(graph.vertices)
            self.edges = list(graph.edges)
            self.faces = list(graph.faces)
        elif vertices is not None and edges is not None and faces is not None:
            if elements is not None:
                raise TypeError()
            self.vertices = list(vertices)
            self.edges = list(edges)
            self.faces = list(faces)
        elif vertices is not None or edges is not None or faces is not None:
            raise TypeError()
        elif elements is not None:
            self.vertices: MutableSequence[Vertex] = []
            self.edges: MutableSequence[Edge] = []
            self.faces: MutableSequence[Face] = []
            for element in elements:
                self.add(element)
        else:
            self.vertices: MutableSequence[Vertex] = []
            self.edges: MutableSequence[Edge] = []
            self.faces: MutableSequence[Face] = []

    def __iter__(self):
        return self.AllElemIter(self)

    def __contains__(self, item: GraphElement):
        return self.vertices.__contains__(item) or self.edges.__contains__(
            item) or self.faces.__contains__(item)

    def __len__(self):
        return len(self.vertices) + len(self.edges) + len(self.faces)

    # noinspection PyDefaultArgument
    def __deepcopy__(self, memodict={}, mapping=None):
        """
        Return a deep copy of the graph with all connections still
        remaining.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memodict[id(self)] = result
        for key, value in self.__dict__.items():
            if key not in ('vertices', 'edges', 'faces'):
                # noinspection PyArgumentList
                setattr(result, key, copy.deepcopy(value, memodict))
        result.vertices = [x.recursive_copy(mapping) for x in self.vertices]
        result.edges = [x.recursive_copy(mapping) for x in self.edges]
        result.faces = [copy.deepcopy(x, memodict) for x in self.faces]
        return result

    def add(self, element: GraphElement):
        element.add_to(self)

    def discard(self, element: GraphElement):
        element.delete_from(self)

    def add_elements(self, elements: Iterable[GraphElement]) -> None:
        """
        Add a collection of elements to the graph.

        :param elements: The elements to be added to the graph.
        """
        for element in elements:
            self.add(element)

    def element_list(self, order: str = 'connected') -> Sequence[GraphElement]:
        """
        A list of the elements of the graph in order of the all element
        iterator.

        Possible values for `order` are:

        * `'connected'`: The order is such that first all vertices and
                         edges are returned in a manner that always
                         leads to a single connected graph. Afterwards
                         the faces, if any, are returned.
        * `'vef'`: First return all vertices, then all edges, then all
                   faces.

        :param order: A string specifying the order of element.
                      Possible are: connected, vef
        """
        if order == 'connected':
            element_list = []
            for element in self:
                element_list.append(element)
            return element_list
        elif order == 'vef':
            return list(itertools.chain(self.vertices, self.edges, self.faces))
        else:
            raise ValueError

    def get_by_id(self, object_id: int) -> GraphElement:
        """
        Return the GraphElement whose object ID is passed as argument.

        If no corresponding GraphElement can be found a KeyError is
        raised.

        :param object_id: The id of the GraphElement object you want to
                          retrieve.
        :return: The requested GraphElement
        """
        for vertex in self.vertices:
            if object_id == id(vertex):
                return vertex
        for edge in self.edges:
            if object_id == id(edge):
                return edge
        for face in self.faces:
            if object_id == id(face):
                return face

    def neighbours(self) -> Iterable[GraphElement]:
        """
        Return a list of elements connected to this graph, but not part
        of this graph.

        This function only makes sens on subgraphs, where it will return
        all elements of the host graph which are connected to but not
        part of the subgraph. For a completed graph it will return an
        empty list.

        :return: A list of elements connected to this graph, but not
                 part of it.
        """
        neighbours = set()
        for element in itertools.chain(self.vertices, self.edges, self.faces):
            candidates = element.neighbours()
            for candidate in candidates:
                if candidate not in self:
                    neighbours.add(candidate)
        return neighbours

    def match(self, other_graph: 'Graph') -> \
            Sized and Iterable[Tuple['Graph', Dict[GraphElement, GraphElement]]]:
        """
        Find all possible matches of the other graph in this graph.

        These matches are partial isomorphism from the other graph to
        this graph from a graph theoretical point of view.

        :param other_graph: The graph to match against this graph.
        :return: A list of all possible matches, empty of there are
                 none.
        """
        log.debug(f'Matching {self} against {other_graph}.')
        matches = []
        other_elements = other_graph.element_list()
        start_element = other_elements[0]
        for own_element in self:
            if own_element.matches(start_element):
                log.debug('Found a matching start element for %r with %r',
                          start_element, own_element)
                matches.extend(
                    self.match_at(own_element, other_elements))
        log.debug(f'Found {len(matches)} matches: {matches}.')
        return matches

    def match_at(self, start: GraphElement, target_elements: Sequence) -> \
            Sized and Iterable[Tuple['Graph', Dict[GraphElement, GraphElement]]]:
        """
        Try to find a match for the graph defined by the list of target
        elements at the specific starting element of this graph.

        :param start: The starting element of this graph.
        :param target_elements: The elements of the graph that is to be
                                matched in such an order that it always
                                builds into a connected graph.
        :return: The matching subgraphs if any exist, an empty list
                 otherwise.
        """
        problems: Sized and Iterable[
            Tuple[Graph, int, Dict[GraphElement, GraphElement]]] = \
            [(Graph(elements=[start]), 1, {target_elements[0]: start})]
        solutions = []
        while len(problems) > 0:
            subgraph, index, matching = problems.pop()
            if index == len(target_elements):
                solutions.append((subgraph, matching))
                break
            candidates = subgraph.neighbours()
            target = target_elements[index]
            for candidate in candidates:
                if candidate.matches(target):
                    new_subgraph = Graph(subgraph)
                    new_subgraph.add(candidate)
                    new_matching = matching.copy()
                    new_matching[target] = candidate
                    problems.append((new_subgraph, index + 1, new_matching))
        return solutions

    def is_isomorph(self, other_graph: 'Graph') -> bool:
        """
        Test if the other graph is isomorph in relation to this graph.

        :param other_graph: The graph to test against.
        :return: True if the two graphs are isomorph, False otherwise.
        """
        if len(self.vertices) != len(other_graph.vertices) \
                or len(self.edges) != len(other_graph.edges) \
                or len(self.faces) != len(other_graph.faces):
            return False
        return len(self.match(other_graph)) > 0

    def to_yaml(self):
        """
        Serialize the graph into a list or dict which can be exported
        into a yaml string.

        :return: A list or dict representing the graph fit for yaml
                 export.
        """
        vertices = [x.to_yaml() for x in self.vertices]
        edges = [x.to_yaml() for x in self.edges]
        fields = {
            'vertices': vertices,
            'edges': edges,
            'id': id(self),
        }
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}) -> 'Graph':
        """
        Deserialize a graph from a list or dict which was saved in a
        yaml file.

        The mapping argument does not need to be specified, it will be
        filled automatically unless you have a specific requirement.

        :param data: The list or dict containing the graph data.
        :param mapping: A dictionary which will be used to recreate
                        references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Graph()
        for vertex_data in data['vertices']:
            result.add(Vertex.from_yaml(vertex_data, mapping))
        for edge_data in data['edges']:
            result.add(Edge.from_yaml(edge_data, mapping))
        mapping[data['id']] = result
        return result

    class AllElemIter:
        """
        Iterates over all elements of a graph in a order such that
        except for the first element all other elements are connected to
        at least one element that came before them.
        """

        def __init__(self, graph: 'Graph'):
            self._marked: MutableSequence[GraphElement] = []
            self._unchecked_vertices = list(graph.vertices)
            self._unchecked_edges = list(graph.edges)
            self._unchecked_faces = list(graph.faces)
            self._graph: 'Graph' = graph

        def __iter__(self):
            return self

        def __next__(self):
            if len(self._marked) == 0:
                element = self._get_first_element()
            else:
                element = self._get_connecting_element()
            self._marked.append(element)
            return element

        def _get_first_element(self):
            """
            Return a graph element to be the first returned by the iteration.

            The logic is to first return a vertex, if there are no vertices,
            return an edge and if there are no edges then return a face.

            If there are no elements in the graph, raise a StopIteration
            exception.

            :return: The graph element from which the iteration will begin.
            :rtype: GraphElement
            """
            if len(self._graph.vertices) > 0:
                return self._graph.vertices[0]
            elif len(self._graph.edges) > 0:
                return self._graph.edges[0]
            elif len(self._graph.edges) > 0:
                return self._graph.faces[0]
            else:
                raise StopIteration

        def _get_connecting_element(self):
            """
            Return a element of the graph that has not yet been part of the
            iteration and is connected to at least one element that has been.

            If there are no more elements to return, raise a StopIteration
            exception.

            :return: A graph element connected to at least one preceding
            element.
            :rtype: GraphElement
            """
            # connecting_element = None
            for element in reversed(self._marked):
                if isinstance(element, Edge):
                    if element.vertex1 not in self._marked \
                            and element.vertex1 is not None:
                        self._unchecked_vertices.remove(element.vertex1)
                        return element.vertex1
                    elif element.vertex2 not in self._marked \
                            and element.vertex2 is not None:
                        self._unchecked_vertices.remove(element.vertex2)
                        return element.vertex2
                    else:
                        continue
                elif isinstance(element, Vertex):
                    for edge in element.edges:
                        if edge not in self._marked:
                            self._unchecked_edges.remove(edge)
                            return edge
                    continue
            raise StopIteration
