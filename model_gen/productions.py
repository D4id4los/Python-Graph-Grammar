import random
from functools import partial
from typing import Iterable, Sized, Union, Tuple, Sequence, Dict

from model_gen.utils import Mapping, get_logger
from model_gen.graph import Graph, GraphElement, Vertex, Edge, \
    get_max_generation, graph_is_consistent
from model_gen.exceptions import ModelGenArgumentError, \
    ModelGenIncongruentGraphStateError
from model_gen.geometry import Vec, angle, norm, perp_right, perp_left, \
    cross

log = get_logger('model_gen.' + __name__)


class ProductionApplicationHierarchy:
    """
    This class serves as a tool to save the hierarchy of the five
    different graphs involved in applying a production and the
    mapping between them.

    The graphs necessary to apply a Production are:
    - Result Graph (R) :: A copy of the Host Graph.
    - Host Graph (H) :: The full graph a production is applied to.
    - Mother Graph (M) :: The left-hand-side of the production.
    - Daughter Graph (D) :: The right-hand-side of the production.
    - Daughter Copy (C) :: A copy of the daughter graph.

    They are connected as follows:
    R <-> H <-> M <-> D <-> C

    With the details on the relationships:
    R <-1-to-1-copy-> H <-Partial-Isomorphism-> M <-Manual-Mapping---
    ---> D <-1-to-1-copy-> C
    """

    def __init__(self,
                 host_graph: Graph,
                 mother_to_host: Mapping,
                 production_option: 'ProductionOption',
                 ) -> None:
        self.host_to_result = Mapping()
        self.result_graph = host_graph.__deepcopy__(
            mapping=self.host_to_result)
        self.host_graph = host_graph
        self.mother_to_host = mother_to_host
        self.mother_graph = production_option.mother_graph
        self.mother_to_daughter = production_option.mapping
        self.daughter_graph = production_option.daughter_graph
        self.daughter_to_copy = Mapping()
        self.copy_graph = self.daughter_graph.__deepcopy__(
            mapping=self.daughter_to_copy)
        self.hierarchy_alias = {
            'R': 0,
            'H': 1,
            'M': 2,
            'D': 3,
            'C': 4
        }
        self.movements = {
            0: {
                'up': self.host_to_result.inverse,
                'down': None,
            },
            1: {
                'up': self.mother_to_host.inverse,
                'down': self.host_to_result
            },
            2: {
                'up': self.mother_to_daughter,
                'down': self.mother_to_host
            },
            3: {
                'up': self.daughter_to_copy,
                'down': self.mother_to_daughter.inverse
            },
            4: {
                'up': None,
                'down': self.daughter_to_copy.inverse
            }
        }

    def map_sequence(self,
                     elements: Sequence[GraphElement],
                     source_levels: Union[Sequence[Union[int, str]], str],
                     target_levels: Union[Sequence[Union[int, str]], str]) \
            -> Tuple[Union[GraphElement, None]]:
        """
        Translates a sequence of elements to from one level of the
        hierarchy to another.

        :param elements: Sequence of the GraphElements to be mapped.
        :param source_levels: The levels the GraphElements are on.
        :param target_levels: The levels the GraphElements should be
            mapped to.
        :return: A Sequence where all GraphElement are mapped to
            their respective target graph.
        """
        if isinstance(source_levels, str) and isinstance(target_levels, str):
            source_levels = [source_levels] * len(elements)
            target_levels = [target_levels] * len(elements)
        elif len(elements) != len(source_levels) \
                or len(source_levels) != len(target_levels):
            raise ModelGenArgumentError
        result = ()
        for index in range(0, len(elements)):
            element = self.map(elements[index],
                               source_levels[index],
                               target_levels[index])
            result += (element,)
        return result

    def map(self, element: GraphElement, source_level: Union[int, str],
            target_level: Union[int, str]) -> Union[GraphElement, None]:
        """
        Translates an element from one graph in the hierarchy to another.

        If no such mapping exists None is returned.

        :param element: The GraphElement to map to a different Graph.
        :param source_level: The level from where the Element is from.
        :param target_level: The level where the Element shall be mapped to.
        :return: The corresponding GraphElement in the target Graph.
        """
        if not isinstance(source_level, int):
            source_level = self.hierarchy_alias[source_level]
        if not isinstance(target_level, int):
            target_level = self.hierarchy_alias[target_level]
        if target_level < 0 or target_level > 4:
            log.error(f'Error trying to map an Element to a nonexistent level'
                      f' {target_level} in the hierarchy.')
            raise ModelGenArgumentError
        if source_level < 0 or source_level > 4:
            log.error(f'Error: The source level is set to {source_level}, '
                      f'outside the bound for the hierarchy. The function has '
                      f'entered an incongruous state; Aborting.')
            raise ModelGenArgumentError
        if source_level == target_level:
            return element
        if source_level < target_level:
            action = 'up'
            new_source_level = source_level + 1
        else:
            action = 'down'
            new_source_level = source_level - 1
        try:
            result = self.movements[source_level][action][element]
        except KeyError:
            return None
        return self.map(result, new_source_level, target_level)


class ProductionOption:
    """
    Saves a daughter graph and all information about the mapping
    from the mother graph to the daughter graph.
    """

    def __init__(self, mother_graph: Graph, mapping: Mapping,
                 daughter_graph: Graph, weight: int = 1):
        self.mapping = mapping
        self.daughter_graph = daughter_graph
        self.mother_graph = mother_graph
        self.weight = weight
        self.attr_requirements: Dict[
            GraphElement, Dict[str, GraphElement]] = {}
        self.conditions: Dict[str, str] = {}

        mother_elements = mother_graph.element_list('vef')
        daughter_elements = daughter_graph.element_list('vef')
        self.to_remove = []
        self.to_change = []
        self.edge_conn_to_remove = []
        for element in mother_elements:
            if element in mapping:
                D_element = mapping[element]
                self.to_change.append(D_element)
                if not isinstance(element, Edge):
                    continue
                for vertex in element.neighbours():
                    if (vertex in mapping
                            and mapping[vertex] not in D_element.neighbours()):
                        self.edge_conn_to_remove.append(
                            (element, vertex)
                        )
            else:
                self.to_remove.append(element)
        self.to_add = [element for element in daughter_elements if
                       element not in mapping.inverse]

    def to_yaml(self) -> Iterable:
        """
        Return a list or dict representing the DaughterMapping which
        can be exported to yaml.

        :return: A list or dict representing the DaughterMapping.
        """
        attr_requirements = {}
        for daughter_element, requirements in self.attr_requirements.items():
            attr_requirements[id(daughter_element)] = {
                name: id(mother_element)
                for name, mother_element in requirements.items()
            }
        fields = {
            'mother_graph': id(self.mother_graph),
            'mapping': self.mapping.to_yaml(),
            'daughter_graph': self.daughter_graph.to_yaml(),
            'weight': self.weight,
            'attr_requirements': attr_requirements,
            'conditions': self.conditions,
            'id': id(self),
        }
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}) -> 'ProductionOption':
        """
        Deserialize a DaughterMapping from a list or dict which was
        saved in a yaml file.

        The mapping argument does not need to be specified, it will
        be filled automatically unless you have a specific requirement.

        :param data: The list or dict containing the DaughterMapping data.
        :param mapping: A dictionary which will be used to recreate
            references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        mother_graph = mapping[data['mother_graph']]
        daughter_graph = Graph.from_yaml(data['daughter_graph'], mapping) \
            if 'daughter_graph' in data else Graph()
        mother_to_daughter_map = Mapping.from_yaml(data['mapping'], mapping) \
            if 'mapping' in data else Mapping()
        weight = data['weight'] if 'weight' in data else 1
        result = ProductionOption(mother_graph, mother_to_daughter_map,
                                  daughter_graph, weight)
        if 'attr_requirements' in data:
            attr_requirements = {}
            for daughter_element, requirements in data[
                'attr_requirements'].items():
                attr_requirements[mapping[daughter_element]] = {
                    name: mapping[mother_element]
                    for name, mother_element in requirements.items()
                }
            result.attr_requirements = attr_requirements
        if 'conditions' in data:
            result.conditions = data['conditions']
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
        self.vectors: \
            Dict[str, Union[Vertex, Tuple[Vertex, Vertex]]] \
            = {}
        self.total_weight = 0
        self.priority = 0
        for mapping in self.mappings:
            self.total_weight += mapping.weight

    def match(self, host_graph: Graph) \
            -> Iterable[Mapping]:
        """
        Tries to match the production against a target Graph.

        :param host_graph: The host graph against which the
                           production is matched.
        :return: All possible matching subgraphs of the target graph.
        """
        return host_graph.match(self.mother_graph, eval_attrs=True)

    def apply(self, host_graph: Graph,
              map_mother_to_host: Mapping) -> Graph:
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

        def map_elements_to_be_removed(element, source_level, target_level,
                                       to_be_removed):
            if element in to_be_removed:
                return hierarchy.map(element, source_level, target_level)
            else:
                return None

        log.debug(f'Applying {self} to graph {id(host_graph)}.')
        option = self.select_option()
        hierarchy = ProductionApplicationHierarchy(
            host_graph,
            map_mother_to_host,
            option
        )
        result_graph = hierarchy.result_graph
        to_add = {hierarchy.map(x, 'D', 'C') for x in option.to_add}
        to_change = {hierarchy.map(x, 'D', 'R') for x in option.to_change}
        to_remove = {hierarchy.map(x, 'M', 'R') for x in option.to_remove}
        to_calc_attr = {(x, hierarchy.map(x, 'D', 'C'), None) for x in
                        option.to_add}
        to_calc_attr = to_calc_attr.union({
            (x, hierarchy.map(x, 'D', 'R'), hierarchy.map(x, 'D', 'H'))
            for x in option.to_change})
        new_generation = get_max_generation(map_mother_to_host.values()) + 1
        # For edges which get reconnected to a different vertex in the daugter
        # graph, set the old connection to None in the result graph
        for M_edge, M_vertex in option.edge_conn_to_remove:
            R_edge = hierarchy.map(M_edge, 'M', 'R')
            R_vertex = hierarchy.map(M_vertex, 'M', 'R')
            R_edge.replace_connection(lambda x: None if x == R_vertex else x,
                                      True)
            R_vertex.edges.remove(R_edge)
        # First remove the now unnecessary Elements, this will remove them
        # from any neighbourhood lists.
        for R_element in to_remove:
            D_edges_to_ignore = [hierarchy.map(e, 'M', 'R') for e, _ in option.edge_conn_to_remove]
            # D_edges_to_ignore = []
            result_graph.discard(R_element,
                                 set(hierarchy.map_sequence(
                                     D_edges_to_ignore, 'D', 'R')))
        # Second add the new elements, which can now have their references
        # contained entirely within the Graph and also add themselves to
        # any neighbourhood lists, if they border any pre-existing elements.
        for C_element in to_add:
            C_element.replace_connection(
                partial(hierarchy.map, source_level='C', target_level='R')
            )
            if isinstance(C_element, Vertex) and (
                    'new_x' not in C_element.attr
                    or 'new_y' not in C_element.attr):
                x, y = _calculate_new_position(C_element, option, hierarchy)
                if 'new_x' not in C_element.attr:
                    C_element.attr['x'] = x
                if 'new_y' not in C_element.attr:
                    C_element.attr['y'] = y
            C_element.attr['.generation'] = new_generation
            valid_inconsistencies = {x for x in C_element.neighbours()
                                     if x in to_add}
            result_graph.add(C_element, ignore_errors=valid_inconsistencies)
        # Then change the neighbourhood lists of any
        # elements that remained un-deleted. It is especially important to
        # make sure all elements are connected correctly
        for R_element in to_change:
            R_element.replace_connection(
                partial(map_elements_to_be_removed, source_level='R',
                        target_level='C', to_be_removed=to_remove)
            )
        # Now calculate the new attributes for all elements that where part of
        # the daughter graph.
        vectors = {}
        for vec_name, vec_info in self.vectors.items():
            if isinstance(vec_info, Vertex):
                vectors[vec_name] = Vec(hierarchy.map(vec_info, 'M', 'H'))
            else:
                vectors[vec_name] = Vec(hierarchy.map(vec_info[0], 'M', 'H'),
                                        hierarchy.map(vec_info[1], 'M', 'H'))
        for D_element, target_element, old_element in to_calc_attr:
            attr_requirements = {}
            if D_element in option.attr_requirements:
                attr_requirements = {
                    name: hierarchy.map(M_element, 'M', 'H')
                    for name, M_element in option.attr_requirements[D_element].items()
                }
            for attr_name, attr_func_text in D_element.attr.items():
                if attr_name in ('x', 'y'):
                    continue
                if attr_name == 'new_x':
                    attr_name = 'x'
                    target_element.attr.pop('new_x')
                elif attr_name == 'new_y':
                    attr_name = 'y'
                    target_element.attr.pop('new_y')

                def attr_func(old, **kwargs):
                    from math import acos, sqrt, pi
                    for name, value in kwargs.items():
                        locals()[name] = value
                    return eval(attr_func_text)

                if attr_name == '.new_pos':
                    from math import pi
                    pos = attr_func(old_element, **attr_requirements,
                                    **vectors)
                    v1 = vectors["v1"]
                    # v2 = vectors["v2"]
                    # log.debug(f'   d={cross(v1, v2)}')
                    # log.debug(f'   angle={angle(v1, v2)}')
                    # log.debug(f'   chose {"left" if (cross(v1,v2) < 0 if angle(v1,v2) > pi/2 else cross(v1,v2) > 0) else "right"}')
                    target_element.attr['x'] = pos.x
                    target_element.attr['y'] = pos.y
                    target_element.attr.pop('.new_pos')
                    continue
                elif attr_name.startswith('.'):
                    continue
                target_element.attr[attr_name] = attr_func(old_element,
                                                           **attr_requirements)

        log.debug(f'Applied {self} with result graph {id(result_graph)}.')
        if not graph_is_consistent(result_graph):
            raise ModelGenIncongruentGraphStateError
        return result_graph

    def select_option(self) -> ProductionOption:
        """
        Randomly select a mapping and daughter graph from the list of possible
        mappings.

        :return: A tuple containing the mapping between mother and daughter
                 graphs and the corresponding daughter graph.
        """
        rand_num = random.randint(0, self.total_weight-1)
        for mapping in self.mappings:
            if rand_num < mapping.weight:
                return mapping
            rand_num -= mapping.weight
        raise ValueError

    def to_yaml(self) -> Iterable:
        """
        Serialize the Production into a list or dict which can be
        exported into yaml.

        :return: A list or dict representing the Production.
        """
        fields = {
            'mother_graph': self.mother_graph.to_yaml(),
            'mappings': [x.to_yaml() for x in self.mappings],
            'vectors': {k: id(v) if isinstance(v, GraphElement)
                        else (id(v[0]), id(v[1]))
                        for k,v in self.vectors.items()},
            'priority': self.priority,
            'id': id(self)
        }
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}) -> 'Production':
        """
        Deserialize a Production from a list or dict which was saved
        in a yaml file.

        The mapping argument does not need to be specified, it will
        be filled automatically unless you have a specific requirement.

        :param data: The list or dict containing the Production data.
        :param mapping: A dictionary which will be used to recreate
            references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        mother_graph = Graph.from_yaml(data['mother_graph'], mapping)
        mappings = [ProductionOption.from_yaml(x, mapping) for x in
                    data['mappings']]
        result = Production(mother_graph, mappings)
        if 'vectors' in data:
            vectors = {}
            for k, v in data['vectors'].items():
                if isinstance(v, int):
                    vectors[k] = mapping[v]
                elif len(v) == 2:
                    vectors[k] = (mapping[v[0]], mapping[v[1]])
                else:
                    raise ValueError
            result.vectors = vectors
        if 'priority' in data:
            result.priority = int(data['priority'])
        mapping[data['id']] = result
        return result


def _calculate_new_position(new_element, option, hierarchy) -> (float, float):
    """
    Calculate the position of a newly added element dependend on the
    barycenter of all mapped daughter elements.

    :param new_element: The element hose new position is to be
        calculated.
    :param option: The matched production option.
    :param hierarchy: The production application hierarchy of this
        application of the production option.
    :return:
    """
    daughter_barycenter = _calculate_daughter_barycenter(option)
    host_barycenter = _calculate_host_barycenter(option, hierarchy)
    x = float(new_element.attr['x'])
    y = float(new_element.attr['y'])
    dx = x - daughter_barycenter[0]
    dy = y - daughter_barycenter[1]
    new_x = host_barycenter[0] + dx
    new_y = host_barycenter[1] + dy
    log.debug(f'   Position Calculation: D.B.: {daughter_barycenter}, H.B.: '
              f'{host_barycenter}, delta: {(dx, dy)}.')
    log.debug(f'   Old position: {(x, y)} new position: {(new_x, new_y)}.')
    return new_x, new_y


def _calculate_daughter_barycenter(option: ProductionOption) -> (float, float):
    """
    Calculate the barycenter of mapped elements in the daughter graph
    of a production option.

    :param option: The production option whose barycenter is to be
        calculated.
    :return: A tuple with the position of the barycenter.
    """
    num_elements = 0
    x = 0
    y = 0
    for daughter_element in option.mapping.values():
        if isinstance(daughter_element, Vertex):
            num_elements += 1
            x += float(daughter_element.attr['x'])
            y += float(daughter_element.attr['y'])
        elif isinstance(daughter_element, Edge):
            if daughter_element.vertex1 is not None:
                num_elements += 1
                x += float(daughter_element.vertex1.attr['x'])
                y += float(daughter_element.vertex1.attr['y'])
            if daughter_element.vertex2 is not None:
                num_elements += 1
                x += float(daughter_element.vertex2.attr['x'])
                y += float(daughter_element.vertex2.attr['y'])
    if num_elements == 0:
        return 0,0
    x /= num_elements
    y /= num_elements
    return x, y


def _calculate_host_barycenter(
        option: ProductionOption,
        hierarchy: ProductionApplicationHierarchy
) -> (float, float):
    """
    Calculate the barycenter of elements of a host graph which have
    been mapped to daughter elements by a match.

    :param option: The production option whose barycenter is to be
        calculated.
    :return: A tuple with the position of the barycenter.
    """
    num_elements = 0
    x = 0
    y = 0
    for daughter_element in option.mapping.values():
        host_element = hierarchy.map(daughter_element, 'D', 'H')
        if isinstance(host_element, Vertex):
            num_elements += 1
            x += float(host_element.attr['x'])
            y += float(host_element.attr['y'])
        elif isinstance(host_element, Edge):
            mother_element = hierarchy.map(daughter_element, 'D', 'M')
            if mother_element.vertex1 is not None:
                host_vertex1 = hierarchy.map(mother_element.vertex1, 'M', 'H')
                host_x = float(host_vertex1.attr["x"])
                host_y = float(host_vertex1.attr["y"])
                log.debug(f'      Host vertex1 position: '
                          f'{(host_x, host_y)} {host_vertex1}.')
                num_elements += 1
                x += host_x
                y += host_y
            if mother_element.vertex2 is not None:
                host_vertex2 = hierarchy.map(mother_element.vertex2, 'M', 'H')
                host_x = float(host_vertex2.attr["x"])
                host_y = float(host_vertex2.attr["y"])
                log.debug(f'      Host vertex2 position: '
                          f'{(host_x, host_y)} {host_vertex2}.')
                num_elements += 1
                x += host_x
                y += host_y
            #TODO: Handle the case without any vertices
    if num_elements == 0:
        for mother_element in option.mother_graph:
            host_element = hierarchy.map(mother_element, 'M', 'H')
            if isinstance(host_element, Vertex):
                num_elements += 1
                x += float(host_element.attr['x'])
                y += float(host_element.attr['y'])
            elif isinstance(host_element, Edge):
                if host_element.vertex1 is not None:
                    host_vertex1 = host_element.vertex1
                    host_x = float(host_vertex1.attr["x"])
                    host_y = float(host_vertex1.attr["y"])
                    log.debug(f'      Host vertex1 position: '
                              f'{(host_x, host_y)} {host_vertex1}.')
                    num_elements += 1
                    x += host_x
                    y += host_y
                if host_element.vertex2 is not None:
                    host_vertex2 = host_element.vertex2
                    host_x = float(host_vertex2.attr["x"])
                    host_y = float(host_vertex2.attr["y"])
                    log.debug(f'      Host vertex1 position: '
                              f'{(host_x, host_y)} {host_vertex2}.')
                    num_elements += 1
                    x += host_x
                    y += host_y
    x /= num_elements
    y /= num_elements
    return x, y
