"""
Contains export functions for graphs.
"""

import svgwrite
from svgwrite import cm, mm
from model_gen.graph import Graph, GraphElement, Vertex, Edge, \
    get_min_max_points


def add_graphelement_to_svg_drawing(element: GraphElement,
                                    drawing: svgwrite.Drawing) -> None:
    args = {}
    for attr, value in element.attr.items():
        if attr.startswith('.svg_'):
            args[attr[5:]] = value
    if isinstance(element, Vertex):
        x = float(element.attr['x'])
        y = float(element.attr['y'])
        args.setdefault('r', '0.4cm')
        args.setdefault('stroke_width', '1mm')
        args.setdefault('stroke', 'black')
        args.setdefault('fill', 'none')
        drawing.add(drawing.circle(center=(x*cm,y*cm), **args))
    elif isinstance(element, Edge):
        v1 = element.vertex1
        v2 = element.vertex2
        x1 = float(v1.attr['x'])
        y1 = float(v1.attr['y'])
        x2 = float(v2.attr['x'])
        y2 = float(v2.attr['y'])
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
                               profile='tiny', size=size, viewBox=view_box)
    for element in graph:
        add_graphelement_to_svg_drawing(element, drawing)
    drawing.save()
