from pathlib import Path
from fragview.projects import Project, project_log_path, project_script
from fragview.tools import RefineOptions
from fragview.fileio import upload_dir
from fragview.versions import BUSTER_MOD, PHENIX_MOD
from fragview.sites.plugin import BatchFile, Duration, DataSize
from fragview.sites.current import get_hpc_runner, get_dimple_command


PRESTO_MODULES = ["gopresto", BUSTER_MOD, PHENIX_MOD]


def generate_batch(
    project: Project, dataset, proc_tool: str, input_mtz: Path, options: RefineOptions
) -> BatchFile:

    cmd, cpus = get_dimple_command("input.mtz", options.custom_args)

    script_prefix = f"dimple-{proc_tool}-{dataset.name}"
    batch = get_hpc_runner().new_batch_file(
        f"DIMPLE",
        project_script(project, f"{script_prefix}.sh"),
        project_log_path(project, f"{script_prefix}_%j_out.txt"),
        project_log_path(project, f"{script_prefix}_%j_err.txt"),
        cpus,
    )

    batch.set_options(
        time=Duration(hours=12),
        nodes=1,
        mem_per_cpu=DataSize(gigabyte=5),
    )

    batch.assign_variable("WORK_DIR", "`mktemp -d`")

    batch.add_commands(
        "cd $WORK_DIR",
        f"cp {options.pdb_file} model.pdb",
        f"cp {input_mtz} input.mtz",
    )

    # TODO: load tool specific modules?
    batch.load_modules(PRESTO_MODULES)

    results_dir = Path(project.get_dataset_results_dir(dataset), proc_tool)

    batch.add_commands(
        cmd,
        "# upload results\n",
        f"rm $WORK_DIR/model.pdb\n",
        f"{upload_dir('$WORK_DIR', results_dir)}",
        "cd",
        "rm -rf $WORK_DIR",
    )

    return batch
