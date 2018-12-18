"""
Contains export functions for graphs.
"""

import svgwrite
from svgwrite import cm, mm
from functools import singledispatch
from typing import List, Tuple
from model_gen.graph import Graph, GraphElement, Vertex, Edge, \
    get_min_max_points
from model_gen.productions import Production


def add_graphelement_to_svg_drawing(element: GraphElement,
                                    drawing: svgwrite.Drawing) -> None:
    args = {}
    for attr, value in element.attr.items():
        if attr.startswith('.svg_tag'):
            continue
        if attr.startswith('.svg_'):
            args[attr[5:]] = value
    if '.svg_tag' in element.attr:
        if element.attr['.svg_tag'] == 'rect':
            x = float(element.attr['x'])
            y = -float(element.attr['y'])
            width = float(element.attr['.svg_width'])
            height = float(element.attr['.svg_height'])
            x = x - width / 2
            y = y - height / 2
            drawing.add(drawing.rect((x*cm, y*cm), (width*cm, height*cm),
                                     **args))
    elif isinstance(element, Vertex):
        x = float(element.attr['x'])
        y = -float(element.attr['y'])
        args.setdefault('r', '0.4cm')
        args.setdefault('stroke_width', '1mm')
        args.setdefault('stroke', 'black')
        args.setdefault('fill', 'none')
        drawing.add(drawing.circle(center=(x*cm,y*cm), **args))
    elif isinstance(element, Edge):
        v1 = element.vertex1
        v2 = element.vertex2
        x1 = float(v1.attr['x'])
        y1 = -float(v1.attr['y'])
        x2 = float(v2.attr['x'])
        y2 = -float(v2.attr['y'])
        args.setdefault('stroke_width', '1mm')
        args.setdefault('stroke', 'black')
        drawing.add(drawing.line(start=(x1*cm, y1*cm), end=(x2*cm, y2*cm),
                                 **args))
    else:
        raise ValueError


def export_graph_to_svg(graph: Graph, filename: str) -> None:
    min_point, max_point = get_min_max_points(graph)
    size = (max_point[0] - min_point[0], max_point[1] - min_point[1])
    view_box = f'{min_point[0]*100} {min_point[1]*100} {size[0]*100} {size[1]*100}'
    size = size[0] * cm, size[1] * cm
    drawing = svgwrite.Drawing(filename=filename, debug=True,
                               profile='full', size=size, viewBox=view_box,
                               preserveAspectRatio='xMidYMid meet')
    for element in graph:
        add_graphelement_to_svg_drawing(element, drawing)
    drawing.save()








class TIKZVertex:
    def __init__(self, name, x, y):
        self.name = name
        self.label = ''
        self.x = x
        self.y = y
        self.style = 'vertex'


class TIKZEdge:
    def __init__(self, name, vertex1, vertex2):
        self.name = name
        self.vertex1 = vertex1
        self.vertex2 = vertex2
        self.label = ''
        self.style = 'edge'


class TIKZGraph:
    def __init__(self, name=''):
        self.name = name
        self.vertices: List[TIKZVertex] = []
        self.edges: List[TIKZEdge] = []
        self.pos_offset = (0,0)


class TIKZMappings:
    def __init__(self):
        self.mappings = []


def get_min_max_positions(list
                          ) -> Tuple[Tuple[float, float], Tuple[float, float]]:
    min_x = None
    max_x = None
    min_y = None
    max_y = None
    for element in list:
        if min_x is None:
            min_x = element.x
            max_x = element.x
            min_y = element.y
            max_y = element.y
        if element.x < min_x:
            min_x = element.x
        if element.x > max_x:
            max_x = element.x
        if element.y < min_y:
            min_y = element.y
        if element.y > max_y:
            max_y = element.y
    return (min_x, min_y), (max_x, max_y)


def normalize_tikz_graph(graph: TIKZGraph) -> None:
    min, max = get_min_max_positions(graph.vertices)
    dx = max[0] - min[0]
    dy = max[1] - min[1]
    normalizer_x = 1
    normalizer_y = 1
    if abs(dx) > 5:
        normalizer_x = 5 / dx
    if abs(dy) > 5:
        normalizer_y = 5 / dy
    for vertex in graph.vertices:
        vertex.x = vertex.x * normalizer_x
        vertex.y = vertex.y * normalizer_y


def graph_to_TIKZ(graph: Graph, graph_name='', prefix='', element_names=None) -> TIKZGraph:
    tikz_graph = TIKZGraph(graph_name)
    v_nr = 0
    if element_names is None:
        element_names = {}
    for vertex in graph.vertices:
        vertex_name = f'{prefix}v{v_nr}'
        tikz_vertex = TIKZVertex(vertex_name,
                                 float(vertex.attr['x']),
                                 float(vertex.attr['y']))
        tikz_graph.vertices.append(tikz_vertex)
        element_names[vertex] = vertex_name
        v_nr += 1
    e_nr = 0
    # TODO: Figure out how to deal with None vertices in edges.
    for edge in graph.edges:
        edge_name = f'{prefix}e{e_nr}'
        tikz_edge = TIKZEdge(edge_name,
                             element_names[edge.vertex1],
                             element_names[edge.vertex2])
        tikz_graph.edges.append(tikz_edge)
        element_names[edge] = edge_name
        e_nr += 1
    if v_nr + e_nr == 0:
        return tikz_graph
    normalize_tikz_graph(tikz_graph)
    return tikz_graph


def mappings_to_TIKZ(mappings, mother_names, daughter_names):
    tikz_mappings = TIKZMappings()
    for m_element, d_element in mappings.items():
        m_name = mother_names[m_element]
        d_name = daughter_names[d_element]
        tikz_mappings.mappings.append((m_name, d_name))
    return tikz_mappings


@singledispatch
def get_TIKZ_string(arg) -> str:
    return ''


@get_TIKZ_string.register(TIKZGraph)
def _(tikz_graph: TIKZGraph) -> str:
    result = ''
    for vertex in tikz_graph.vertices:
        x = round(vertex.x + tikz_graph.pos_offset[0], 1)
        y = round(vertex.y + tikz_graph.pos_offset[1], 1)
        result = f'{result}\\node [{vertex.style}] ({vertex.name}) ' \
                 f'at ({x},{y}) [label={vertex.label}] {{}};\n'
    result = f'{result}\n'
    for edge in tikz_graph.edges:
        result = f'{result}\\path [{edge.style}] ({edge.vertex1}) ' \
                 f'edge node ({edge.name}) {{ {edge.label} }}' \
                 f'({edge.vertex2});\n'
    result = f'{result}\n\\node [box,fit='
    for vertex in tikz_graph.vertices:
        result = f'{result}({vertex.name}) '
    result = f'{result}] [label={tikz_graph.name}] {{}};\n'
    return result


@get_TIKZ_string.register(TIKZMappings)
def _(tikz_mappings: TIKZMappings) -> str:
    result = '\\path [isomorphism] '
    for m_name, d_name in tikz_mappings.mappings:
        result = f'{result}({m_name}) edge ({d_name})\n'
    result = f'{result};\n\n'
    return result


def export_production_to_TIKZ(production: Production, filename: str) -> None:
    mother_names = {}
    tikz_mother_graph = graph_to_TIKZ(production.mother_graph, 'L', 'l_',
                                      mother_names)
    min, max = get_min_max_positions(tikz_mother_graph.vertices)
    pos_offset = ((max[0] - min[0]) * 1.5), 0
    daughter_names = {}
    tikz_daughter_graph = graph_to_TIKZ(production.production_options[0].daughter_graph,
                                        'R', 'r_', daughter_names)
    tikz_daughter_graph.pos_offset = pos_offset
    tikz_mappings = mappings_to_TIKZ(production.production_options[0].mapping,
                                     mother_names,
                                     daughter_names)
    preamble = '  % Define block styles\n' \
               '  \\usetikzlibrary{shapes,arrows,matrix,positioning,fit}\n' \
               '  \\tikzstyle{vertex} = [circle, draw=black, minimum size=8mm]\n' \
               '  \\tikzstyle{edge} = [-, thin]\n' \
               '  \\tikzstyle{isomorphism} = [->, dotted]\n' \
               '  \\tikzstyle{box} = [draw, inner sep=5mm]\n' \
               '\n' \
               '  \\begin{tikzpicture}[' \
               '        ->,>=stealth\', auto, node distance=2cm, ' \
               '        every matrix/.style={column sep = 5mm, inner sep=5mm, row sep=1mm}, ' \
               '        every label/.style={label distance=0.3mm, inner sep=3pt, fill=white},' \
               '  ]\n'
    postamble = '  \\end{tikzpicture}\n'
    with open(filename, 'w') as file:
        file.write(preamble)
        file.write(get_TIKZ_string(tikz_mother_graph))
        file.write(get_TIKZ_string(tikz_daughter_graph))
        file.write(get_TIKZ_string(tikz_mappings))
        file.write(postamble)


def export_graph_to_TIKZ(graph: Graph, filename: str) -> None:
    tikz_graph = graph_to_TIKZ(graph, 'A')
    preamble = '  % Define block styles\n' \
               '  \\usetikzlibrary{shapes,arrows,matrix,positioning,fit}\n' \
               '  \\tikzstyle{vertex} = [circle, draw=black, minimum size=8mm]\n' \
               '  \\tikzstyle{edge} = [-, thin]\n' \
               '  \\tikzstyle{isomorphism} = [->, dotted]\n' \
               '  \\tikzstyle{box} = [draw, inner sep=5mm]\n' \
               '\n' \
               '  \\begin{tikzpicture}[' \
               '        ->,>=stealth\', auto, node distance=2cm, ' \
               '        every matrix/.style={column sep = 5mm, inner sep=5mm, row sep=1mm}, ' \
               '        every label/.style={label distance=0.3mm, inner sep=3pt, fill=white},' \
               '  ]\n'
    postamble = '  \\end{tikzpicture}\n'
    with open(filename, 'w') as file:
        file.write(preamble)
        file.write(get_TIKZ_string(tikz_graph))
        file.write(postamble)
