#!/usr/bin/env python3

from setuptools import setup

setup(
    name="icx",
    version="0.1.0",
    py_modules=['icx'],
    install_requires=[
        'iconsdk',
        'click',
    ],
    entry_points={
        'console_scripts': [
            'icx = icx.main:main',
        ]
    }
)
