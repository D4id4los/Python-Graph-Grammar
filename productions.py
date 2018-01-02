from graph import *


class Mapping:
    """
    Maps the elements of one graph to the elements of another graph.

    This mapping can be empty, if there is no correspondence of elements or
    it can be a bijection.
    """

    def __init__(self):
        self._mapping: Dict[GraphElement, GraphElement] = {}


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

    def __init__(self, left_graph: Graph, right_graph: Graph,
                 mapping: Mapping):
        self._left_graph: Graph = left_graph
        self._right_graph: Graph = right_graph
        self._mapping: Mapping = mapping

    def match(self, target_graph: Graph):
        """
        Tries to match the production against a target Graph.

        :return: All possible matching subgraphs of the target graph.
        :rtype: List[Graph]
        """
        raise NotImplementedError

    def apply(self, target_graph: Graph, matching_subgraph: Graph):
        """
        Applies a production to a specific subgraph of the target graph and
        returns the result graph.

        :param target_graph: The graph to which the production is applied.
        :param matching_subgraph: The specific subgraph of the target graph
        to which the production will be applied.
        :return: The graph resulting from applying the production.
        :rtype: Graph
        """
        raise NotImplementedError
