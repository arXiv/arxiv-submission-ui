# arXiv Submission UI

This is the primary interface for arXiv users to submit e-prints to arXiv.
It is comprised of a Flask application built around the [submission core
events](https://github.com/cul-it/arxiv-submission-core) package.

## Quick start

```bash
$ pipenv install --dev
$ CLASSIC_DATABASE_URI='sqlite:///db.sqlite' LOGLEVEL=10 FLASK_APP=app.py FLASK_DEBUG=1 pipenv run flask run
```
## Code quality

### Linting

[Pylint](https://github.com/PyCQA/pylint) should pass at 9/10 or greater, given
the ``.pylintrc`` config in this repo.

```bash
$ pipenv run pylint submit

Using config file /Users/brp53/projects/arxiv-submission-ui/.pylintrc
************* Module submit.routes.ui
submit/routes/ui.py:9: [W0511(fixme), ] TODO: might be refactored into a series of macros and fewer single-page

-----------------------------------
Your code has been rated at 9.88/10
```

### Code documentation

[Pydocstyle](https://github.com/PyCQA/pydocstyle) should pass without errors,
using [NumPy style
docstrings](http://www.sphinx-doc.org/en/master/ext/example_numpy.html).

```bash
$ pipenv run pydocstyle --convention=numpy --add-ignore=D401
$
```

### Static checking

Use [type annotations](https://docs.python.org/3/library/typing.html)
throughout this project (except in tests). [Mypy](http://mypy-lang.org/) should
pass with no errors or warnings, given the ``mypy.ini`` configuration in this
repo and excluding "defined here" messages.

```
$ pipenv run mypy submit | grep -v "test.*" | grep -v "defined here"
$
```

If mypy complains about something that is verifiably not an error (e.g. a
known limitation of mypy), use inline ``# type: ignore`` comments to suppress
the message. You should also add a comment describing why you're suppressing
the error, including any relevant context (e.g. GitHub issues, SO threads,
etc).
