import abc
from typing import Dict, Tuple, Set, MutableSequence, Union
from functools import partial

import wx
from matplotlib import pyplot as plt
from matplotlib.backends.backend_wx import \
    NavigationToolbar2Wx as NavigationToolbar
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.patches import ConnectionPatch
import matplotlib.patheffects as pe
import matplotlib.backend_bases
import matplotlib.artist
from pydispatch import dispatcher

from model_gen.exceptions import ModelGenArgumentError
from model_gen.graph import GraphElement, Graph, Vertex, Edge
from model_gen.utils import Bidict, Mapping, get_logger
from model_gen.opts import Opts

log = get_logger('model_gen.' + __name__)
opts = Opts()


def _get_round_edges_bitmap(width: int, height: int, radius: int):
    """
    Calculate a bitmap for use as a wx frame background with rounded
    corners.

    :param width: Width of the frame.
    :param height: Height of the frame.
    :param radius: Radius of the corner.
    :return: A bitmap for use as a wx frame background.
    """
    mask_color = opts['gui']['attrs']['mask_color']
    background_color = opts['gui']['attrs']['background_color']
    bitmap = wx.Bitmap(width, height)
    dc = wx.MemoryDC(bitmap)
    dc.SetBrush(wx.Brush(mask_color))
    dc.DrawRectangle(0, 0, width, height)
    dc.SetBrush(wx.Brush(background_color))
    dc.SetPen(wx.Pen(background_color))
    dc.DrawRoundedRectangle(0, 0, width, height, radius)
    bitmap.SetMaskColour(mask_color)
    return bitmap


class AttributeEditingFrame(wx.Frame):
    """
    This frame is used to open a small window near a graph element
    to allow editing of the elements attribute.
    """

    def __init__(self, *args, position=(0, 0), element=None, **kwargs):
        style = wx.CLIP_CHILDREN | wx.NO_BORDER \
                | wx.FRAME_SHAPED | wx.FRAME_NO_TASKBAR \
                | wx.FRAME_NO_WINDOW_MENU
        super().__init__(*args, **kwargs, style=style)
        self.SetTransparent(240)
        self.SetPosition(position)
        self._set_frame_shape()
        self.attr_buttons: Dict[int, wx.Button] = {}
        self.attr_labels: Dict[int, wx.TextCtrl] = {}
        self.attr_values: Dict[int, wx.TextCtrl] = {}
        self.attr_ids: Dict[int, str] = {}
        self.element = element
        self.box = wx.BoxSizer(wx.VERTICAL)
        self.flex_grid = wx.FlexGridSizer(0, 0, 0)
        self.add_attr_button = wx.Button(self, wx.ID_ANY, label='+')
        self.box.AddMany([
            (self.flex_grid, 0),
            (self.add_attr_button, 0, wx.ALIGN_LEFT)
        ])
        self.SetSizer(self.box)
        self.Bind(wx.EVT_MOTION, self.on_mouse_movement)
        self.Bind(wx.EVT_BUTTON, self.add_attr, self.add_attr_button)
        self._load_attrs()
        self.Show(True)
        self._drag_start_pos = None

    def _set_frame_shape(self) -> None:
        """
        Sets this frames shape to a rounded rectangle.
        """
        width, height = self.GetSize()
        self.SetShape(wx.Region(_get_round_edges_bitmap(width, height, 10)))

    def _update_attr_list(self) -> None:
        """
        Updates the list of displayed attribute text inputs.
        """
        old_flex_grid = self.flex_grid
        self.flex_grid = wx.FlexGridSizer(cols=3, vgap=5, hgap=10)
        wx_elements = []
        for attr_id in self.attr_ids:
            button = self.attr_buttons[attr_id]
            label_input = self.attr_labels[attr_id]
            value_input = self.attr_values[attr_id]
            wx_elements.extend([
                (button, 0, wx.ALIGN_CENTER_VERTICAL),
                (label_input, 0, wx.EXPAND),
                (value_input, 1, wx.EXPAND)
            ])
        self.flex_grid.AddMany(wx_elements)
        if old_flex_grid is not None:
            self.box.Replace(old_flex_grid, self.flex_grid)
        self.box.Layout()

    def _load_attrs(self) -> None:
        """
        Load the attributes from the connected element.
        """
        self.attr_ids.clear()
        for attr_label, attr_value in self.element.attr.items():
            self.add_attr(None, attr_label, attr_value)
        self._update_attr_list()

    def _save_attrs(self) -> None:
        """
        Save the changes to the attributes to the connected element.
        """
        for attr_id in self.attr_ids:
            orig_label = self.attr_ids[attr_id]
            attr_label = self.attr_labels[attr_id].GetValue()
            attr_value = self.attr_values[attr_id].GetValue()
            if attr_label == '':
                continue
            if orig_label != attr_label and orig_label != '':
                self.element.attr.pop(orig_label)
                self.attr_ids[attr_id] = attr_label
            if attr_label not in self.element.attr \
                    or self.element.attr[attr_label] != attr_value:
                self.element.attr[attr_label] = attr_value

    def add_attr(self, event: Union[wx.CommandEvent, None], attr_label: str = '',
                 attr_value: str = '') -> None:
        """
        Add an attribute to the element on the push of a button.
        :param event: The wx event of pushing a button.
        :param attr_label: The label of the attribute.
        :param attr_value: The value to set the attribute to.
        """
        new_id = len(self.attr_ids)
        self.attr_ids[new_id] = attr_label
        button_remove = wx.Button(self, wx.ID_ANY, label='-')
        self.Bind(wx.EVT_BUTTON, partial(self.remove_attr, attr_id=new_id),
                  button_remove)
        text_label = wx.TextCtrl(self, value=attr_label)
        text_value = wx.TextCtrl(self, value=attr_value)
        self.attr_labels[new_id] = text_label
        self.attr_values[new_id] = text_value
        self.attr_buttons[new_id] = button_remove
        if event is not None:
            self._update_attr_list()

    def remove_attr(self, event: Union[wx.CommandEvent, None],
                    attr_id: Union[int, None]) -> None:
        """
        Remove the specified attribute from the element and the gui.

        :param event: The wx event initiating the action
        :param attr_id: The ID of the attribute to remove.
        """
        self.attr_buttons.pop(attr_id).Destroy()
        self.attr_values.pop(attr_id).Destroy()
        self.attr_labels.pop(attr_id).Destroy()
        attr_label = self.attr_ids.pop(attr_id)
        if attr_label != '':
            self.element.attr.pop(attr_label)
        if event is not None:
            self._update_attr_list()

    def Close(self, *args, **kwargs):
        """
        Override to save changes to arguments before closing the
        frame.
        """
        self._save_attrs()
        super().Close(*args, **kwargs)

    def on_mouse_movement(self, event: wx.MouseEvent) -> None:
        """
        This handles the dragging of the window.

        :param event: The wx event object.
        """
        if not event.Dragging():
            self._drag_start_pos = None
            return
        # self.CaptureMouse()
        if self._drag_start_pos is None:
            self._drag_start_pos = event.GetPosition()
        else:
            current_pos = event.GetPosition()
            change = self._drag_start_pos - current_pos
            self.SetPosition(self.GetPosition() - change)


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
        self.canvas.mpl_connect('key_press_event', self.on_key_press)
        self.canvas.mpl_connect('key_release_event', self.on_key_release)
        self.canvas.mpl_connect('pick_event', self.on_pick)
        self.canvas.mpl_connect('motion_notify_event', self.on_motion)

        self.pressed_elements: Dict[FigureElement, Tuple[float, float]] = {}
        self.press_start_position: Tuple[float, float] = None
        self.pressed_keys: Dict[str, bool] = {}
        self.selected_element: FigureElement = None
        self.attr_editing_window = None

        self.graph: Graph = None
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
            if graph_edge.vertex1 is not None:
                figure_vertex1 = self.graph_to_figure[graph_edge.vertex1]
            else:
                position = free_spaces[i]
                add_new_free_spaces(position, free_spaces)
                figure_vertex1 = FigureVertex(None, position, 0.5,
                                              color='w', ec='w', zorder=10)
                self.vertices.add(figure_vertex1)
                axes.add_artist(figure_vertex1)
                i += 1
            if graph_edge.vertex2 is not None:
                figure_vertex2 = self.graph_to_figure[graph_edge.vertex2]
            else:
                position = free_spaces[i]
                add_new_free_spaces(position, free_spaces)
                figure_vertex2 = FigureVertex(None, position, 0.5,
                                              color='w', ec='w', zorder=10)
                self.vertices.add(figure_vertex2)
                axes.add_artist(figure_vertex2)
                i += 1
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
                 axes: plt.Axes = None) -> Union[plt.Annotation, None]:
        """
        Places an annotation on the subplot.

        :param text: The text to place.
        :param position: The positon of the annotation.
        :param axes: The axes to add the annotation to
        :return: The Annotation object representing the annotation.
        """
        if text == '':
            return None
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
        if element.annotation is not None:
            element.annotation.set_text(element.get_hover_text())
            return element.annotation
        else:
            return self.annotate(element.get_hover_text(),
                                 element.get_center(),
                                 element.axes)

    def _clear_drawing(self) -> None:
        """
        Clears the current drawing and dicts/lists referencing the
        drawn elements.
        """
        self.vertices.clear()
        self.edges.clear()
        self.subplot.clear()
        self.selected_element = None
        self.pressed_elements.clear()

    def _redraw_graph(self) -> None:
        """
        Redraw the currently loaded graph.
        """
        self._clear_drawing()
        self.draw_graph()

    def load_graph(self, graph: Graph) -> None:
        """
        Load and display the passed graph.

        :param graph: The graph to be displayed
        """
        self.graph = graph
        self._redraw_graph()

    def _get_connected_graph(self, axes: plt.Axes) -> Graph:
        """
        Return the graph that is represented by the specified axes.

        :param axes: Axes to which the corresponding graph is to be
            found.
        :return: Graph represented by the Axes.
        """
        if axes == self.subplot:
            return self.graph
        else:
            raise KeyError('Specified Axes could not be found.')

    def add_vertex(self, event: matplotlib.backend_bases.LocationEvent) \
            -> None:
        """
        Adds a vertex to the graph at the position defined by the mpl event.

        :param event: The matplotlib event that initiated the adding.
        """
        log.info(f'Adding Vertex @ {event.x} - {event.y}')
        graph = self._get_connected_graph(event.inaxes)
        vertex = Vertex()
        graph.add(vertex)
        self._redraw_graph()

    def _add_mapping(self, mother_element: GraphElement,
                     daughter_element: GraphElement) -> None:
        """
        Add a mapping between the two elements to the production.

        :param mother_element: The element on the left-hand side of
            the production.
        :param daughter_element: The element on the right-hand side
            of the production.
        """
        pass

    def _add_edge(self, graph: Graph, vertex1: Vertex, vertex2: Vertex) \
            -> None:
        """
        Add an edge between two vertices to a graph.

        :param graph: The graph to add the edge two.
        :param vertex1: The first vertex of the edge.
        :param vertex2: The second vertex of the edge.
        """
        new_edge = Edge(vertex1, vertex2)
        graph.add(new_edge)

    def connect_elements(self, event: matplotlib.backend_bases.LocationEvent,
                         element: 'FigureElement') -> None:
        """
        Connects any two elements if it makes sense in context.

        Adds a new Edge between two vertices, if self.selected_element
        is not None and both vertices are in the same axes. If
        selected_element is None then it sets self.selected_element
        to the vertex passed as argument.

        If two edges are in the same axes nothing happens.

        If any two elements are in two different axes then a mapping
        is created between them.

        :param event: The event that initiated this action.
        :param element: Element to connect to another element.
        """
        if self.selected_element is None:
            self.selected_element = element
            element.add_extra_path_effect('selection',
                                          pe.Stroke(linewidth=5,
                                                    foreground='b'))
            return
        graph = self._get_connected_graph(event.inaxes)
        vertex1 = self.graph_to_figure.inverse[self.selected_element][0]
        vertex2 = self.graph_to_figure.inverse[element][0]
        if self.selected_element.axes != element.axes:
            log.debug('Adding Mapping.')
            self._add_mapping(vertex1, vertex2)
        elif isinstance(vertex1, Vertex) and isinstance(vertex2, Vertex):
            log.debug('Connecting Vertices.')
            self._add_edge(graph, vertex1, vertex2)
        self.selected_element.remove_extra_path_effect('selection')
        self.selected_element = None
        self._redraw_graph()

    def delete_element(self, event: matplotlib.backend_bases.LocationEvent) \
            -> None:
        """
        Removes the hovered Elements from the graph.

        :param event: The matplotlib event that initiated the removal.
        """
        log.info(f'Removing Element(s) @ {event.x} - {event.y}')
        graph = self._get_connected_graph(event.inaxes)
        to_remove = {x for x in self.elements if x.contains(event)[0]}
        log.info(f'Elements to remove are {to_remove}')
        for element in to_remove:
            graph.remove(self.graph_to_figure.inverse[element][0])
        self._redraw_graph()

    def open_attr_editing(self, element) -> None:
        """
        Display a window that allows for editing of an elements
        attributes.
        """
        if self.attr_editing_window is not None:
            self.close_attr_editing()
        else:
            position = wx.GetMousePosition()
            self.attr_editing_window = AttributeEditingFrame(self, wx.ID_ANY,
                                                             position=position,
                                                             element=element)
            figure_element = self.graph_to_figure[element]
            figure_element.annotation = self.annotate_element(figure_element)

    def close_attr_editing(self) -> None:
        """
        Closes an opened element attribute editing window.
        """
        self.attr_editing_window.Close()
        self.attr_editing_window = None

    def event_in_axes(self, event: matplotlib.backend_bases.LocationEvent) \
            -> bool:
        """
        Test if an event is inside the axes of this Panel.

        :param event: The event to check.
        :return: True if the event is inside the axes, False otherwise.x
        """
        return event.inaxes == self.subplot

    # For Checking Keyboard presses during mouse-clicks using the mpl functions
    # results in keys such as Alt getting "stuck", for reasons see:
    # https://stackoverflow.com/a/36837686
    # Therefore I need to use event.guiEvent.CmdDown() and the like.
    def on_press(self, event: matplotlib.backend_bases.MouseEvent):
        if not self.event_in_axes(event):
            return
        if self.attr_editing_window is not None:
            self.close_attr_editing()
            self.redraw()
        if event.button == 1:  # 1 = left click
            self.press_start_position = (event.xdata, event.ydata)
            for element in self.elements:
                if element.contains(event)[0]:
                    if event.guiEvent.ShiftDown() \
                            and self.attr_editing_window is None:
                        self.open_attr_editing(
                            self.graph_to_figure.inverse[element][0])
                    self.pressed_elements[element] = element.get_center()
                    dispatcher.connect(receiver=element.on_position_change,
                                       signal='element_position_changed')

    def on_release(self, event: matplotlib.backend_bases.MouseEvent):
        if not self.event_in_axes(event):
            return
        if event.button == 1:  # 1 = left click
            if event.guiEvent.CmdDown():
                self.add_vertex(event)
                return
            self.press_start_position = None
            for element in self.elements:
                if element.contains(event)[0] \
                        and element in self.pressed_elements:
                    self.pressed_elements.pop(element)
                    dispatcher.disconnect(receiver=element.on_position_change,
                                          signal='element_position_changed')
        elif event.button == 3:  # 3 = right click
            for element in self.vertices | self.edges:
                if element.contains(event)[0]:
                    self.connect_elements(event, element)
                    return
            if self.selected_element is not None:
                self.selected_element.remove_extra_path_effect('selection')
                self.selected_element = None
            self.redraw()

    def on_key_press(self, event: matplotlib.backend_bases.KeyEvent):
        self.pressed_keys[event.key] = True

    def on_key_release(self, event: matplotlib.backend_bases.KeyEvent):
        if (event.key == 'd' and self.pressed_keys['control']) \
                or event.key == 'delete':
            self.delete_element(event)
        self.pressed_keys[event.key] = False

    def on_pick(self, event: matplotlib.backend_bases.PickEvent):
        pass

    def on_motion(self, event: matplotlib.backend_bases.MouseEvent):
        if not self.event_in_axes(event):
            return
        for element in self.elements:
            if element.contains(event)[0]:
                if not element.hovered:
                    element.hovered = True
                    element.on_hover()
                    if element.annotation is None \
                            and element.get_hover_text() != '':
                        element.annotation = self.annotate_element(element)
            else:
                if element.hovered:
                    element.hovered = False
                    element.on_unhover()
                    if element.annotation is not None \
                            and not opts['show_all_labels']:
                        element.annotation.set_visible(False)
                        element.annotation.remove()
                        element.annotation = None
        # This is a sanity check. With gui interactions it could easily happen
        # that a mouse release occurs is such a way that an inconsistency
        # appears.
        if len(self.pressed_elements) != 0 \
                and self.press_start_position is None:
            self.pressed_elements.clear()
        elif len(self.pressed_elements) > 0:
            dispatcher.send(signal='element_position_changed', sender=self)
            for element, center in self.pressed_elements.items():
                if isinstance(element, FigureVertex):
                    dx = event.xdata - self.press_start_position[0]
                    dy = event.ydata - self.press_start_position[1]
                    element.center = (center[0] + dx, center[1] + dy)
        self.redraw()


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
        self.graph2: Graph = None
        self.mapping: Mapping = None
        self.setup_mpl_visuals(self.subplot)
        self.setup_mpl_visuals(self.subplot2)
        self.mappings: Set[ConnectionPatch] = set()

    def _clear_drawing(self) -> None:
        """
        Clears the current drawing and dicts/lists referencing the
        drawn elements.
        """
        self.vertices.clear()
        self.edges.clear()
        self.subplot.clear()
        self.subplot2.clear()

    def _redraw_graph(self) -> None:
        """
        Redraw the currently loaded graphs.
        """
        self._clear_drawing()
        self.draw_graph(graph=self.graph, axes=self.subplot)
        self.draw_graph(graph=self.graph2, axes=self.subplot2)
        self.draw_mappings(self.mapping)

    def load_graph(self, graph_data: Tuple[Graph, Mapping, Graph]) -> None:
        """
        Load graphs into the two graph displays.

        :param graph_data: The graphs to load
        """
        self.graph = graph_data[0]
        self.graph2 = graph_data[2]
        self.mapping = graph_data[1]
        self._clear_drawing()
        self._redraw_graph()

    def _add_mapping(self, mother_element: GraphElement,
                     daughter_element: GraphElement) -> None:
        """
        Add a mapping between the two elements to the production.

        :param mother_element: The element on the left-hand side of
            the production.
        :param daughter_element: The element on the right-hand side
            of the production.
        """
        self.mapping[mother_element] = daughter_element

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
            figure_element1.mapping_left = patch
            figure_element2.mapping_right = patch
            self.mappings.add(patch)
            self.subplot.add_artist(patch)
        self.redraw()

    def _get_connected_graph(self, axes: plt.Axes) -> Graph:
        """
        Return the graph that is represented by the specified axes.

        :param axes: Axes to which the corresponding graph is to be
            found.
        :return: Graph represented by the Axes.
        """
        if axes == self.subplot:
            return self.graph
        elif axes == self.subplot2:
            return self.graph2
        else:
            raise KeyError('Specified Axes could not be found.')

    def event_in_axes(self, event: matplotlib.backend_bases.LocationEvent):
        if event.inaxes == self.subplot.axes \
                or event.inaxes == self.subplot2.axes:
            return True
        else:
            return False


class FigureElement(matplotlib.artist.Artist):
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
        self.mapping_left: ConnectionPatch = None
        """Saves the ConnectionPatch if this element is on the left hand side
        of the production."""
        self.mapping_right: ConnectionPatch = None
        """Saves the ConnectionPatch if this element is on the right hand side
        of the production."""
        self.extra_path_effects: Dict[str, pe.AbstractPathEffect] = {}
        """Saves a dict mapping text labels to applied path effects."""

    def get_hover_text(self) -> str:
        """
        Get and return the on-hover text of the element.

        :return: A string containing the hover text of the element.
        """
        if self.graph_element is None:
            return ''
        text = ''
        for name, value in self.graph_element.attr.items():
            text += f'{name}: {value}\n'
        return text[:-1]

    def add_extra_path_effect(self, name: str,
                              effect: pe.AbstractPathEffect) -> None:
        """
        Add an extra path effect to the element.

        :param name: Name of the effect.
        :param effect: The effect to add.
        """
        self.extra_path_effects[name] = effect

    def remove_extra_path_effect(self, name: str):
        """
        Removes the path effect with the specified name from the
        element.

        :param name: Name of the path effect to remove.
        """
        self.extra_path_effects.pop(name)

    def on_hover(self) -> None:
        """
        Called when the element is hovered.
        """

    def on_unhover(self) -> None:
        """
        Called when an element stops being hovered.
        """

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


class FigureVertex(FigureElement, plt.Circle):
    """
    The visual representation of a Vertex.
    """

    def __init__(self, graph_element: Union[GraphElement, None], *args,
                 edges=None,
                 **kwargs):
        FigureElement.__init__(self, graph_element)
        plt.Circle.__init__(self, *args, **kwargs)
        self.edges: Set[FigureEdge] = set() if edges is None else edges
        """A set containing all Edges connected to this Vertex."""
        if graph_element is None:
            self.set_color('w')
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

    def update_path_effects(self) -> None:
        """
        Updates the applied path effects.
        """
        effects = list(self.extra_path_effects.values())
        effects.append(pe.Normal())
        self.set_path_effects(effects)

    def add_extra_path_effect(self, name: str,
                              effect: pe.AbstractPathEffect) -> None:
        """
        Add an extra path effect to the element.

        :param name: Name of the effect.
        :param effect: The effect to add.
        """
        super().add_extra_path_effect(name, effect)
        self.update_path_effects()

    def remove_extra_path_effect(self, name: str):
        """
        Removes the path effect with the specified name from the
        element.

        :param name: Name of the path effect to remove.
        """
        super().remove_extra_path_effect(name)
        self.update_path_effects()

    def on_position_change(self):
        for edge in self.edges:
            edge.on_position_change()
        if self.annotation is not None:
            self.annotation.xy = self.center
        if self.mapping_left is not None:
            self.mapping_left.xy1 = self.center
        if self.mapping_right is not None:
            self.mapping_right.xy2 = self.center

    def on_hover(self):
        log.debug(f'Setting path effect on {self}')
        self.add_extra_path_effect('hover',
                                   pe.Stroke(linewidth=3, foreground='r'))

    def on_unhover(self):
        log.debug(f'Unsetting path effect on {self}')
        self.remove_extra_path_effect('hover')


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

    def update_path_effects(self) -> None:
        """
        Updates the applied path effects.
        """
        effects = list(self.extra_path_effects.values())
        effects.append(pe.Normal())
        self.set_path_effects(effects)

    def add_extra_path_effect(self, name: str,
                              effect: pe.AbstractPathEffect) -> None:
        """
        Add an extra path effect to the element.

        :param name: Name of the effect.
        :param effect: The effect to add.
        """
        super().add_extra_path_effect(name, effect)
        self.update_path_effects()

    def remove_extra_path_effect(self, name: str):
        """
        Removes the path effect with the specified name from the
        element.

        :param name: Name of the path effect to remove.
        """
        super().remove_extra_path_effect(name)
        self.update_path_effects()

    def on_position_change(self):
        self.update_position()
        if self.annotation is not None:
            self.annotation.xy = self.get_center()
        if self.mapping_left is not None:
            self.mapping_left.xy1 = self.get_center()
        if self.mapping_right is not None:
            self.mapping_right.xy2 = self.get_center()

    def on_hover(self):
        log.debug(f'Setting path effect on {self}')
        self.add_extra_path_effect('hover',
                                   pe.Stroke(linewidth=3, foreground='r'))

    def on_unhover(self):
        log.debug(f'Unsetting path effect on {self}')
        self.remove_extra_path_effect('hover')
