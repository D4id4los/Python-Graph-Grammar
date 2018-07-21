import random
import copy
from functools import partial
from typing import Iterable, Sized, Tuple, Dict

from model_gen.utils import Bidict, get_logger
from model_gen.graph import Graph, GraphElement

log = get_logger('model_gen.' + __name__)


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
    def from_yaml(data, mapping={}) -> 'Mapping':
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


class ProductionOption():
    """
    Saves a daughter graph and all information about the mapping from the mother
    graph to the daughter graph.
    """

    def __init__(self, mother_graph: Graph, mapping: Mapping,
                 daughter_graph: Graph, weight: int = 1):
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
                neighbour_mapping = {}
                unmapped_neighbours_in_m = [x for x in element.neighbours() if
                                            x not in mapping]
                unmapped_neighbours_in_d = [x for x in
                                            mapping[element].neighbours() if
                                            x not in mapping.values()]
                if len(unmapped_neighbours_in_m) == 1 and \
                        len(unmapped_neighbours_in_d) == 1:
                    neighbour_mapping = {
                        unmapped_neighbours_in_m[0]:
                            unmapped_neighbours_in_d[0]}
                self.to_change.append((element, neighbour_mapping))
            else:
                self.to_remove.append(element)
        self.to_add = [element for element in daughter_elements if
                       element not in mapping.inverse]

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
    def from_yaml(data, mapping={}) -> 'ProductionOption':
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
        result = ProductionOption(mother_graph, mother_to_daughter_map,
                                  daughter_graph, weight)
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

    def __init__(self, mother_graph: Graph,
                 mappings: Sized and Iterable[ProductionOption]):
        self.mother_graph: Graph = mother_graph
        self.mappings: Sized and Iterable[ProductionOption] = mappings
        self.total_weight = 0
        for mapping in self.mappings:
            self.total_weight += mapping.weight

    def match(self, host_graph: Graph) -> Iterable[
        Tuple[Graph, Dict[GraphElement, GraphElement]]]:
        """
        Tries to match the production against a target Graph.

        :param host_graph: The host graph against which the production is matched.
        :return: All possible matching subgraphs of the target graph.
        """
        log.debug(f'Matching {self} against {host_graph}.')
        matches = []
        mother_elements = self.mother_graph.element_list()
        start_element = mother_elements[0]
        for host_element in host_graph:
            if host_element.matches(start_element):
                log.debug('Found a matching start element for %r with %r',
                          start_element, host_element)
                matches.extend(
                    host_graph.match_at(host_element, mother_elements))
        log.debug(f'Found {len(matches)} matches: {matches}.')
        return matches

    def apply(self, host_graph: Graph,
              map_mother_to_host: Dict[GraphElement, GraphElement]) -> Graph:
        """
        Applies a production to a specific subgraph of the host graph and
        returns the result graph.

        The relationship between the different graphs is as follows:
        `Result - Host - Mother - Daughter - Daughter Copy`
        Abbreviated as:
        `R - H - M - D - C`

        :param host_graph: The graph to which the production is applied.
        :param map_mother_to_host: The specific subgraph of the host graph
        to which the production will be applied.
        :return: The graph resulting from applying the production.
        """

        def get_M_to_R(map_M_to_H, map_H_to_R):
            def M_to_R(x):
                return map_H_to_R[map_M_to_H[x]]

            return M_to_R

        def get_C_to_R(map_M_to_H, map_H_to_R, map_M_to_D, map_D_to_C):
            def C_to_R(x):
                try:
                    return map_H_to_R[
                        map_M_to_H[map_M_to_D.inverse[map_D_to_C.inverse[x][0]][0]]]
                except KeyError:
                    return None

            return C_to_R

        def get_R_to_C(M_to_R, map_D_to_C):
            def R_to_C(x_neighbour_map, x):
                map = {M_to_R(m): map_D_to_C[d] for m, d in
                       x_neighbour_map.items()}
                if x in map:
                    return map[x]
                else:
                    return None

            return R_to_C

        log.debug(f'Applying {self} to {host_graph} according to '
                  f'{map_mother_to_host}.')
        map_M_to_H = map_mother_to_host
        map_H_to_R = Mapping()
        result_graph = host_graph.__deepcopy__(mapping=map_H_to_R)
        option = self._select_option()
        daughter_graph = option.daughter_graph
        map_M_to_D = option.mapping
        map_D_to_C = Mapping()
        daughter_copy = daughter_graph.__deepcopy__(mapping=map_D_to_C)
        M_to_R = get_M_to_R(map_M_to_H, map_H_to_R)
        C_to_R = get_C_to_R(map_M_to_H, map_H_to_R, map_M_to_D, map_D_to_C)
        R_to_C = get_R_to_C(M_to_R, map_D_to_C)
        for m_element in option.to_remove:
            result_graph.remove(M_to_R(m_element))
        for m_element, neighbour_mapping in option.to_change:
            r_element = M_to_R(m_element)
            for name, value in map_M_to_D[m_element].attr.items():
                r_element.attr[name] = value
            r_element.replace_connection(partial(R_to_C, neighbour_mapping))
        for d_element in option.to_add:
            new_element = map_D_to_C[d_element]
            new_element.replace_connection(C_to_R)
            result_graph.add(new_element)
        log.debug(f'Applied {self} with result {result_graph}.')
        return result_graph

    def _select_option(self) -> ProductionOption:
        """
        Randomly select a mapping and daughter graph from the list of possible
        mappings.

        :return: A tuple containing the mapping between mother and daughter
                 graphs and the corresponding daughter graph.
        """
        rand_num = random.randint(0, len(self.mappings) - 1)
        index = 0
        lower_bound = 0
        while True:
            if lower_bound <= rand_num < lower_bound + self.mappings[
                index].weight:
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
        mappings = [ProductionOption.from_yaml(x, mapping) for x in
                    data['mappings']]
        result = Production(mother_graph, mappings)
        mapping[data['id']] = result
        return result
