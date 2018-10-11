"""
@author: phdenzel

Use glass to read glass .state and zap through the models

Usage:
    python modelzapper.py [gls.state]
"""
import sys
import os

app_root = os.path.dirname(os.path.abspath(os.path.realpath(__file__)))
libspath = os.path.join(app_root, 'libs')
if os.path.exists(libspath):
    libs = os.listdir(libspath)[::-1]
    for l in libs:
        lib = os.path.join(libspath, l)
        if lib not in sys.path or not any(['glass' in p for p in sys.path]):
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

from app import Zapp
import getopt
import traceback

from glass.command import command, Commands
from glass.environment import env, Environment
from glass.exmass import *
from glass.exceptions import GLInputError

_omp_opts = None


def help():
    print >>sys.stderr, "Usage: modelzapper.py <input>"
    sys.exit(2)


def _detect_cpus():
    """
    Detects the number of CPUs on a system.
    From http://codeliberates.blogspot.com/2008/05/detecting-cpuscores-in-python.html
    From http://www.artima.com/weblogs/viewpost.jsp?thread=230001
    """
    import subprocess
    # Linux, Unix and MacOS
    if hasattr(os, "sysconf"):
        if "SC_NPROCESSORS_ONLN" in os.sysconf_names:
            # Linux & Unix:
            ncpus = os.sysconf("SC_NPROCESSORS_ONLN")
            if isinstance(ncpus, int) and ncpus > 0:
                return ncpus
        # OSX
        else:
            return int(subprocess.Popen("sysctl -n hw.ncpu", shell=True, stdout=subprocess.PIPE).communicate()[0])
    # Windows
    if "NUMBER_OF_PROCESSORS" in os.environ:
        ncpus = int(os.environ["NUMBER_OF_PROCESSORS"])
        if ncpus > 0:
            return ncpus
    # Default
    return 1

def _detect_omp():
    global _omp_opts
    if _omp_opts is not None:
        return _omp_opts
    try:
        import weave
        kw = dict(
            extra_compile_args=['-O3', '-fopenmp', '-DWITH_OMP',
                                '-Wall', '-Wno-unused-variable'],
            extra_link_args=['-lgomp'],
            headers=['<omp.h>'])
        weave.inline(' ', **kw)
    except ImportError:
        kw = {}
    _omp_opts = kw
    return kw


@command('Load a glass basis set')
def glass_basis(env, name, **kwargs):
    env.basis_options = kwargs
    f = __import__(name, globals(), locals())
    for name, [f, g, help_text] in Commands.glass_command_list.iteritems():
        if name in __builtins__.__dict__:
            message = 'WARNING: Glass command {:s} ({:s}) overrides previous function {:s}'
            print(message.format(name, f, __builtins__.__dict__[name]))
        __builtins__.__dict__[name] = g


if __name__ == "__main__":

    app = 'app.py'
    Environment.global_opts['ncpus_detected'] = _detect_cpus()
    Environment.global_opts['ncpus'] = 1
    Environment.global_opts['omp_opts'] = _detect_omp()
    Environment.global_opts['withgfx'] = True
    Commands.set_env(Environment())

    import glass.glcmds
    import glass.scales
    if Environment.global_opts['withgfx']:
        import glass.plots

    glass_basis('glass.basis.pixels', solver=None)
    exclude_all_priors()

    Environment.global_opts['argv'] = [app]+sys.argv[1:]
    opts = Environment.global_opts['argv']
    states = [loadstate(f) for f in opts[1:]]

    root, zapper = Zapp.init(gls_states=states, verbose=1)
    zapper.display()
