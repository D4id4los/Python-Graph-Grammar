import random
import scipy.stats
import numpy
from math import pi, asin, atan, isnan, isinf
from functools import partial, singledispatch
from typing import Iterable, Sized, Union, Tuple, Sequence, Dict, List, Any

from model_gen.utils import Mapping, get_logger
from model_gen.graph import Graph, GraphElement, Vertex, Edge, \
    get_max_generation, graph_is_consistent, copy_without_meta_elements, \
    get_min_max_points, get_positions, get_position, non_recursive_copy
from model_gen.exceptions import ModelGenArgumentError, \
    ModelGenIncongruentGraphStateError
from model_gen.geometry import Vec, angle, norm, perp_right, perp_left, \
    cross, rotate, normalize

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
        self.host_to_result: Mapping = Mapping()
        self.result_graph: Graph = non_recursive_copy(host_graph,
                                                      self.host_to_result)
        self.host_graph: Graph = host_graph
        self.mother_to_host: Mapping = mother_to_host
        self.mother_graph: Graph = production_option.mother_graph
        self.mother_to_daughter: Mapping = production_option.mapping
        self.daughter_graph: Graph = production_option.daughter_graph
        self.daughter_to_copy: Mapping = Mapping()
        self.copy_graph: Graph = non_recursive_copy(self.daughter_graph,
                                                    self.daughter_to_copy)
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
                 daughter_graph: Graph, weight: int = 1,
                 attr_requirements: Dict[GraphElement,
                                         Dict[str, GraphElement]]=None,
                 conditions: Dict[str, str]=None,
                 var_calc_instructions=None):
        self.mapping = mapping
        self.daughter_graph = daughter_graph
        self.mother_graph = mother_graph
        self.weight = weight
        if attr_requirements is None:
            attr_requirements = {}
        self.attr_requirements: Dict[
            GraphElement, Dict[str, GraphElement]] = attr_requirements
        if conditions is None:
            conditions = {}
        self.conditions: Dict[str, str] = conditions
        if var_calc_instructions is None:
            var_calc_instructions = []
        self.var_calc_instructions = var_calc_instructions

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
        self.var_per_run = []
        self.var_per_application = []
        for name, instruction, eval_strategy in self.var_calc_instructions:
            compiled_instr = compile(instruction, '<stdin>', 'eval')
            if eval_strategy == 'run':
                self.var_per_run.append((name, compiled_instr))
            elif eval_strategy == 'application':
                self.var_per_application.append((name, compiled_instr))
            else:
                raise ValueError('Incorrect evaluation strategy specified.')
        self.vars = {}

    def to_yaml(self) -> Iterable:
        """
        Return a list or dict representing the DaughterMapping which
        can be exported to yaml.

        :return: A list or dict representing the DaughterMapping.
        """
        attr_requirements = {}
        for daughter_element, requirements in self.attr_requirements.items():
            if daughter_element == 'all':
                attr_requirements['all'] = {
                    name: id(mother_element)
                    for name, mother_element in requirements.items()
                }
                continue
            attr_requirements[id(daughter_element)] = {
                name: id(mother_element)
                for name, mother_element in requirements.items()
            }
        fields = {
            'id': id(self),
            'mother_graph': id(self.mother_graph),
            'weight': self.weight,
            'conditions': self.conditions,
            'daughter_graph': self.daughter_graph.to_yaml(),
            'mapping': self.mapping.to_yaml(),
            'attr_requirements': attr_requirements,
            'var_calc_instructions': self.var_calc_instructions,
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
        var_calc_instructions = data.get('var_calc_instructions', [])
        result = ProductionOption(mother_graph, mother_to_daughter_map,
                                  daughter_graph, weight,
                                  var_calc_instructions=var_calc_instructions)
        if 'attr_requirements' in data:
            attr_requirements = {}
            for daughter_element, requirements in data['attr_requirements'].items():
                if daughter_element=='all':
                    key = 'all'
                else:
                    key = mapping[daughter_element]
                attr_requirements[key] = {
                    name: mapping[mother_element]
                    for name, mother_element in requirements.items()
                }
            result.attr_requirements = attr_requirements
        if 'conditions' in data:
            result.conditions = data['conditions']
        mapping[data['id']] = result
        return result


def evaluate_per_run_vars(prod_opt: ProductionOption, variables: Dict=None
                          ) -> Dict[str, Any]:
    """
    Evaluates all precompiled variables which are to be calculated
    once per run.

    :param prod_opt: The production option to evaluate the variables for.
    :param variables: Variables to set during evaluation.
    :return: A dictionary of variable and value pairs for all variables.
    """
    result = {}
    if variables is None:
        variables = {}
    for name, compiled_expr in prod_opt.var_per_run:
        result[name] = eval(compiled_expr, None, variables)
    return result


def evaluate_per_app_vars(prod_opt: ProductionOption, variables: Dict=None
                          ) -> Dict[str, Any]:
    """
    Evaluate and return a dictionary of variables defined in the production
    option to be calculated with every application of the production.

    :param prod_opt: The production option to evaluate variables for.
    :param variables: Variables to set during evaluation.
    :return: A dictionary of variable and value pairs.
    """
    result = {}
    if variables is None:
        variables = {}
    for name, compiled_expr in prod_opt.var_per_application:
        result[name] = eval(compiled_expr, None, variables)
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
                 production_options: List[ProductionOption],
                 vectors: Dict[str, Union[Vertex, Tuple[Vertex, Vertex]]]=None,
                 priority: int=0,
                 conditions: Dict[str, str]=None):
        self.mother_graph: Graph = mother_graph
        self.production_options: List[ProductionOption] = production_options
        if vectors is None:
            vectors = {}
        self.vectors: \
            Dict[str, Union[Vertex, Tuple[Vertex, Vertex]]] \
            = vectors
        self.priority = priority
        self.total_weight = 0
        if conditions is None:
            conditions = {}
        self.conditions = conditions
        for mapping in self.production_options:
            self.total_weight += mapping.weight
        self.mother_elem_sorted_by_x = sorted(
            mother_graph.vertices,
            key=lambda vertex: float(vertex.attr['x'])
        )
        self.mother_elem_sorted_by_y = sorted(
            mother_graph.vertices,
            key=lambda vertex: float(vertex.attr['y'])
        )
        self.global_vars: Dict[str, Any] = {}

    def match(self, host_graph: Graph) \
            -> Iterable[Mapping]:
        """
        Tries to match the production against a target Graph.

        :param host_graph: The host graph against which the
                           production is matched.
        :return: All possible matching subgraphs of the target graph.
        """
        if ('.geometric_ordering' in self.conditions
                and eval(self.conditions['.geometric_ordering'])):
            return host_graph.match(self.mother_graph, eval_attrs=True,
                                    geometric_order=(
                                        self.mother_elem_sorted_by_x,
                                        self.mother_elem_sorted_by_y
                                    ))
        return host_graph.match(self.mother_graph, eval_attrs=True,
                                eval_vars=self.global_vars)

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
        vectors = {}
        for vec_name, vec_info in self.vectors.items():
            if isinstance(vec_info, Vertex):
                vectors[vec_name] = Vec(hierarchy.map(vec_info, 'M', 'H'))
            else:
                vectors[vec_name] = Vec(hierarchy.map(vec_info[0], 'M', 'H'),
                                        hierarchy.map(vec_info[1], 'M', 'H'))
        global_attr_reqs = {name: hierarchy.map(value, 'M', 'H')
                            for name, value
                            in option.attr_requirements.get('all', {}).items()}
        local_eval_vars = {**global_attr_reqs, **vectors}
        variables = evaluate_per_app_vars(option, local_eval_vars)
        variables.update(option.vars)
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
            if (isinstance(C_element, Vertex)
                    # and ( 'new_x' not in C_element.attr
                    #       or 'new_y' not in C_element.attr)
                    # and '.new_pos' not in C_element.attr
            ):
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
                    # for name, value in kwargs.items():
                    #     locals()[name] = value
                    eval_vars = {**kwargs, **global_attr_reqs, 'old': old}
                    return eval(attr_func_text, None, eval_vars)

                if attr_name == '.new_pos':
                    pos = attr_func(old_element, self_=target_element,
                                    **attr_requirements,
                                    **vectors, **variables)
                    # v1 = vectors["v1"]
                    # v2 = vectors["v2"]
                    # log.debug(f'   d={cross(v1, v2)}')
                    # log.debug(f'   angle={angle(v1, v2)}')
                    # log.debug(f'   chose {"left" if (cross(v1,v2) < 0 if angle(v1,v2) > pi/2 else cross(v1,v2) > 0) else "right"}')
                    target_element.attr['x'] = pos.x
                    target_element.attr['y'] = pos.y
                    if '.new_pos' in target_element.attr:
                        target_element.attr.pop('.new_pos')
                    continue
                elif (attr_name.startswith('.')
                      and not attr_name.startswith('.svg_')
                      and not attr_name.startswith('.svgx_')):
                    continue
                target_element.attr[attr_name] = attr_func(old_element,
                                                           self_=target_element,
                                                           **attr_requirements,
                                                           **vectors,
                                                           **variables)

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
        for mapping in self.production_options:
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
            'mappings': [x.to_yaml() for x in self.production_options],
            'vectors': {k: id(v) if isinstance(v, GraphElement)
                        else (id(v[0]), id(v[1]))
                        for k,v in self.vectors.items()},
            'conditions': self.conditions,
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
        if 'conditions' in data:
            result.conditions = data['conditions']
        if 'priority' in data:
            result.priority = int(data['priority'])
        mapping[data['id']] = result
        return result


def _calculate_new_position(new_element, option, hierarchy) -> (float, float):
    """
    Calculate the position of a newly added element dependend on the
    barycenter of all mapped daughter elements.

    :param new_element: The element whose new position is to be
        calculated.
    :param option: The matched production option.
    :param hierarchy: The production application hierarchy of this
        application of the production option.
    :return:
    """
    daughter_barycenter = _calculate_daughter_barycenter(option)
    mother_positions = get_positions(option.mother_graph.vertices)
    mother_barycenter = _calculate_barycenter(mother_positions)
    mother_deviations = numpy.std(mother_positions, 0)
    host_barycenter = _calculate_host_barycenter(option, hierarchy)
    daughter_vertices = option.daughter_graph.vertices
    daughter_positions = get_positions(daughter_vertices)
    daughter_deviations = numpy.std(daughter_positions, 0)
    if mother_deviations[0] == 0:
        mother_angle = pi/2
    else:
        mother_verticality = mother_deviations[1] / mother_deviations[0]
        if mother_verticality > 2:
            mother_slope, _ = _get_gradient(
                [(y, x) for x, y in mother_positions]
            )
            if mother_slope == 0:
                mother_slope = float('inf')
            else:
                mother_slope = 1 / mother_slope
                mother_slope = normalize(Vec(x1=1, y1=mother_slope)).y
        else:
            mother_slope, _ = _get_gradient(mother_positions)
            mother_slope = normalize(Vec(x1=1, y1=mother_slope)).y
        if isinf(mother_slope):
            mother_angle = pi / 2
        else:
            mother_angle = numpy.arcsin(mother_slope)
    if daughter_deviations[0] == 0:
        daughter_angle = pi/2
    else:
        daughter_verticality = daughter_deviations[1] / daughter_deviations[0]
        if daughter_verticality > 2:
            daughter_slope, _ = _get_gradient(
                [(y, x) for x,y in daughter_positions]
            )
            if daughter_slope == 0:
                daughter_slope = float('inf')
            else:
                daughter_slope = 1 / daughter_slope
                daughter_slope = normalize(Vec(x1=1, y1=daughter_slope)).y
        else:
            daughter_slope, _ = _get_gradient(daughter_positions)
            daughter_slope = normalize(Vec(x1=1, y1=daughter_slope)).y
        if isinf(daughter_slope):
            daughter_angle = pi/2
        else:
            daughter_angle = numpy.arcsin(daughter_slope)
    host_vertices = hierarchy.map_sequence(option.mother_graph.vertices,
                                           'M', 'H')
    host_positions = get_positions(host_vertices)
    host_deviations = numpy.std(host_positions, 0)
    if host_deviations[0] == 0:
        host_angle = pi/2
    else:
        host_verticality = host_deviations[1] / host_deviations[0]
        if host_verticality > 2:
            host_slope, _ = _get_gradient(
                [(y, x) for x, y in host_positions]
            )
            if host_slope == 0:
                host_slope = float('inf')
            else:
                host_slope = 1 / host_slope
                host_slope = normalize(Vec(x1=1, y1=host_slope)).y
        else:
            host_slope, _ = _get_gradient(host_positions)
            host_slope = normalize(Vec(x1=1, y1=host_slope)).y
        if isinf(host_slope):
            host_angle = pi/2
        else:
            host_angle = numpy.arcsin(host_slope)
    delta_angle = host_angle - mother_angle
    x,y = get_position(new_element)
    if delta_angle != 0:
        new_pos = rotate(Vec(x1=x, y1=y), delta_angle,
                         Vec(x1=daughter_barycenter[0], y1=daughter_barycenter[1]))
        daughter_rot_vecs = [
            rotate(Vec(x1=x, y1=y),
                   delta_angle,
                   Vec(x1=daughter_barycenter[0], y1=daughter_barycenter[1]))
            for x,y in daughter_positions
        ]
        daughter_rot_positions = [(vec.x,vec.y) for vec in daughter_rot_vecs]
        mother_rot_vecs = [
            rotate(Vec(x1=x, y1=y),
                   delta_angle,
                   Vec(x1=mother_barycenter[0], y1=mother_barycenter[1]))
            for x, y in mother_positions
        ]
        mother_rot_positions = [(vec.x, vec.y) for vec in mother_rot_vecs]
    else:
        daughter_rot_positions = daughter_positions
        mother_rot_positions = mother_positions
        new_pos = Vec(x1=x, y1=y)
    log.debug(f'   Angles (in x*pi): H.a.: {host_angle / pi}, M.a.: {mother_angle / pi}, D.a.: {daughter_angle / pi}, delta angle: '
              f'{delta_angle}. new position: {new_pos}.')

    mother_extent = _calculate_extent(mother_positions)
    daughter_extent = _calculate_extent(daughter_positions)
    mother_rot_extent = _calculate_extent(mother_rot_positions)
    daughter_rot_extent = _calculate_extent(daughter_rot_positions)
    host_extent = _calculate_extent(host_positions)
    x_ratio = 1
    y_ratio = 1
    if not daughter_rot_extent[0] == 0:
        x_mother_to_daughter = (mother_rot_extent[0] / daughter_rot_extent[0])
        if x_mother_to_daughter == 0:
            x_mother_to_daughter = 1
        if host_extent[0] != 0:
            x_ratio = (host_extent[0] / daughter_rot_extent[0]) / x_mother_to_daughter
    if not daughter_rot_extent[1] == 0:
        y_mother_to_daughter = (mother_rot_extent[1] / daughter_rot_extent[1])
        if y_mother_to_daughter == 0:
            y_mother_to_daughter = 1
        if host_extent[1] != 0:
            y_ratio = (host_extent[1] / daughter_rot_extent[1]) / y_mother_to_daughter
    dx = new_pos.x - daughter_barycenter[0]
    dy = new_pos.y - daughter_barycenter[1]
    new_x = host_barycenter[0] + dx * x_ratio
    new_y = host_barycenter[1] + dy * y_ratio
    log.debug(f'   Position Calculation: H.B.: {host_barycenter}, M.B.: {mother_barycenter}, D.B.: {daughter_barycenter}.')
    log.debug(f'   Extents: H.E.: {host_extent}, M.E.: {mother_extent}, D.E.: {daughter_extent}.')
    log.debug(f'   Rotated Extents: H.E.: {host_extent}, M.E.: {mother_rot_extent}, D.E.: {daughter_rot_extent}.')
    log.debug(f'   Old position: {(x, y)}, delta: {(dx, dy)},'
              f' ratios: {(x_ratio, y_ratio)},'
              f' new position: {(new_x, new_y)}.')
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
    mapped_daughter_elems = option.mapping.values()
    if len(mapped_daughter_elems) == 0:
        return _calculate_barycenter(
            get_positions(option.daughter_graph.vertices)
        )
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


def _calculate_barycenter(positions: Iterable[Tuple[float, float]]
                          ) -> Tuple[float, float]:
    """
    Calculate the barycenter of the positions passed to the function.

    :param positions: A list of positions to calculate the barycenter
        of.
    :return: A tuple containing the x- and y-coordinates of the
        barycenter.
    """
    x = 0
    y = 0
    num = 0
    for position in positions:
        x += position[0]
        y += position[1]
        num += 1
    if num != 0:
        x /= num
        y /= num
    return x, y


def _calculate_extent(positions: Iterable[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Return the length between the most extreme points on the x- and
    y-axis of all elements in the list.

    :param positions: List of graph elements.
    :return: A tuple with the maximum extent along the x- and y-axis.
    """
    min, max = get_min_max_points(positions)
    x_extent = max[0] - min[0]
    y_extent = max[1] - min[1]
    return x_extent, y_extent


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
            host_x = float(host_element.attr['x'])
            host_y = float(host_element.attr['y'])
            x += host_x
            y += host_y
            log.debug(f'      Host vertex at position {(host_x, host_y)}.')
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
                host_x = float(host_element.attr['x'])
                host_y = float(host_element.attr['y'])
                x += host_x
                y += host_y
                log.debug(f'      Host vertex at position {(host_x, host_y)}.')
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
                    log.debug(f'      Host vertex2 position: '
                              f'{(host_x, host_y)} {host_vertex2}.')
                    num_elements += 1
                    x += host_x
                    y += host_y
    x /= num_elements
    y /= num_elements
    return x, y


def _get_gradient(positions: List[Tuple[float, float]]) -> Tuple[float, float]:
    """
    Return slope and intercept of the gradient of a list of graph elements.

    :param elements: A list of graph elements.
    :return: A tuple containing slope and intercept of the gradient of the
        elements.
    """
    if len(positions) < 3:
        arguments = ([x[0] for x in positions], [x[1] for x in positions])
    else:
        arguments = (positions,)
    slope, intercept, _, _, _ = scipy.stats.linregress(*arguments)
    return slope, intercept





@copy_without_meta_elements.register(Production)
def _(production: Production, mapping: Mapping=None) -> Production:
    if mapping is None:
        mapping = Mapping()
    new_mother_graph = copy_without_meta_elements(production.mother_graph,
                                                  mapping)
    new_production_options = []
    for prod_opt in production.production_options:
        new_daughter_graph = copy_without_meta_elements(
            prod_opt.daughter_graph, mapping
        )
        old_mapping = prod_opt.mapping
        new_mapping = Mapping()
        for old_mother_elem, old_daughter_elem in old_mapping.items():
            new_mother_elem = mapping[old_mother_elem]
            new_daughter_elem = mapping[old_daughter_elem]
            new_mapping[new_mother_elem] = new_daughter_elem
        new_attr_reqs = {mapping[d_elem]: {name: mapping[m_elem]
                                           for name, m_elem in reqs.items()}
                         for d_elem, reqs
                         in prod_opt.attr_requirements.items()
                         if d_elem != 'all'
                         }
        new_attr_reqs['all'] = {name: mapping[m_elem] for name, m_elem in
                                prod_opt.attr_requirements.get('all', {}).items()}
        new_production_option = ProductionOption(
            new_mother_graph,
            new_mapping,
            new_daughter_graph,
            weight=prod_opt.weight,
            attr_requirements=new_attr_reqs,
            conditions=prod_opt.conditions,
            var_calc_instructions=prod_opt.var_calc_instructions
        )
        new_production_options.append(new_production_option)
    new_vectors = {}
    for vec_name, vec_info in production.vectors.items():
        new_vec_info = None
        if isinstance(vec_info, Vertex):
            new_vec_info = mapping[vec_info]
        else:
            new_vec_info = (mapping[vec_info[0]], mapping[vec_info[1]])
        new_vectors[vec_name] = new_vec_info
    new_production = Production(
        new_mother_graph,
        new_production_options,
        priority=production.priority,
        vectors=new_vectors,
        conditions=production.conditions
    )
    return new_production
