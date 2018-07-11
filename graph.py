import abc
import itertools
from typing import MutableSet, Dict, Any, AnyStr, Sequence, Iterable, MutableSequence, Sized


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

        In this test the graph_element is considered to be the mother graph, or left-hand-side, of a production. This
        means that all attributes of the graph_element must also be present and matching in this element for the
        function to return true.

        :param graph_element: The graph element to test for matching
        attributes.
        :return: True if the attributes of the two elements are matching.
        """
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


class Vertex(GraphElement):
    """
    Represents a vertex inside a graph.
    """

    def __init__(self):
        super().__init__()
        self.edges: MutableSet = set()

    def matches(self, graph_element):
        if not isinstance(graph_element, Vertex):
            return False
        return super().matches(graph_element)

    def add_to(self, graph: 'Graph'):
        graph.vertices.append(self)

    def delete_from(self, graph: 'Graph'):
        graph.vertices.remove(self)

    def neighbours(self):
        return self.edges


class Edge(GraphElement):
    """
    Represents an edge inside a graph.
    """

    def __init__(self, vertex1: Vertex, vertex2: Vertex):
        super().__init__()
        self.vertex1: Vertex = vertex1
        self.vertex2: Vertex = vertex2

    def matches(self, graph_element):
        if not isinstance(graph_element, Edge):
            return False
        return super().matches(graph_element)

    def add_to(self, graph: 'Graph'):
        graph.edges.append(self)
        for vertex in (self.vertex1, self.vertex2):
            vertex.edges.add(self)

    def delete_from(self, graph: 'Graph'):
        graph.edges.remove(self)
        for vertex in (self.vertex1, self.vertex2):
            vertex.edges.remove(self)

    def neighbours(self):
        return [self.vertex1, self.vertex2]


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

    def __init__(self, graph: 'Graph' = None, vertices: Iterable[Vertex] = None, edges: Iterable[Edge] = None,
                 faces: Iterable[Face] = None, elements: Iterable[GraphElement] = None):
        """
        Initialises the graph, can take no arguments, a graph, all three of vertices, edges and faces or a list of
        elements. No other combination is allowed.

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
        return self.vertices.__contains__(item) or self.edges.__contains__(item) or self.faces.__contains__(item)

    def __len__(self):
        return len(self.vertices) + len(self.edges) + len(self.faces)

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

    def element_list(self) -> Sequence[GraphElement]:
        """
        A list of the elements of the graph in order of the all element iterator.

        The order is such that first all vertices and edges are returned in a manner that always leads to a single
        connected graph. Afterwards the faces, if any, are returned.
        """
        element_list = []
        for element in self:
            element_list.append(element)
        return element_list

    def neighbours(self) -> Iterable[GraphElement]:
        """
        Return a list of elements connected to this graph, but not part of this graph.

        This function only makes sens on subgraphs, where it will return all elements of the host graph which are
        connected to but not part of the subgraph. For a completed graph it will return an empty list.

        :return: A list of elements connected to this graph, but not part of it.
        """
        neighbours = set()
        for element in itertools.chain(self.vertices, self.edges, self.faces):
            candidates = element.neighbours()
            for candidate in candidates:
                if candidate not in self:
                    neighbours.add(candidate)
        return neighbours

    def match_at(self, start: GraphElement, target_elements: Sequence) -> Iterable['Graph']:
        """
        Try to find a match for the graph defined by the list of target elements at the specific starting element of
        this graph.

        :param start: The starting element of this graph.
        :param target_elements: The elements of the graph that is to be matched in such an order that it always builds into a connected graph.
        :return: The matching subgraphs if any exist, an empty list otherwise.
        """
        problems = [(Graph(elements=[start]), 1)]
        solutions = []
        while len(problems) > 0:
            subgraph, index = problems.pop()
            if index == len(target_elements):
                solutions.append(subgraph)
                break
            candidates = subgraph.neighbours()
            target = target_elements[index + 1]
            for candidate in candidates:
                if candidate.matches(target):
                    new_subgraph = Graph(subgraph)
                    new_subgraph.add(candidate)
                    problems.append((new_subgraph, index + 1))
        return solutions

    class AllElemIter:
        """
        Iterates over all elements of a graph in a order such that except for
        the first element all other elements are connected to at least one
        element that came before them.
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
            element = None
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
            connecting_element = None
            if len(self._unchecked_vertices) + len(self._unchecked_edges) == 0:
                connecting_element = self._unchecked_faces.pop()
            else:
                last_element = self._marked[-1]
                # TODO: Find a nicer pattern to solve this problem.
                if isinstance(last_element, Edge):
                    if not last_element.vertex1 in self._marked:
                        self._unchecked_vertices.remove(last_element.vertex1)
                        return last_element.vertex1
                    elif not last_element.vertex2 in self._marked:
                        self._unchecked_vertices.remove(last_element.vertex2)
                        return last_element.vertex2
                else:
                    for edge in self._unchecked_edges:
                        if edge.vertex1 in self._marked or edge.vertex2 in self._marked:
                            self._unchecked_edges.remove(edge)
                            return edge
                    raise StopIteration
