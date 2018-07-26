#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from functools import wraps
from typing import TypeVar, Dict, Tuple, MutableSequence, Callable

import matplotlib.pyplot as plt
import wx
import wx.lib.newevent
import yaml
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as NavigationToolbar
from matplotlib.figure import Figure
from model_gen.grammar import Grammar
from model_gen.productions import Production, Mapping
from model_gen.utils import Bidict, get_logger
from model_gen.graph import Graph

T = TypeVar('T')

RunGrammarEvent, EVT_RUN_GRAMMAR_EVENT = wx.lib.newevent.NewCommandEvent()
log = get_logger('model_gen')


class GraphUI(wx.Frame):
    """
    The main window of the Application.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_menus()
        self.panel = wx.Panel(self)
        self.notebook = MainNotebook(self.panel)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.notebook, proportion=1, flag=wx.ALL | wx.EXPAND)
        self.panel.SetSizer(sizer)
        self.Layout()
        self.Show()

        self.host_graphs: Dict[str, Graph] = {}
        self.productions: Dict[str, Production] = {}
        self.result_graphs: Dict[str, Graph] = {}

    def setup_menus(self) -> None:
        """
        Add all menu items to the wx window.
        """
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        file_quit = file_menu.Append(wx.ID_EXIT, item='Quit', helpString='Quit Model Gen')
        file_export = file_menu.Append(wx.ID_ANY, item='Export\tCtrl+e', helpString='Export all Graphs to YAML file')
        file_import = file_menu.Append(wx.ID_ANY, item='Import\tCtrl+i', helpString='Import Graphs from YAML file')
        file_run = file_menu.Append(wx.ID_ANY, item='Run Grammar\tCtrl+r', helpString='Run the defined Grammar')
        menubar.Append(file_menu, title='&File')
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_quit, file_quit)
        self.Bind(wx.EVT_MENU, self.export_graphs, file_export)
        self.Bind(wx.EVT_MENU, self.import_graphs, file_import)
        self.Bind(wx.EVT_MENU, self.run_grammar, file_run)

        self.Bind(EVT_RUN_GRAMMAR_EVENT, self.run_grammar)

    def load_graphs(self, host_graphs: Dict[str, Graph], productions: Dict[str, Production],
                    result_graphs: Dict[str, Graph]) -> None:
        log.info('Loading new graphs and productions.')
        self.host_graphs = host_graphs
        self.productions = productions
        self.result_graphs = result_graphs
        self.notebook.host_graph_panel.load_data(self.host_graphs)
        self.notebook.production_panel.load_data(self.productions)
        self.notebook.result_panel.load_data(self.result_graphs)

    def export_graphs(self, _) -> None:
        """
        Export all currently loaded graphs as a yaml file.
        """
        log.debug('Opening export dialog.')
        with wx.FileDialog(self, 'Export Graphs', wildcard='YAML files (*.yml)|*.yml',
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            log.info('Exporting all graphs and productions.')
            path = file_dialog.GetPath()
            log.debug(f'Exporting to file »{path}«.')
            data = {
                'host_graphs': {k: v.to_yaml() for k, v in self.host_graphs.items()},
                'productions': {k: v.to_yaml() for k, v in self.productions.items()},
                'result_graphs': {k: v.to_yaml() for k, v in self.result_graphs.items()}
            }
            try:
                with open(path, 'w') as stream:
                    yaml.safe_dump(data, stream)
            except IOError:
                log.error(f'Could not open/write-to file {path}.')
                wx.LogError(f'Cannot save export to file {path}.')

    def import_graphs(self, _) -> None:
        """
        Import graphs for display from a yaml file.
        """
        log.debug('Opening import dialog.')
        with wx.FileDialog(self, 'Export Graphs', wildcard='YAML files (*.yml)|*.yml',
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            log.info('Importing graphs and productions.')
            path = file_dialog.GetPath()
            log.debug(f'Importing from file »{path}«.')
            try:
                with open(path, 'r') as stream:
                    data = yaml.safe_load(stream)
                    mapping = {}
                    host_graphs = {k: Graph.from_yaml(v, mapping) for k, v in data['host_graphs'].items()}
                    productions = {k: Production.from_yaml(v, mapping) for k, v in data['productions'].items()}
                    result_graphs = {k: Graph.from_yaml(v, mapping) for k, v in data['result_graphs'].items()}
                    self.load_graphs(host_graphs, productions, result_graphs)
            except IOError:
                log.error(f'Cannon open/read from file »{path}«.')
                wx.LogError(f'Cannot open file {path}.')

    def run_grammar(self, _) -> None:
        """
        Run the grammar defined by the productions on the active hostgraph and add
        the result to result graphs.
        """
        log.info('Running grammar.')
        grammar = Grammar(self.productions.values())
        host_graph = self.notebook.host_graph_panel.get_active()
        if host_graph is None:
            log.error(f'Can not run grammar because no host graphs are loaded/defined.')
            wx.LogError('Error: No host graphs loaded/defined.')
            return
        results = grammar.apply(host_graph, 1)
        log.debug(f'There where {len(results)} derivations calculated: {results}.')
        offset = len(self.result_graphs) - 1
        for i, result in enumerate(results):
            self.result_graphs[f'Result {i + offset}'] = result
            self.notebook.result_panel.load_data(self.result_graphs)

    def on_quit(self, _) -> None:
        log.info('Closing Model Gen.')
        self.Close()


class MainNotebook(wx.Notebook):
    """
    The notebook containing the three main tabs of the UI.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.host_graph_panel = HostGraphPanel(self)
        self.production_panel = ProductionPanel(self)
        self.result_panel = ResultGraphPanel(self)
        self.AddPage(self.host_graph_panel, 'Host Graphs')
        self.AddPage(self.production_panel, 'Productions')
        self.AddPage(self.result_panel, 'Result Graphs')


class HostGraphPanel(wx.Panel):
    """
    Container used to display and edit host graphs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.graph_panel = GraphPanel(self)
        self.list = GraphList(self, graph_panel=self.graph_panel)
        hbox.Add(self.list, proportion=0, flag=wx.EXPAND)
        hbox.Add(self.graph_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)

    def load_data(self, data: Dict[str, Graph]) -> None:
        """
        Load new data into the host graph displays.

        :param data: The host graphs to load
        """
        self.list.load_data(data)

    def get_active(self) -> Graph or None:
        """
        Return the currently active host graph.

        :return: The currently active host graph
        """
        return self.list.get_active()


class ProductionPanel(wx.Panel):
    """
        Container used to display and edit productions.
        """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.production_panel = ProductionGraphsPanel(self)
        self.list = ProductionList(self, production_panel=self.production_panel)
        hbox.Add(self.list, proportion=0, flag=wx.EXPAND)
        hbox.Add(self.production_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)

    def load_data(self, data: Dict[str, Production]) -> None:
        """
        Load new productions into the list to display.

        :param data: The productions to load.
        """
        self.list.load_data(data)


class ResultGraphPanel(wx.Panel):
    """
    Container used to display result graphs.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        self.graph_panel = GraphPanel(self)
        vbox = wx.BoxSizer(wx.VERTICAL)
        self.list = GraphList(self, graph_panel=self.graph_panel)
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        self.del_button = wx.Button(self, label='Delete')
        self.run_button = wx.Button(self, label='Run')
        self.run_button.Bind(wx.EVT_BUTTON, self.on_run_button)
        hbox2.Add(self.del_button, proportion=0, flag=wx.ALIGN_LEFT)
        hbox2.Add(self.run_button, proportion=0, flag=wx.ALIGN_LEFT)
        vbox.Add(self.list, proportion=1, flag=wx.EXPAND)
        vbox.Add(hbox2, proportion=0, flag=wx.EXPAND)
        hbox.Add(vbox, proportion=0, flag=wx.EXPAND)
        hbox.Add(self.graph_panel, proportion=1, flag=wx.EXPAND)
        self.SetSizer(hbox)

    def load_data(self, data: Dict[str, Graph]) -> None:
        """
        Load new data into the result graph displays.

        :param data: The result graphs to load
        """
        self.list.load_data(data)

    def on_run_button(self, _) -> None:
        """
        Post a RunGrammarEvent wx Event when the button is clicked.
        """
        event = RunGrammarEvent(wx.ID_ANY)
        wx.PostEvent(self, event)


class GraphList(wx.ListCtrl):
    """
    A container for displaying a list of graphs.
    """

    def __init__(self, *args, graph_panel, style=wx.LC_REPORT, **kwargs):
        super().__init__(*args, style=style, **kwargs)
        self.graph_panel = graph_panel
        self.InsertColumn(0, 'name', width=150)
        self.graphs: Dict[int, Tuple[str, Graph]] = {}
        self.selected = None
        self.active = None

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select)

    def load_data(self, data: Dict[str, Graph]) -> None:
        """
        Load new data into the graph list.

        :param data: The graphs to load as dict with names matched to graphs.
        """
        self.DeleteAllItems()
        self.graphs.clear()
        if len(data) > 0:
            self.active = 0
        i = 0
        for name, graph_data in data.items():
            index = self.InsertItem(i, name)
            self.graphs[index] = (name, graph_data)
            i += 1

    def delete_selection(self) -> None:
        """
        Delete the currently selected graph from the list.
        """
        if self.selected is None:
            return
        self.DeleteItem(self.selected)
        self.graphs.pop(self.selected)
        self.graph_panel.load_graph(Graph())

    def get_active(self) -> Graph or None:
        """
        Return the currently active host graph.

        :return: The currently active Graph
        """
        if self.active is not None:
            _, active_graph = self.graphs[self.active]
            return active_graph
        return None

    def on_select(self, event) -> None:
        """
        Display the selected graph in the connected graph panel.
        """
        item_index = event.GetIndex()
        self.selected = item_index
        self.active = item_index
        graph = self.graphs[item_index][1]
        self.graph_panel.load_graph(graph)


class ProductionList(wx.ListCtrl):
    """
    A container for displaying a list of productions.
    """

    def __init__(self, *args, production_panel, style=wx.LC_REPORT, **kwargs):
        super().__init__(*args, style=style, **kwargs)
        self.production_panel = production_panel
        self.InsertColumn(0, 'name', width=150)
        self.InsertColumn(1, 'daughters', width=150)
        self.productions: Dict[int, Tuple[str, Production], int] = {}
        self.graphs: Dict[int, Tuple[Graph, Mapping, Graph]] = {}
        self.selected = None

        self.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_select)

    def load_data(self, data: Dict[str, Production]) -> None:
        """
        Load new data into the graph list.

        :param data: The graphs to load as dict with names matched to graphs.
        """
        self.DeleteAllItems()
        self.productions.clear()
        for index, (name, production) in enumerate(data.items()):
            mother_graph = production.mother_graph
            for sub_index, daughter_mapping in enumerate(production.mappings):
                mapping = daughter_mapping.mapping
                daughter_graph = daughter_mapping.daughter_graph
                self.InsertItem(index, name)
                self.SetItem(index, 1, f'Daughter {sub_index}')
                self.productions[index] = (name, production, sub_index)
                self.graphs[index] = (mother_graph, mapping, daughter_graph)

    def delete_selection(self) -> None:
        """
        Delete the currently selected graph from the list.
        """
        if self.selected is None:
            return
        self.DeleteItem(self.selected)
        self.productions.pop(self.selected)
        self.graphs.pop(self.selected)
        self.production_panel.load_graph(Graph(), Mapping(), Graph())

    def on_select(self, event) -> None:
        """
        Display the selected graph in the connected graph panel.
        """
        item_index = event.GetIndex()
        self.selected = item_index
        graphs = self.graphs[item_index]
        self.production_panel.load_graph(graphs)


class ProductionGraphsPanel(wx.Panel):
    """
    A container for the plots of two graphs.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.graph1 = GraphPanel(self)
        self.graph2 = GraphPanel(self)
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self.graph1, proportion=1, flag=wx.EXPAND)
        sizer.Add(self.graph2, proportion=1, flag=wx.EXPAND)
        self.SetSizer(sizer)

    def load_graph(self, graph_data: Tuple[Graph, Mapping, Graph]) -> None:
        """
        Load graphs into the two graph displays.

        :param graph_data: The graphs to load
        """
        self.graph1.load_graph(graph_data[0])
        self.graph2.load_graph(graph_data[2])


class GraphPanel(wx.Panel):
    """
    A container for the plots of a graph.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # matplotlib objects
        self.figure = Figure(figsize=(2, 2))
        self.figure.patch.set_facecolor('white')
        self.subplot = self.figure.add_subplot(111)
        self.canvas = FigureCanvas(self, id=wx.ID_ANY, figure=self.figure)
        self.toolbar = NavigationToolbar(canvas=self.canvas)
        self.toolbar.Realize()
        # wxpython layout elements
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, proportion=1, flag=wx.EXPAND)
        sizer.Add(self.toolbar, proportion=0, flag=wx.LEFT | wx.EXPAND)

        self.SetSizer(sizer)
        # Other Stuff
        self.setup_mpl_visuals()
        self.canvas.Show()

        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('motion_notify_event', self.on_move)

        self.points = [(0, 0), (1, 1), (3, 1), (-2, -2)]
        self.circles = Bidict()
        self.lines = Bidict()
        self.graph = None

    def setup_mpl_visuals(self) -> None:
        """
        Setup all the visual setting of the matplotlib canvas, figure and subplot.

        This function needs to be called every time the mpl figure is redrawn because
        clearing the figure allso resets all these visual settings.
        """
        self.subplot.patch.set_facecolor('white')
        self.subplot.set_xlim(-10, 10, auto=True)
        self.subplot.set_ylim(-10, 10, auto=True)
        # TODO: Make XYLim confort to window size/dimensions
        self.subplot.set_xticks([])
        self.subplot.set_yticks([])
        self.figure.subplots_adjust(bottom=0, top=1, left=0, right=1)
        self.subplot.axis('off')

    def redraw(self) -> None:
        """
        Call all update function necessary to update the graph visualisation.
        """
        self.canvas.draw()
        self.Refresh()

    # noinspection PyMethodParameters
    def _is_update(f: Callable[..., T]) -> Callable[..., T]:
        """
        A decorator to wrap a function performing visual updates with all necessary
        housekeeping functions.
        """

        @wraps(f)
        def wrap(self, *args, **kwargs) -> T:
            # Before update operations
            self.subplot.clear()
            # Update Function
            result = f(self, *args, **kwargs)
            # After update operations
            self.setup_mpl_visuals()
            self.redraw()
            return result

        return wrap

    # noinspection PyArgumentList
    @_is_update
    def draw_line(self) -> None:
        """
        Draw a line connecting all points in self.points.
        """
        self.subplot.plot([x for x, _ in self.points], [y for _, y in self.points], picker=100)

    # noinspection PyArgumentList
    @_is_update
    def draw_points(self) -> None:
        """
        Draw all points in self.points as individual circles.
        """
        for point in self.points:
            self.circles[point] = DraggableCircle(point, 0.5, update_func=self.redraw, color='w', ec='k')
        for point, circle in self.circles:
            self.subplot.add_artist(circle)
            circle.register_events()

    # noinspection PyArgumentList
    @_is_update
    def draw_graph(self) -> None:
        """
        Draw the graph as a set of circles and connecting edges.
        """

        # noinspection PyShadowingNames
        def add_new_free_spaces(pos: Tuple[int, int], free_spaces: MutableSequence[Tuple[int, int]]) -> None:
            """
            Add newly available free spaces adjacent to pos to the list if they are not already present.

            :param pos: The position adjacent to which new spaces will be searched.
            :param free_spaces: The list to which new free spaces will be added
            """
            offset = 2
            possible_positions = [
                (pos[0] + offset, pos[1] + offset),
                (pos[0] + offset, pos[1]),
                (pos[0] + offset, pos[1] - offset),
                (pos[0], pos[1] - offset),
                (pos[0] - offset, pos[1] - offset),
                (pos[0] - offset, pos[1]),
                (pos[0] - offset, pos[1] + offset),
                (pos[0], pos[1] + offset)
            ]
            for candidate in possible_positions:
                if candidate not in free_spaces:
                    free_spaces.append(candidate)

        i = 0
        free_spaces = [(0, 0)]
        for vertex in self.graph.vertices:
            position = free_spaces[i]
            add_new_free_spaces(position, free_spaces)
            circle = DraggableCircle(position, 0.5, update_func=self.redraw, label_func=self.get_vertex_desc, color='w',
                                     ec='k', zorder=10)
            self.circles[vertex] = circle
            self.subplot.add_artist(circle)
            circle.register_events()
            i += 1
        for edge in self.graph.edges:
            try:
                pos1 = self.circles[edge.vertex1].center
            except KeyError:
                print(f'ERROR: Edge {edge} has incorrect vertex1: {edge.vertex1}')
                pos1 = (0, 0)
            try:
                pos2 = self.circles[edge.vertex2].center
            except KeyError:
                print(f'ERROR: Edge {edge} has incorrect vertex2: {edge.vertex2}')
                pos2 = (0, 0)
            line = EdgeLine((pos1[0], pos2[0]), (pos1[1], pos2[1]), update_func=self.redraw,
                            label_func=self.get_edge_desc, c='k')
            self.lines[edge] = line
            self.subplot.add_artist(line)
            line.register_events()

    def load_graph(self, graph: Graph) -> None:
        """
        Load and display the passed graph.

        :param graph: The graph to be displayed
        """
        self.graph = graph
        self.circles = Bidict()
        self.draw_graph()

    def get_vertex_desc(self, circle: plt.Circle) -> str:
        """
        Get a textual description of the attributes of the vertex corresponding to the circle passed as argument.

        :param circle: The circle to which the corresponding description is requested.
        :return: The description of the corresponding vertex
        """
        vertex = self.circles.inverse[circle][0]
        # TODO: Create a attr_desc function in GraphElement
        text = ''
        for name, value in vertex.attr.items():
            text += f'{name}: {value}\n'
        return text[:-1]

    def get_edge_desc(self, line: plt.Line2D) -> str:
        """
        Get a textual description of the attributes of the edge represented by line given as argument.

        :param line: The line to which the corresponding attributes are required.
        :return: A string containing a description of all attributes of the corresponding edge.
        """
        edge = self.lines.inverse[line][0]
        text = ''
        for name, value in edge.attr.items():
            text += f'{name}: {value}\n'
        return text[:-1]

    def on_press(self, event):
        # print(f'button={event.button}, x={event.x}, y={event.y}, xdata={event.xdata}, ydata={event.ydata}')
        pass

    def on_release(self, event):
        pass

    def on_pick(self, event):
        pass

    def on_move(self, event):
        pass


class DraggableCircle(plt.Circle):

    def __init__(self, *args, update_func, label_func, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_func = update_func
        self.label_func = label_func
        self.annotation = None
        self.pressed = False
        self.hovered = False
        self.start_circ_pos = None
        self.start_mouse_pos = None
        self.on_press_cid = None
        self.on_release_cid = None
        self.on_hover_cid = None

    def remove(self):
        super().remove()

    def register_events(self):
        self.on_press_cid = self.figure.canvas.mpl_connect('button_press_event', self.on_press)
        self.on_release_cid = self.figure.canvas.mpl_connect('button_release_event', self.on_release)
        self.on_hover_cid = self.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_press(self, event):
        if self.contains(event)[0]:
            self.pressed = True
            self.start_circ_pos = self.center
            self.start_mouse_pos = (event.xdata, event.ydata)
            self.set_facecolor('red')
            self.update_func()

    def on_release(self, _):
        if self.pressed:
            self.pressed = False
            self.start_circ_pos = None
            self.start_mouse_pos = None
            self.set_facecolor('white')
            self.update_func()

    def on_motion(self, event):
        if event.inaxes != self.axes:
            return
        if self.pressed:
            dx = event.xdata - self.start_mouse_pos[0]
            dy = event.ydata - self.start_mouse_pos[1]
            self.center = (self.start_circ_pos[0] + dx, self.start_circ_pos[1] + dy)
            self.update_func()
        if self.contains(event)[0]:
            if not self.hovered:
                self.hovered = True
                if self.annotation is None:
                    axis = self.figure.gca()
                    text = self.label_func(self)
                    self.annotation = axis.annotate(text,
                                                    xy=self.center,
                                                    xytext=(10, 10),
                                                    textcoords='offset pixels',
                                                    arrowprops=dict(arrowstyle='->'),
                                                    bbox=dict(boxstyle='round', fc='w'),
                                                    zorder=20)
                self.annotation.set_visible(True)
                self.update_func()
        else:
            if self.hovered:
                self.hovered = False
                if self.annotation is not None:
                    self.annotation.set_visible(False)
                    self.update_func()


class EdgeLine(plt.Line2D):
    """
    This class is a specialization of a line that offers mouseover labels.
    """

    def __init__(self, *args, update_func, label_func, **kwargs):
        super().__init__(*args, **kwargs)
        self.update_func = update_func
        self.label_func = label_func
        self.on_hover_cid = None
        self.hovered = False
        self.annotation = None

    def remove(self):
        super().remove()

    def register_events(self):
        self.on_hover_cid = self.figure.canvas.mpl_connect('motion_notify_event', self.on_motion)

    def on_motion(self, event):
        if event.inaxes != self.axes:
            return
        if self.contains(event)[0]:
            if not self.hovered:
                self.hovered = True
                if self.annotation is None:
                    axis = self.figure.gca()
                    text = self.label_func(self)
                    x1, x2 = self.get_xdata()
                    y1, y2 = self.get_ydata()
                    center = (x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
                    self.annotation = axis.annotate(text,
                                                    xy=center,
                                                    xytext=(10, 10),
                                                    textcoords='offset pixels',
                                                    arrowprops=dict(arrowstyle='->'),
                                                    bbox=dict(boxstyle='round', fc='w'),
                                                    zorder=20)
                self.annotation.set_visible(True)
                self.update_func()
        else:
            if self.hovered:
                self.hovered = False
                if self.annotation is not None:
                    self.annotation.set_visible(False)
                    self.update_func()


if __name__ == '__main__':
    log.info('Starting up Model Gen.')
    app = wx.App()
    main_frame = GraphUI(None, title="Model Gen Graph Grammar", size=(1000, 500))
    # main_frame.load_graphs(test1.host_graphs, test1.productions, test1.result_graphs)
    # plot = GraphPanel(main_frame)
    # plot.load_data(data)
    # main_frame.Show()
    app.MainLoop()
