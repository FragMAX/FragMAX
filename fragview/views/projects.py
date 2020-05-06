from glob import glob

from os import path

from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponseNotFound, HttpResponseBadRequest

from fragview.models import Project, PendingProject
from fragview.forms import ProjectForm
from fragview.proposals import get_proposals
from fragview.projects import current_project, project_shift_dirs

from worker import setup_project_files


def list(request):
    """
    projects list page, aka 'manage projects' page
    """
    return render(request,
                  "fragview/projects.html",
                  {"pending_projects": PendingProject.get_projects()})


def edit(request, id):
    """
    GET requests show the 'Edit Project' page
    POST requests will update or delete the project
    """
    proj = get_object_or_404(Project, pk=id)
    form = ProjectForm(request.POST or None, request.FILES or None, model=proj)

    if request.method == "POST":
        action = request.POST["action"]
        if action == "modify":
            if form.is_valid():
                form.update()
                return redirect("/projects/")
        elif action == "delete":
            proj.delete()
            return redirect("/projects/")
        else:
            return HttpResponseBadRequest(f"unexpected action '{action}'")

    return render(
        request,
        "fragview/project.html",
        {"form": form, "project_id": proj.id})


def new(request):
    """
    GET requests show the 'Create new Project' page
    POST requests will try to create a new project
    """
    if request.method == "GET":
        return render(request, "fragview/project.html")

    form = ProjectForm(request.POST, request.FILES)

    if not form.is_valid():
        return render(request, "fragview/project.html", {"form": form})

    proj = form.save(pending=True)
    setup_project_files.delay(proj.id)

    return redirect("/projects/")


def set_current(request, id):
    proj = Project.get_project(get_proposals(request), id)
    if proj is None:
        return HttpResponseNotFound()

    request.user.set_current_project(proj)

    # redirect to the 'landing page' page
    return redirect(reverse("project_summary"))


def project_summary(request):
    proj = current_project(request)

    number_known_apo = len(glob(proj.data_path() + "/raw/" + proj.protein + "/*Apo*"))
    number_datasets = len(glob(proj.data_path() + "/raw/" + proj.protein + "/*"))

    totalapo = 0
    totaldata = 0

    for shift_dir in project_shift_dirs(proj):
        totalapo += len(glob(shift_dir + "/raw/" + proj.protein + "/*Apo*"))
        totaldata += len(glob(shift_dir + "/raw/" + proj.protein + "/*"))

    months = {
        "01": "Jan", "02": "Feb", "03": "Mar", "04": "Apr", "05": "May", "06": "Jun",
        "07": "Jul", "08": "Aug", "09": "Sep", "10": "Oct", "11": "Nov", "12": "Dec",
    }

    natdate = proj.shift[0:4] + " " + months[proj.shift[4:6]] + " " + proj.shift[6:8]

    return render(
        request,
        "fragview/project_summary.html",
        {
            "known_apo": number_known_apo,
            "num_dataset": number_datasets,
            "totalapo": totalapo,
            "totaldata": totaldata,
            "fraglib": proj.library.name,
            "exp_date": natdate
        })


def log_viewer(request):
    logFile = str(request.GET.get('logFile'))
    logFile = f"/data/visitors/{logFile}"
    downloadPath = f"/static/{logFile}"
    if path.exists(logFile):
        with open(logFile, "r") as r:
            log="".join(r.readlines())
    else:
        log=""
    return render(
        request,
        "fragview/log_viewer.html",
        {
            "log": log,
            "dataset": logFile,
            "downloadPath": downloadPath
        })
