"""Custom Jinja2 filters."""

from typing import List, Tuple, Optional, Union, Dict, Mapping, Callable
from collections import OrderedDict
from datetime import datetime, timedelta
from pytz import UTC

from arxiv import taxonomy
from arxiv.submission.domain.process import ProcessStatus
from arxiv.submission.domain.submission import Compilation, Submission
#from .domain import FileStatus, Upload
from submit.domain import FileStatus, Upload
from submit.util import tidy_filesize
from submit.flow_control import get_workflow

from .tex_filters import compilation_log_display

# additions for compilation log markup
import re

NestedFileTree = Mapping[str, Union[FileStatus, 'NestedFileTree']]


def group_files(files: List[FileStatus]) -> NestedFileTree:
    """
    Group a set of file status objects by directory structure.

    Parameters
    ----------
    list
        Elements are :class:`FileStatus` objects.

    Returns
    -------
    :class:`OrderedDict`
        Keys are strings. Values are either :class:`FileStatus` instances
        (leaves) or :class:`OrderedDict` (containing more :class:`FileStatus`
        and/or :class:`OrderedDict`, etc).

    """
    # First step is to organize by file tree.
    tree = {}
    for f in files:
        parts = f.path.split('/')
        if len(parts) == 1:
            tree[f.name] = f
        else:
            subtree = tree
            for part in parts[:-1]:
                if part not in subtree:
                    subtree[part] = {}
                subtree = subtree[part]
            subtree[parts[-1]] = f

    # Reorder subtrees for nice display.
    def _order(subtree: Union[dict, FileStatus]) -> OrderedDict:
        if type(subtree) is FileStatus:
            return subtree
        _subtree = OrderedDict()
        for key, value in sorted(subtree.items(), key=lambda o: o[0]):
            _subtree[key] = _order(value)
        return _subtree

    return _order(tree)


def timesince(timestamp: datetime, default: str = "just now") -> str:
    """Format a :class:`datetime` as a relative duration in plain English."""
    diff = datetime.now(tz=UTC) - timestamp
    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )
    for period, singular, plural in periods:
        if period > 1:
            return "%d %s ago" % (period, singular if period == 1 else plural)
    return default


def duration(delta: timedelta) -> str:
    s = ""
    for period in ['days', 'hours', 'minutes', 'seconds']:
        value = getattr(delta, period, 0)
        if value > 0:
            s += f"{value} {period}"
    if not s:
        return "less than a second"
    return s


def just_updated(status: FileStatus, seconds: int = 2) -> bool:
    """
    Filter to determine whether a specific file was just touched.

    Parameters
    ----------
    status : :class:`FileStatus`
        Represents the state of the uploaded file, as conveyed by the file
        management service.
    seconds : int
        Threshold number of seconds for determining whether a file was just
        touched.

    Returns
    -------
    bool

    Examples
    --------

    .. code-block:: html

       <p>
           This item
           {% if item|just_updated %}was just updated
           {% else %}has been sitting here for a while
           {% endif %}.
       </p>

    """
    now = datetime.now(tz=UTC)
    return abs((now - status.modified).seconds) < seconds


def get_category_name(category: str) -> str:
    """
    Get the display name for a category in the :mod:`base:taxonomy`.

    Parameters
    ----------
    category : str
        Canonical category ID, e.g. ``astro-ph.HE``.

    Returns
    -------
    str
        Display name for the category.

    Raises
    ------
    KeyError
        Raised if the specified category is not found in the active categories.

    """
    return taxonomy.CATEGORIES_ACTIVE[category]['name']


def process_status_display(status: ProcessStatus.Status) -> str:
    if status is ProcessStatus.Status.REQUESTED:
        return "in progress"
    elif status is ProcessStatus.Status.FAILED:
        return "failed"
    elif status is ProcessStatus.Status.SUCCEEDED:
        return "suceeded"
    raise ValueError("Unknown status")


def compilation_status_display(status: Compilation.Status) -> str:
    if status is Compilation.Status.IN_PROGRESS:
        return "in progress"
    elif status is Compilation.Status.FAILED:
        return "failed"
    elif status is Compilation.Status.SUCCEEDED:
        return "suceeded"
    raise ValueError("Unknown status")

TEX = 'tex'
LATEX = 'latex'
PDFLATEX = 'pdflatex'

ENABLE_TEX = r'(\~+\sRunning tex.*\s\~+)'
ENABLE_LATEX = r'(\~+\sRunning latex.*\s\~+)'
ENABLE_PDFLATEX = r'(\~+\sRunning pdflatex.*\s\~+)'

DISABLE_HTEX = r'(\~+\sRunning htex.*\s\~+)'
DISABLE_HLATEX = r'(\~+\sRunning hlatex.*\s\~+)'
DISABLE_HPDFLATEX = r'(\~+\sRunning hpdflatex.*\s\~+)'

RUN_ORDER = ['last', 'first', 'second', 'third', 'forth']

def XXX_compilation_log_display(autotex_log: str) -> str:
    """

    :param autotex_log:
    :return:
    """

    # Create summary information for runs and markup key.

    run_summary = ("If you are attempting to compile "
                   "with a specific engine (PDFLaTeX, LaTeX, \nTeX) please "
                   "carefully review the appropriate log below.\n\n"
                   )

    log_summary = (
        "Key: \n"
        "\t<span class=\"tex-fatal\">Severe warnings/errors.</span>'\n"
        "\t<span class=\"tex-danger\">Warnings deemed important</span>'\n"
        "\t<span class=\"tex-warning\">General warnings/errors from packages.</span>'\n"
        
        "\t<span class=\"tex-ignore\">Warnings/Errors deemed unimportant. "
        "Example: undefined references in first TeX run.</span>'\n"
        "\t<span class=\"tex-success\">Indicates positive event, does not guarantee overall success</span>\n"
        "\t<span class=\"tex-info\">Informational markup</span>\n"
        
        "\n"
        "\tNote: Almost all marked up messaged are generated by TeX \n\tengine "
        "or packages. \n\n"
        "\t<span class=\"tex-help\">Links to relevant help pages.</span>\n"
        "\t<span class=\"tex-suggestion\">Suggested solution based on "
        "previous experience.</span>\n"
        "\n\n"
    )

    run_summary = run_summary + (
        "Summary of TeX runs:\n\n"
    )

    new_log = ''

    last_run_for_engine = {}

    # TODO : THIS LIKELY BECOMES ITS OWN ROUTINE

    # Lets figure out what we have in terms of TeX runs
    # ~~~~~~~~~~~ Running hpdflatex for the first time ~~~~~~~~
    # ~~~~~~~~~~~ Running latex for the first time ~~~~~~~~
    run_regex = re.compile(r'\~+\sRunning (.*) for the (.*) time\s\~+',
                           re.IGNORECASE | re.MULTILINE)

    hits = run_regex.findall(autotex_log)

    enable_markup = []
    disable_markup = []

    for run in hits:
        (engine, run) = run

        run_summary = run_summary + f"\tRunning {engine} for {run} time." + '\n'

        last_run_for_engine[engine] = run

        # Now, when we see a normal TeX run, we will eliminate the hypertex run.
        # Since normal run and hypertex run a basically identical this eliminates
        # unnecessary cruft. When hypertex run succeed it will be displayed and
        # marked up appropriately.

        if engine == PDFLATEX:
            disable_markup.append(DISABLE_HPDFLATEX)
            enable_markup.append(ENABLE_PDFLATEX)
        if engine == LATEX:
            disable_markup.append(DISABLE_HLATEX)
            enable_markup.append(ENABLE_LATEX)
        if engine == TEX:
            disable_markup.append(DISABLE_HTEX)
            enable_markup.append(ENABLE_TEX)

    run_summary = run_summary + '\n'


    for e,r in last_run_for_engine.items():
        run_summary = run_summary + f"\tLast run for engine {e} is {r}\n"

    # Ignore lines that we know submitters are not interested in or that
    # contain little useful value

    skip_markup = []

    current_engine = ''
    current_run = ''

    last_run = False

    # Filters  [class, regex, run spec]
    #
    # run spec: specifies when to start applying filter
    #           OR apply to last run.
    #
    #       Example: run spec of 'second' will apply filter on second, third, ...
    #                run spec of 'last' will run on last run for each engine.
    #
    filters = [

        # Examples
        ['danger', 'is of type', ''],
        ['suggestion', 'Set working directory to', ''],

        # Informational
        ['info', r'\~+\sRunning.*\s\~+', ''],

        # Warnings
        ['warning', r'Citation.*undefined', ''],
        ['warning', r'reference.*undefined', 'second'],
        ['warning', r'No .* file', ''],
        ['warning', 'warning', ''],
        ['warning', 'unsupported', ''],
        ['warning', 'unable', ''],
        ['warning', 'ignore', ''],
        ['warning', 'undefined', ''],

        # Danger
        ['danger', r'file (.*) not found', ''],
        ['danger', 'failed', ''],
        ['danger', 'emergency stop', ''],
        ['danger', 'not allowed', ''],
        ['danger', 'does not exist', ''],

        # Fatal
        ['fatal', r'Fatal (.*) error', ''],
        ['fatal', 'fatal', '']
    ]

    warn_filters = [[r'Citation.*undefined', 'second'],
                    [r'reference.*undefined', 'second'],
                    [r'No .* file', ''],
                    ['warning', ''],
                    ['unsupported', ''],
                    ['unable', ''],
                    ['ignore', ''],
                    ['undefined', '']
                    ]
    warn_filters = []


    danger_filters = [[r'file (.*) not found', ''],
                      ['failed', ''],
                      ['emergency stop', ''],
                      ['not allowed', ''],
                      ['does not exist', '']
                      ]
    danger_filters = []

    fatal_filters = [[r'Fatal (.*) error', ''],
                     ['fatal', '']
                     ]
    fatal_filters = []

    line_by_line = autotex_log.splitlines()

    markup_enabled = True

    for line in line_by_line:

        # Disable markup for TeX runs we do not want to markup
        for regex in disable_markup:

            if re.search(regex, line, re.IGNORECASE):
                markup_enabled = False
                new_log = new_log + f"DISABLE MARKUP:{line}\n"
                break

        # Enable markiup for runs that user is interested in
        for regex in enable_markup:

            if re.search(regex, line, re.IGNORECASE):
                markup_enabled = True
                new_log = new_log + f"ENABLE MARKUP:{line}\n"
                #log_summary = log_summary + "\tRun: " + re.search(regex, line, re.IGNORECASE).group() + '\n'
                found = run_regex.search(line)
                if found:
                    current_engine = found.group(1)
                    current_run = found.group(2)
                    new_log = new_log + f"Set engine:{current_engine} Run:{current_run}\n"

                if current_engine and current_run:
                    if last_run_for_engine[current_engine] == current_run:
                        new_log = new_log + f"LAST RUN:{current_engine} Run:{current_run}\n"
                        last_run = True
                break


        # Disable markup for TeX runs that we are not interested in.
        if not markup_enabled:
            continue

        # We are not done with this line until there is a match
        done_with_line = False

        for regex in skip_markup:
            if re.search(regex, line, re.IGNORECASE):
                done_with_line = True
                new_log = new_log + f"Skip line {line}\n"
                break

        if done_with_line:
            continue

        # Tests
        regex = r'(\*\*\* Using TeX Live 2016 \*\*\*)'
        if re.search(regex, line, re.IGNORECASE):
            line = re.sub(regex, r'<span class="tex-ignore">\1</span>', line, re.IGNORECASE)
            done_with_line = True


        regex = r'(Extracting files from archive:)'
        if re.search(regex, line, re.IGNORECASE):
            line = re.sub(regex, r'<span class="tex-success">\1</span>', line, re.IGNORECASE)
            done_with_line = True

        regex = r'(Summary of TeX runs:)'
        if re.search(regex, line, re.IGNORECASE):
            line = re.sub(regex, r'<span class="tex-success">\1</span>', line, re.IGNORECASE)
            done_with_line = True

        if done_with_line:
            new_log = new_log + line + '\n'
            continue

        # Fatal
        for filter, run in fatal_filters:
            regex = r'(' + filter + r')'

            if not run:
                run = 'first'
            if run and current_run \
                    and ((RUN_ORDER.index(run) > RUN_ORDER.index(current_run)
                          or (run == 'last' and current_run != last_run_for_engine[current_engine]))):
                #new_log = new_log + f"NOT RIGHT RUN LEVEL: SKIP {filter}" + '\n'
                continue


            if re.search(regex, line, re.IGNORECASE):
                line = re.sub(regex, r'<span class="tex-fatal">\1</span>', line, re.IGNORECASE)
                done_with_line = True
                break

        if done_with_line:
            new_log = new_log + line + '\n'
            continue

        # Danger
        for filter, run in danger_filters:
            regex = r'(' + filter + r')'
            #new_log = f"Apply danger regex: {regex}" + '\n' + new_log

            if not run:
                run = 'first'
            if run and current_run \
                    and ((RUN_ORDER.index(run) > RUN_ORDER.index(current_run)
                          or (run == 'last' and current_run != last_run_for_engine[current_engine]))):
                #new_log = new_log + f"NOT RIGHT RUN LEVEL: SKIP {filter}" + '\n'
                continue

            if re.search(regex, line, re.IGNORECASE ):
                line = re.sub(regex, r'<span class="tex-danger">\1</span>', line, re.IGNORECASE)
                done_with_line = True
                break

        if done_with_line:
            new_log = new_log + line + '\n'
            continue

        # Warning
        for filter, run in warn_filters:

            if not run:
                run = 'first'
            if run and current_run \
                    and ((RUN_ORDER.index(run) > RUN_ORDER.index(current_run)
                          or (run == 'last' and current_run != last_run_for_engine[current_engine]))):
                #new_log = new_log + f"NOT RIGHT RUN LEVEL: SKIP {filter}" + '\n'
                continue

            regex = r'('+ filter + r')'

            if re.search(regex, line, re.IGNORECASE):
                line = re.sub(regex, r'<span class="tex-warning">\1</span>', line, flags=re.IGNORECASE)
                done_with_line = True
                break

        if done_with_line:
            new_log = new_log + line + '\n'
            continue

        # Info
        for level, filter, run in filters:
            regex = r'('+ filter + r')'


            #if run and current_run:
            #    new_log = new_log + f"RUN:{run}:{RUN_ORDER.index(run)} CURRENT:{current_run}:{RUN_ORDER.index(current_run)}:Last:{last_run_for_engine[current_engine]}" + '\n'

            if not run:
                run = 'first'
            if run and current_run \
                    and ((RUN_ORDER.index(run) > RUN_ORDER.index(current_run)
                          or (run == 'last' and current_run != last_run_for_engine[current_engine]))):
                #new_log = new_log + "NOT RIGHT RUN LEVEL: SKIP" + '\n'
                continue

            if re.search(regex, line, re.IGNORECASE):
                line = re.sub(regex, rf'<span class="tex-{level}">\1</span>', line, re.IGNORECASE)
                break

        # Append line to new marked up log
        new_log = new_log + line + '\n'

    # Put together a nice report, list TeX runs, markup info, and marked up log.
    # In future we can add 'Recommendation' section or collect critical errors.
    new_log = run_summary + log_summary + '\n\nMarked Up Log:\n\n' + new_log + "I'm DONE"

    return new_log


def get_filters() -> List[Tuple[str, Callable]]:
    """Get the filter functions available in this module."""
    return [
        ('group_files', group_files),
        ('timesince', timesince),
        ('just_updated', just_updated),
        ('get_category_name', get_category_name),
        ('process_status_display', process_status_display),
        ('compilation_status_display', compilation_status_display),
        ('duration', duration),
        ('tidy_filesize', tidy_filesize),
        ('compilation_log_display', compilation_log_display)
    ]
