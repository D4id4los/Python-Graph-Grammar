"""
This files contains functions for serialisation and deserialisation of objects
used in the software.

Currently it only contains the functions for newly added classes, further
functions await a refactoring.
"""

from functools import singledispatch
from typing import Dict
from model_gen.grammar import GrammarInfo
from model_gen.graph import Graph
from model_gen.productions import Production
from model_gen.opts import Opts


opts = Opts()


# noinspection PyUnusedLocal
@singledispatch
def to_yaml(object_):
    """
    Serialise the passed object into basic yaml compatible collections
    and return them.

    :param object_: The object to be serialised
    :return: A basic collection representing the object.
    """
    raise NotImplementedError


# noinspection PyUnusedLocal
@singledispatch
def from_yaml(cls, data):
    """
    Instantiate and return an object of the requested class from the
    data provided.

    :param cls: The class to deserialise from the data.
    :param data: The data necessary to deserialise the class.
    :return: An object of the appropriate class.
    """
    raise NotImplementedError


@to_yaml.register(GrammarInfo)
def grammar_info_to_yaml(grammar_info: GrammarInfo) -> Dict:
    result = {
        'host_graphs': {name: graph.to_yaml() for name, graph in
                        grammar_info.host_graphs.items()},
        'productions': {name: prod.to_yaml() for name, prod in
                        grammar_info.productions.items()},
        'result_graphs': {name: graph.to_yaml() for name, graph in
                          grammar_info.result_graphs.items()},
        'global_vars': grammar_info.global_vars,
        'options': grammar_info.options,
        'extra': grammar_info.extra,
        'svg': {
            'preamble': grammar_info.svg_preamble
        }
    }
    result['extra']['file_version'] = opts['yaml']['file_version']
    return result


@from_yaml.register(GrammarInfo)
def grammar_info_from_yaml(_: GrammarInfo, data: Dict) -> GrammarInfo:
    result = GrammarInfo()

    mapping = {}
    result.host_graphs = {name: Graph.from_yaml(graph_data, mapping)
                          for name, graph_data in data['host_graphs'].items()}
    result.productions = {name: Production.from_yaml(prod_data, mapping)
                          for name, prod_data in data['productions'].items()}
    result.result_graphs = {name: Graph.from_yaml(graph_data, mapping)
                            for name, graph_data
                            in data['result_graphs'].items()}
    result.global_vars = data.get('global_vars', {})
    result.options = data.get('options', {})
    result.extra = data.get('extra', {})
    result.svg_preamble = data.get('svg', {}).get('preamble', {})
    return result
