from typing import List, Dict, Any, AnyStr


class GraphElement:
    """
    Base class from which all elements of a graph derive.

    It contains basic functionality that all graph elements share, such as a
    list of attributes.
    """
    def __init__(self):
        self.attr: Dict[AnyStr, Any] = {}


class Vertex(GraphElement):
    """
    Represents a vertex inside a graph.
    """
    def __init__(self):
        super().__init__()


class Edge(GraphElement):
    """
    Represents an edge inside a graph.
    """
    def __init__(self, vertex1: Vertex, vertex2: Vertex):
        super().__init__()
        self._vertex1: Vertex = vertex1
        self._vertex2: Vertex = vertex2


class Face(GraphElement):
    """
    Represents a face inside a graph.
    """
    def __init__(self, vertices: List[Vertex], edges: List[Edge]):
        super().__init__()
        self._vertices: List[Vertex] = vertices
        self._edges: List[Vertex] = edges


class Graph:
    """
    Represents a graph made out of vertices, edges and faces.

    Saves lists of all elements contained inside the graph.
    """
    def __init__(self):
        self.vertices: List[Vertex] = []
        self.edges: List[Edge] = []
        self.faces: List[Face] = []


