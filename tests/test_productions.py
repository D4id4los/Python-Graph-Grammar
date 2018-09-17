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

    def test_apply_no_change(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        mother_graph.add(m_n1)
        daughter_graph = Graph()
        d_n1 = Vertex()
        mother_daughter_mapping = Mapping()
        mother_daughter_mapping[m_n1] = d_n1
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        h_n1.attr['test'] = 1
        host_graph.add(h_n1)
        host_mother_mapping = Mapping()
        host_mother_mapping[m_n1] = h_n1
        result = production.apply(host_graph, host_mother_mapping)
        assert len(result) == 1
        assert result.vertices[0].attr['test'] == 1

    def test_apply_add_attr(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        mother_graph.add(m_n1)
        daughter_graph = Graph()
        d_n1 = Vertex()
        d_n1.attr['new_attr'] = 'test'
        mother_daughter_mapping = Mapping()
        mother_daughter_mapping[m_n1] = d_n1
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        h_n1.attr['test'] = 1
        host_graph.add(h_n1)
        host_mother_mapping = Mapping()
        host_mother_mapping[m_n1] = h_n1
        result = production.apply(host_graph, host_mother_mapping)
        assert len(result) == 1
        assert result.vertices[0].attr['test'] == 1
        assert result.vertices[0].attr['new_attr'] == 'test'

    def test_apply_vertex_new_connection(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        m_e1 = Edge(m_n1)
        mother_graph.add_elements([m_n1, m_e1])
        daughter_graph = Graph()
        d_n1 = Vertex()
        d_e1 = Edge(d_n1)
        daughter_graph.add_elements([d_n1, d_e1])
        mother_daughter_mapping = Mapping()
        mother_daughter_mapping[m_n1] = d_n1
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        h_e1 = Edge(h_n1)
        host_graph.add_elements([h_n1, h_e1])
        mother_host_mapping = Mapping()
        mother_host_mapping[m_n1] = h_n1
        mother_host_mapping[m_e1] = h_e1
        result = production.apply(host_graph, mother_host_mapping)
        # Test if there are no superfluous elements in the graph
        assert len(result.vertices) == 1
        assert len(result.edges) == 1
        # Test if graph has the correct connections and element count
        assert result.is_isomorph(daughter_graph)
        # Test if there are no extra neighbours introduced to the vertex.
        assert len(result.vertices[0].edges) == 1
        assert result.edges[0] in result.vertices[0].edges
        # Test if the new edge was correctly connected to the vertex.
        assert result.edges[0].vertex1 == result.vertices[0]

    def test_apply_edge_new_connection(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        m_e1 = Edge(m_n1)
        mother_graph.add_elements([m_n1, m_e1])
        daughter_graph = Graph()
        d_n1 = Vertex()
        d_e1 = Edge(d_n1)
        daughter_graph.add_elements([d_n1, d_e1])
        mother_daughter_mapping = Mapping()
        mother_daughter_mapping[m_e1] = d_e1
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        h_e1 = Edge(None, h_n1)
        host_graph.add_elements([h_n1, h_e1])
        mother_host_mapping = Mapping()
        mother_host_mapping[m_n1] = h_n1
        mother_host_mapping[m_e1] = h_e1
        result = production.apply(host_graph, mother_host_mapping)
        # Test if there are no superfluous elements in the graph
        assert len(result.vertices) == 1
        assert len(result.edges) == 1
        # Test if graph has the correct connections and element count
        assert result.is_isomorph(daughter_graph)
        # Test if there are no extra neighbours introduced to the vertex.
        assert len(result.vertices[0].edges) == 1
        assert result.edges[0] in result.vertices[0].edges
        # Test if the new edge was correctly connected to the vertex.
        assert result.edges[0].vertex2 == result.vertices[0]

    def test_apply_remove_connection_from_vertex(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        m_e1 = Edge(m_n1)
        mother_graph.add_elements([m_n1, m_e1])
        daughter_graph = Graph()
        d_n1 = Vertex()
        daughter_graph.add_elements([d_n1])
        mother_daughter_mapping = Mapping()
        mother_daughter_mapping[m_n1] = d_n1
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        h_e1 = Edge(h_n1)
        host_graph.add_elements([h_n1, h_e1])
        mother_host_mapping = Mapping()
        mother_host_mapping[m_n1] = h_n1
        mother_host_mapping[m_e1] = h_e1
        result = production.apply(host_graph, mother_host_mapping)
        # Test if the edge was deleted
        assert len(result.vertices) == 1
        assert len(result.edges) == 0
        # Test if the edge was removed from the neighbours list of the vertex
        assert len(result.vertices[0].edges) == 0

    def test_apply_remove_connection_from_edge(self):
        mother_graph = Graph()
        m_n1 = Vertex()
        m_e1 = Edge(m_n1)
        mother_graph.add_elements([m_n1, m_e1])
        daughter_graph = Graph()
        d_e1 = Edge()
        daughter_graph.add_elements([d_e1])
        mother_daughter_mapping = Mapping()
        mother_daughter_mapping[m_e1] = d_e1
        prod_option = ProductionOption(mother_graph,
                                       mother_daughter_mapping,
                                       daughter_graph)
        production = Production(mother_graph, [prod_option])
        host_graph = Graph()
        h_n1 = Vertex()
        h_e1 = Edge(None, h_n1)
        host_graph.add_elements([h_n1, h_e1])
        mother_host_mapping = Mapping()
        mother_host_mapping[m_n1] = h_n1
        mother_host_mapping[m_e1] = h_e1
        result = production.apply(host_graph, mother_host_mapping)
        # Test if the vertex was deleted
        assert len(result.vertices) == 0
        assert len(result.edges) == 1
        # Test if the vertex was removed from the edges connection field
        assert result.edges[0].vertex2 is None
