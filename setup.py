"""
@author: phdenzel

Usage:
    python setup.py py2app
"""
from setuptools import setup


APP = ['modelzapper.py']
DATAFILES = [('', ['imgs']), ('', ['libs']), ('', ['includes'])]
INFO = dict(name='ModelZapper',
            description='Model inspector for GLASS state files',
            author='Philipp Denzel',
            author_email='phdenzel@gmail.com',
            version='1.0')
OPTIONS = {'iconfile': 'imgs'}

setup(
    app=APP,
    data_files=DATAFILES,
    options=OPTIONS,
    setup_requires=["py2app"],
    **INFO
)
