from typing import Iterable
from graph import *


class Mapping:
    """
    Maps the elements of one graph to the elements of another graph.

    This mapping can be empty, if there is no correspondence of elements or
    it can be a bijection.
    """

    def __init__(self):
        self.mapping: Iterable[None | GraphElement, GraphElement] = {}


class Production:
    """
    A Production mapping one graph onto another graph.

    Each production consists of two graphs, the left-hand side and the
    right-hand side, and a mapping between these two graphs.
    G1 ---Mapping--> G2

    When applying a production the left-hand graph is matched against a target
    graph. If a match is found then the right-hand graph is glued into the
    source graph according to the matching defined in the production.
    """

    def __init__(self, mother_graph: Graph, daughter_mappings: Iterable[Iterable[Mapping, Graph, int]]):
        self._mother_graph: Graph = mother_graph
        self._daughter_mappings: Iterable[Iterable[Mapping, Graph, int]] = daughter_mappings

    def match(self, host_graph: Graph):
        """
        Tries to match the production against a target Graph.

        :param host_graph: The host graph against which the production is matched.
        :return: All possible matching subgraphs of the target graph.
        :rtype: List[Graph]
        """
        for mother_element in self._mother_graph:
            for host_element in host_graph:
                if host_element.matches(mother_element):
                    pass
        raise NotImplementedError

    def apply(self, host_graph: Graph, matching_subgraph: Graph):
        """
        Applies a production to a specific subgraph of the host graph and
        returns the result graph.

        :param host_graph: The graph to which the production is applied.
        :param matching_subgraph: The specific subgraph of the host graph
        to which the production will be applied.
        :return: The graph resulting from applying the production.
        :rtype: Graph
        """
        raise NotImplementedError
