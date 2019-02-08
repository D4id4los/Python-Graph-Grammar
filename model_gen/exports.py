"""
Contains export functions for graphs.
"""

import svgwrite
from svgwrite import cm, mm
from functools import singledispatch
from typing import List, Tuple, Union, Dict
from model_gen.graph import Graph, GraphElement, Vertex, Edge, \
    get_min_max_points, get_positions
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
            width = float(element.attr.get('.svg_width', 0.1))
            height = float(element.attr.get('.svg_height', 0.1))
            x = x - width / 2
            y = y - height / 2
            drawing.add(drawing.rect((x*cm, y*cm), (width*cm, height*cm),
                                     **args))
        elif element.attr['.svg_tag'] == 'path':
            drawing.add(drawing.path(**args))
        elif element.attr['.svg_tag'] == 'circle':
            x = float(element.attr['x'])
            y = -float(element.attr['y'])
            args.setdefault('r', '1cm')
            args.setdefault('stroke_width', '0.1mm')
            args.setdefault('stroke', 'black')
            args.setdefault('fill', 'none')
            drawing.add(drawing.circle(center=(x * cm, y * cm), **args))
    elif isinstance(element, Vertex):
        if '.helper_node' in element.attr and element.attr['.helper_node']:
            return
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
    min_point, max_point = get_min_max_points(get_positions(graph.vertices))
    size = (max_point[0] - min_point[0], max_point[1] - min_point[1])
    view_box = f'{min_point[0]*100} {-max_point[1]*100} {size[0]*100} {size[1]*100}'
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
        self.ids: Dict[Union[Vertex, Edge], int] = {}
        self.pos_offset = (0,0)
        self.right_of = None


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
    x_offset = 0
    y_offset = 0
    if min[0] < 0:
        x_offset = -min[0]
    if min[1] < 0:
        y_offset = -min[1]
    for vertex in graph.vertices:
        vertex.x = vertex.x * normalizer_x + x_offset
        vertex.y = vertex.y * normalizer_y + y_offset


def graph_to_TIKZ(graph: Graph, graph_name='', prefix='', element_names=None,
                  element_id_offset=0) -> TIKZGraph:
    tikz_graph = TIKZGraph(graph_name)
    v_nr = 0
    current_id = element_id_offset
    if element_names is None:
        element_names = {}
    for vertex in graph.vertices:
        vertex_name = f'{prefix}v{v_nr}'
        tikz_vertex = TIKZVertex(vertex_name,
                                 float(vertex.attr['x']),
                                 float(vertex.attr['y']))
        if('.helper_node' in vertex.attr and vertex.attr['.helper_node']):
            tikz_vertex.style = 'meta_vertex'
        else:
            tikz_vertex.label = str(current_id)
        tikz_graph.vertices.append(tikz_vertex)
        tikz_graph.ids[vertex] = current_id
        current_id += 1
        element_names[vertex] = vertex_name
        v_nr += 1
    e_nr = 0
    for edge in graph.edges:
        edge_name = f'{prefix}e{e_nr}'
        tikz_edge = TIKZEdge(edge_name,
                             element_names[edge.vertex1],
                             element_names[edge.vertex2])
        if '.directed' in edge.attr and edge.attr['.directed']:
            tikz_edge.style = 'directed_edge'
        tikz_edge.label = str(current_id)
        tikz_graph.edges.append(tikz_edge)
        tikz_graph.ids[edge] = current_id
        current_id += 1
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
    positioning = ''
    if tikz_graph.right_of is not None:
        positioning = f', shift={{($({tikz_graph.right_of}.east |- 0,0) + (3cm, 0)$)}}'
    result = f'  \\begin{{scope}}[local bounding box={tikz_graph.name}{positioning}]\n'
    for vertex in tikz_graph.vertices:
        x = round(vertex.x + tikz_graph.pos_offset[0], 1)
        y = round(vertex.y + tikz_graph.pos_offset[1], 1)
        result = f'{result}    \\node [{vertex.style}] ({vertex.name}) ' \
                 f'at ({x},{y}) [label={vertex.label}] {{}};\n'
    result = f'{result}\n'
    for edge in tikz_graph.edges:
        result = f'{result}    \\path [{edge.style}] ({edge.vertex1}) ' \
                 f'edge node ({edge.name}) {{ {edge.label} }}' \
                 f'({edge.vertex2});\n'
    result = f'{result}\n    \\node [box,fit='
    for vertex in tikz_graph.vertices:
        result = f'{result} ({vertex.name}) '
    result = f'{result}] [label={{[centered]north:{tikz_graph.name}}}] {{}};\n\n'
    result = f'{result}  \\end{{scope}}\n'
    return result


@get_TIKZ_string.register(TIKZMappings)
def _(tikz_mappings: TIKZMappings) -> str:
    result = '    \\path [isomorphism] \n'
    for m_name, d_name in tikz_mappings.mappings:
        result = f'{result}      ({m_name}) edge ({d_name})\n'
    result = f'{result}      ;\n\n'
    return result


def get_latex_attr_table_string(tikz_graph: TIKZGraph) -> str:
    result = ''
    for element, id_ in tikz_graph.ids.items():
        attrs = dict(element.attr)
        attrs.pop('.generation', None)
        attrs.pop('x', None)
        attrs.pop('y', None)
        if len(attrs) == 0:
            continue
        elif len(attrs) > 1:
            result = f'{result}      \\multirow{{{len(attrs)}}}{{*}}{{\\textbf{{{str(id_)}:}}}} '
        else:
            result = f'{result}      \\textbf{{{str(id_)}:}} '
        for attr_name, attr_value in attrs.items():
            result = f'{result}      & \\verb|{attr_name}| & \\lstinline[]${str(attr_value)}$ \\\\ \n'
    return result


def get_latex_vector_table_string(production: Production,
                                  element_names: Dict[GraphElement, str]
                                  ) -> str:
    result = ''
    for vec_name, elements in production.vectors.items():
        if isinstance(elements, Vertex):
            result = f'{result}      \\textbf{{{vec_name}}} & ' \
                     f'Point \\textbf{{{element_names[elements]}}} \\\\ \n'
        else:
            result = f'{result}      \\textbf{{{vec_name}}} & ' \
                     f'Line from \\textbf{{{element_names[elements[0]]}}} to ' \
                     f'\\textbf{{{element_names[elements[1]]}}} \\\\ \n'
    return result


def export_production_to_TIKZ(production: Production, filename: str) -> None:
    mother_names = {}
    tikz_mother_graph = graph_to_TIKZ(production.mother_graph,
                                      graph_name='L',
                                      prefix='l_',
                                      element_names=mother_names)
    min, max = get_min_max_positions(tikz_mother_graph.vertices)
    pos_offset = ((max[0] - min[0]) * 1.5), 0
    daughter_names = {}
    tikz_daughter_graph = graph_to_TIKZ(
        production.production_options[0].daughter_graph,
        graph_name='R',
        prefix='r_',
        element_names=daughter_names,
        element_id_offset=len(tikz_mother_graph.ids)
    )
    tikz_daughter_graph.right_of = 'L'
    # tikz_daughter_graph.pos_offset = pos_offset
    tikz_mappings = mappings_to_TIKZ(production.production_options[0].mapping,
                                     mother_names,
                                     daughter_names)
    preamble = '  % Define block styles\n' \
               '  \\usetikzlibrary{shapes,arrows,matrix,positioning,fit,calc}\n' \
               '  \\tikzstyle{vertex} = [circle, draw=black, minimum size=8mm]\n' \
               '  \\tikzstyle{meta_vertex} = [circle, draw=none, minimum size=8mm]\n' \
               '  \\tikzstyle{edge} = [-, thin]\n' \
               '  \\tikzstyle{directed_edge} = [->, thin]\n' \
               '  \\tikzstyle{isomorphism} = [->, dotted]\n' \
               '  \\tikzstyle{box} = [draw, inner sep=10mm]\n' \
               '\n' \
               '  \\begin{tikzpicture}[\n' \
               '        ->,>=stealth\', auto, node distance=2cm, \n' \
               '        every matrix/.style={column sep = 5mm, inner sep=5mm, row sep=1mm}, \n' \
               '        every label/.style={label distance=0.3mm, inner sep=3pt, fill=white},\n' \
               '  ]\n'
    postamble = '  \\end{tikzpicture}\n'
    table_preamble = ('  \\begin{table}[h]\n'
                      '    \\centering\n')
    attr_table_preamble = ('    \\begin{tabularx}{\\textwidth}{llX}\n'
                           '      \\toprule\n'
                           '      \\textbf{Element} & \\textbf{Attribute} & \\textbf{Value} \\\\ \n')
    attr_table_postamble = ('      \\bottomrule\n'
                            '    \\end{tabularx}\n')
    vector_table_preamble = ('    \\begin{tabularx}{\\textwidth}{lX}\n'
                             '      \\toprule\n'
                             '      \\textbf{Vector Name} & \\textbf{Definition} \\\\ \n')
    vector_table_postamble = ('      \\bottomrule\n'
                              '    \\end{tabularx}\n')
    table_postamble = ('    \\caption{Attribute definitions of the production "".}\n'
                       '    \\label{tab:}\n'
                       '   \\end{table}\n')
    with open(filename, 'w') as file:
        file.write(preamble)
        file.write(get_TIKZ_string(tikz_mother_graph))
        file.write(get_TIKZ_string(tikz_daughter_graph))
        file.write(get_TIKZ_string(tikz_mappings))
        file.write(postamble)
        file.write('\n\n\n')
        file.write(table_preamble)
        file.write(attr_table_preamble)
        file.write(get_latex_attr_table_string(tikz_mother_graph))
        file.write(get_latex_attr_table_string(tikz_daughter_graph))
        file.write(attr_table_postamble)
        file.write(vector_table_preamble)
        file.write(get_latex_vector_table_string(production, tikz_mother_graph.ids))
        file.write(vector_table_postamble)
        file.write(table_postamble)


def export_graph_to_TIKZ(graph: Graph, filename: str) -> None:
    tikz_graph = graph_to_TIKZ(graph, 'A')
    preamble = '  % Define block styles\n' \
               '  \\usetikzlibrary{shapes,arrows,matrix,positioning,fit,calc}\n' \
               '  \\tikzstyle{vertex} = [circle, draw=black, minimum size=8mm]\n' \
               '  \\tikzstyle{meta_vertex} = [circle, draw=none, minimum size=8mm]\n' \
               '  \\tikzstyle{edge} = [-, thin]\n' \
               '  \\tikzstyle{directed_edge} = [->, thin]\n' \
               '  \\tikzstyle{isomorphism} = [->, dotted]\n' \
               '  \\tikzstyle{box} = [draw, inner sep=10mm]\n' \
               '\n' \
               '  \\begin{tikzpicture}[\n' \
               '        ->,>=stealth\', auto, node distance=2cm, \n' \
               '        every matrix/.style={column sep = 5mm, inner sep=5mm, row sep=1mm}, \n' \
               '        every label/.style={label distance=0.3mm, inner sep=3pt, fill=white},\n' \
               '  ]\n'
    postamble = '  \\end{tikzpicture}\n'
    table_preamble = ('  \\begin{table}[h]\n'
                      '    \\centering\n'
                      '    \\begin{tabularx}{\\textwidth}{llX}\n'
                      '      \\toprule\n'
                      '      \\textbf{Element} & \\textbf{Attribute} & \\textbf{Value} \\\\ \n')
    table_postamble = ('      \\bottomrule\n'
                       '    \\end{tabularx}\n'
                       '    \\caption{Attribute definitions of the production "".}\n'
                       '    \\label{tab:}\n'
                       '   \\end{table}\n')
    with open(filename, 'w') as file:
        file.write(preamble)
        file.write(get_TIKZ_string(tikz_graph))
        file.write(postamble)
        file.write('\n\n\n')
        file.write(table_preamble)
        file.write(get_latex_attr_table_string(tikz_graph))
        file.write(table_postamble)