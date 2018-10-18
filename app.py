"""
@author: phdenzel

Use glass to read glass .state in 'GLASS mode' and show individual models one by one

Usage:
    python model_zapper.py [gls.state]

TODO:
    - perform tests and decide whether it's better to flush the buffer permanently
    - find easy way to generally fix styling differences with different macOS versions
    - perform virtualbox tests on different OSs
"""
# Imports
import sys
import os

app_root = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
libspath = os.path.join(app_root, 'libs')
if os.path.exists(libspath):
    libs = os.listdir(libspath)[::-1]
    for l in libs:
        lib = os.path.join(libspath, l)
        if lib not in sys.path and not any(['glass' in p for p in sys.path]):
            sys.path.insert(2, lib)

includespath = os.path.join(app_root, 'includes')
if os.path.exists(includespath):
    includes = os.listdir(includespath)[::-1]
    for i in includespath:
        inc = os.path.join(includespath, i)
        if 'LD_LIBRARY_PATH' in os.environ:
            if inc not in os.environ['LD_LIBRARY_PATH']:
                os.environ['LD_LIBRARY_PATH'] += ':'+inc
        else:
            os.environ['LD_LIBRARY_PATH'] = inc

import warnings
import numpy as np
import matplotlib
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['font.sans-serif'] = 'DejaVu Sans'
matplotlib.rcParams['text.usetex'] = False
matplotlib.rcParams['figure.figsize'] = (8, 6)
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
import matplotlib.backends.tkagg as tkagg
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from PIL import Image, ImageTk
if sys.version_info.major < 3:
    import Tkinter as tk
    # import ttk
    import tkFileDialog as filedialog
elif sys.version_info.major == 3:
    import tkinter as tk
    import tkinter.filedialog as filedialog
    # import tkinter.ttk as ttk
else:
    raise ImportError("Could not import Tkinter")

from glass.command import command


class Zapp(tk.Frame, object):
    """
    Model zapper for GLASS states
    """
    __version__ = "0.2.0"
    def __init__(self, master, gls_states=[], selection=None, **kwargs):
        """
        Initialize with reference to master Tk

        Args:
            master <Tk object> - master root of the frame

        Kwargs:
            gls_states <list(glass.Environment objects)> - glass environments from state files
            selection <list(int)> - preload a model selection
            verbose <bool> -  verbose mode; print command line statements

        Return:
            <Zapp object> - standard initializer
        """
        # default naming convention
        name = kwargs.pop('name', self.__class__.__name__.lower())
        verbose = kwargs.pop('verbose', False)
        themecolor1 = 'white smoke'
        themecolor2 = 'SlateBlue1'

        # GLASS initializations
        self.gls = gls_states
        self.g_index = len(self.gls)-1  # latest addition
        for g in self.gls:
            g.make_ensemble_average()
        if selection:
            self.model_selection = set(selection)
        else:
            self.model_selection = set([])
        self.model_mappings = ['arrival time', 'mass', 'kappa(R)', 'kappa(<R)',
                               'Hubble time', 'Hubble constant', 'time delays',
                               'shear(R)', 'shear']

        # Tk initializations
        tk.Frame.__init__(self, master, name=name, **kwargs)
        self.master.title('Zapp')
        self.master.protocol('WM_DELETE_WINDOW', self._on_close)
        self.canvas = tk.Canvas(self, name='canvas', borderwidth=0, highlightthickness=0,
                                width=650, height=500, bg='grey', **kwargs)
        self.img_buffer = None

        # Sidebar buttons, entry boxes, and other stuff
        self.buttons = {}
        self.labels = {}
        self.limits = {}

        self.labels['model'] = tk.Label(self, text=u'Model  ( \u25BC | \u25B2 )')
        self.model_map = tk.StringVar()
        self.model_map.set(self.model_mappings[0])
        self.model_option = tk.OptionMenu(self, self.model_map, "", *self.model_mappings)
        self.model_option.configure(width=11, highlightthickness=0)
        self.labels['object'] = tk.Label(self, text="Lens")
        self.lens_selection = tk.Spinbox(
            self, from_=0, to=len(self.models()[0]['obj,data'])-1, wrap=True,
            command=self._on_lens_switch,
            width=5, borderwidth=0,
            highlightcolor=themecolor2)

        self.labels['selection'] = tk.Label(self, text='Model selection')
        self.buttons['next'] = tk.Button(self, width=15, text=u"Next ( \ / \u25B6 )",
                                         command=self.next,
                                         borderwidth=0,
                                         highlightcolor=themecolor2, activeforeground='white')
        self.buttons['back'] = tk.Button(self, width=15, text=u"Back ( \u232B / \u25C0 )",
                                         command=self.back,
                                         borderwidth=0,
                                         activebackground=themecolor2, activeforeground='white')
        self.buttons['tag'] = tk.Button(self, width=15, text=u"Tag (\u23B5)", command=self.tag,
                                        borderwidth=0,
                                        activebackground=themecolor2, activeforeground='white')

        self.labels['limits'] = tk.Label(self, text='Subset selection')
        self.limits['min'] = tk.Spinbox(self, from_=0, to=len(self.models()),
                                        command=self._on_subselection, wrap=True,
                                        width=5, borderwidth=0,
                                        highlightcolor=themecolor2)
        self.limits['max'] = tk.Spinbox(self, from_=0, to=len(self.models()),
                                        command=self._on_subselection, wrap=True,
                                        width=5, borderwidth=0,
                                        highlightcolor=themecolor2)
        self.model_min = 0
        self.model_max = len(self.models())
        self.selection = tk.Spinbox(self, from_=self.model_min, to=self.model_max-1,
                                    command=self._on_selection, wrap=True,
                                    width=5, borderwidth=0,
                                    highlightcolor=themecolor2)
        self.model_index = 0

        self.labels['H0_filter'] = tk.Label(self, text='H0 filter (km/s/Mpc):\n[{}]')
        dist = self.H0_dist()
        distmin, distmax = int(min(dist)//1), int((max(dist)+1)//1)
        self.limits['H0_min'] = tk.Spinbox(self, from_=distmin, to=distmax,
                                           command=self._on_H0filter, wrap=True,
                                           width=5, borderwidth=0,
                                           highlightcolor=themecolor2)
        self.limits['H0_max'] = tk.Spinbox(self, from_=distmin, to=distmax,
                                           command=self._on_H0filter, wrap=True,
                                           width=5, borderwidth=0,
                                           highlightcolor=themecolor2)
        self.H0_min = distmin
        self.H0_max = distmax
        self.labels['H0_filter'].configure(
            text='H0 filter (km/s/Mpc):\n[{}]'.format(len(self.H0filter())))

        self.buttons['save'] = tk.Button(self, width=15, text=u"Save ( Ctrl+S )",
                                         command=self.save,
                                         borderwidth=0,
                                         activebackground=themecolor2, activeforeground='white')
        self.buttons['write'] = tk.Button(self, width=15, text=u"Write ( Ctrl+W )",
                                          command=self.write,
                                          borderwidth=0,
                                          activebackground=themecolor2, activeforeground='white')
        self.buttons['load'] = tk.Button(self, width=15, text=u"Load ( Ctrl+Y )",
                                         command=self.load,
                                         borderwidth=0,
                                         activebackground=themecolor2, activeforeground='white')
        self.buttons['clrselection'] = tk.Button(self, width=13, text=u"Clear selection",
                                                 command=self.clear_selection,
                                                 borderwidth=0,
                                                 activebackground=themecolor2,
                                                 activeforeground='white')
        self.buttons['clrbuffer'] = tk.Button(self, width=10, text=u"Clear buffer",
                                              command=self.clear_buffer,
                                              borderwidth=0,
                                              activebackground=themecolor2,
                                              activeforeground='white')

        # add some more colors
        self.configure(background=themecolor1)
        for l in self.labels:
            self.labels[l]['bg'] = self.labels[l].master['bg']
        for b in self.buttons:
            self.buttons[b].configure(highlightbackground=self.buttons[b].master['bg'])

        # configure frame grid
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.grid(sticky=tk.N+tk.S+tk.E+tk.W)
        grid_placement = [(0, 0, 1, tk.NW),
                          (1, 0, 1, tk.N),
                          (2, 0, 1, tk.NW), (2, 1, 1, tk.NW),
                          (3, 0, 1, tk.NW), (3, 1, 1, tk.NW),
                          (5, 0, 1, tk.N),
                          (6, 0, 1, tk.N),
                          (7, 0, 1, tk.N),
                          (8, 0, 1, tk.NW),
                          (9, 0, 1, tk.N), (9, 1, 1, tk.NW),
                          (10, 0, 1, tk.NW),
                          (11, 0, 1, tk.N), (11, 1, 1, tk.NW),
                          (12, 0, 1, tk.NW), (12, 1, 1, tk.NW),
                          (13, 0, 1, tk.NW),
                          (14, 0, 1, tk.NW), (14, 1, 1, tk.NW),
                          (0, 2, 15, tk.NSEW)]
        grid_objects = [self.labels['model'],
                        self.model_option,
                        self.labels['object'], self.lens_selection,
                        self.labels['selection'], self.selection,
                        self.buttons['next'],
                        self.buttons['back'],
                        self.buttons['tag'],
                        self.labels['limits'],
                        self.limits['min'], self.limits['max'],
                        self.labels['H0_filter'],
                        self.limits['H0_min'], self.limits['H0_max'],
                        self.buttons['save'], self.buttons['write'],
                        self.buttons['load'],
                        self.buttons['clrselection'], self.buttons['clrbuffer'],
                        self.canvas]
        for pos, o in zip(grid_placement, grid_objects):
            o.grid(row=pos[0], column=pos[1], rowspan=pos[2], sticky=pos[3],
                   padx=10, pady=10)
        self.rowconfigure(max([g[0] for g in grid_placement]), weight=2)
        self.columnconfigure(2, weight=1)

        # bind keys to the canvas
        # careful! binding MouseWheel causes UnicodeDecodeError on MacOS Tcl/Tk < 8.6
        self.canvas.bind("<Configure>", self._on_resize)
        self.master.bind("<\>", self.next)
        self.master.bind("<BackSpace>", self.back)
        self.master.bind("<Right>", self.next)
        self.master.bind("<Left>", self.back)
        self.master.bind("<Up>", self.back_property)
        self.master.bind("<Down>", self.next_property)
        self.master.bind("<space>", self.tag)
        self.master.bind("<Escape>", self._on_close)
        self.master.bind("<Control-s>", self.save)
        self.master.bind("<Control-w>", self.write)
        self.master.bind("<Control-y>", self.load)
        self.selection.bind("<Return>", self._on_selection)
        self.lens_selection.bind("<Return>", self._on_lens_switch)
        self.model_map.trace('w', lambda name, index, mode: self._on_selection())
        self.limits['min'].bind("<Return>", self._on_subselection)
        self.limits['max'].bind("<Return>", self._on_subselection)
        self.limits['H0_min'].bind("<Return>", self._on_H0filter)
        self.limits['H0_max'].bind("<Return>", self._on_H0filter)

        # set up the menu
        self.menubar = tk.Menu(self.master, tearoff=0, activeborderwidth=0)
        self.filemenu = tk.Menu(self.menubar, tearoff=0, activeborderwidth=0)
        self.filemenu.add_command(label="Open...", command=self.open_as)
        self.filemenu.add_command(label="Load selection...", command=self.load_as)
        # self.filemenu.add_command(label="Save selection", command=self.save)
        self.filemenu.add_command(label="Save selection as...", command=self.save_as)
        # self.filemenu.add_command(label="Write state", command=self.write)
        self.filemenu.add_command(label="Write state as...", command=self.write_as)
        self.filemenu.add_command(label="Clear", command=self.clear_selection)
        self.filemenu.add_command(label="Clear All", command=self.clear_all)
        self.filemenu.add_command(label="Exit", command=self._on_close)
        self.menubar.add_cascade(label="File", menu=self.filemenu)

        self.helpmenu = tk.Menu(self.menubar, tearoff=0, activeborderwidth=0)
        self.helpmenu.add_command(label="Help", command=self.help_link)
        self.helpmenu.add_command(label="About...", command=self.about)
        self.menubar.add_cascade(label="Help", menu=self.helpmenu)

        self.master.configure(menu=self.menubar)
        # Connect to Apple Finder events
        self.master.createcommand("::tk::mac::OpenDocument", self.open)

        if verbose:
            print(self.__v__)

    @classmethod
    def init(cls, gls_states=[], verbose=False):
        """
        From files initialize a Zapper instance together with it's tk root

        Args:
            None

        Kwargs:
            gls_states <list(glass.Environment objects)> - glass environments from state files
            verbose <bool> -  verbose mode; print command line statements

        Return:
            root <Tk object> - the master Tk object
            zapper <Zapper object> - the actual app frame
        """
        root = tk.Tk()
        zapper = Zapp(root, gls_states=gls_states, verbose=verbose)
        return root, zapper

    def __str__(self):
        return "{0:}{1:}({2:}x{3:})".format(self.master, self.__class__.__name__,
                                            self.winfo_width(), self.winfo_height())

    def __repr__(self):
        return self.__str__()

    def help_link(self):
        """
        Follow the help URL to the GitHub wiki page

        Args/Kwargs/Return:
            None
        """
        import webbrowser
        helpurl = "https://github.com/phdenzel/model-zapper/blob/master/README.org"
        webbrowser.open(helpurl, new=0)

    def about(self):
        """
        Show an About window for some infos and links

        Args/Kwargs/Return:
            None
        """
        import webbrowser
        filewin = tk.Toplevel(self.master)
        ffilewin = tk.Frame(filewin)
        # enable resizing
        ffilewin.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        filewin.columnconfigure(0, weight=1)
        filewin.rowconfigure(0, weight=1)
        ffilewin.columnconfigure(0, weight=1)
        ffilewin.rowconfigure(1, weight=1)
        # create widgets
        title = tk.Label(ffilewin, text="ModelZapper", font=("Deja Vu Sans", 28))
        # add logo to img buffer
        if not hasattr(self, '_img_buffer'):
            self._img_buffer = {}
        self._img_buffer['logo'] = ImageTk.PhotoImage(
            Image.open('imgs/zapper.iconset/icon_128x128.png'))
        logo = tk.Label(ffilewin, image=self._img_buffer['logo'])
        modelzapper_url = tk.Label(ffilewin, text=r"https://github.com/phdenzel/model-zapper",
                                   fg='blue', cursor='pointinghand')
        msg_text = "\n".join([
            "ModelZapper Version {}".format(Zapp.__version__),
            "powered by",
            self.glsdoc])
        msg = tk.Label(ffilewin, text=msg_text, font=("Deja Vu Sans", 14))
        glass_url = tk.Label(ffilewin, text=r"https://github.com/jpcoles/glass",
                             fg="blue", cursor="pointinghand")
        statement = tk.Label(
            ffilewin, text=u"Copyright \u00A9 2018, " \
            + "Philipp Denzel <phdenzel@gmail.com>, " \
            + "All Rights Reserved")
        # place the widgets
        title.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        logo.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        modelzapper_url.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        msg.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        glass_url.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        statement.grid(sticky=tk.N+tk.E+tk.S+tk.W)
        # make actual links out of the url labels
        modelzapper_url.bind("<Button-1>", lambda event: webbrowser.open(modelzapper_url['text'], new=0))
        glass_url.bind("<Button-1>", lambda event: webbrowser.open(glass_url['text'], new=0))

    @property
    def glsdoc(self):
        if self.gls:
            return self.gls[self.g_index].meta_info['glheader'].replace('\n', '\t')
        else:
            return "GLASS - A parallel, free-form gravitational lens modeling tool and framework"

    @property
    def tests(self):
        """
        A list of attributes being tested when calling __v__

        Args/Kwargs:
            None

        Return:
            tests <list(str)> - a list of test variable strings
        """
        return ['__doc__', 'model_property', 'model_mappings', 'model_index',
                'obj_index', '_img_copy', 'img_buffer']

    @property
    def __v__(self):
        """
        Info string for test printing

        Args/Kwargs:
            None

        Return:
            <str> - test of the classes attributes
        """
        return "\n".join([t.ljust(20)+"\t{}".format(self.__getattribute__(t)) for t in self.tests])

    @property
    def state_filename(self):
        """
        Wrapper for gls[0].global_opts['argv'][-1]
        """
        return os.path.basename(self.gls[0].global_opts['argv'][-1])

    def models(self, selection=None):
        """
        The glass state's models

        Args/Kwargs:
            None

        Return:
            models <list(dict)> - the glass model dictionary list
        """
        if not self.gls:
            return [{'obj,data': [(0, 0)]}]
        if selection:
            models = [self.gls[self.g_index].models[i] for i in selection]
        else:
            models = self.gls[self.g_index].models
        return models

    @property
    def model_index(self):
        """
        The model index is determined by the selection <Spinbox object>

        Args/Kwargs:
            None

        Return:
            index <int> - the model index of the glass models
        """
        try:
            index = int(self.selection.get())
        except ValueError:
            index = None
        return index

    @model_index.setter
    def model_index(self, value):
        """
        Set the model index to a given value

        Args:
            value <int/str> - value to be assigned to model_index

        Kwargs/Return:
            None
        """
        strv = str(value)
        self.selection.delete(0, tk.END)
        self.selection.insert(0, strv)
        self._on_selection()

    @property
    def model_property(self):
        """
        Wrapper for the StringVal getter

        Args/Kwargs:
            None

        Return:
            model_property <str> - the model property string (from self.model_options)
        """
        return self.model_map.get()

    def next_property(self, event=None):
        """
        Switch to the next model property

        Args/Kwargs/Return:
            None
        """
        cidx = self.model_mappings.index(self.model_map.get())
        nextidx = (cidx + 1) % len(self.model_mappings)
        self.model_map.set(self.model_mappings[nextidx])
        self.load_image()

    def back_property(self, event=None):
        """
        Switch to the last model property

        Args/Kwargs/Return:
            None
        """
        cidx = self.model_mappings.index(self.model_map.get())
        nextidx = (cidx - 1) % len(self.model_mappings)
        self.model_map.set(self.model_mappings[nextidx])
        self.load_image()

    @property
    def obj_index(self):
        """
        Index of the current lens object (always 0 if only a single lens was modeled)
        The object index is determined by the lens_selection <Spinbox object>

        Args/Kwargs:
            None

        Return:
            obj_index <int> - integer index of the current lens object
        """
        try:
            index = int(self.lens_selection.get())
        except ValueError:
            index = 0
        return index

    @obj_index.setter
    def obj_index(self, idx):
        """
        Setter for the lens object index

        Args:
            idx <int> - integer index which changes the current object index

        Kwargs/Return:
            None
        """
        strv = str(idx)
        self.lens_selection.delete(0, tk.END)
        self.lens_selection.insert(0, strv)

    @property
    def model_max(self):
        """
        The model index maximum limit is determined by the limits['max'] <Spinbox object>

        Args/Kwargs:
            None

        Return:
            modelmax <int> - the upper model index limit of the glass models
        """
        N = len(self.models())
        try:
            modelmax = min(int(self.limits['max'].get()), N)
        except ValueError:
            modelmax = N
        return modelmax

    @model_max.setter
    def model_max(self, value):
        """
        Set the model max limit to a given value

        Args:
            value <int/str> - value to be assigned to model_max

        Kwargs/Return:
            None
        """
        strv = str(value)
        self.limits['max'].delete(0, tk.END)
        self.limits['max'].insert(0, strv)

    @property
    def model_min(self):
        """
        The model index minimum limit is determined by the limits['min'] <Spinbox object>

        Args/Kwargs:
            None

        Return:
            modelmin <int> - the lower model index limit of the glass models
        """
        try:
            modelmin = max(int(self.limits['min'].get()), 0)
        except ValueError:
            modelmin = 0
        return modelmin

    @model_min.setter
    def model_min(self, value):
        """
        Set the model min limit to a given value

        Args:
            value <int/str> - value to be assigned to model_min

        Kwargs/Return:
            None
        """
        strv = str(value)
        self.limits['min'].delete(0, tk.END)
        self.limits['min'].insert(0, strv)

    def H0_dist(self, key='accepted'):
        """
        The state's Hubble rate distribution

        Args:
            None

        Kwargs:
            key <str> - key <str> - model selector key (not_accepted, accepted, no_tag)

        Return:
            dist <list()> - distribution of the model's Hubble rate
        """
        dist = [[], [], []]  # 0: not_accepted; 1: accepted; 2: notag
        for m in self.models():
            obj, data = m['obj,data'][self.obj_index]
            if data and 'H0' in data:
                # False = 0; True = 1; default = 2
                dist[m.get(key, 2)].append(data['H0'])
        if dist[True]:
            return dist[True]
        else:
            return [0]

    def H0filter(self):
        """
        Filter models lying within a certain range of Hubble rates
        """
        filtered = []
        for i, m in enumerate(self.models()):
            obj, data = m['obj,data'][self.obj_index]
            if data and 'H0' in data:
                h = data['H0']
                if h <= self.H0_max and h >= self.H0_min:
                    filtered.append(i)
        return filtered

    @property
    def H0lim(self):
        """
        The minimal and maximal values of the H0 distribution of the models

        Args/Kwargs:
            None

        Return:
            limits <float,float> - lower and upper limits of the H0 distribution
        """
        return [float(self.limits[l].get()) for l in ['H0_min', 'H0_max']]

    @property
    def H0_max(self):
        """
        The H0 filter maximum is determined by the limits['H0_max'] <Spinbox object>

        Args/Kwargs:
            None

        Return:
            H0_max <int> - the H0 filter maximum
        """
        try:
            hmax = min(float(self.limits['H0_max'].get()), self.H0lim[1])
        except ValueError:
            hmax = self.H0lim[1]
        return hmax

    @H0_max.setter
    def H0_max(self, value):
        """
        Set the H0 max limit to a given value

        Args:
            value <int/str> - value to be assigned to H0_max

        Kwargs/Return:
            None
        """
        strv = str(value)
        self.limits['H0_max'].delete(0, tk.END)
        self.limits['H0_max'].insert(0, strv)

    @property
    def H0_min(self):
        """
        The H0 filter minimum is determined by the limits['H0_min] <Spinbox object>

        Args/Kwargs:
            None

        Return:
            H0_min <int> - the H0 filter minimum
        """
        try:
            hmin = max(float(self.limits['H0_min'].get()), self.H0lim[0])
        except ValueError:
            hmin = self.H0lim[0]
        return hmin

    @H0_min.setter
    def H0_min(self, value):
        """
        Set the H0 min limit to a given value

        Args:
            value <int/str> - value to be assigned to H0_min

        Kwargs/Return:
            None
        """
        strv = str(value)
        self.limits['H0_min'].delete(0, tk.END)
        self.limits['H0_min'].insert(0, strv)

    def next(self, event=None):
        """
        Increments the model index
        """
        index = min(self.model_index + 1, self.model_max-1)
        filtered = self.H0filter()
        while index not in filtered:
            index = (index + 1) % (self.model_max-1)
        self.model_index = index

    def back(self, event=None):
        """
        Decrements the model index
        """
        index = max(self.model_index - 1, self.model_min)
        filtered = self.H0filter()
        while index not in filtered:
            index = (index - 1) % (self.model_max-1)
        self.model_index = index

    def tag(self, event=None):
        """
        Tag the model index
        """
        selected = self.model_index
        if selected in self.model_selection:
            self.model_selection.remove(selected)
        else:
            self.model_selection.update([selected])
        self.load_image()

    def open(self, name='filtered.state'):
        """
        Open a state file for zapping
        """
        state_file = name
        state = loadstate(state_file)
        if state not in self.gls:
            self.gls.append(state)
        else:
            self.gls.remove(state)
            self.gls.append(state)
        self.grid_forget()
        self.clear_buffer(all_=True)
        self.clear_selection(all_=True)
        self.__init__(self.master, gls_states=self.gls, selection=self.model_selection)
        self.load_image()

    def open_as(self):
        """
        Dialog-open a state file for zapping
        """
        fin = filedialog.askopenfilename(parent=self.master, defaultextension=".state")
        if fin:
            self.open(name=fin)

    def open_state(self):
        """
        """
        pass

    def load(self, event=None, name="model_selection.dat"):
        """
        Load a text file containing the model selection
        """
        print("Loading {}".format(name))
        with open(name, "r") as f:
            selection = [int(s.strip()) for s in f.readlines() if not s.startswith('#')]
        self.model_selection = set(sorted(selection))
        self.load_image()

    def load_as(self):
        """
        Dialog-load a text file containing the model selection
        """
        fin = filedialog.askopenfilename(parent=self.master, defaultextension=".dat")
        if fin:
            self.load(name=fin)

    def save(self, event=None, name="model_selection.dat"):
        """
        Save a text file containing the model selection
        """
        print("Saving {}".format(name))
        with open(name, "w") as f:
            f.write("".join(["# ", self.state_filename, "\n"]))
            f.write("\n".join([str(i) for i in sorted(self.model_selection)]))

    def save_as(self):
        """
        Dialog-save a text file containing the model selection
        """
        fout = filedialog.asksaveasfilename(parent=self.master, defaultextension=".dat",
                                            initialfile='model_selection.dat')
        if fout:
            self.save(name=fout)

    def write(self, event=None, name="filtered.state"):
        """
        Write a new state file including only the selected models
        """
        export_state(self.gls[self.g_index], selection=self.model_selection, name=name)

    def write_as(self, event=None):
        """
        Dialog-write new state file including only the selected models
        """
        fout = filedialog.asksaveasfilename(parent=self.master, defaultextension=".state",
                                            initialfile='filtered.state')
        if fout:
            self.write(name=fout)

    def display(self, term=True):
        """
        Display the main window (wrapper for tk.mainloop)

        Args:
            None

        Kwargs:
            term <bool> - start with terminal control

        Return:
            None
        """
        if term:
            self.after(100, self._term_control)
        self.mainloop()

    def _term_control(self, verbose=False):
        """
        Add terminal control functionality to self.display

        Args/Kwargs/Return:
            None
        """
        if sys.version_info.major < 3:
            user_input = raw_input(">> ")
        else:
            user_input = input(">>> ")

        if user_input in ["exit", "exit()", "q", "quit", "quit()"]:
            if verbose:
                print("Quitting the app")
            self.master.quit()
        else:
            # DEBUGGING
            print(self.__v__)
            self.after(100, self._term_control)

    def _on_lens_switch(self, event=None):
        """
        Execute when lens selection is changed
        """
        if event:
            self.focus()
        if self.obj_index < 0:
            self.obj_index = 0
        if self.obj_index > len(self.models()[0]['obj,data'])-1:
            self.obj_index = len(self.models()[0]['obj,data'])-1
        self.load_image()

    def _on_selection(self, event=None):
        """
        Execute when selection is changed
        """
        self._on_subselection(event=event)
        self.load_image()

    def _on_subselection(self, event=None):
        """
        Execute when subselection is changed
        """
        if event:
            self.focus()
        if self.model_max <= self.model_min and self.model_max > 0:
            self.model_min = max(self.model_max-1, 0)
        elif self.model_max <= self.model_min:
            self.model_min = 0
            self.model_max = 1
        if self.model_index < self.model_min:
            self.model_index = self.model_min
        if self.model_index > self.model_max:
            self.model_index = self.model_max
        self.selection.configure(from_=self.model_min, to=self.model_max-1)

    def _on_H0filter(self, event=None):
        """
        Execute when Hubble filter is changed
        """
        dist = self.H0_dist()
        distmin, distmax = min(dist), max(dist)
        if event:
            self.focus()
        if self.H0_max <= self.H0_min and self.H0_max > distmin:
            self.H0_min = max(self.H0_max-1, distmin)
        elif self.H0_max <= self.H0_min:
            self.H0_max = distmax
            self.H0_min = distmin
        filtered = self.H0filter()
        self.labels['H0_filter'].configure(
            text='H0 filter (km/s/Mpc):\n[{}]'.format(len(filtered)))
        self.selection.configure(values=filtered)
        while self.model_index not in filtered:
            self.next()

    def _on_resize(self, event=None):
        """
        Resize actions applied when master is resized

        Args:
            event <str> - event to be bound to this function; format <[modifier-]type[-detail]>

        Kwargs/Return:
            None
        """
        self.load_image()

    def _on_close(self, event=None):
        """
        Execute when window is closed
        """
        self.master.quit()
        sys.exit(1)

    @property
    def img_buffer(self):
        """
        Image cache buffer for persistent/efficient window projection

        Args/Kwargs:
            None

        Return:
            img_buffer <PIL.ImageTk.PhotoImage object> - the current photoimage object
        """
        if self._img_buffer:
            return self._img_buffer[(self.model_index, self.obj_index, self.model_property)]

    @img_buffer.setter
    def img_buffer(self, img):
        """
        Setter of image cache buffer for persistent/efficient window projection

        Args:
            img <dict(PIL.Image object)> - image to be moved to the buffer

        Kwargs/Return:
            None

        Note:
            - _img_buffer is a dictionary, but img_buffer will hold only the current image
        """
        # lazy load
        if not hasattr(self, '_img_buffer'):
            self._img_buffer = {}
            self._img_copy = {}
        # expand buffer list if it's too short
        if img:
            self._img_buffer[(self.model_index, self.obj_index, self.model_property)] = img

    def clear_selection(self, all_=False):
        """
        Clear the model selection

        Args:
            None

        Kwargs:
            all_ <bool> - clear everything, including selection of current obj_index

        Return:
            None
        """
        self.model_selection = set([])
        if not all_:
            img = self._img_copy[
                (self.model_index, self.obj_index, self.model_property)]
            self.load_image(image=img)

    def clear_buffer(self, all_=False):
        """
        Clear the buffer containing the calculated images (current state is preserved)

        Args:
            None

        Kwargs:
            all_ <bool> - clear everything, including selection of current obj_index

        Return:
            None
        """
        if not all_:
            img = self._img_copy[(self.model_index, self.obj_index, self.model_property)]
        self._img_copy = {}
        self._img_buffer = {}
        if not all_:
            self.load_image(image=img)

    def clear_all(self):
        """
        Clear the entire app from any input

        Args/Kwargs/Return:
            None
        """
        self.grid_forget()
        self.clear_buffer(all_=True)
        self.clear_selection(all_=True)
        self.__init__(self.master)

    def model_function(self, g, model_property):
        """
        The model function is determined by the model_option <OptionMenu object>

        Args:
            g <glass.Environment object> - the glass environment
            model_property <str> - the desired mapping/transformation of the model

        Kwargs:
            None

        Return:
            model_func <func> - the function selected by the current Zapp state
                                (model_index, model_selection, obj_index, etc.)
        """
        if len(self.model_selection) > 0:
            models = [g.models[i] for i in self.model_selection]
        else:
            models = [g.models[i] for i in range(self.model_min, self.model_max)]
        map_properties = {
            '': (g.arrival_wsrc, {'only_contours': True,
                                  'clevels': 75,
                                  'colors': ['#603dd0']}),
            self.model_mappings[0]: (g.arrival_wsrc, {'only_contours': True,
                                                      'clevels': 75,
                                                      'colors': ['#603dd0']}),
            self.model_mappings[1]: (g.mass_plot, {'with_colorbar': True,
                                                   'vmin': 0, 'vmax': 5}),
            self.model_mappings[2]: (g.profile_plot, {'ptype': model_property,
                                                      'xkeys': ['R', 'arcsec'],
                                                      'models': models,
                                                      'yscale': 'linear'}),
            self.model_mappings[3]: (g.profile_plot, {'ptype': model_property,
                                                      'xkeys': ['R', 'arcsec'],
                                                      'models': models}),
            self.model_mappings[4]: (g.Hubble_plot, {'ptype': 'H0inv',
                                                     'models': models}),
            self.model_mappings[5]: (g.Hubble_plot, {'ptype': 'H0',
                                                     'models': models}),
            self.model_mappings[6]: (g.td_plot, {'models': models}),
            self.model_mappings[7]: (g.gamma_plot, {'ptype': 'shear',
                                                    'models': models}),
            self.model_mappings[8]: (g.gamma_plot, {'ptype': 'shear2d',
                                                    'models': models})
        }
        return map_properties[model_property]

    def model_image(self, image=None):
        """
        Get the current model image based on model_index, obj_index, and model_map
        """
        if image:
            img = image
        elif not self.gls:
            img = Image.new('RGB', (650, 500))
        elif (self.model_index, self.obj_index, self.model_property) in self._img_copy:
            img = self._img_copy[(self.model_index, self.obj_index, self.model_property)]
        else:
            g = self.gls[self.g_index]
            model = self.models()[self.model_index]
            func, kwargs = self.model_function(g, self.model_property)
            func(model, obj_index=self.obj_index, **kwargs)
            plt.tight_layout(h_pad=1)
            canvas = plt.get_current_fig_manager().canvas
            canvas.draw()
            img = Image.frombytes('RGB', canvas.get_width_height(),
                                  canvas.tostring_rgb())
            plt.clf()
        return img

    def add_image(self, image, verbose=False):
        """
        Insert image at specified index in buffer and project onto canvas

        Args:
            image <PIL.Image object> - image to be added to buffer
            index <int> - index of the image in the buffer

        Kwargs:
            verbose <bool> - verbose mode; print command line statements

        Return:
            None

        Note:
            - self._img_copy <dict(PIL.Image object)>
            - self._img_buffer <dict(PIL.ImageTk.PhotoImage object)>
        """
        # copy original
        self._img_copy[(self.model_index, self.obj_index, self.model_property)] = image
        # move image to buffer and show on canvas
        if image is not None:
            pos = (0, 0)
            image = image.resize((self.canvas.winfo_width(), self.canvas.winfo_height()))
            self.img_buffer = ImageTk.PhotoImage(master=self.canvas, image=image)
            self.canvas.create_image(*pos, image=self.img_buffer, anchor=tk.NW)
        # add tag indication
        if self.model_index in self.model_selection:
            OKAY = u'\u2713'
            self.canvas.create_text(50, 50, text=OKAY, fill='SpringGreen4',
                                    font=("Arial", 32), width=10)

    def load_image(self, image=None):
        """
        Create the image and add it to the canvas
        """
        img = self.model_image(image=image)
        self.add_image(img)


@command
def arrival_wsrc(env, model, **kwargs):
    """
    Wrapper for 'glass.plots.img_plot' and 'glass.plots.arrival_plot'
    """
    img_kwargs = {}
    img_kwargs['obj_index'] = kwargs.get('obj_index', 0)
    img_kwargs['src_index'] = kwargs.get('src_index', None)
    img_kwargs['tight'] = kwargs.pop('tight', False)
    img_kwargs['with_guide'] = kwargs.pop('with_guide', False)
    img_kwargs['color'] = kwargs.pop('color', '#fe4365')
    img_kwargs['with_maximum'] = kwargs.pop('with_maximum', True)

    env.img_plot(**img_kwargs)
    env.arrival_plot(model, **kwargs)


@command
def mass_plot(env, model, **kwargs):
    """
    Wrapper for 'glass.plots.kappa_plot'
    """
    obj_index = kwargs.pop('obj_index', 0)
    obj, data = model['obj,data'][obj_index]
    if not data:
        return

    # get keywords
    subtract = kwargs.pop('subtract', 0)
    xlabel = kwargs.pop('xlabel', '$\mathrm{arcsec}$')
    ylabel = kwargs.pop('ylabel', '$\mathrm{arcsec}$')
    with_colorbar = kwargs.pop('with_colorbar', False)
    with_contours = kwargs.pop('with_contours', False)

    # data
    grid = obj.basis._to_grid(data['kappa'] - subtract, 1)
    R = obj.basis.mapextent

    # keyword defaults
    kwargs.setdefault('cmap', 'gnuplot2')
    kwargs.setdefault('interpolation', 'nearest')
    kwargs.setdefault('extent', [-R, R, -R, R])
    kwargs.setdefault('aspect', 'equal')
    kwargs.setdefault('origin', 'upper')
    vmin = kwargs.get('vmin', None)
    vmax = kwargs.get('vmax', None)
    if vmin is None:
        w = data['kappa'] != 0
        if not np.any(w):
            vmin = -15
            grid += 10**vmin
        else:
            vmin = np.log10(np.amin(data['kappa'][w]))
            kwargs.setdefault('vmin', vmin)
    if vmax is not None:
        kwargs.setdefault('vmax', vmax)
    lvls = [0.25*k for k in range(-1, 5)]  # levels of log(kappa)

    # resample the grid
    # grid_data = np.log10(grid)
    grid_data = grid

    # actual plotting
    plt.imshow(grid_data, **kwargs)
    if with_contours:
        plt.contour(grid_data, levels=lvls, color='black', **kwargs)
    if with_colorbar:
        plt.colorbar()
    # labels
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)


@command
def profile_plot(env, model, **kwargs):
    """
    Wrapper for 'glass.plots.glerrorplot'
    """
    kwargs.pop('obj_index', 0)
    ptype = kwargs.pop('ptype', 'kappa(R)')
    xkeys = kwargs.pop('xkeys', ['R', 'arcsec'])
    env.glerrorplot(ptype, xkeys, **kwargs)


@command
def Hubble_plot(env, model, **kwargs):
    """
    Wrapper for 'glass.plots.H0inv_plot' and 'glass.plots.H0_plots'
    """
    func = {'H0inv': env.H0inv_plot,
            'H0': env.H0_plot}[kwargs.pop('ptype', 'H0inv')]
    func(**kwargs)


@command
def td_plot(env, model, **kwargs):
    """
    Wrapper for 'glass.plots.time_delays_plot
    """
    env.time_delays_plot(**kwargs)


@command
def gamma_plot(env, model, **kwargs):
    """
    Wrapper for 'glass.plots.shear_plot' and 'glass.plots.shear2d_plot'
    """
    func = {'shear': env.shear_plot,
            'shear2d': env.shear_plot2d}[kwargs.pop('ptype', 'shear2d')]
    func(**kwargs)


def filter_env(env, selection):
    """
    Filter a GLASS environment according to a selection

    Args:
        env <glass.environment object> - the glass state to be filtered
        selection <list(int)> - list of indices used to filter out models

    Kwargs:
        None

    Return:
        envcpy <glass.environment object> - the filtered glass state
    """
    import copy
    envcpy = copy.deepcopy(env)
    for i in range(len(envcpy.models)-1, -1, -1):
        if i in selection:
            continue
        del envcpy.models[i]
        del envcpy.accepted_models[i]
        del envcpy.solutions[i]
    envcpy.meta_info['filtered'] = (os.path.basename(env.global_opts['argv'][-1]),
                                    len(env.models), len(envcpy.models))
    return envcpy


def export_state(env, selection=None, name="filtered.state"):
    """
    Save a filtered state in a new state file

    Args:
        env <glass.environment object> - state to be exported

    Kwargs:
        selection <list(int)> - list of indices used to filter out models

    Return:
        None
    """
    if selection:
        state = filter_env(env, selection)
    else:
        state = env
    state.savestate(name)


if __name__ == "__main__":
    root, zapper = Zapp.init(gls_states=[], verbose=1)
    zapper.display()
