#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import TypeVar, Dict, Tuple, MutableSequence, Set

import matplotlib.pyplot as plt
import wx
import wx.lib.newevent
import wx.lib.agw.aui as aui
import yaml
import abc
from pydispatch import dispatcher
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.backends.backend_wxagg import \
    NavigationToolbar2WxAgg as NavigationToolbar
from matplotlib.figure import Figure
from matplotlib.patches import ConnectionPatch
from model_gen.grammar import Grammar
from model_gen.productions import Production, Mapping
from model_gen.utils import Bidict, get_logger
from model_gen.graph import Graph, GraphElement
from model_gen.exceptions import ModelGenArgumentError
from model_gen.opts import Opts

T = TypeVar('T')

RunGrammarEvent, EVT_RUN_GRAMMAR = wx.lib.newevent.NewCommandEvent()
log = get_logger('model_gen')


class GraphUI(wx.Frame):
    """
    The main window of the Application.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._setup_menus()
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

        if 'last_grammar_file_path' in opts:
            self.load_graph_from_file(opts['last_grammar_file_path'])

    # noinspection PyAttributeOutsideInit
    def _setup_menus(self) -> None:
        """
        Add all menu items to the wx window.
        """
        menubar = wx.MenuBar()
        file_menu = wx.Menu()
        file_quit = file_menu.Append(wx.ID_EXIT, item='Quit',
                                     helpString='Quit Model Gen')
        file_export = file_menu.Append(
            wx.ID_ANY,
            item='Export\tCtrl+e',
            helpString='Export all Graphs to YAML file'
        )
        file_import = file_menu.Append(
            wx.ID_ANY,
            item='Import\tCtrl+i',
            helpString='Import Graphs from YAML file'
        )
        file_run = file_menu.Append(
            wx.ID_ANY,
            item='Run Grammar\tCtrl+r',
            helpString='Run the defined Grammar'
        )
        menubar.Append(file_menu, title='&File')
        view_menu = wx.Menu()
        self.view_show_all_labels: wx.MenuItem = view_menu.Append(
            wx.ID_ANY,
            item='Show All Lables\tCtrl+l',
            helpString='Show labels for all Elements of a Graph',
            kind=wx.ITEM_CHECK
        )
        self.view_show_all_labels.Check(opts['show_all_labels'])
        menubar.Append(view_menu, title='&View')
        self.SetMenuBar(menubar)

        self.Bind(wx.EVT_MENU, self.on_quit, file_quit)
        self.Bind(wx.EVT_MENU, self.export_graphs, file_export)
        self.Bind(wx.EVT_MENU, self.import_graphs, file_import)
        self.Bind(wx.EVT_MENU, self.run_grammar, file_run)
        self.Bind(wx.EVT_MENU, self.switch_label_display,
                  self.view_show_all_labels)

        self.Bind(EVT_RUN_GRAMMAR, self.run_grammar)

    def load_graphs(self, host_graphs: Dict[str, Graph],
                    productions: Dict[str, Production],
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
        with wx.FileDialog(self, 'Export Graphs',
                           wildcard='YAML files (*.yml)|*.yml',
                           style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
                           ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            log.info('Exporting all graphs and productions.')
            path = file_dialog.GetPath()
            log.debug(f'Exporting to file »{path}«.')
            data = {
                'host_graphs': {k: v.to_yaml() for k, v in
                                self.host_graphs.items()},
                'productions': {k: v.to_yaml() for k, v in
                                self.productions.items()},
                'result_graphs': {k: v.to_yaml() for k, v in
                                  self.result_graphs.items()}
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
        with wx.FileDialog(self, 'Import Graphs',
                           wildcard='YAML files (*.yml)|*.yml',
                           style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
                           ) as file_dialog:
            if file_dialog.ShowModal() == wx.ID_CANCEL:
                return
            log.info('Importing graphs and productions.')
            path = file_dialog.GetPath()
            log.debug(f'Importing from file »{path}«.')
            self.load_graph_from_file(path)
            opts['last_grammar_file_path'] = path


    def load_graph_from_file(self, file_path: str) -> None:
        """
        Loads a graph saved in a yaml file and displays it in the gui.
        :param file_path: Path to the file.
        """
        try:
            with open(file_path, 'r') as stream:
                data = yaml.safe_load(stream)
                mapping = {}
                host_graphs = {k: Graph.from_yaml(v, mapping) for k, v in
                               data['host_graphs'].items()}
                productions = {k: Production.from_yaml(v, mapping) for k, v
                               in data['productions'].items()}
                result_graphs = {k: Graph.from_yaml(v, mapping) for k, v in
                                 data['result_graphs'].items()}
                self.load_graphs(host_graphs, productions, result_graphs)
        except IOError:
            log.error(f'Cannon open/read from file »{file_path}«.')
            wx.LogError(f'Cannot open file {file_path}.')

    def run_grammar(self, _) -> None:
        """
        Run the grammar defined by the productions on the active
        hostgraph and add the result to result graphs.
        """
        log.info('Running grammar.')
        grammar = Grammar(self.productions.values())
        host_graph = self.notebook.host_graph_panel.get_active()
        if host_graph is None:
            log.error(
                f'Can not run grammar because no host graphs are '
                f'loaded/defined.')
            wx.LogError('Error: No host graphs loaded/defined.')
            return
        results = grammar.apply(host_graph, 2)
        log.debug(
            f'There where {len(results)} derivations calculated: {results}.')
        offset = len(self.result_graphs)
        for i, result in enumerate(results):
            self.result_graphs[f'Result {i + offset}'] = result
            self.notebook.result_panel.load_data(self.result_graphs)

    def switch_label_display(self, _) -> None:
        """
        Switch the label display Mode between displaying Labels for
        all GraphElements and only displaying them for hovered
        GraphElements.

        :param _: The event passed by wx
        """
        if self.view_show_all_labels.IsChecked():
            opts['show_all_labels'] = True
        else:
            opts['show_all_labels'] = False

    def on_quit(self, _) -> None:
        log.info('Closing Model Gen.')
        self.Close()


class MainNotebook(aui.AuiNotebook):
    """
    The notebook containing the three main tabs of the UI.

    I am using AuiNotebook instead of wx.Notebook because the
    Navigation Toolbar from matplotlib throws negative content height
    warnings if it is placed somewhere inside a wx.Notebook, but not
    if it is placed inside a aui.AuiNotebook.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, agwStyle=aui.AUI_NB_TOP, **kwargs)
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
        self.list = ProductionList(self,
                                   production_panel=self.production_panel)
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
        self.productions: Dict[int, Tuple[str, Production, int]] = {}
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


# def _is_update(f: Callable[..., T]) -> Callable[..., T]:
#     """
#     A decorator to wrap a function performing visual updates in a
#     matplotlib figure with all necessary housekeeping functions to
#     have the changes render as expected.
#     """
#
#     @wraps(f)
#     def wrap(self, *args, **kwargs) -> T:
#         # Before update operations
#         self.subplot.clear()
#         # Update Function
#         result = f(self, *args, **kwargs)
#         # After update operations
#         self.setup_mpl_visuals()
#         self.redraw()
#         return result
#
#     return wrap


class GraphPanel(wx.Panel):
    """
    A container for the plots of a graph.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # matplotlib objects
        self.figure = Figure(figsize=(2, 2))
        self.figure.patch.set_facecolor('white')
        self.subplot = self.figure.add_subplot(111)  # Is of type Axes
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
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)

        self.pressed_elements: Dict[FigureElement, Tuple[float, float]] = {}
        self.press_start_position: Tuple[float, float] = None

        self.graph = None
        self.graph_to_figure: Bidict[GraphElement, FigureElement] = Bidict()
        self.vertices: Set[FigureVertex] = set()
        self.edges: Set[FigureEdge] = set()

    @property
    def elements(self) -> Set['FigureElement']:
        return self.vertices | self.edges

    def setup_mpl_visuals(self, axes=None) -> None:
        """
        Setup all the visual setting of the matplotlib canvas, figure
        and subplot.

        This function needs to be called every time the mpl figure is
        redrawn because clearing the figure allso resets all these
        visual settings.

        :param axes: The axes for which the visuals shall be set.
        """
        if axes is None:
            axes = self.subplot
        axes.patch.set_facecolor('white')
        axes.set_xlim(-10, 10, auto=True)
        axes.set_ylim(-10, 10, auto=True)
        # TODO: Make XYLim confort to window size/dimensions
        axes.set_xticks([])
        axes.set_yticks([])
        self.figure.subplots_adjust(bottom=0, top=1, left=0, right=1)
        axes.axis('off')

    def redraw(self) -> None:
        """
        Call all update function necessary to update the graph visualisation.
        """
        self.canvas.draw_idle()
        self.Refresh()

    def draw_graph(self, graph=None, axes=None) -> None:
        """
        Draw the graph as a set of circles and connecting edges.
        """

        # noinspection PyShadowingNames
        def add_new_free_spaces(pos: Tuple[int, int],
                                free_spaces: MutableSequence[
                                    Tuple[int, int]]) -> None:
            """
            Add newly available free spaces adjacent to pos to the
            list if they are not already present.

            :param pos: The position adjacent to which new spaces
                        will be searched.
            :param free_spaces: The list to which new free spaces
                                will be added
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

        if axes is None:
            axes = self.subplot
        if graph is None:
            graph = self.graph
        i = 0
        free_spaces = [(0, 0)]
        for graph_vertex in graph.vertices:
            position = free_spaces[i]
            add_new_free_spaces(position, free_spaces)
            figure_vertex = FigureVertex(graph_vertex, position, 0.5,
                                         color='w', ec='k', zorder=10)
            self.vertices.add(figure_vertex)
            self.graph_to_figure[graph_vertex] = figure_vertex
            axes.add_artist(figure_vertex)
            i += 1
        for graph_edge in graph.edges:
            figure_vertex1 = self.graph_to_figure[graph_edge.vertex1]
            figure_vertex2 = self.graph_to_figure[graph_edge.vertex2]
            figure_edge = FigureEdge(graph_edge, vertex1=figure_vertex1,
                                     vertex2=figure_vertex2, c='k')
            self.edges.add(figure_edge)
            self.graph_to_figure[graph_edge] = figure_edge
            axes.add_artist(figure_edge)
        if opts['show_all_labels']:
            for element in self.elements:
                if element.get_hover_text() != '':
                    element.annotation = self.annotate_element(element)
        self.setup_mpl_visuals(axes)
        self.redraw()

    def annotate(self, text: str, position: Tuple[int, int],
                 axes: plt.Axes = None) -> plt.Annotation:
        """
        Places an annotation on the subplot.
        
        :param text: The text to place.
        :param position: The positon of the annotation.
        :param axes: The axes to add the annotation to
        :return: The Annotation object representing the annotation.
        """
        if axes is None:
            axes = self.subplot
        annotation = axes.annotate(text,
                                   xy=position,
                                   xytext=(10, 10),
                                   textcoords='offset pixels',
                                   arrowprops=dict(
                                       arrowstyle='->'),
                                   bbox=dict(
                                       boxstyle='round',
                                       fc='w'),
                                   zorder=20)
        annotation.set_visible(True)
        return annotation

    def annotate_element(self, element: 'FigureElement') -> plt.Annotation:
        """
        Annotate a FigureElement.

        This is a convenience function so you don't need to pass all
        three arguments separately, they are all taken from the
        passed element.

        :param element: The FigureElement to annotate
        :return: The Annotation object representing the annotation.
        """
        return self.annotate(element.get_hover_text(),
                             element.get_center(),
                             element.axes)

    def load_graph(self, graph: Graph) -> None:
        """
        Load and display the passed graph.

        :param graph: The graph to be displayed
        """
        self.graph = graph
        self.vertices.clear()
        self.edges.clear()
        self.subplot.clear()
        self.draw_graph()

    def event_in_axes(self, event) -> bool:
        """
        Test if an event is inside the axes of this Panel.

        :param event: The event to check.
        :return: True if the event is inside the axes, False otherwise.x
        """
        return event.inaxes == self.subplot

    def on_press(self, event):
        if not self.event_in_axes(event):
            return
        self.press_start_position = (event.xdata, event.ydata)
        for element in self.elements:
            if element.contains(event)[0]:
                self.pressed_elements[element] = element.get_center()
                dispatcher.connect(receiver=element.on_position_change,
                                   signal='element_position_changed')
                try:
                    # element.on_press(event)
                    self.redraw()
                except AttributeError:
                    pass

    def on_release(self, event):
        if not self.event_in_axes(event):
            return
        self.press_start_position = None
        for element in self.elements:
            if element.contains(event)[0]:
                self.pressed_elements.pop(element)
                dispatcher.disconnect(receiver=element.on_position_change,
                                      signal='element_position_changed')
                try:
                    # element.on_release(event)
                    self.redraw()
                except AttributeError:
                    pass

    def on_pick(self, event):
        pass

    def on_motion(self, event):
        if not self.event_in_axes(event):
            return
        for element in self.elements:
            if element.contains(event)[0]:
                if not element.hovered:
                    element.hovered = True
                    if element.annotation is None \
                            and element.get_hover_text() != '':
                        element.annotation = self.annotate_element(element)
                        self.redraw()
                try:
                    # element.on_motion(event)
                    self.redraw()
                except AttributeError:
                    pass
            else:
                if element.hovered:
                    element.hovered = False
                    if element.annotation is not None \
                            and not opts['show_all_labels']:
                        element.annotation.set_visible(False)
                        element.annotation.remove()
                        element.annotation = None
                        self.redraw()
        # This is a sanity check. With gui interactions it could easily happen
        # that a mouse release occurs is such a way that an inconsistency
        # appears.
        if len(self.pressed_elements) != 0 and self.press_start_position is None:
            self.pressed_elements.clear()
        elif len(self.pressed_elements) > 0:
            dispatcher.send(signal='element_position_changed', sender=self)
            for element, center in self.pressed_elements.items():
                if isinstance(element, FigureVertex):
                    dx = event.xdata - self.press_start_position[0]
                    dy = event.ydata - self.press_start_position[1]
                    element.center = (center[0] + dx, center[1] + dy)


class ProductionGraphsPanel(GraphPanel):
    """
    A container for the plots of two graphs with arrows connecting
    certain elements.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.subplot.remove()
        del self.subplot
        self.subplot = self.figure.add_subplot(121)
        self.subplot2 = self.figure.add_subplot(122)
        self.graph2 = None
        self.setup_mpl_visuals(self.subplot)
        self.setup_mpl_visuals(self.subplot2)
        self.mappings: Set[ConnectionPatch] = set()

    def load_graph(self, graph_data: Tuple[Graph, Mapping, Graph]) -> None:
        """
        Load graphs into the two graph displays.

        :param graph_data: The graphs to load
        """
        self.graph = graph_data[0]
        self.graph2 = graph_data[2]
        self.vertices.clear()
        self.edges.clear()
        self.subplot.clear()
        self.subplot2.clear()
        self.draw_graph(graph=self.graph, axes=self.subplot)
        self.draw_graph(graph=self.graph2, axes=self.subplot2)
        self.draw_mappings(graph_data[1])

    def draw_mappings(self, mapping: Mapping) -> None:
        """
        Draw arrows between the GraphElements that are mapped together.

        :param mapping: A Mapping containing the information on what
                        arrows to draw.
        """
        for graph_element1, graph_element2 in mapping.items():
            figure_element1 = self.graph_to_figure[graph_element1]
            figure_element2 = self.graph_to_figure[graph_element2]
            patch = ConnectionPatch(
                xyA=figure_element1.get_center(),
                xyB=figure_element2.get_center(),
                coordsA="data",
                coordsB="data",
                axesA=self.subplot,
                axesB=self.subplot2,
                arrowstyle="->",
                clip_on=False,
            )
            self.mappings.add(patch)
            self.subplot.add_artist(patch)
        self.redraw()

    def event_in_axes(self, event):
        if event.inaxes == self.subplot.axes \
                or event.inaxes == self.subplot2.axes:
            return True
        else:
            return False


class DraggableCircle(plt.Circle):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pressed = False
        self.start_circ_pos = None
        self.start_mouse_pos = None

    def on_press(self, event):
        if self.contains(event)[0]:
            self.pressed = True
            self.start_circ_pos = self.center
            self.start_mouse_pos = (event.xdata, event.ydata)
            self.set_facecolor('red')

    def on_release(self, _):
        if self.pressed:
            self.pressed = False
            self.start_circ_pos = None
            self.start_mouse_pos = None
            self.set_facecolor('white')

    def on_motion(self, event):
        if event.inaxes != self.axes:
            return


class FigureElement(abc.ABC):
    """
    Visual representation of a GraphElement inside a matplotlib figure.

    This is a base class for all other FigureElements to derive from.
    """

    def __init__(self, graph_element: GraphElement):
        self.graph_element = graph_element
        """The GraphElement that is represented by this FigureElement."""
        self.hovered: bool = False
        """Whether or not this element is currently being hovered over."""
        self.annotation: plt.Annotation = None
        """Saves any matplotlib annotation associated with this Element."""

    def get_hover_text(self) -> str:
        """
        Get and return the on-hover text of the element.

        :return: A string containing the hover text of the element.
        """
        text = ''
        for name, value in self.graph_element.attr.items():
            text += f'{name}: {value}\n'
        return text[:-1]

    @abc.abstractmethod
    def get_center(self) -> Tuple[int, int]:
        """
        Return the center position of this element.

        :return: A tuple containing the centers x and y coordinate.
        """
        raise NotImplementedError()

    def on_position_change(self) -> None:
        """
        Is called when the Position of an Element is changed.
        """
        pass

    def on_press(self, e):
        DraggableCircle.on_press(self, e)

    def on_release(self, e):
        DraggableCircle.on_release(self, e)


class FigureVertex(FigureElement, DraggableCircle):
    """
    The visual representation of a Vertex.
    """

    def __init__(self, graph_element: GraphElement, *args, edges=None,
                 **kwargs):
        FigureElement.__init__(self, graph_element)
        DraggableCircle.__init__(self, *args, **kwargs)
        self.edges: Set[FigureEdge] = set() if edges is None else edges
        """A set containing all Edges connected to this Vertex."""
        for edge in self.edges:
            if self not in {edge.vertex1, edge.vertex2}:
                if edge.vertex1 is None:
                    edge.vertex1 = self
                elif edge.vertex2 is None:
                    edge.vertex2 = self
                else:
                    log.error(f'The FigureVertex was passed Edge {edge} as '
                              f'Argument but the Edge is already connected to '
                              f'two other Vertices.')
                    raise ModelGenArgumentError('Edge is already connected to '
                                                'two other Vertices.')

    def get_center(self) -> Tuple[int, int]:
        return self.center

    def on_position_change(self):
        for edge in self.edges:
            edge.update_position()
        if self.annotation is not None:
            self.annotation.xy = self.center


class FigureEdge(FigureElement, plt.Line2D):
    """
    The visual representation of an Edge.
    """

    def __init__(self, graph_element: GraphElement, *args,
                 vertex1: FigureVertex = None,
                 vertex2: FigureVertex = None, **kwargs):
        FigureElement.__init__(self, graph_element)
        if vertex1 is not None and vertex2 is not None:
            center1 = vertex1.center
            center2 = vertex2.center
            plt.Line2D.__init__(self, (center1[0], center2[0]),
                                (center1[1], center2[1]), *args, **kwargs)
            vertex1.edges.add(self)
            vertex2.edges.add(self)
        else:
            plt.Line2D.__init__(self, *args, **kwargs)
        self.vertex1: FigureVertex = vertex1
        """The first Vertex connected to this Edge."""
        self.vertex2: FigureVertex = vertex2
        """The second Vertex connected to this Edge."""

    def update_position(self):
        """
        Update the position of the Edge based on the connected Edges.
        """
        center1 = self.vertex1.center
        center2 = self.vertex2.center
        self.set_xdata((center1[0], center2[0]))
        self.set_ydata((center1[1], center2[1]))

    def get_center(self) -> Tuple[int, int]:
        x1, x2 = self.get_xdata()
        y1, y2 = self.get_ydata()
        center = (x1 + (x2 - x1) / 2, y1 + (y2 - y1) / 2)
        return center

    def on_position_change(self):
        self.update_position()
        if self.annotation is not None:
            self.annotation.xy = self.get_center()


if __name__ == '__main__':
    log.info('Starting up Model Gen.')
    log.info('Reading in Options.')
    opts = Opts()
    app = wx.App()
    main_frame = GraphUI(None, title="Model Gen Graph Grammar",
                         size=(1000, 500))
    app.MainLoop()
    log.info('Saving Options.')
    opts.save()
