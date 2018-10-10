"""
@author: phdenzel

Usage:
    python setup.py py2app
"""
import os
from setuptools import setup

APP = ['modelzapper.py']
PLIST = dict(CFBundleName='ModelZapper',
             CFBundleDisplayName='ModelZapper',
             CFBundleGetInfoString='Model inspector for GLASS state files',
             CFBundleIdentifier='com.pythonmac.modelzapper',
             author_email='phdenzel@gmail.com',
             CFBundleVersion='0.1.0',
             CFBundleShortVersionString='0.1.0',
             NSHumanReadableCopyright=u"Copyright \u00A9 2018, Philipp Denzel, All Rights Reserved",
             LSBackgroundOnly=False,
)
DATAFILES = [('', ['imgs']),
             ('', ['libs']),
             ('', ['includes']),
]
PACKAGES = ['PIL',
            'matplotlib',
]
OPTIONS = {'iconfile': 'imgs/zapper.icns',
           'plist': PLIST,
           'packages': PACKAGES,
}
setup(
    app=APP,
    data_files=DATAFILES,
    options={'py2app': OPTIONS},
    setup_requires=["py2app"],
)
