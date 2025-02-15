from typing import Optional
from os import path
from django.http import HttpResponse, Http404, FileResponse
from fragview.fileio import read_proj_file
from fragview.models import Library, Fragment
from fragview.projects import Project
from fragview.tools import get_tool_ul_label


class ToolsCombo:
    def __init__(self, proc_tool: str, refine_tool: str):
        self.proc = proc_tool
        self.refine = refine_tool
        self.ui_label = (
            f"{get_tool_ul_label(proc_tool)} - {get_tool_ul_label(refine_tool)}"
        )


def binary_http_response(file_path, content_type):
    return HttpResponse(read_proj_file(file_path), content_type=content_type)


def jpeg_http_response(file_path):
    return binary_http_response(file_path, "image/jpeg")


def download_http_response(file_path, filename=None):
    if filename is None:
        filename = path.basename(file_path)

    return FileResponse(open(file_path, "rb"), as_attachment=True, filename=filename)


def get_pdb_by_id(project: Project, pdb_id):
    pdb = project.get_pdb(id=pdb_id)
    if pdb is None:
        raise Http404(f"no PDB with id '{pdb_id}' found")

    return pdb


def get_dataset_by_id(project: Project, dataset_id):
    dataset = project.get_dataset(dataset_id)
    if dataset is None:
        raise Http404(f"no dataset with id '{dataset_id}' exist")

    return dataset


def get_refine_result_by_id(project: Project, result_id):
    result = project.get_refine_result(result_id)
    if result is None:
        raise Http404(f"no refine result with id '{result_id}' exist")

    return result


def get_ligfit_result_by_id(project: Project, result_id):
    result = project.get_ligfit_result(result_id)
    if result is None:
        raise Http404(f"no ligfit result with id '{result_id}' exist")

    return result


def get_crystals_fragment(crystal) -> Optional[Fragment]:
    """
    get Crystal's Fragment, returns None for apo crystals
    """
    if crystal.is_apo():
        return None

    return Fragment.get_by_id(crystal.fragment_id)


def get_fragment_by_id(fragment_id: str) -> Fragment:
    try:
        fragment = Fragment.get_by_id(fragment_id)
    except Fragment.DoesNotExist:
        raise Http404(f"no fragment with id '{fragment_id}' exist")

    return fragment


def get_project_libraries(project: Project) -> set[Library]:
    libs = set()

    for crystal in project.get_crystals():
        if crystal.is_apo():
            continue

        frag = Fragment.get_by_id(crystal.fragment_id)
        libs.add(frag.library)

    return libs
