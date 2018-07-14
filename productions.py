import random
import copy
from graph import *
from utils import Bidict


class Mapping(Bidict):
    """
    Maps the elements of one graph to the elements of another graph.

    This mapping can be empty, if there is no correspondence of elements or
    it can be a bijection.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class DaughterMapping():
    """
    Saves a daughter graph and all information about the mapping from the mother
    graph to the daughter graph.
    """

    def __init__(self, mother_graph: Graph, mapping: Mapping, daughter_graph: Graph, weight: int = 1):
        self.mapping = mapping
        self.daughter_graph = daughter_graph
        self.mother_graph = mother_graph
        self.weight = weight

        mother_elements = mother_graph.element_list('vef')
        daughter_elements = daughter_graph.element_list('vef')
        self.to_remove = []
        self.to_change = []
        for element in mother_elements:
            if element in mapping:
                self.to_change.append(element)
            else:
                self.to_remove.append(element)
        self.to_add = [element for element in daughter_elements if element not in mapping.inverse]


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

    def __init__(self, mother_graph: Graph, mappings: Sized and Iterable[DaughterMapping]):
        self._mother_graph: Graph = mother_graph
        self._mappings: Sized and Iterable[DaughterMapping] = mappings
        self._total_weight = 0
        for mapping in self._mappings:
            self._total_weight += mapping.weight

    def match(self, host_graph: Graph) -> Iterable[Tuple[Graph, Dict[GraphElement, GraphElement]]]:
        """
        Tries to match the production against a target Graph.

        :param host_graph: The host graph against which the production is matched.
        :return: All possible matching subgraphs of the target graph.
        """
        matches = []
        mother_elements = self._mother_graph.element_list()
        start_element = mother_elements[0]
        for host_element in host_graph:
            if host_element.matches(start_element):
                matches.extend(host_graph.match_at(host_element, mother_elements))
        return matches

    def apply(self, host_graph: Graph, map_mother_to_host: Dict[GraphElement, GraphElement]):
        """
        Applies a production to a specific subgraph of the host graph and
        returns the result graph.

        :param host_graph: The graph to which the production is applied.
        :param map_mother_to_host: The specific subgraph of the host graph
        to which the production will be applied.
        :return: The graph resulting from applying the production.
        :rtype: Graph
        """

        def get_daughtercopy_to_host(mother_to_host, mother_to_daughter, copy_to_daughterID, daughter_graph):
            def map_daughtercopy_to_host(x):
                try:
                    daughter_id = copy_to_daughterID[x]
                    daughter_element = daughter_graph.get_by_id(daughter_id)
                    mother_element = mother_to_daughter.inverse[daughter_element][0]
                    host_element = mother_to_host[mother_element]
                    return host_element
                except KeyError:
                    return None
            return map_daughtercopy_to_host

        result_graph = Graph(graph=host_graph)
        daughter_mapping = self._select_mapping()
        daughter_graph = daughter_mapping.daughter_graph
        map_mother_to_daughter = daughter_mapping.mapping
        map_daughterID_to_copy = {}
        daughter_copy = copy.deepcopy(daughter_graph, map_daughterID_to_copy)
        map_copy_to_daughterID = {value: key for key, value in map_daughterID_to_copy.items() if
                                  isinstance(value, GraphElement)}
        daughtercopy_to_host = get_daughtercopy_to_host(map_mother_to_host,
                                                        map_mother_to_daughter,
                                                        map_copy_to_daughterID,
                                                        daughter_graph)
        for element in daughter_mapping.to_remove:
            result_graph.remove(map_mother_to_host[element])
        for element in daughter_mapping.to_change:
            orig_element = map_mother_to_host[element]
            for name, value in element.attr.items():
                orig_element.attr[name] = value
        for element in daughter_mapping.to_add:
            new_element = map_daughterID_to_copy[id(element)]
            new_element.replace_connection(daughtercopy_to_host)
            result_graph.add(new_element)
        return result_graph

    def _select_mapping(self) -> DaughterMapping:
        """
        Randomly select a mapping and daughter graph from the list of possible mappings.

        :return: A tuple containing the mapping between mother and daughter graphs and the corresponding daughter graph.
        """
        rand_num = random.randint(0, len(self._mappings) - 1)
        index = 0
        lower_bound = 0
        while True:
            if lower_bound <= rand_num < lower_bound + self._mappings[index].weight:
                return self._mappings[index]
            else:
                lower_bound += self._mappings[index].weight
                index += 1
