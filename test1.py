from graph import *
from grammar import *
from productions import *

host_graphs = []
productions = []
result_graphs = []

h1 = Graph()
hv1_1 = Vertex()
hv1_1.attr['label'] = 'a'
hv1_2 = Vertex()
he1_1 = Edge(hv1_1, hv1_2)
h1.add_elements([hv1_1, hv1_2, he1_1])
host_graphs.append(h1)
m1 = Graph()
mv1_1 = Vertex()
mv1_1.attr['label'] = 'a'
m1.add_elements([mv1_1])
d1 = Graph()
dv1_1 = Vertex()
dv1_2 = Vertex()
dv1_2.attr['label'] = 'a'
de1_1 = Edge(dv1_1, dv1_2)
d1.add_elements([dv1_1, dv1_2, de1_1])
e1 = Mapping()
e1.mapping = [(mv1_1, dv1_1)]
p1 = Production(m1, [(e1, d1, 1)])
productions.append(p1)
print (p1.match(h1))
result_graphs.append(p1.match(h1))
