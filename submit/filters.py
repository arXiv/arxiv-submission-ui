from collections import OrderedDict
from datetime import datetime
from typing import List, Tuple, Optional, Union
from .domain import FileStatus


def group_files(files: List[FileStatus]) \
        -> List[Tuple[int, Optional[str], Optional[FileStatus]]]:
    """
    Group a set of file status objects by directory structure.

    Parameters
    ----------
    list
        Elements are :class:`FileStatus` objects.

    Returns
    -------
    list
        Elements are (int, str or None, :class:`FileStatus` or None) tuples,
        where the first element is the tree level, the second element (if
        not None) is the parent directory, and the third element (if not None)
        if the leaf file status object.

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
    """ """
    now = datetime.utcnow()
    diff = now - timestamp

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
