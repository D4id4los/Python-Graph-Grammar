import pytest
import pytest_mock

from productions import Production, ProductionOption, Mapping
from graph import Graph, Vertex, Edge


class TestProduction:
    def test_apply_delete_single_element(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        mother_graph.add(m_n1)
        daughter_graph = Graph()
        mother_daughter_mapping = Mapping()
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        host_graph.add(h_n1)
        host_mother_mapping = Mapping()
        host_mother_mapping[m_n1] = h_n1
        result = production.apply(host_graph, host_mother_mapping)
        assert len(result) == 0
