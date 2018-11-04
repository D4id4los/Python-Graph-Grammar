from typing import Dict, Tuple

import wx
import wx.lib.newevent
from wx.lib.agw import aui as aui

from graph import Graph
from gui_graphs import GraphPanel, ProductionGraphsPanel
from productions import Production
from utils import Mapping

RunGrammarEvent, EVT_RUN_GRAMMAR = wx.lib.newevent.NewCommandEvent()

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

    def get_data(self) -> Dict[str, Graph]:
        """
        Get the graph data associated with this list of graphs.

        :return: A dictionary with all the data about the Graphs.
        """
        result = {name: graph for name, graph in self.graphs.values()}
        return result

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


class GrammarTree(wx.TreeCtrl):
    """
    Used to display grammars, sub-grammars and their productions in a
    list from which an active production can be selected for detailed
    display.
    """
    def __init__(self, *args, production_graph_panel, **kwargs):
        super().__init__(*args, **kwargs)
        self.AddRoot('Grammar')


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
        self.graphs: Dict[int, Tuple[Graph, Mapping, Graph, Dict]] = {}
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
                attr_requirements = daughter_mapping.attr_requirements
                new_index = index + sub_index
                self.InsertItem(new_index, name)
                self.SetItem(new_index, 1, f'Daughter {sub_index}')
                self.productions[new_index] = (name, production, sub_index)
                self.graphs[new_index] = (mother_graph, mapping, daughter_graph,
                                          attr_requirements)

    def get_data(self) -> Dict[str, Production]:
        """
        Get the production data associated with this production list.

        :return: A dictionary with all the data about the productions.
        """
        result = {name: production for name, production, _ in
                  self.productions.values()}
        return result

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