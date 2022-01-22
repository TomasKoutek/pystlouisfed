from pathlib import Path

from setuptools import setup

setup(
    name='pystlouisfed',
    version='1.0.1',
    packages=['pystlouisfed'],
    url='https://github.com/TomasKoutek/pystlouisfed',
    license='MIT',
    author='Tomas Koutek',
    author_email='66636b6f6666@gmail.com',
    maintainer="Tomas Koutek",
    # maintainer_email="",
    description='Federal Reserve Bank of St. Louis - FRED, ALFRED, GeoFRED and FRASER',

    long_description=Path(__file__).resolve().parent.joinpath('README.md').open(encoding='utf-8').read(),
    long_description_content_type='text/markdown',

    download_url="https://github.com/TomasKoutek/pystlouisfed.git",

    project_urls={
        'Documentation': 'https://tomaskoutek.github.io/pystlouisfed/',
        'Source': 'https://github.com/TomasKoutek/pystlouisfed',
        'Tracker': 'https://github.com/TomasKoutek/pystlouisfed/issues',
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP",
        "Natural Language :: English",
        "Topic :: Office/Business :: Financial",
        "Topic :: Office/Business :: Financial :: Investment",
        "Intended Audience :: Education",
        "Topic :: Scientific/Engineering",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],

    keywords=["economics", "API", "financial", "FRED", "ALFRED", "FRASER", "GEOFRED", "stlouisfed", "trading", "algotrading"],

    platforms=["Any"],

    python_requires=">=3.7",

    install_requires=[
        "pandas",
        "requests",
        "ratelimiter",
        "shapely",
        "sickle",
        "numpy"
    ],
)
