from model_gen.utils import *

from model_gen.productions import *

log = get_logger('model_gen.' + __name__)


class Grammar:
    """
    A grammar is a collection of productions that can be applied on a graph.
    """
    def __init__(self, productions: Iterable[Production]):
        self.productions: Iterable[Production] = productions

    def apply(self, target_graph: Graph, max_steps: int = 0) \
            -> Sized and Iterable[Graph]:
        """
        Apply the productions of the grammar to a target graph and return a derivation
        sequence of the result graph.

        :param target_graph: The graph to which the productions will be applied.
        :param max_steps: The maximum number of productions to be applied. If 0
        then there is no limit, execution will only stop if
        :return: The sequence of graphs that results from applying the grammar to the target
        graph.
        """
        log.debug(f'Applying the grammar {self} to the target {target_graph} for max {max_steps} steps.')
        step_count = 0
        result_graphs = []
        new_host_graph = target_graph
        while True:
            production, matches = self._find_matching_production(new_host_graph)
            if production is None:
                break
            match = self._select_match(matches)
            matching_subgraph, matching_mapping = match
            new_host_graph = production.apply(new_host_graph, matching_mapping)
            result_graphs.append(new_host_graph)
            step_count += 1
            if max_steps != 0 and max_steps <= step_count:
                break
        return result_graphs

    def _find_matching_production(self, target_graph: Graph):
        """
        Find a single production that has at least one match against the target
        Graph.

        This function will randomly search the list of productions for a
        matching production.

        :param target_graph: The target graph to find a matching production against.
        :return: One matching production along with all the possible matching
        subgraphs of the target graph. If no match is found returns (None,[]).
        :rtype: Tupel[Production|None, List[Graph]]
        """
        result = (None, [])
        for production in randomly(self.productions):
            matching_subgraphs = production.match(target_graph)
            if len(matching_subgraphs) == 0:
                continue
            else:
                result = (production, matching_subgraphs)
                break
        return result

    @staticmethod
    def _select_match(matches: Sized and Iterable[Graph]):
        """
        Select a singe match out of a list of possible matches.

        :param matches: The list of matches from which to select one.
        :return: The selected match
        :rtype: Graph
        """
        i = random.randint(0, len(matches) - 1)
        return matches[i]

    def to_yaml(self) -> Iterable:
        """
        Serialize the grammar into a list or dict which can be exported into a yaml file.

        :return: The grammar as a list or dict.
        """
        data = {}
        data['productions'] = [x.to_yaml() for x in self.productions]
        return data

