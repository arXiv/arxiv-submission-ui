from typing import List, Tuple, Optional
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

    # Second step is to unpack the tree in order.
    def _unpack(i, k, v):
        if type(v) is FileStatus:
            return [(i, '', v)]
        r = [(i, k, None)]
        for _k, _v in v.items():
            r += _unpack(i + 1, _k, _v)
        return r
    return _unpack(0, '', tree)
