import abc
from typing import List, Dict, Any, AnyStr


class GraphElement(abc.ABC):
    """
    Base class from which all elements of a graph derive.

    It contains basic functionality that all graph elements share, such as a
    list of attributes.
    """
    def __init__(self):
        self.attr: Dict[AnyStr, Any] = {}

    @abc.abstractmethod
    def matches(self, graph_element):
        """

        :param graph_element: The graph element to test for matching
        attributes.
        :return: True if the attributes of the two elements are matching.
        """
        shared_attrs = [attr_key for attr_key in self.attr.keys()
                        if attr_key in graph_element.attr.keys()]
        for attr_key in shared_attrs:
            if self.attr[attr_key] != graph_element.attr[attr_key]:
                return False
        return True


class Vertex(GraphElement):
    """
    Represents a vertex inside a graph.
    """
    def __init__(self):
        super().__init__()

    def matches(self, graph_element):
        if isinstance(graph_element, Vertex):
            return False
        super().matches(graph_element)


class Edge(GraphElement):
    """
    Represents an edge inside a graph.
    """
    def __init__(self, vertex1: Vertex, vertex2: Vertex):
        super().__init__()
        self.vertex1: Vertex = vertex1
        self.vertex2: Vertex = vertex2

    def matches(self, graph_element):
        if isinstance(graph_element, Edge):
            return False
        super().matches(graph_element)

class Face(GraphElement):
    """
    Represents a face inside a graph.
    """
    def __init__(self, vertices: List[Vertex], edges: List[Edge]):
        super().__init__()
        self._vertices: List[Vertex] = vertices
        self._edges: List[Vertex] = edges

    def matches(self, graph_element):
        if isinstance(graph_element, Face):
            return False
        super().matches(graph_element)

class Graph:
    """
    Represents a graph made out of vertices, edges and faces.

    Saves lists of all elements contained inside the graph.
    """
    def __init__(self):
        self.vertices: List[Vertex] = []
        self.edges: List[Edge] = []
        self.faces: List[Face] = []

    def __iter__(self):
        return self.AllElemIter(self)

    class AllElemIter:
        """
        Iterates over all elements of a graph in a order such that except for
        the first element all other elements are connected to at least one
        element that came before them.
        """
        def __init__(self, graph: Graph):
            self._marked: List[GraphElement] = []
            self._unchecked_vertices = list(graph.vertices)
            self._unchecked_edges = list(graph.edges)
            self._unchecked_faces = list(graph.faces)
            self._graph: Graph = graph

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
                #TODO: Find a nicer pattern to solve this problem.
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
