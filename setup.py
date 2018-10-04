"""
@author: phdenzel

Usage:
    python setup.py py2app
"""
from setuptools import setup


APP = ['modelzapper.py']
INFO = dict(name='ModelZapper',
            description='Model inspector for GLASS state files',
            author='Philipp Denzel',
            author_email='phdenzel@gmail.com',
            version='1.0')
DATAFILES = [('', ['imgs'])]
OPTIONS = {'iconfile': 'imgs/zapper.icns',
           'argv_emulation': True}

setup(
    app=APP,
    data_files=DATAFILES,
    options={'py2app': OPTIONS},
    setup_requires=["py2app"],
)
