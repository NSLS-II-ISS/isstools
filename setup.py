from __future__ import (absolute_import, division, print_function)
import versioneer

import setuptools

setuptools.setup(
    name='isstools',
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    license="BSD (3-clause)",
    url="https://github.com/NSLS-II-ISS/isstools",
    packages=setuptools.find_packages(),
    package_data={'isstools': ['ui/*.ui']},
    # install_requires=['numpy', 'matplotlib', 'netcdf4', 'pyqt', 'pyparsing'],
    install_requires=['netcdf4','pyparsing', 'numpexpr', 'pysmbc'], #needs zbarlight
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
)
