import time
from pathlib import Path
from django.shortcuts import render
from django.http import HttpResponseBadRequest
from fragview import versions
from fragview.views import crypt_shell
from fragview.views.utils import start_thread
from fragview.projects import project_process_dataset_dir, project_results_dataset_dir
from fragview.projects import current_project, project_script, project_log_path
from fragview.filters import get_refine_datasets
from fragview.pipeline_commands import (
    get_dimple_command,
    get_fspipeline_commands,
)
from fragview.models import PDB
from fragview.forms import RefineForm
from fragview.sites import SITE
from fragview.sites.plugin import Duration, DataSize
from fragview.views.update_jobs import add_update_job
from fragview.scraper import edna, autoproc
from jobs.client import JobsSet


HPC_MODULES = ["gopresto", versions.BUSTER_MOD, versions.PHENIX_MOD]


def datasets(request):
    proj = current_project(request)

    form = RefineForm(request.POST)
    if not form.is_valid():
        return HttpResponseBadRequest(f"invalid refinement arguments {form.errors}")

    pdbmodel = PDB.get(form.pdb_model)
    pdb_file = pdbmodel.file_path()

    if form.use_dimple:
        cmd, cpus = get_dimple_command("input.mtz", form.custom_dimple)
        start_thread(
            launch_refine_jobs,
            proj,
            form.datasets_filter,
            pdb_file,
            form.ref_space_group,
            form.run_aimless,
            "dimple",
            [cmd],
            cpus,
        )

    if form.use_fspipeline:
        cmds, cpus = get_fspipeline_commands(pdb_file, form.custom_fspipe)
        start_thread(
            launch_refine_jobs,
            proj,
            form.datasets_filter,
            pdbmodel.file_path(),
            form.ref_space_group,
            form.run_aimless,
            "fspipeline",
            cmds,
            cpus,
        )

    return render(request, "fragview/jobs_submitted.html")


def launch_refine_jobs(
    proj,
    filters,
    pdb_file,
    space_group,
    run_aimless,
    refine_tool,
    refine_tool_commands,
    cpus,
):
    epoch = round(time.time())
    jobs = JobsSet("Refine")
    hpc = SITE.get_hpc_runner()

    for dset in get_refine_datasets(proj, filters, refine_tool):
        for tool, input_mtz in _find_input_mtzs(proj, dset):
            dset_results_dir = project_results_dataset_dir(proj, dset)

            batch = hpc.new_batch_file(
                f"refine {tool} {dset}",
                project_script(proj, f"refine_{tool}_{refine_tool}_{dset}.sh"),
                project_log_path(proj, f"refine_{tool}_{dset}_{epoch}_%j_out.txt"),
                project_log_path(proj, f"refine_{tool}_{dset}_{epoch}_%j_err.txt"),
                cpus,
            )
            batch.set_options(
                time=Duration(hours=12), nodes=1, mem_per_cpu=DataSize(gigabyte=5),
            )

            batch.add_commands(crypt_shell.crypt_cmd(proj))

            batch.assign_variable("WORK_DIR", "`mktemp -d`")
            batch.add_commands(
                "cd $WORK_DIR",
                crypt_shell.fetch_file(proj, pdb_file, "model.pdb"),
                crypt_shell.fetch_file(proj, input_mtz, "input.mtz"),
            )

            # TODO: load tool specific modules?
            batch.load_modules(HPC_MODULES)

            if run_aimless:
                batch.add_commands(_aimless_cmd(space_group, "input.mtz"))

            batch.add_commands(
                *refine_tool_commands,
                _upload_result_cmd(proj, Path(dset_results_dir, tool)),
                "cd",
                "rm -rf $WORK_DIR",
            )

            batch.save()
            jobs.add_job(batch)

            add_update_job(jobs, hpc, proj, refine_tool, dset, batch)

    jobs.submit()


def _find_input_mtzs(proj, dataset):
    mtz_map = [
        ("xdsapp", "*F.mtz"),
        ("dials", "DEFAULT/scale/AUTOMATIC_DEFAULT_scaled.mtz"),
        ("xdsxscale", "DEFAULT/scale/AUTOMATIC_DEFAULT_scaled.mtz"),
    ]

    dset_dir = project_process_dataset_dir(proj, dataset)

    for tool, mtz_glob in mtz_map:
        tool_dir = Path(dset_dir, tool)
        mtz = next(tool_dir.glob(mtz_glob), None)
        if mtz is not None:
            yield tool, mtz

    #
    # handle ENDA mtz
    #
    mtz = edna.get_result_mtz(proj, dataset)
    if mtz is not None:
        yield "edna", mtz

    #
    # handle autoPROC
    #
    mtz = autoproc.get_result_mtz(proj, dataset)
    if mtz is not None:
        yield "autoproc", mtz


def _aimless_cmd(spacegroup, dstmtz):
    return (
        f"echo 'choose spacegroup {spacegroup}' | pointless HKLIN {dstmtz} HKLOUT {dstmtz} | tee "
        f"pointless.log ; sleep 0.1 ; echo 'START' | aimless HKLIN "
        f"{dstmtz} HKLOUT {dstmtz} | tee aimless.log"
    )


def _upload_result_cmd(proj, res_dir):
    return (
        f"# upload results\n"
        + f"rm $WORK_DIR/model.pdb\n"
        + f"{crypt_shell.upload_dir(proj, '$WORK_DIR', res_dir)}"
    )
