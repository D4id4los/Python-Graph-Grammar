import random
from typing import List, TypeVar, Tuple
from timeit import default_timer as timer
from model_gen.utils import *
from model_gen.graph import get_generations, copy_without_meta_elements
from model_gen.productions import *


log = get_logger('model_gen.' + __name__)

T = TypeVar('T')


class Grammar:
    """
    A grammar is a collection of productions that can be applied on a graph.
    """
    def __init__(self, productions: Iterable[Production]=None,
                 global_vars: Dict[str, str]=None,
                 subgrammars: Iterable['Grammar']=None):
        self.productions: Iterable[Production] = [
            copy_without_meta_elements(production)
            for production in productions
        ]
        self.grouped_productions = {}
        for production in self.productions:
            self.grouped_productions.setdefault(
                production.priority, []
            ).append(production)
        self.global_vars: Dict[str, str] = global_vars
        self.subgrammars: Iterable['Grammar'] = subgrammars

    def apply(self, target_graph: Graph, max_steps: int = 0) \
            -> List[Graph]:
        """
        Apply the productions of the grammar to a target graph and
        return a derivation sequence of the result graph.

        :param target_graph: The graph to which the productions will
                             be applied.
        :param max_steps: The maximum number of productions to be
                          applied. If 0 then there is no limit,
                          execution will only stop if
        :return: The sequence of graphs that results from applying
                 the grammar to the target graph.
        """
        start_time = timer()
        log.info(f'Applying the grammar {self} to the target '
                 f'{id(target_graph)} for max {max_steps} steps.')
        step_count = 0
        result_graphs = []
        global_var_results = {
            name: eval(instruction) for name, instruction
            in self.global_vars.items()
        }
        log.info(f'Global variables are: {global_var_results}.')
        for prod in self.productions:
            prod.global_vars = global_var_results
            for prod_opt in prod.production_options:
                prod_opt.vars = {**evaluate_per_run_vars(prod_opt, global_var_results),
                                 **global_var_results}
        new_host_graph = target_graph
        while True:
            log.info(f'Runnig derivation {step_count}.')
            production, matches = self._find_matching_production(
                new_host_graph
            )
            if production is None:
                break
            production_option = production.select_option()
            matching_mapping = self._select_match(matches, production_option)
            new_host_graph = production.apply(new_host_graph, matching_mapping)
            result_graphs.append(new_host_graph)
            log.info(f'Resulted in a graph with {len(new_host_graph)} elements.')
            step_count += 1
            if max_steps != 0 and max_steps <= step_count:
                break
        end_time = timer()
        dt = end_time - start_time
        log.info(f'Calculated {len(result_graphs)} derivations in {dt} seconds.')
        return result_graphs

    def _find_matching_production(self, target_graph: Graph) \
            -> Tuple[Production, List[Mapping]]:
        """
        Find a single production that has at least one match against the target
        Graph.

        This function will randomly search the list of productions for a
        matching production.

        :param target_graph: The target graph to find a matching production
            against.
        :return: One matching production along with all the possible matching
            subgraphs of the target graph. If no match is found returns
            (None,[]).
        """
        result = (None, [])
        for priority in sorted(self.grouped_productions.keys()):
            for production in randomly(self.grouped_productions[priority]):
                matching_mappings = production.match(target_graph)
                if len(matching_mappings) == 0:
                    continue
                else:
                    result = (production, matching_mappings)
                    break
            if result[0] is not None:
                break
        return result

    @staticmethod
    def _select_match(matches: List[Mapping],
                      production_option: ProductionOption) -> Mapping:
        """
        Select a singe match out of a list of possible matches.

        :param matches: The list of matches from which to select one.
        :param production_option: The production option which is being matched.
        :return: The selected match
        """
        valid_matches = matches
        if ('generation' in production_option.conditions
                and production_option.conditions['generation'] == 'oldest'):
            best_generations = None
            best_mappings = []
            for mapping in matches:
                generations = get_generations(mapping.values())
                if best_generations is None:
                    best_generations = generations
                    best_mappings = [mapping]
                    continue
                if generations > best_generations:
                    best_generations = generations
                    best_mappings = [mapping]
                elif generations == best_generations:
                    best_mappings.append(mapping)
            valid_matches = best_mappings
            log.debug(f'Oldest generations were {repr(best_generations)}.')
        i = random.randint(0, len(valid_matches)-1)
        return valid_matches[i]

    def to_yaml(self) -> Iterable:
        """
        Serialize the grammar into a list or dict which can be
        exported into a yaml file.

        :return: The grammar as a list or dict.
        """
        data = {
            'productions': [x.to_yaml() for x in self.productions],
            'subgrammars': [x.to_yaml() for x in self.subgrammars],
            'id': id(self)
        }
        return data

    @staticmethod
    def from_yaml(data, mapping=None):
        if mapping is None:
            mapping = {}
        if data['id'] in mapping:
            return mapping[data['id']]
        result = Grammar()
        result.productions = Production.from_yaml(data, mapping)
        result.subgrammars = Grammar.from_yaml(data, mapping)
        mapping[data['id']] = result
        return result


class GrammarInfo:

    def __init__(self):
        self.host_graphs: Dict[str, Graph] = None
        self.productions: Dict[str, Production] = None
        self.result_graphs: Dict[str, Graph] = None
        self.global_vars: Dict[str, Any] = None
        self.options: Dict[str, Any] = None
        self.extra: Dict[str, Any] = None
        self.svg_preamble: List[str] = None
