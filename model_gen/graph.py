import abc
import itertools
import copy
from typing import MutableSet, Dict, Any, AnyStr, Sequence, Iterable, List, Set
from typing import MutableSequence, Tuple, Callable, AbstractSet
from types import SimpleNamespace
from model_gen.exceptions import ModelGenArgumentError
from model_gen.exceptions import ModelGenIncongruentGraphStateError
from model_gen.utils import get_logger, Mapping

log = get_logger('model_gen.' + __name__)


class GraphElement(abc.ABC):
    """
    Base class from which all elements of a graph derive.

    It contains basic functionality that all graph elements share, such as a
    list of attributes.
    """

    def __init__(self):
        self.attr: Dict[AnyStr, Any] = {}

    @abc.abstractmethod
    def matches(self, graph_element, eval_attr=False) -> bool:
        """
        Test if the two graph elements match based on their attributes.

        In this test the graph_element is considered to be the mother graph, or
        left-hand-side, of a production. This means that all attributes of the
        graph_element must also be present and matching in this element for the
        function to return true.

        :param graph_element: The graph element to test for matching
            attributes.
        :param eval_attr: If true then the function will evaluate the
            attribute of the graph_element as a boolean expression
            rather than compare equality.
        :return: True if the attributes of the two elements are matching.
        """
        if not isinstance(graph_element, GraphElement):
            raise ModelGenArgumentError()
        try:
            for attr_key in graph_element.attr.keys():
                if attr_key in ('x', 'y'):
                    continue
                if eval_attr:
                    def matching_function(attr):
                        return eval(graph_element.attr[attr_key])
                    if not matching_function(self.attr[attr_key]):
                        return False
                else:
                    if self.attr[attr_key] != graph_element.attr[attr_key]:
                        return False
        except KeyError:
            return False
        return True

    @abc.abstractmethod
    def add_to(self, graph: 'Graph', ignore_errors: AbstractSet=None) -> None:
        """
        Add this element to the graph passed as argument.

        :param graph: The graph to add this element to.
        :param ignore_errors: An set of GraphElements who should be
            ignored when checking for errors.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_from(self, graph: 'Graph', ignore_errors: AbstractSet=None) \
            -> None:
        """
        Remove this element from the graph passed as argument.

        :param graph: The graph to remove this element from.
        :param ignore_errors: An set of GraphElements who should be
            ignored when checking for errors.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def neighbours(self) -> Iterable['GraphElement']:
        """
        Return all a list of all neighbouring elements of this element.

        :return: A list of all neighbouring elements.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']) -> None:
        """
        Replace all connected elements with results returned by replacement
        function.

        If the function returns None, no replacement is performed.

        :param get_replacement: The function deciding if and by what a
        GraphElement is to be replaced.
        """
        raise NotImplementedError()

    def to_yaml(self) -> Dict:
        """
        Serialize the GraphElement into a list or dict which can be used to
        create a yaml export.

        :return: A list or dict representing the GraphElement.
        """
        fields = {
            'attr': self.attr,
            'id': id(self)
        }

        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        """
        Create a GraphElement for the serialized list or dict from a yaml
        import.

        :return: A GraphElement corresponding to the list or dict.
        """
        raise NotImplementedError


class Vertex(GraphElement):
    """
    Represents a vertex inside a graph.
    """

    def __init__(self):
        super().__init__()
        self.edges: MutableSet['Edge'] = set()

    # noinspection PyDefaultArgument
    def __deepcopy__(self, memodict={}, mapping=None):
        """
        Return a deep copy of the Vertex where connecting edges are only
        present if they have a corresponding deepcopy in memodict.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memodict[id(self)] = result
        if mapping is not None:
            mapping[self] = result
        for key, value in self.__dict__.items():
            if key == 'edges':
                # Do not copy connected edges
                setattr(result, key, value)
            else:
                # noinspection PyArgumentList
                setattr(result, key, copy.deepcopy(value, memodict))
        return result

    # noinspection PyDefaultArgument
    def recursive_copy(self,
                       mapping: Dict['GraphElement', 'GraphElement'] = {}
                       ) -> 'Vertex':
        """
        Like deepcopy, but will also create copies for connected graph
        elements.

        :arg mapping: A dict mapping original elements to already
                      created copies of them.
        :return: A copy of this graph element
        """
        if self in mapping:
            # noinspection PyTypeChecker
            return mapping[self]
        cls = self.__class__
        result = cls.__new__(cls)
        mapping[self] = result
        for key, value in self.__dict__.items():
            if key == 'edges':
                new_edges = set()
                for old_edge in value:
                    new_edges.add(old_edge.recursive_copy(mapping))
                setattr(result, key, new_edges)
            else:
                setattr(result, key, copy.deepcopy(value))
        return result

    def matches(self, graph_element, eval_attr=False):
        if not isinstance(graph_element, GraphElement):
            raise ModelGenArgumentError()
        if not isinstance(graph_element, Vertex):
            return False
        return super().matches(graph_element, eval_attr)

    def add_to(self, graph: 'Graph', ignore_errors: AbstractSet=None):
        graph.vertices.append(self)
        for edge in self.edges:
            if edge not in graph.edges and edge not in ignore_errors:
                log.error('Error adding Vertex to Graph: Vertex references an'
                          ' Edge which does not exist inside the Graph.')
                raise ModelGenIncongruentGraphStateError
            if self not in edge.neighbours():
                if edge.vertex1 is None:
                    edge.vertex1 = self
                elif edge.vertex2 is None:
                    edge.vertex2 = self
                elif edge not in ignore_errors:
                    log.error('Error adding Vertex to Graph: Vertex references'
                              ' an Edge that does not reference the Vertex.')
                    raise ModelGenIncongruentGraphStateError

    def delete_from(self, graph: 'Graph', ignore_errors: AbstractSet=None):
        graph.vertices.remove(self)
        for edge in self.edges:
            if self in edge.neighbours():
                if edge.vertex1 == self:
                    edge.vertex1 = None
                if edge.vertex2 == self:
                    edge.vertex2 = None
            elif edge not in ignore_errors:
                log.error('Error deleting Vertex from Graph: Vertex referenced'
                          'an Edge that did not reference the Vertex.')
                raise ModelGenIncongruentGraphStateError

    def neighbours(self):
        return self.edges

    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']):
        to_add = []
        to_remove = []
        for edge in self.edges:
            result = get_replacement(edge)
            if result is not None and not isinstance(result, Edge):
                raise ValueError()
            if result is not None:
                to_add.append(result)
                to_remove.append(edge)
        for edge in to_remove:
            self.edges.remove(edge)
        for edge in to_add:
            self.edges.add(edge)

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Vertex()
        result.attr = data['attr']
        mapping[data['id']] = result
        return result


class Edge(GraphElement):
    """
    Represents an edge inside a graph.
    """

    def __init__(self, vertex1: Vertex = None, vertex2: Vertex = None):
        super().__init__()
        self.vertex1 = vertex1
        self.vertex2 = vertex2

    # noinspection PyDefaultArgument
    def __deepcopy__(self, memodict={}, mapping=None):
        """
        Return a deepcopy of the edge where the vertices are only present if
        they have a corresponding deepcopy in memodict.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memodict[id(self)] = result
        if mapping is not None:
            mapping[self] = result
        for key, value in self.__dict__.items():
            if key == 'vertex1' or key == 'vertex2':
                # Do not create copies of connected vertices
                setattr(result, key, value)
            else:
                # noinspection PyArgumentList
                setattr(result, key, copy.deepcopy(value, memodict))
        return result

    # noinspection PyDefaultArgument
    def recursive_copy(self,
                       mapping: Dict['GraphElement', 'GraphElement'] = {}
                       ) -> 'Edge':
        """
        Like deepcopy, but will also create copies for connected graph
        elements.

        :arg mapping: A dict mapping original elements to already created
                      copies of them.
        :return: A copy of this graph element
        """
        if self in mapping:
            # noinspection PyTypeChecker
            return mapping[self]
        cls = self.__class__
        result = cls.__new__(cls)
        mapping[self] = result
        for key, value in self.__dict__.items():
            if (key == 'vertex1' or key == 'vertex2') and value is not None:
                setattr(result, key, value.recursive_copy(mapping))
            else:
                setattr(result, key, copy.deepcopy(value))
        return result

    def matches(self, graph_element, eval_attr=False):
        if not isinstance(graph_element, GraphElement):
            raise ModelGenArgumentError
        if not isinstance(graph_element, Edge):
            return False
        return super().matches(graph_element, eval_attr)

    def add_to(self, graph: 'Graph', ignore_errors: AbstractSet=None):
        graph.edges.append(self)
        for vertex in self.get_neighbour_vertices():
            if vertex not in graph.vertices and vertex not in ignore_errors:
                log.error('Error adding Edge: The Edge references a Vertex '
                          'which is not part of the Graph I am adding the Edge'
                          'to.')
                raise ModelGenIncongruentGraphStateError
            if vertex is not None:
                vertex.edges.add(self)

    def delete_from(self, graph: 'Graph', ignore_errors: AbstractSet=None):
        graph.edges.remove(self)
        for vertex in (self.vertex1, self.vertex2):
            if vertex is not None and self in vertex.edges:
                vertex.edges.remove(self)
            elif vertex is not None and vertex not in ignore_errors:
                log.error('Error deleting Edge: The Edge references a Vertex'
                          ' which does not reference back to the Edge.')
                raise ModelGenIncongruentGraphStateError

    def get_neighbour_vertices(self) -> List[Vertex]:
        result = []
        if self.vertex1 is not None:
            result.append(self.vertex1)
        if self.vertex2 is not None:
            result.append(self.vertex2)
        return result

    def neighbours(self):
        return self.get_neighbour_vertices()

    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']):
        result = get_replacement(self.vertex1)
        if result is not None:
            if not isinstance(result, Vertex):
                raise ValueError()
            self.vertex1 = result
        result = get_replacement(self.vertex2)
        if result is not None:
            if not isinstance(result, Vertex):
                raise ValueError()
            self.vertex2 = result

    def to_yaml(self):
        fields = super().to_yaml()
        fields['vertex1'] = id(self.vertex1) if self.vertex1 is not None else None
        fields['vertex2'] = id(self.vertex2) if self.vertex2 is not None else None
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        if data['id'] in mapping:
            return mapping[data['id']]
        vertex1 = mapping[data['vertex1']] if data['vertex1'] is not None else None
        vertex2 = mapping[data['vertex2']] if data['vertex2'] is not None else None
        result = Edge(vertex1, vertex2)
        result.attr = data['attr']
        mapping[data['id']] = result
        return result

    def get_other_vertex(self, vertex: Vertex) -> Vertex:
        """
        Given one of the two vertices the edge connects to, return the
        second one.

        :param vertex: One of the two vertices the edge connects to.
        :return: The second vertex this edge connects to.
        """
        if vertex == self.vertex1:
            return self.vertex2
        elif vertex == self.vertex2:
            return self.vertex1
        else:
            raise ValueError


class Face(GraphElement):
    """
    Represents a face inside a graph.
    """

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}):
        pass

    def replace_connection(self,
                           get_replacement:
                           Callable[['GraphElement'], 'GraphElement']) -> None:
        pass

    def __init__(self, vertices: MutableSet[Vertex], edges: MutableSet[Edge]):
        super().__init__()
        self._vertices: MutableSet[Vertex] = vertices
        self._edges: MutableSet[Vertex] = edges

    def matches(self, graph_element):
        if not isinstance(graph_element, Face):
            return False
        return super().matches(graph_element)

    def add_to(self, graph: 'Graph', **kwargs):
        graph.faces.append(self)

    def delete_from(self, graph: 'Graph', **kwargs):
        graph.faces.remove(self)

    def neighbours(self):
        return list(self._vertices) + list(self._edges)


class Graph(MutableSet):
    """
    Represents a graph made out of vertices, edges and faces.

    Saves lists of all elements contained inside the graph.
    """

    def __init__(self, graph: 'Graph' = None,
                 vertices: Iterable[Vertex] = None,
                 edges: Iterable[Edge] = None,
                 faces: Iterable[Face] = None,
                 elements: Iterable[GraphElement] = None):
        """
        Initialises the graph, can take no arguments, a graph, all three
        of vertices, edges and faces or a list of elements. No other
        combination is allowed.

        :param graph:
        :param vertices:
        :param edges:
        :param faces:
        :param elements:
        """
        if graph is not None:
            if vertices is not None \
                    or edges is not None \
                    or faces is not None \
                    or elements is not None:
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
        return self.vertices.__contains__(item) or self.edges.__contains__(
            item) or self.faces.__contains__(item)

    def __len__(self):
        return len(self.vertices) + len(self.edges) + len(self.faces)

    # noinspection PyDefaultArgument
    def __deepcopy__(self, memodict={}, mapping={}):
        """
        Return a deep copy of the graph with all connections still
        remaining.
        """
        cls = self.__class__
        result = cls.__new__(cls)
        memodict[id(self)] = result
        for key, value in self.__dict__.items():
            if key not in ('vertices', 'edges', 'faces'):
                # noinspection PyArgumentList
                setattr(result, key, copy.deepcopy(value, memodict))
        result.vertices = [x.recursive_copy(mapping) for x in self.vertices]
        result.edges = [x.recursive_copy(mapping) for x in self.edges]
        result.faces = [copy.deepcopy(x) for x in self.faces]
        return result

    def add(self, element: GraphElement, ignore_errors: AbstractSet=None):
        element.add_to(self, ignore_errors)

    def discard(self, element: GraphElement, ignore_errors: AbstractSet=None):
        element.delete_from(self, ignore_errors)

    def add_elements(self, elements: Iterable[GraphElement]) -> None:
        """
        Add a collection of elements to the graph.

        :param elements: The elements to be added to the graph.
        """
        for element in elements:
            self.add(element)

    def element_list(self, order: str = 'connected') -> Sequence[GraphElement]:
        """
        A list of the elements of the graph in order of the all element
        iterator.

        Possible values for `order` are:

        * `'connected'`: The order is such that first all vertices and
                         edges are returned in a manner that always
                         leads to a single connected graph. Afterwards
                         the faces, if any, are returned.
        * `'vef'`: First return all vertices, then all edges, then all
                   faces.

        :param order: A string specifying the order of element.
                      Possible are: connected, vef
        """
        if order == 'connected':
            element_list = []
            for element in self:
                element_list.append(element)
            return element_list
        elif order == 'vef':
            return list(itertools.chain(self.vertices, self.edges, self.faces))
        else:
            raise ValueError

    def get_by_id(self, object_id: int) -> GraphElement:
        """
        Return the GraphElement whose object ID is passed as argument.

        If no corresponding GraphElement can be found a KeyError is
        raised.

        :param object_id: The id of the GraphElement object you want to
                          retrieve.
        :return: The requested GraphElement
        """
        for vertex in self.vertices:
            if object_id == id(vertex):
                return vertex
        for edge in self.edges:
            if object_id == id(edge):
                return edge
        for face in self.faces:
            if object_id == id(face):
                return face

    def neighbours(self) -> Iterable[GraphElement]:
        """
        Return a list of elements connected to this graph, but not part
        of this graph.

        This function only makes sens on subgraphs, where it will return
        all elements of the host graph which are connected to but not
        part of the subgraph. For a completed graph it will return an
        empty list.

        :return: A list of elements connected to this graph, but not
                 part of it.
        """
        neighbours = set()
        for element in itertools.chain(self.vertices, self.edges, self.faces):
            candidates = element.neighbours()
            for candidate in candidates:
                if candidate not in self:
                    neighbours.add(candidate)
        return neighbours

    def match3(self, other_graph: 'Graph', eval_attrs: bool=False
               ) -> List[Mapping]:
        """
        Find all possible matches of the other graph in this graph.

        These matches are partial isomorphism from the other graph to
        this graph from a graph theoretical point of view.

        :param other_graph: The graph to match against this graph.
        :param eval_attrs: If true then the attributes will be
            evaluated as boolean expression rather than testing for
            equality. Use for matching productions to host graphs.
        :return: A list of all possible matches, empty of there are
                 none.
        """
        all_other_elements = set(other_graph)
        not_seen_elements = all_other_elements
        log.debug(f'Matching graph {id(self):#x} against graph '
                  f'{id(other_graph):#x}.')
        tasks: List[Tuple[Mapping,Dict[GraphElement, GraphElement]]] = []
        start_other_element = None
        for other_element in other_graph:
            start_other_element = other_element
            break
        start_elements_left = {n: start_other_element for n
                               in start_other_element.neighbours()}
        start_it_map = {x for x in start_elements_left.keys()}
        start_it_map.add(start_other_element)
        for own_element in self:
            if own_element.matches(start_other_element, eval_attrs):
                tasks.append(
                    (Mapping({start_other_element: own_element}),
                     start_elements_left,
                     {start_other_element},
                     0, {0: start_it_map})
                )
        result = []
        while len(tasks) > 0:
            matches, elements_left, processed_elements, iteration, it_map = tasks.pop()
            iteration += 1
            new_it_map = dict(it_map)
            new_it_map[iteration] = set(elements_left.keys())
            processed_items = set()
            for d in it_map.values():
                processed_items = processed_items | {x for x in d}
            if len(matches) == len(other_graph) and len(elements_left) == 0:
                if len(matches) > len(self):
                    raise ValueError
                log.debug(f'Found match len {len(matches)} of graph len '
                          f'{len(self)} with graph len {len(other_graph)}.')
                result.append(matches)
                continue
            elif len(matches) == len(other_graph):
                raise ValueError
            other_neighbour, other_element = elements_left.popitem()
            if other_neighbour in matches:
                continue
            own_element = matches[other_element]
            new_elements_left = dict(elements_left)
            for new_other_neighbour in other_neighbour.neighbours():
                new_it_map[iteration].add(new_other_neighbour)
                if new_other_neighbour in processed_elements:
                    continue
                if new_other_neighbour in elements_left:
                    continue
                new_elements_left[new_other_neighbour] = other_neighbour
                new_it_map[iteration].add(new_other_neighbour)
            for own_neighbour in own_element.neighbours():
                if own_neighbour in matches.values():
                    continue
                if own_neighbour.matches(other_neighbour, eval_attrs):
                    new_matches = Mapping(matches)
                    new_matches[other_neighbour] = own_neighbour
                    new_processed_elements = set(processed_elements)
                    new_processed_elements.add(other_neighbour)
                    tasks.append((new_matches, new_elements_left, new_processed_elements, iteration, new_it_map))

        log.debug(f'Found {len(result)} matches.')
        return result

    def get_any_element(self) -> GraphElement:
        """
        Returns a single element from this graph.

        :return: A graph element
        """
        for element in self:
            return element

    def check_matching(self, matching: Mapping) -> bool:
        """
        Check if the mapping is internally consistent.

        This means that if two elements connected within the mother
        graph must also be connected in the matching.

        :param matching: The matching calculated by the match function.
        :return: True if the matching is valid and false otherwise
        """
        for mother_element, host_element in matching.items():
            for mother_neighbour in mother_element.neighbours():
                if matching[mother_neighbour] not in host_element.neighbours():
                    return False
        return True

    def matched_neighbours_compatible(self, matching: Mapping,
                                      own_element: GraphElement,
                                      other_element: GraphElement) -> bool:
        """
        Tests if the already matched neighbours of a mother element
        are compatable with a prospective new match.

        :param matching: A dict of the already matched elements.
        :param own_element: The host element to check.
        :param other_element: The mother element to check.
        :return:
        """
        for other_neighbour in other_element.neighbours():
            if other_neighbour in matching:
                if matching[other_neighbour] not in own_element.neighbours():
                    return False
        return True

    def match(self, other_graph: 'Graph', eval_attrs: bool=False) -> List[Mapping]:
        """
        Find all possible matches of the other graph in this graph.

        These matches are partial isomorphism from the other graph to
        this graph from a graph theoretical point of view.

        :param other_graph: The graph to match against this graph.
        :param eval_attrs: If true then the attributes will be
            evaluated as boolean expression rather than testing for
            equality. Use for matching productions to host graphs.
        :return: A list of all possible matches, empty of there are
                 none.
        """
        log.debug(f'Matching graph {id(self):#x} against graph '
                  f'{id(other_graph):#x}.')
        other_element = other_graph.get_any_element()
        task_list: List[Tuple] = []
        results: List[Mapping] = []
        """List of (Mapping, UnmappedElements[UnmappedElement: MappedConnectedElement])"""
        for own_element in self:
            if not own_element.matches(other_element, eval_attrs):
                continue
            mapping = Mapping({other_element: own_element})
            unmapped_elements = {e: other_element for e
                                 in other_element.neighbours()}
            debug = SimpleNamespace()
            debug.log = []
            debug.log.append(f'Mapped {other_element} to {own_element}.')
            debug.log.append(f'Unmapped elements found: '
                             f'{other_element.neighbours()} -> '
                             f'{other_element}.')
            task_list.append(
                (mapping, unmapped_elements, debug)
            )
        while len(task_list) > 0:
            mapping, unmapped_elements, debug = task_list.pop()
            if len(mapping) == len(other_graph) and len(unmapped_elements) == 0:
                if not self.check_matching(mapping):
                    raise ModelGenIncongruentGraphStateError
                if mapping not in results:
                    results.append(mapping)
                continue
            elif len(mapping) == len(other_graph):
                raise ValueError('Finished mapping, but unmapped_elements is '
                                 'not empty')
            elif len(unmapped_elements) == 0:
                raise ValueError('Did not finish mapping, but '
                                 'unmapped_elements is empty')
            other_element, other_element_parent = unmapped_elements.popitem()
            own_element_parent = mapping[other_element_parent]
            debug.log.append(f'Searching for mapping for {other_element}.')
            possible_new_mappings = []
            for own_element in own_element_parent.neighbours():
                debug.log.append(f'    Testing against {own_element}')
                if own_element in mapping.values():
                    debug.log.append(f'    {own_element} already in mapping.')
                    continue
                elif not own_element.matches(other_element, eval_attrs):
                    debug.log.append(f'    {own_element} does not match.')
                    continue
                elif not self.matched_neighbours_compatible(mapping,
                                                            own_element,
                                                            other_element):
                    debug.log.append(f'    {own_element}\' neighbours are '
                                     f'incompatible with current mapping.')
                    continue
                new_mapping = Mapping(mapping)
                new_mapping[other_element] = own_element
                possible_new_mappings.append(new_mapping)
                debug.log.append(f'    Found mapping from {other_element} -> '
                                 f'{own_element}.')
            if len(possible_new_mappings) == 0:
                debug.log.append('Found no possible matching; discarding this '
                                 'branch.')
                continue
            debug.log.append(f'Searching for new unmapped elements connected '
                             f'to {other_element}.')
            new_unmapped_elements = dict(unmapped_elements)
            for other_neighbour in other_element.neighbours():
                debug.log.append(f'    Testing element {other_neighbour}.')
                if other_neighbour in mapping:
                    debug.log.append(f'    {other_neighbour} already in '
                                     f'mapping.')
                    continue
                elif other_neighbour in unmapped_elements:
                    debug.log.append(f'    {other_neighbour} already in '
                                     f'unmapped_elements.')
                new_unmapped_elements[other_neighbour] = other_element
                debug.log.append(f'    Adding {other_neighbour} -> '
                                 f'{other_element} to unmapped_elements')
            debug.log.append('Adding to tasks to task list.')
            for new_mapping in possible_new_mappings:
                task_list.append((new_mapping,
                                  dict(new_unmapped_elements),
                                  debug))
        log.debug(f'Found {len(results)} matches.')
        return results


    def is_isomorph(self, other_graph: 'Graph') -> bool:
        """
        Test if the other graph is isomorph in relation to this graph.

        :param other_graph: The graph to test against.
        :return: True if the two graphs are isomorph, False otherwise.
        """
        if len(self.vertices) != len(other_graph.vertices) \
                or len(self.edges) != len(other_graph.edges) \
                or len(self.faces) != len(other_graph.faces):
            return False
        return len(self.match(other_graph)) > 0

    def to_yaml(self):
        """
        Serialize the graph into a list or dict which can be exported
        into a yaml string.

        :return: A list or dict representing the graph fit for yaml
                 export.
        """
        vertices = [x.to_yaml() for x in self.vertices]
        edges = [x.to_yaml() for x in self.edges]
        fields = {
            'vertices': vertices,
            'edges': edges,
            'id': id(self),
        }
        return fields

    # noinspection PyDefaultArgument
    @staticmethod
    def from_yaml(data, mapping={}) -> 'Graph':
        """
        Deserialize a graph from a list or dict which was saved in a
        yaml file.

        The mapping argument does not need to be specified, it will be
        filled automatically unless you have a specific requirement.

        :param data: The list or dict containing the graph data.
        :param mapping: A dictionary which will be used to recreate
                        references between objects.
        """
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Graph()
        for vertex_data in data['vertices']:
            result.add(Vertex.from_yaml(vertex_data, mapping))
        for edge_data in data['edges']:
            result.add(Edge.from_yaml(edge_data, mapping))
        mapping[data['id']] = result
        return result

    class AllElemIter:
        """
        Iterates over all elements of a graph in a order such that
        except for the first element all other elements are connected to
        at least one element that came before them.
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
            # connecting_element = None
            for element in reversed(self._marked):
                if isinstance(element, Edge):
                    if element.vertex1 not in self._marked \
                            and element.vertex1 is not None:
                        self._unchecked_vertices.remove(element.vertex1)
                        return element.vertex1
                    elif element.vertex2 not in self._marked \
                            and element.vertex2 is not None:
                        self._unchecked_vertices.remove(element.vertex2)
                        return element.vertex2
                    else:
                        continue
                elif isinstance(element, Vertex):
                    for edge in element.edges:
                        if edge not in self._marked:
                            self._unchecked_edges.remove(edge)
                            return edge
                    continue
            raise StopIteration


def get_min_max_points(graph: Graph
                       ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    """
    Retrun the minimum and maximum extend of a graphs elements.

    I.e.: Return the upper left and the lower right point in a coordinate
    system containing between them all graph elements, which have x and y
    coordinates attributed to them.

    :param graph: The graph whose minumum and maximum extend is to be
         calculated.
    :return: A tuple containing the two points in x and y coordinates.
    """
    min_x = None
    min_y = None
    max_x = None
    max_y = None
    for element in graph:
        if 'x' not in element.attr or 'y' not in element.attr:
            continue
        x = float(element.attr['x'])
        y = float(element.attr['y'])
        if min_x is None:
            min_x = x
            max_x = x
            min_y = y
            max_y = y
        if min_x > x:
            min_x = x
        if max_x < x:
            max_x = x
        if min_y > y:
            min_y = y
        if max_y < y:
            max_y = y
    return (min_x, min_y), (max_x, max_y)
