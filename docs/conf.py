# Configuration file for the Sphinx documentation builder.
#
# This file only contains a selection of the most common options. For a full
# list see the documentation:
# http://www.sphinx-doc.org/en/master/config

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
#
import os
import sys
sys.path.insert(0, os.path.abspath('.'))
sys.path.append(os.path.abspath('..'))
import patched_sphinx_autodoc_typehints
from submit.factory import create_ui_web_app

app = create_ui_web_app()
app.app_context().push()

# -- Project information -----------------------------------------------------

project = 'arXiv Submission UI'
copyright = '2019, arXiv-NG Team'
author = 'arXiv-NG Team'

# The full version, including alpha/beta/rc tags
release = '0.1'


# -- General configuration ---------------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom
# ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.imgmath',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.graphviz',
    'sphinx.ext.githubpages',
    'patched_sphinx_autodoc_typehints'
]


# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']


# -- Options for HTML output -------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
#
html_theme = 'alabaster'

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

intersphinx_mapping = {
    'python':  ('https://docs.python.org/3.6', None),
    'arxitecture':  ('https://arxiv.github.io/arxiv-arxitecture/', None),
    'arxiv.submission':  ('https://arxiv.github.io/arxiv-submission-core/', None),
    'arxiv.taxonomy': ('https://arxiv.github.io/arxiv-base', None),
    'arxiv.base':  ('https://arxiv.github.io/arxiv-base', None),
    'browse':  ('https://arxiv.github.io/arxiv-browse/', None),
    'search':  ('https://arxiv.github.io/arxiv-search/', None),
    'zero':  ('https://arxiv.github.io/arxiv-zero/', None),
    'hvac': ('https://hvac.readthedocs.io/en/stable/', None)
}
