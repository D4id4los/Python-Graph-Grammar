#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import TypeVar, Dict

import wx
import wx.lib.newevent
import yaml

from gui_elements import MainNotebook, EVT_RUN_GRAMMAR
from model_gen.grammar import Grammar
from model_gen.productions import Production
from model_gen.utils import get_logger
from model_gen.graph import Graph
from model_gen.opts import Opts

T = TypeVar('T')



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
        self.global_vars: Dict[str, str] = {}

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
                    result_graphs: Dict[str, Graph],
                    global_vars: Dict[str, str]) -> None:
        log.info('Loading new graphs and productions.')
        self.host_graphs = host_graphs
        self.productions = productions
        self.result_graphs = result_graphs
        self.global_vars = global_vars
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
            host_graphs = self.notebook.host_graph_panel.list.get_data()
            productions = self.notebook.production_panel.list.get_data()
            result_graphs = self.notebook.result_panel.list.get_data()
            data = {
                'host_graphs': {k: v.to_yaml() for k, v in
                                host_graphs.items()},
                'productions': {k: v.to_yaml() for k, v in
                                productions.items()},
                'global_vars': self.global_vars,
                'result_graphs': {k: v.to_yaml() for k, v in
                                  result_graphs.items()}
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
                global_vars = data.get('global_vars', {})
                result_graphs = {k: Graph.from_yaml(v, mapping) for k, v in
                                 data['result_graphs'].items()}
                self.load_graphs(host_graphs, productions, result_graphs, global_vars)
        except IOError:
            log.error(f'Cannon open/read from file »{file_path}«.')
            wx.LogError(f'Cannot open file {file_path}.')

    def run_grammar(self, _) -> None:
        """
        Run the grammar defined by the productions on the active
        hostgraph and add the result to result graphs.
        """
        log.info('Running grammar.')
        grammar = Grammar(self.productions.values(), self.global_vars)
        host_graph = self.notebook.host_graph_panel.get_active()
        if host_graph is None:
            log.error(
                f'Can not run grammar because no host graphs are '
                f'loaded/defined.')
            wx.LogError('Error: No host graphs loaded/defined.')
            return
        results = grammar.apply(host_graph, opts['max_derivations'])
        log.debug(
            f'There where {len(results)} derivations calculated.')
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
