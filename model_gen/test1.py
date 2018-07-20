from grammar import *
from productions import *

from model_gen.graph import *

if __name__ == '__main__':

    host_graphs = {}
    productions = {}
    result_graphs = {}

    h1 = Graph()
    hv1_1 = Vertex()
    hv1_1.attr['label'] = 'a'
    hv1_2 = Vertex()
    he1_1 = Edge(hv1_1, hv1_2)
    he1_1.attr['label'] = '_1'
    h1.add_elements([hv1_1, hv1_2, he1_1])
    host_graphs['Host 1'] = h1
    m1 = Graph()
    mv1_1 = Vertex()
    mv1_1.attr['label'] = 'a'
    m1.add_elements([mv1_1])
    host_graphs['Mother 1'] = m1
    d1 = Graph()
    dv1_1 = Vertex()
    dv1_2 = Vertex()
    dv1_2.attr['label'] = 'a'
    de1_1 = Edge(dv1_1, dv1_2)
    de1_1.attr['label'] = '_2'
    d1.add_elements([dv1_1, dv1_2, de1_1])
    host_graphs['Daughter 1'] = d1
    host_graphs['Daughter copy'] = copy.deepcopy(d1)
    e1 = Mapping()
    e1[mv1_1] = dv1_1
    dm1 = DaughterMapping(m1, e1, d1)
    p1 = Production(m1, [dm1])
    productions['Production 1'] = p1
    g1 = Grammar([p1])
    results = g1.apply(h1, 2)
    for i, result in enumerate(results):
        result_graphs[f'Derivation {i}'] = result

