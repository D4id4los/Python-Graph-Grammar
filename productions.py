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

    def to_yaml(self) -> Iterable:
        """
        Return a dict or list giving a representation of the mapping fit for export with yaml.

        In this case this means use object ids rather than objects themselves.

        :return: A representation of a Match in list or dict.
        """
        fields = {}
        fields['dict'] = {id(k): id(v) for k, v in self.items()}
        fields['id'] = id(self)
        return fields

    @staticmethod
    def from_yaml(data, mapping = {}) -> 'Mapping':
        """
        Deserialize a Mapping from a list or dict which was saved in a yaml file.

        The mapping argument does not need to be specified, it will be filled automatically unless
        you have a specific requirement.

        :param data: The list or dict containing the Mapping data.
        :param mapping: A dictionary which will be used to recreate references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Mapping()
        for key, value in data['dict'].items():
            result[mapping[key]] = mapping[value]
        mapping[data['id']] = result
        return result


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

    def to_yaml(self) -> Iterable:
        """
        Return a list or dict representing the DaughterMapping which can be exported to yaml.

        :return: A list or dict representing the DaughterMapping.
        """
        fields = {}
        fields['mother_graph'] = id(self.mother_graph)
        fields['mapping'] = self.mapping.to_yaml()
        fields['daughter_graph'] = self.daughter_graph.to_yaml()
        fields['weight'] = self.weight
        fields['id'] = id(self)
        return fields

    @staticmethod
    def from_yaml(data, mapping = {}) -> 'DaughterMapping':
        """
        Deserialize a DaughterMapping from a list or dict which was saved in a yaml file.

        The mapping argument does not need to be specified, it will be filled automatically unless
        you have a specific requirement.

        :param data: The list or dict containing the DaughterMapping data.
        :param mapping: A dictionary which will be used to recreate references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        mother_graph = mapping[data['mother_graph']]
        daughter_graph = Graph.from_yaml(data['daughter_graph'], mapping)
        mother_to_daughter_map = Mapping.from_yaml(data['mapping'], mapping)
        weight = data['weight']
        result = DaughterMapping(mother_graph, mother_to_daughter_map, daughter_graph, weight)
        mapping[data['id']] = result
        return result


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
        self.mother_graph: Graph = mother_graph
        self.mappings: Sized and Iterable[DaughterMapping] = mappings
        self.total_weight = 0
        for mapping in self.mappings:
            self.total_weight += mapping.weight

    def match(self, host_graph: Graph) -> Iterable[Tuple[Graph, Dict[GraphElement, GraphElement]]]:
        """
        Tries to match the production against a target Graph.

        :param host_graph: The host graph against which the production is matched.
        :return: All possible matching subgraphs of the target graph.
        """
        matches = []
        mother_elements = self.mother_graph.element_list()
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

        def get_daughtercopy_to_result(map_host_to_result, mother_to_host, mother_to_daughter, copy_to_daughterID, daughter_graph):
            def map_daughtercopy_to_host(x):
                try:
                    daughter_id = copy_to_daughterID[x]
                    daughter_element = daughter_graph.get_by_id(daughter_id)
                    mother_element = mother_to_daughter.inverse[daughter_element][0]
                    host_element = mother_to_host[mother_element]
                    result_element = map_host_to_result[id(host_element)]
                    return result_element
                except KeyError:
                    return None
            return map_daughtercopy_to_host

        map_hostID_to_result = {}
        result_graph = copy.deepcopy(host_graph, map_hostID_to_result)
        daughter_mapping = self._select_mapping()
        daughter_graph = daughter_mapping.daughter_graph
        map_mother_to_daughter = daughter_mapping.mapping
        map_daughterID_to_copy = {}
        daughter_copy = copy.deepcopy(daughter_graph, map_daughterID_to_copy)
        map_copy_to_daughterID = {value: key for key, value in map_daughterID_to_copy.items() if
                                  isinstance(value, GraphElement)}
        daughtercopy_to_result = get_daughtercopy_to_result(map_hostID_to_result,
                                                        map_mother_to_host,
                                                        map_mother_to_daughter,
                                                        map_copy_to_daughterID,
                                                        daughter_graph)
        for element in daughter_mapping.to_remove:
            result_graph.remove(map_hostID_to_result[id(map_mother_to_host[element])])
        for element in daughter_mapping.to_change:
            orig_element = map_hostID_to_result[id(map_mother_to_host[element])]
            for name, value in map_mother_to_daughter[element].attr.items():
                orig_element.attr[name] = value
        for element in daughter_mapping.to_add:
            new_element = map_daughterID_to_copy[id(element)]
            new_element.replace_connection(daughtercopy_to_result)
            result_graph.add(new_element)
        return result_graph

    def _select_mapping(self) -> DaughterMapping:
        """
        Randomly select a mapping and daughter graph from the list of possible mappings.

        :return: A tuple containing the mapping between mother and daughter graphs and the corresponding daughter graph.
        """
        rand_num = random.randint(0, len(self.mappings) - 1)
        index = 0
        lower_bound = 0
        while True:
            if lower_bound <= rand_num < lower_bound + self.mappings[index].weight:
                return self.mappings[index]
            else:
                lower_bound += self.mappings[index].weight
                index += 1

    def to_yaml(self) -> Iterable:
        """
        Serialize the Production into a list or dict which can be exported into yaml.

        :return: A list or dict representing the Production.
        """
        fields = {}
        fields['mother_graph'] = self.mother_graph.to_yaml()
        fields['mappings'] = [x.to_yaml() for x in self.mappings]
        fields['id'] = id(self)
        return fields

    @staticmethod
    def from_yaml(data, mapping={}) -> 'Production':
        """
        Deserialize a Production from a list or dict which was saved in a yaml file.

        The mapping argument does not need to be specified, it will be filled automatically unless
        you have a specific requirement.

        :param data: The list or dict containing the Production data.
        :param mapping: A dictionary which will be used to recreate references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        mother_graph = Graph.from_yaml(data['mother_graph'], mapping)
        mappings = [DaughterMapping.from_yaml(x, mapping) for x in data['mappings']]
        result = Production(mother_graph, mappings)
        mapping[data['id']] = result
        return result
