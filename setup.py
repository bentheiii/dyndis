import setuptools

import dyndis_data as dyndis

setuptools.setup(
    name='dyndis',
    version=dyndis.__version__,
    url=dyndis.__url__,
    author=dyndis.__author__,
    packages=['dyndis', 'dyndis_data'],
    python_requires='>=3.7.0',
    include_package_data=True,
    data_files=[
        ('', ['README.md', 'CHANGELOG.md']),
    ],
    install_requires=["sortedcontainers"],
    extras_require={
        "testing": ['numpy']
    }
)
