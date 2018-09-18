from grammar import *
from productions import *

from model_gen.graph import *

import wx
import wx.lib.agw.aui as aui
from matplotlib.figure import Figure
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as Canvas
from matplotlib.backends.backend_wxagg import NavigationToolbar2WxAgg as Toolbar


class Plot(wx.Panel):
    def __init__(self, parent, id=-1, dpi=None, **kwargs):
        wx.Panel.__init__(self, parent, id=id, **kwargs)
        self.figure = Figure(dpi=dpi, figsize=(2, 2))
        self.canvas = Canvas(self, -1, self.figure)
        self.toolbar = Toolbar(self.canvas)
        self.toolbar.Realize()

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(self.canvas, 1, wx.EXPAND)
        sizer.Add(self.toolbar, 0, wx.LEFT | wx.EXPAND)
        self.SetSizer(sizer)


class PlotNotebook(wx.Panel):
    def __init__(self, parent, id=-1):
        wx.Panel.__init__(self, parent, id=id)
        #self.nb = wx.Notebook(self)
        self.nb = aui.AuiNotebook(self)
        sizer = wx.BoxSizer()
        sizer.Add(self.nb, 1, wx.EXPAND)
        self.SetSizer(sizer)

    def add(self, name="plot"):
        page = Plot(self.nb)
        self.nb.AddPage(page, name)
        return page.figure

class A:
    def get_value(self):
        return 'a'
    def print(self):
        print(self.get_value())
class B(A):
    def get_value(self):
        return 'b'

if __name__ == '__main__':
    b = B()
    b.print()
    # app = wx.App()
    # frame = wx.Frame(None, wx.ID_ANY, 'TEST GUI')
    # plotter = PlotNotebook(frame)
    # axes1 = plotter.add('figure 1').gca()
    # axes1.plot([1, 2, 3], [2, 1, 4])
    #axes2 = plotter.add('figure 2').gca()
    #axes2.plot([1, 2, 3, 4, 5], [2, 1, 4, 2, 3])
    # frame.Show()
    # app.MainLoop()

    # host_graphs = {}
    # productions = {}
    # result_graphs = {}
    #
    # h1 = Graph()
    # hv1_1 = Vertex()
    # hv1_1.attr['label'] = 'a'
    # hv1_2 = Vertex()
    # he1_1 = Edge(hv1_1, hv1_2)
    # he1_1.attr['label'] = '_1'
    # h1.add_elements([hv1_1, hv1_2, he1_1])
    # host_graphs['Host 1'] = h1
    # m1 = Graph()
    # mv1_1 = Vertex()
    # mv1_1.attr['label'] = 'a'
    # m1.add_elements([mv1_1])
    # host_graphs['Mother 1'] = m1
    # d1 = Graph()
    # dv1_1 = Vertex()
    # dv1_2 = Vertex()
    # dv1_2.attr['label'] = 'a'
    # de1_1 = Edge(dv1_1, dv1_2)
    # de1_1.attr['label'] = '_2'
    # d1.add_elements([dv1_1, dv1_2, de1_1])
    # host_graphs['Daughter 1'] = d1
    # host_graphs['Daughter copy'] = copy.deepcopy(d1)
    # e1 = Mapping()
    # e1[mv1_1] = dv1_1
    # dm1 = ProductionOption(m1, e1, d1)
    # p1 = Production(m1, [dm1])
    # productions['Production 1'] = p1
    # g1 = Grammar([p1])
    # results = g1.apply(h1, 2)
    # for i, result in enumerate(results):
    #     result_graphs[f'Derivation {i}'] = result
    #
