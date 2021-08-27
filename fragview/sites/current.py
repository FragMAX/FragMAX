from typing import Iterable
from pathlib import Path
from fragview.sites import SITE
from fragview.sites.plugin import DatasetMetadata

"""
A utility module for accessing site specific implementation of the
various aspects of the application.

This module wraps the 'current' site-plugin's methods in convenience functions.
"""

#
# features
#


def proposals_disabled() -> bool:
    """
    returns True if 'proposals' feature is disabled for this site
    """
    return "proposals" in SITE.DISABLED_FEATURES


#
# paths
#


def get_project_dir(project) -> Path:
    return SITE.get_project_dir(project)


def get_project_dataset_dirs(project) -> Iterable[Path]:
    return SITE.get_project_dataset_dirs(project)


def get_dataset_runs(data_dir: Path) -> Iterable[int]:
    """
    get all run numbers for a dataset given it's root folder
    """
    return SITE.get_dataset_runs(data_dir)


def get_dataset_metadata(
    project, dataset_dir: Path, crystal_id: str, run: int
) -> DatasetMetadata:
    return SITE.get_dataset_metadata(project, dataset_dir, crystal_id, run)
