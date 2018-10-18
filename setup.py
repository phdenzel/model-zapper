"""
@author: phdenzel

Usage:
    python setup.py py2app
"""
import os
from setuptools import setup

APP = ['modelzapper.py']
PLIST = {
    'CFBundleName': "ModelZapper",
    'CFBundleDisplayName': "ModelZapper",
    'CFBundleGetInfoString': "Model inspector for GLASS state files",
    'CFBundleIdentifier': "com.phdsystems.model-zapper",
    'CFBundleVersion': "0.2.0",
    'CFBundleShortVersionString': "0.2.0",
    'author_email': "phdenzel@gmail.com",
    
    
    'CFBundleDocumentTypes': [{
        'CFBundleTypeName': "state",
        'CFBundleTypeRole': "Editor",
        'LSHandlerRank': "Owner",
        'LSItemContentTypes': ["com.phdsystems.state"],
    }],

    'UTExportedTypeDeclarations': [{
        'UTTypeConformsTo': ["public.data"],
        'UTTypeIdentifier': "com.phdsystems.state",
        'UTTypeDescription': "state",
        'UTTypeTagSpecification': {
            'public.filename-extension': "state"}
    }],

    'NSHumanReadableCopyright': u"Copyright \u00A9 2018, Philipp Denzel, All Rights Reserved"
}

DATAFILES = [('', ['imgs']),
             ('', ['libs']),
             ('', ['includes']),
]
PACKAGES = [
    'numpy',
    'matplotlib',
    'scipy',
    'PIL',
            
]
OPTIONS = {'iconfile': "imgs/zapper.icns",
           'argv_emulation': True,
           'plist': PLIST,
           'packages': PACKAGES,
}
setup(
    app=APP,
    data_files=DATAFILES,
    options={'py2app': OPTIONS},
    setup_requires=["py2app"],
)
