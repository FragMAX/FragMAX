from django.shortcuts import render, get_object_or_404, redirect, render_to_response
from django.utils import timezone
from .models import Post
from .forms import PostForm
from difflib import SequenceMatcher

import glob
import os
import random
import natsort
import shutil
import subprocess
import h5py
import itertools
from time import sleep
import threading




################################
#User specific data
#Changing this parameters for different projects based on user credentials
#acr="hCAII"
#proposal="20180489"
#shift="20190127"


setfile="/mxn/home/guslim/Projects/webapp/static/projectSettings/.settings"

def project_definitions():
    proposal = ""
    shift    = ""
    acronym  = ""
    proposal_type = ""
    with open(setfile,"r") as inp:
        prjset=inp.readlines()[0]

    proposal = prjset.split(";")[1].split(":")[-1]
    shift    = prjset.split(";")[2].split(":")[-1]    
    acronym  = prjset.split(";")[3].split(":")[-1]    
    proposal_type = prjset.split(";")[4].split(":")[-1].replace("\n","") 


    path="/data/"+proposal_type+"/biomax/"+proposal+"/"+shift
    subpath="/data/"+proposal_type+"/biomax/"+proposal+"/"
    static_datapath="/static/biomax/"+proposal+"/"+shift
    panddaprocessed="/fragmax/results/pandda/pandda/processed_datasets/"

    
    return proposal, shift, acronym, proposal_type, path, subpath, static_datapath,panddaprocessed


proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

if len(proposal)<7 or len(shift)<7 or len(acr)<2 or len(proposal_type)<5:
    acr="ProteinaseK"
    proposal="20180479"
    shift="20190323"
    proposal_type="visitors"
    path="/data/"+proposal_type+"/biomax/"+proposal+"/"+shift
    subpath="/data/"+proposal_type+"/biomax/"+proposal+"/"
    static_datapath="/static/biomax/"+proposal+"/"+shift
    panddaprocessed="/fragmax/results/pandda/pandda/processed_datasets/"

################################

def index(request):
    return render(request, "fragview/index.html")

def process_all(request):
    return render(request, "fragview/process_all.html",{"acronym":acr})

def settings(request):
    allprc  = str(request.GET.get("updatedefinitions"))
    status = "not updated"
    if ";" in allprc:  
    
        with open(setfile,"w") as outsettings:
            outsettings.write(allprc)
        status="updated"
    else:
        status="No update"
    return render(request, "fragview/settings.html",{"upd":status})

def pipedream(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()   

    datasetPathList=glob.glob(path+"/raw/"+acr+"/*/*master.h5")
    datasetPathList=natsort.natsorted(datasetPathList)
    datasetNameList= [i.split("/")[-1].replace("_master.h5","") for i in datasetPathList]
    datasetList=zip(datasetPathList,datasetNameList)
    return render(request, "fragview/pipedream.html",{"data":datasetList})

def submit_pipedream(request):
    ppdCMD=str(request.GET.get("ppdform"))
    return render(request, "fragview/submit_pipedream.html",{"command":ppdCMD})
    
def load_project_summary(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    number_known_apo=len(glob.glob(path+"/raw/"+acr+"/*Apo*"))
    number_datasets=len(glob.glob(path+"/raw/"+acr+"/*"))
    if "JBSA" in "".join(glob.glob(path+"/raw/"+acr+"/*")):
        fraglib="JBS Xtal Screen"
    else:
        fraglib="Custom library"
    months={"01":"Jan","02":"Feb","03":"Mar","04":"Apr","05":"May","06":"Jun","07":"Jul","08":"Aug","09":"Sep","10":"Oct","11":"Nov","12":"Dec"}
    natdate=shift[0:4]+" "+months[shift[4:6]]+" "+shift[6:8]
    
    return render(request,'fragview/project_summary.html', {
        'acronym':acr,
        "proposal":proposal,
        "proposal_type":proposal_type,
        "shift":shift,
        "known_apo":number_known_apo,
        "num_dataset":number_datasets,
        "fraglib":fraglib,
        "exp_date":natdate})
    
def project_summary_load(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    a=str(request.GET.get('submitProc')) 
    out="No option selected"
    if "colParam" in a:
        create_dataColParam(acr,path)
        out="Data collection parameters synced"
    elif "panddaResults" in a:
        panddaResultSummary()
        out="PanDDA result summary synced"
    elif "procRef" in a:
        resultSummary()    
        out="Data processing and Refinement results synced"
    elif "ligfitting" in a:
        parseLigand_results()
        out="Ligand fitting results synced"
    return render(request,'fragview/project_summary_load.html', {'option': out})



def dataset_info(request):    
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    a=str(request.GET.get('proteinPrefix'))     
    prefix=a.split(";")[0]
    images=a.split(";")[1]
    run=a.split(";")[2]

    images=str(int(images)/2)
    xmlfile=path+"/fragmax/process/"+acr+"/"+prefix+"/"+prefix+"_1.xml"
    datainfo=retrieveParameters(xmlfile)    

    energy=format(float(datainfo["wavelength"])*13.6307922,".2f")
    totalExposure=str(float(datainfo["exposureTime"])*float(datainfo["numberOfImages"]))
    edgeResolution=str(float(datainfo["resolution"])*0.75625)
    ligpng="JBS/"+prefix.split("-")[1]+"/image.png"

    fragConc="100 mM"
    solventConc="15%"
    soakTime="24h"

    if "Apo" in prefix:
        soakTime="Soaking not performed"
        fragConc="-"
        solventConc="-"
    
    new_run=""
    search_new_run_path=path+"/fragmax/manual_proc/"+acr+"/"+prefix

    if os.path.exists(search_new_run_path):
        if glob.glob(path+"/fragmax/manual_proc/"+acr+"/"+prefix+"/"+prefix+"_"+run+"/*") == []:
            new_run="<p style='padding-left:310px;'><font color='green'>All processed data are merged to your project.</font></p>"    
        elif os.path.exists(path+"/fragmax/manual_proc/"+acr+"/"+prefix+"/"+prefix+"_"+run+"/stat"):
            with open(path+"/fragmax/manual_proc/"+acr+"/"+prefix+"/"+prefix+"_"+run+"/stat","r") as inp:
                if "None" in inp.readlines()[0]:
                    new_run="<p style='padding-left:310px;'><font color='green'>All processed data are merged to your project.</font></p>"    
                else:
                    new_run="""<form style="padding-left:310px;" action="/dataproc_merge/" method="get" id="mergeproc">
                               <p><font color='red'>You have manual processed data not merged to your project. 
                               <input type="hidden" value="""+search_new_run_path+""" name="mergeprocinput" size="1">
                               <a href="javascript:{}" onclick="document.getElementById('mergeproc').submit();">Click here</a> to compare results</font></p></form>"""
        else:
            new_run="""<form style="padding-left:310px;" action="/dataproc_merge/" method="get" id="mergeproc">
                       <p><font color='red'>You have manual processed data not merged to your project. 
                       <input type="hidden" value="""+search_new_run_path+""" name="mergeprocinput" size="1">
                       <a href="javascript:{}" onclick="document.getElementById('mergeproc').submit();">Click here</a> to compare results</font></p></form>"""
        #new_run+=search_new_run_path
    #new_run="<p style='padding-left:260px;'>"+path+"/fragmax/manual_proc/"+acr+"/"+prefix+"/"+prefix+"_"+run+"     "+search_new_run_path+"</p>"
    return render(request,'fragview/dataset_info.html', {
        "proposal":proposal,
        "shift":shift,
        "new_proc_run":new_run,
        "run":run,
        'imgprf': prefix, 
        'imgs': images,
        "ligand": ligpng,
        "fragConc": fragConc,
        "solventConc":solventConc,
        "soakTime":soakTime,
        "axisEnd":datainfo["axisEnd"],
        "axisRange":datainfo["axisRange"],
        "axisStart":datainfo["axisStart"],
        "beamShape":datainfo["beamShape"],
        "beamSizeSampleX":datainfo["beamSizeSampleX"],
        "beamSizeSampleY":datainfo["beamSizeSampleY"],
        "detectorDistance":datainfo["detectorDistance"],
        "endTime":datainfo["endTime"],
        "exposureTime":datainfo["exposureTime"],
        "flux":datainfo["flux"],
        "imageDirectory":datainfo["imageDirectory"],
        "imagePrefix":datainfo["imagePrefix"],
        "kappaStart":datainfo["kappaStart"],
        "numberOfImages":datainfo["numberOfImages"],
        "overlap":datainfo["overlap"],
        "phiStart":datainfo["phiStart"],
        "resolution":datainfo["resolution"],
        "rotatioAxis":datainfo["rotatioAxis"],
        "runStatus":datainfo["runStatus"],
        "slitV":datainfo["slitV"],
        "slitH":datainfo["slitH"],
        "startTime":datainfo["startTime"],
        "synchrotronMode":datainfo["synchrotronMode"],
        "transmission":datainfo["transmission"],
        "wavelength":datainfo["wavelength"],
        "xbeampos":datainfo["xbeampos"],
        "snapshot1":datainfo["snapshot1"],
        "snapshot2":datainfo["snapshot2"],
        "snapshot3":datainfo["snapshot3"],
        "snapshot4":datainfo["snapshot4"],
        "ybeampos":datainfo["ybeampos"],        
        "energy":energy,
        "totalExposure":totalExposure,
        "edgeResolution":edgeResolution,
        "acr":prefix.split("-")[0]
        })
  
def post_list(request):
    
    posts = Post.objects.filter(published_date__lte=timezone.now()).order_by('published_date')
    #posts = glob.glob("/data/visitors/*")
    return render(request, 'fragview/post_list.html', {'posts': posts})

def post_detail(request,pk):
    post = get_object_or_404(Post, pk=pk)
    return render(request, 'fragview/post_detail.html', {'post': post})

def post_new(request):
    if request.method == "POST":
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.author = request.user
            post.published_date = timezone.now()
            post.save()
            return redirect('post_detail', pk=post.pk)
    else:
        form = PostForm()
    return render(request, 'fragview/post_edit.html', {'form': form})

def datasets(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()


    #path="/data/"+proposal_type+"/biomax/"+proposal+"/"+shift
    create_dataColParam(acr,path)
    
    with open(path+"/fragmax/process/datacollectionPar.csv","r") as inp:
        a=inp.readlines()
    try:
        acr_list=a[1].split(",")
        prf_list=a[2].split(",")
        res_list=a[3].split(",")
        img_list=a[4].split(",")
        path_list=a[5].split(",")
        snap_list=a[6].split(",")
        png_list=a[7].split(",")
        run_list=a[8].split(",")

        results = zip(img_list,prf_list,res_list,path_list,snap_list,acr_list,png_list,run_list)
        return render_to_response('fragview/datasets.html', {'files': results})
    except:
        return render_to_response('fragview/datasets_notready.html')    
    
def results(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    try:
        with open(path+"/fragmax/process/generalrefsum.csv","r") as inp:
            a=inp.readlines()
        return render_to_response('fragview/results.html', {'files': a})
    except:
        return render_to_response('fragview/results_notready.html')

def request_page(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    a=str(request.GET.get('structure'))     
    name=a.split(";")[0].split("/modelled_structures/")[-1].split(".pdb")[0]  
    a=zip([a.split(";")[0]],[a.split(";")[1]],[a.split(";")[2]],[a.split(";")[3]])  
    
    return render(request,'fragview/pandda_density.html', {'structure': a,'protname':name})

def request_page_res(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    a=str(request.GET.get('structure')) 
    center=""
    if "],[" in a.split(";")[3]:
        center=a.split(";")[3].split("],[")[0]+"]"
    else:
        center=a.split(";")[3].replace("],","")
    center=[a.split(";")[0]]    
    a=zip([a.split(";")[0].split("/pandda/")[-1].split("/final")[0]],[a.split(";")[0]],[a.split(";")[1]],[a.split(";")[2]],[a.split(";")[3]],center )    
    
    return render(request,'fragview/density.html', {'structure': a})

def ugly(request):
    return render(request,'fragview/ugly.html')

def dual_ligand(request):
    try:
        a="load maps and pdb"
        return render(request,'fragview/dual_ligand.html', {'Report': a})
    except:
        return render(request,'fragview/dual_ligand_notready.html', {'Report': a})

##################################
####### COMPARE TWO LIGANDS ######
##################################

def compare_poses(request):   
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()
    a=str(request.GET.get('ligfit_dataset')) 
    data=a.split(";")[0]
    blob=a.split(";")[1]
    png=data.split(acr+"-")[-1].split("_")[0]
    return render(request,'fragview/dual_density.html', {'ligfit_dataset': data,'blob': blob, 'png':png})

def ligfit_results(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    if os.path.exists(path+"/fragmax/process/autolig.csv"):
        try:
            with open(path+"/fragmax/process/autolig.csv","r") as outp:
                a="".join(outp.readlines())
            
            return render(request,'fragview/ligfit_results.html', {'resTable': a})
        except:
            return render(request,'fragview/ligfit_results_notready.html')
    else:
        return render(request,'fragview/ligfit_results_notready.html')

###################################
##########Load external HTML#######
###################################


def pandda(request):    
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    if os.path.exists(path+"/fragmax/results/pandda/pandda/analyses/html_summaries/pandda_analyse.html"):
        try:
            with open(path+"/fragmax/results/pandda/pandda/analyses/html_summaries/pandda_analyse.html","r") as inp:
                a="".join(inp.readlines())

            with open(path+"/fragmax/process/panddarefsum.csv","r") as inp:
                body="".join(inp.readlines())
            thead_ini=a.index("<thead>")+8
            thead_end=a.index("</thead>") 
            tbody_ini=a.index("<tbody>")+8
            tbody_end=a.index("</tbody>")     
            a=a.replace(a[thead_ini:thead_end],"""<tr>
                    <th>Data set</th>
                    <th>Space group</th>
                    <th>Res. [Å]</th>
                    <th>R<sub>work</sub> [%]</th>
                    <th>R<sub>free</sub> [%]</th>
                    <th>RMS bonds [Å]</th>
                    <th>RMS angles [°]</th>
                    <th>a</th>
                    <th>b</th>
                    <th>c</th>
                    <th>α</th>
                    <th>β</th>
                    <th>γ</th>
                    <th>Unmodelled blobs</th>
                    <th>σ</th>
                    <th>Event</th>
                    </tr>""")
            a=a.replace(a[tbody_ini:tbody_end],"<tr></tr>"+body)
            a=a.replace('class="table-responsive"','').replace('id="main-table" class="table table-bordered table-striped"','id="resultsTable"')
            
            return render(request,'fragview/pandda.html', {'Report': a})
        except:
            return render(request,'fragview/pandda_notready.html')
    else:
        return render(request,'fragview/pandda_notready.html')

def procReport(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    biomax_static=path.replace("/data/visitors/","/static/")
    a=str(request.GET.get('dataHeader')) 
    if a.startswith("dials"):
        a=a.replace("dials","")
        a=path+"/fragmax/process/"+a.split("-")[0]+"/"+a+"/"+a+"_1/dials/xia2.html"
        if os.path.exists(a):
            with open(a,"r") as inp:
                html="".join(inp.readlines())
        else:
            html='<h5 style="padding-left:260px;" >DIALS report for this dataset is not available</h5>'
        html=html.replace("DEFAULT/scale/",a.replace(path,biomax_static).replace("xia2.html","DEFAULT/scale/"))
        html=html.replace("DataFiles/",a.replace(path,biomax_static).replace("xia2.html","DataFiles/"))
    
    if a.startswith("xdsxscale"):
        a=a.replace("xdsxscale","")
        a=path+"/fragmax/process/"+a.split("-")[0]+"/"+a+"/"+a+"_1/xdsxscale/xia2.html"
        if os.path.exists(a):
            with open(a,"r") as inp:
                html="".join(inp.readlines())
        else:
            html='<h5 style="padding-left:260px;" >XDS/XSCALE report for this dataset is not available</h5>'
        html=html.replace("DEFAULT/scale/",a.replace(path,biomax_static).replace("xia2.html","DEFAULT/scale/"))
        html=html.replace("DataFiles/",a.replace(path,biomax_static).replace("xia2.html","DataFiles/"))
    
    if a.startswith("xdsapp"):
        a=a.replace("xdsapp","")
        a=path+"/fragmax/process/"+acr+"/"+a+"/"+a+"_1/xdsapp/results_"+a+"_1_data.txt"
        #a=path+"/fragmax/process/"+a.split("-")[0]+"/"+a+"/"+a+"_1/xdsxscale/xia2.html"
        if os.path.exists(a):
            with open(a,"r") as inp:
                html="<br>".join(inp.readlines())
        else:
            html='<h5 style="padding-left:260px;" >XDSAPP report for this dataset is not available</h5>'
        #html=html.replace("DEFAULT/scale/",a.replace(path,biomax_static).replace("xia2.html","DEFAULT/scale/"))
        #html=html.replace("DataFiles/",a.replace(path,biomax_static).replace("xia2.html","DataFiles/"))
        html='''<style>  .card {  margin: 40px 0 0 50px !important; }</style><div class="card" ><div class="card-content"><div class="card-title">XDSAPP Processing report</div><br>'''+html+'</div></div>'

    if a.startswith("autoPROC"):
        a=a.replace("autoPROC","")
        if os.path.exists(path+"/fragmax/results/"+a+"_1/pipedream/process/summary.html"):
            a=path+"/fragmax/results/"+a+"_1/pipedream/process/summary.html"
        else:
            a=path+"/fragmax/process/"+a.split("-")[0]+"/"+a+"/"+a+"_1/autoproc/summary.html"


        if os.path.exists(a):
            with open(a,"r") as inp:
                html="".join(inp.readlines())
        else:
            html='<h5 style="padding-left:310px;" >autoPROC report for this dataset is not available</h5>' 
    html=html.replace('src="/data/visitors/','src="/static/').replace('href="/data/visitors/','href="/static/').replace("gphl_logo.png","data:image/png;base64,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")

    return render(request,'fragview/procReport.html', {'Report': html})

def dataproc_merge(request):    
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    outinfo=str(request.GET.get("mergeprocinput")).replace("static","data/visitors")
    
    runList="<br>".join(glob.glob(outinfo+"*/*"))
    
    return render(request,'fragview/dataproc_merge.html', {'datasetsRuns': runList})


def reproc_web(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()
    
    dataproc = str(request.GET.get("submitProc"))
    outdir=dataproc.split(";")[0]
    data=dataproc.split(";")[1]
    SW=outdir.split(" #")[-1]
    outdir=add_run_DP(outdir)
    if "autoPROC" in SW:
        data=data+" -d "+outdir.split("cd ")[-1].split(" #")[0]
    if "XDSAPP" in SW:
        data=data.replace("xdsapp --cmd","xdsapp --cmd "+" --dir "+outdir.split("cd ")[-1].split(" #")[0])
    
    base_script="""#!/bin/bash\n#!/bin/bash\n#SBATCH -t 99:55:00\n#SBATCH -J FragWeb\n#SBATCH --exclusive\n#SBATCH -N1\n#SBATCH --cpus-per-task=48\n#SBATCH --mem=220000\n#SBATCH -o /data/visitors/biomax/20180489/20190127/fragmax/logs/manual_proc_WebApp_%j.out\n#SBATCH -e /data/visitors/biomax/20180489/20190127/fragmax/logs/manual_proc_WebApp_%j.err\nmodule purge\nmodule load CCP4 XDSAPP autoPROC Phenix BUSTER\n\n{0}\n\n{1}\n""".format(outdir, data)

    with open("/data/visitors/biomax/20180489/20190127/fragmax/scripts/reprocess_webapp.sh","w") as inp:
        inp.write(base_script)

    command ='echo "module purge | module load CCP4 XDSAPP | sbatch /data/visitors/biomax/20180489/20190127/fragmax/scripts/reprocess_webapp.sh " | ssh -F ~/.ssh/ clu0-fe-1'
    subprocess.call(command,shell=True)

    proc = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'squeue','-u','guslim'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    output=""
    for i in out.decode("UTF-8").split("\n")[1:-1]:
        output+="<tr><td>"+"</td><td>".join(i.split())+"</td></tr>"
    base_script=base_script.replace("\n","<br>")
    return render(request,'fragview/reproc_web.html', {'command': base_script})


def dataproc_datasets(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    allprc  = str(request.GET.get("submitallProc"))
    dtprc   = str(request.GET.get("submitdtProc"))
    refprc  = str(request.GET.get("submitrfProc"))
    ligproc = str(request.GET.get("submitligProc"))
    if allprc!="None":
        pass
    if dtprc!="None":
        dtprc_inp=dtprc.split(";")
        usedials=dtprc_inp[1].split(":")[-1]
        usexdsxscale=dtprc_inp[2].split(":")[-1]
        usexdsapp=dtprc_inp[3].split(":")[-1]
        useautproc=dtprc_inp[4].split(":")[-1]
        spacegroup=dtprc_inp[5].split(":")[-1]
        cellparam=dtprc_inp[6].split(":")[-1]
        friedel=dtprc_inp[7].split(":")[-1]
        datarange=dtprc_inp[8].split(":")[-1]
        rescutoff=dtprc_inp[9].split(":")[-1]
        cccutoff=dtprc_inp[10].split(":")[-1]
        isigicutoff=dtprc_inp[11].split(":")[-1]
        sbatch_script_list=list()
        if usexdsapp=="true":
            t = threading.Thread(target=run_xdsapp,args=(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff))
            t.daemon = True
            t.start()
            
            sbatch_script_list.append(path+"/fragmax/scripts/xdsapp_fragmax_part0.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/xdsapp_fragmax_part1.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/xdsapp_fragmax_part2.sh")
        if usedials=="true":
            t = threading.Thread(target=run_dials,args=(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff))
            t.daemon = True
            t.start()
            
            sbatch_script_list.append(path+"/fragmax/scripts/dials_fragmax_part0.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/dials_fragmax_part1.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/dials_fragmax_part2.sh")
        if useautproc=="true":
            t = threading.Thread(target=run_autoproc,args=(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff))
            t.daemon = True
            t.start()

            sbatch_script_list.append(path+"/fragmax/scripts/autoproc_fragmax_part0.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/autoproc_fragmax_part1.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/autoproc_fragmax_part2.sh")            
        if usexdsxscale=="true":
            t = threading.Thread(target=run_xdsxscale,args=(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff))
            t.daemon = True
            t.start()
            
            sbatch_script_list.append(path+"/fragmax/scripts/xdsxscale_fragmax_part0.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/xdsxscale_fragmax_part1.sh")
            sbatch_script_list.append(path+"/fragmax/scripts/xdsxscale_fragmax_part2.sh")
        
        
        #for script in sbatch_script_list:            
        #    command ='echo "module purge | module load CCP4 XDSAPP DIALS/1.12.3-PReSTO | sbatch '+script+' " | ssh -F ~/.ssh/ clu0-fe-1'
        #    subprocess.call(command,shell=True)
        
    
    if refprc!="None":
        pass
    if ligproc!="None":
        pass
    return render(request,'fragview/dataproc_datasets.html', {'allproc': "\n"+"\n".join(sbatch_script_list)})

def kill_HPC_job(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    jobid_k=str(request.GET.get('jobid_kill'))     

    subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'scancel', jobid_k], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    sleep(5)
    proc = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'squeue','-u','guslim'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    output=""   


    for i in out.decode("UTF-8").split("\n")[1:-1]:
        proc_info = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'scontrol', 'show', 'jobid', '-dd', i.split()[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_info, err_info = proc_info.communicate()
        stdout_file=[x for x in out_info.decode("UTF-8").splitlines() if "StdOut=" in x][0].split("/data/visitors")[-1]
        stderr_file=[x for x in out_info.decode("UTF-8").splitlines() if "StdErr=" in x][0].split("/data/visitors")[-1]
        try:
            prosw=      [x for x in out_info.decode("UTF-8").splitlines() if "#SW=" in x][0].split("#SW=")[-1]
        except:
            prosw="Unkown"
        output+="<tr><td>"+"</td><td>".join(i.split())+"</td><td>"+prosw+"</td><td><a href='/static"+stdout_file+"'> job_"+i.split()[0]+".out</a></td><td><a href='/static"+stderr_file+"'>job_"+i.split()[0]+""".err</a></td><td>
           
        <form action="/hpcstatus_jobkilled/" method="get" id="kill_job_{0}" >
            <button class="btn-small" type="submit" value={0} name="jobid_kill" size="1">Kill</button>
        </form>

        </tr>""".format(i.split()[0])

    proc_sacct = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'sacct','-u','guslim'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_sacct, err_sacct = proc_sacct.communicate()
    sacct=""
    for a in out_sacct.decode("UTF-8").split("\n")[2:-1]:
        linelist=[a[:13],a[13:23],a[23:34],a[34:45],a[45:56],a[56:67],a[67:]]
        linelist=[x.replace(" ","") for x in linelist]
        sacct+="<tr><td>"+"</td><td>".join(linelist)+"</td></tr>"

    
    
    return render(request,'fragview/hpcstatus_jobkilled.html', {'command': output, 'history': sacct})

def hpcstatus(request):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()


    proc = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'squeue','-u','guslim'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    output=""

    


    for i in out.decode("UTF-8").split("\n")[1:-1]:
        proc_info = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'scontrol', 'show', 'jobid', '-dd', i.split()[0]], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out_info, err_info = proc_info.communicate()
        stdout_file=[x for x in out_info.decode("UTF-8").splitlines() if "StdOut=" in x][0].split("/data/visitors")[-1]
        stderr_file=[x for x in out_info.decode("UTF-8").splitlines() if "StdErr=" in x][0].split("/data/visitors")[-1]
        try:
            prosw=      [x for x in out_info.decode("UTF-8").splitlines() if "#SW=" in x][0].split("#SW=")[-1]
        except:
            prosw="Unkown"
        output+="<tr><td>"+"</td><td>".join(i.split())+"</td><td>"+prosw+"</td><td><a href='/static"+stdout_file+"'> job_"+i.split()[0]+".out</a></td><td><a href='/static"+stderr_file+"'>job_"+i.split()[0]+""".err</a></td><td>
           
        <form action="/hpcstatus_jobkilled/" method="get" id="kill_job_{0}" >
            <button class="btn-small" type="submit" value={0} name="jobid_kill" size="1">Kill</button>
        </form>

        </tr>""".format(i.split()[0])

    proc_sacct = subprocess.Popen(['ssh', '-t', 'clu0-fe-1', 'sacct','-u','guslim'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out_sacct, err_sacct = proc_sacct.communicate()
    sacct=""
    for a in out_sacct.decode("UTF-8").split("\n")[2:-1]:
        linelist=[a[:13],a[13:23],a[23:34],a[34:45],a[45:56],a[56:67],a[67:]]
        linelist=[x.replace(" ","") for x in linelist]
        sacct+="<tr><td>"+"</td><td>".join(linelist)+"</td></tr>"

    

    return render(request,'fragview/hpcstatus.html', {'command': output, 'history': sacct})


#####################################################################################
#####################################################################################
########################## REGULAR PYTHON FUNCTIONS #################################
#####################################################################################
#####################################################################################

def add_run_DP(outdir):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    fout=outdir.split("cd ")[-1].split(" #")[0]
    SW=outdir.split(" #")[-1]
    runs=[x for x in glob.glob(fout+"/*") if os.path.isdir(x) and "run_" in x]
    if len(runs)==0:
        last_run=0
    else:
        rlist=[x.split("/")[-1] for x in runs]
        last_run=[int(x.replace("run_","")) for x in natsort.natsorted(rlist)][-1]
    
    next_run=fout+"/run_"+str(last_run+1)
    
    if not os.path.exists(next_run) and "autoPROC" not in SW:
        os.makedirs(next_run, exist_ok=True)

    return "cd "+next_run+" #"+SW

def retrieveParameters(xmlfile):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    #Dictionary with parameters for dataset info template page
    
    with open(xmlfile,"r") as inp:
        a=inp.readlines()

    paramDict=dict()
    paramDict["axisEnd"]=format(float(a[4].split("</")[0].split(">")[1]),".1f")
    paramDict["axisRange"]=format(float(a[5].split("</")[0].split(">")[1]),".1f")
    paramDict["axisStart"]=format(float(a[6].split("</")[0].split(">")[1]),".1f")
    paramDict["beamShape"]=a[7].split("</")[0].split(">")[1]
    paramDict["beamSizeSampleX"]=format(float(a[8].split("</")[0].split(">")[1])*1000,".0f")
    paramDict["beamSizeSampleY"]=format(float(a[9].split("</")[0].split(">")[1])*1000,".0f")
    paramDict["detectorDistance"]=format(float(a[16].split("</")[0].split(">")[1]),".2f")
    paramDict["endTime"]=a[18].split("</")[0].split(">")[1]
    paramDict["exposureTime"]=format(float(a[19].split("</")[0].split(">")[1]),".3f")
    paramDict["flux"]=a[22].split("</")[0].split(">")[1]
    paramDict["imageDirectory"]=a[23].split("</")[0].split(">")[1]
    paramDict["imagePrefix"]=a[24].split("</")[0].split(">")[1]
    paramDict["kappaStart"]=format(float(a[26].split("</")[0].split(">")[1]),".2f")
    paramDict["numberOfImages"]=a[27].split("</")[0].split(">")[1]
    paramDict["overlap"]=format(float(a[29].split("</")[0].split(">")[1]),".1f")
    paramDict["phiStart"]=format(float(a[30].split("</")[0].split(">")[1]),".2f")
    paramDict["resolution"]=format(float(a[32].split("</")[0].split(">")[1]),".2f")
    paramDict["rotatioAxis"]=a[33].split("</")[0].split(">")[1]
    paramDict["runStatus"]=a[34].split("</")[0].split(">")[1]
    paramDict["slitV"]=format(float(a[35].split("</")[0].split(">")[1])*1000,".1f")
    paramDict["slitH"]=format(float(a[36].split("</")[0].split(">")[1])*1000,".1f")
    paramDict["startTime"]=a[38].split("</")[0].split(">")[1]
    paramDict["synchrotronMode"]=a[39].split("</")[0].split(">")[1]
    paramDict["transmission"]=format(float(a[40].split("</")[0].split(">")[1]),".3f")
    paramDict["wavelength"]=format(float(a[41].split("</")[0].split(">")[1]),".6f")
    paramDict["xbeampos"]=format(float(a[42].split("</")[0].split(">")[1]),".2f")
    paramDict["snapshot1"]=a[43].split("</")[0].split(">")[1]
    paramDict["snapshot2"]=a[44].split("</")[0].split(">")[1]
    paramDict["snapshot3"]=a[45].split("</")[0].split(">")[1]
    paramDict["snapshot4"]=a[46].split("</")[0].split(">")[1]
    paramDict["ybeampos"]=format(float(a[47].split("</")[0].split(">")[1]),".2f")
    
    return paramDict

def create_dataColParam(acr, path):
    if os.path.exists(path+"/fragmax/process/datacollectionPar.csv"):
        return
    else:
        xml_list=glob.glob(path+"*/process/"+acr+"/*/*/fastdp/cn*/ISPyBRetrieveDataCollectionv1_4/ISPyBRetrieveDataCollectionv1_4_dataOutput.xml")
        img_list=list()
        prf_list=list()
        res_list=list()
        snap_list=list()
        path_list=list()
        acr_list=list()
        png_list=list()
        run_list=list()

        for xml in natsort.natsorted(xml_list):
            with open(xml) as inp:
                    a=inp.readlines()

            for i in a:
                if "numberOfImages" in i:
                    img_list.append(i.split(">")[1].split("<")[0])
                if "resolution" in i:
                    res_list.append("%.2f" % float(i.split(">")[1].split("<")[0])) 
                #if "xtalSnapshotFullPath1" in i:        
                #    snap_list.append(i.split(">")[1].split("<")[0])     
                if "dataCollectionNumber" in i:
                    run_number=i.split(">")[1].split("<")[0]
                    run_list.append(i.split(">")[1].split("<")[0])
                if "imagePrefix" in i:
                    prf=i.split(">")[1].split("<")[0]
                    prf_list.append(prf) 
            #snap_list.append(path.replace("/data/visitors/","/static/")+"/fragmax/process/"+acr+"/"+prf+"/"+prf+"_snapshot.jpg")
            snap_list.append("/static/pyarch/visitors/"+proposal+"/"+shift+"/raw/"+acr+"/"+prf+"/"+prf+"_"+run_number+"_1.snapshot.jpeg")
            os.makedirs(path+"/fragmax/process/"+acr+"/"+prf+"/",exist_ok=True)
            shutil.copyfile(xml,path+"/fragmax/process/"+acr+"/"+prf+"/"+prf+"_1.xml")
            path_list.append(xml.split("xds")[0].replace("process","raw"))
            acr_list.append(acr)
        
                            
        #Create fragment list png for Datasets view                         
        pngDict=dict()
        for prf in prf_list:
            if "Apo" in prf:
                pngDict[prf]="/static/img/apo.png"
            elif "Apo" not in prf and "DM" not in prf and "ICC" not in prf:
                wellNo=prf.split(acr+"-")[-1]        
                pngDict[prf]="/static/blog/fragment/"+"JBS"+"/"+wellNo+"/"+wellNo+".png"
            elif "ICC" in prf:
                wellNo=prf.split(acr+"-")[-1]        
                pngDict[prf]="/static/blog/fragment/"+"ICCBS"+"/"+wellNo+"/"+wellNo+".png"
            else:
                pngDict[prf]="/static/img/nolig.png"

        png_list=[pngDict[x] for x in prf_list]
        
        line="sep=,"
        line+="\n"
        line+=",".join(acr_list)
        line+="\n"
        line+=",".join(prf_list)
        line+="\n"
        line+=",".join(res_list)
        line+="\n"
        line+=",".join(img_list)
        line+="\n"
        line+=",".join(path_list)
        line+="\n"
        line+=",".join(snap_list)
        line+="\n"
        line+=",".join(png_list)
        line+="\n"

        line+=",".join(run_list)
        for x in os.listdir(subpath):
            if os.path.isdir(subpath+x+"/fragmax/process/"):
                with open(subpath+x+"/fragmax/process/datacollectionPar.csv","w") as outp:
                    outp.write(line)

        xmlDict=dict()
        for x in glob.glob(path+"/fragmax/process/"+acr+"/*/*.xml"):
            xmlDict[x.split("/")[9]]=x
        
        for key,value in xmlDict.items():
            paramDict=retrieveParameters(value)
            try:
                hdf2jpg(paramDict)
            except:
                print("No data for "+key) 
    
def fsp_info(entry):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    usracr=""
    spg=""
    res=""
    r_work=""
    r_free=""
    bonds=""
    angles=""
    blob=""
    sigma=""
    a=""
    b=""
    c=""
    alpha=""
    beta=""
    gamma=""
    blist=""    
    usracr=entry.split("/results/")[1].split("/")[0]+entry.split(entry.split("/results/")[1].split("/")[0])[-1].split("_merged.pdb")[0]+"_fsp"
        
    with open(entry,"r") as inp:
        pdb_file=inp.readlines()
    
    for line in pdb_file:
        if "REMARK Final:" in line:            
            r_work=line.split()[4]
            r_free=line.split()[7]
            r_free=str("{0:.2f}".format(float(r_free)))
            r_work=str("{0:.2f}".format(float(r_work)))
            bonds=line.split()[10]
            angles=line.split()[13]
        if "REMARK   3   RESOLUTION RANGE HIGH (ANGSTROMS) :" in line:
            res=line.split(":")[-1].replace(" ","").replace("\n","")
            res=str("{0:.2f}".format(float(res)))
        if "CRYST1" in line:
            a,b,c,alpha,beta,gamma=line.split()[1:-4]
            a=str("{0:.2f}".format(float(a)))
            b=str("{0:.2f}".format(float(b)))
            c=str("{0:.2f}".format(float(c)))

            spg="".join(line.split()[-4:])
            
    with open("/".join(entry.split("/")[:-1])+"/blobs.log","r") as inp:
        blobs_log=inp.readlines()
    for line in blobs_log:
        if "using sigma cut off " in line:
            sigma=line.split("cut off")[-1].replace(" ","").replace("\n","")
        if "INFO:: cluster at xyz = " in line:
            blob=line.split("(")[-1].split(")")[0].replace("  ","").replace("\n","")
            blob="["+blob+"]"
            blist=blob+"<br>"+blist
        #print(blist)
    try:
        pdbout=[x for x in glob.glob(path+panddaprocessed+usracr+"/*/*.pdb") if "fitted" not in x and "ligand" not in x][0].replace("/data/visitors/","")
        event1=[x for x in glob.glob(path+panddaprocessed+usracr+"/*.ccp4") if "event_1" in x][0].replace("/data/visitors/","")
        ccp4_nat=[x for x in glob.glob(path+panddaprocessed+usracr+"/*.ccp4") if "z_map.native" in x][0].replace("/data/visitors/","")
        tr= """<tr><td><form action="/pandda_density/" method="get" id="%s_form" target="_blank"><input type="hidden" value="%s" name="structure" size="1"/><a href="javascript:{}" onclick="document.getElementById('%s_form').submit();"></form>%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>YES</td></tr>""".replace("        ","").replace("\n","")%(acr,pdbout+";"+event1+";"+ccp4_nat+";"+blob.split("<br>")[0],acr,acr,spg,res,r_work,r_free,bonds,angles,a,b,c,alpha,beta,gamma,blist,sigma)
    except:
        pdbout="None"
        event1="None"
        ccp4_nat="None"
        tr= """<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>NO</td></tr>""".replace("        ","").replace("\n","")%(acr,spg,res,r_work,r_free,bonds,angles,a,b,c,alpha,beta,gamma,blob,sigma)
    
    return tr

def dpl_info(entry):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    usracr=""
    spg=""
    res=""
    r_work=""
    r_free=""
    bonds=""
    angles=""
    blob=""
    sigma=""
    a=""
    b=""
    c=""
    alpha=""
    beta=""
    gamma=""
    
    with open(entry,"r") as inp:
        dimple_log=inp.readlines()
    for n,line in enumerate(dimple_log):
        if "data_file: " in line:
            usracr=line.split("/")[-1].split("_merged.pdb")[0].split("_unmerged_unscaled.mtz")[0].replace("\n","")+"_dimple"
        if "# MTZ " in line:
            spg=line.split(")")[1].split("(")[0].replace(" ","")
            a,b,c,alpha,beta,gamma=line.split(")")[1].split("(")[-1].replace(" ","").split(",")
            alpha=str("{0:.2f}".format(float(alpha)))
            beta=str("{0:.2f}".format(float(beta)))
            gamma=str("{0:.2f}".format(float(gamma)))
        if line.startswith( "info:  8/8   R/Rfree"):
            r_work,r_free=line.split("->")[-1].replace("\n","").replace(" ","").split("/")
            r_free=str("{0:.2f}".format(float(r_free)))
            r_work=str("{0:.2f}".format(float(r_work)))
        if line.startswith( "density_info: Density"):
            sigma=line.split("(")[-1].split(" sigma")[0]
        if line.startswith("blobs: "):
            l=""
            l=ast.literal_eval(line.split(":")[-1].replace(" ",""))
            blob="<br>".join(map(str,l[:3]))
            #print(blob)
        if line.startswith("#     RMS: "):
            bonds,angles=line.split()[5],line.split()[9]
        if line.startswith("info: resol. "):
            res=line.split()[2]
            res=str("{0:.2f}".format(float(res)))
    try:
        pdbout=[x for x in glob.glob(path+panddaprocessed+usracr+"/*/*.pdb") if "fitted" not in x and "ligand" not in x][0].replace("/data/visitors/","")
        event1=[x for x in glob.glob(path+panddaprocessed+usracr+"/*.ccp4") if "event_1" in x][0].replace("/data/visitors/","")
        ccp4_nat=[x for x in glob.glob(path+panddaprocessed+usracr+"/*.ccp4") if "z_map.native" in x][0].replace("/data/visitors/","")
        tr= """<tr><td><form action="/pandda_density/" method="get" id="%s_form" target="_blank"><input type="hidden" value="%s" name="structure" size="1"/><a href="javascript:{}" onclick="document.getElementById('%s_form').submit();"></form>%s</a></td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>YES</td></tr>"""%(acr,pdbout+";"+event1+";"+ccp4_nat+";"+blob.split("<br>")[0],acr,acr,spg,res,r_work,r_free,bonds,angles,a,b,c,alpha,beta,gamma,blob,sigma)

    except:
        pdbout="None"
        event1="None"
        ccp4_nat="None"
        tr= """<tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>NO</td></tr>"""%(acr,spg,res,r_work,r_free,bonds,angles,a,b,c,alpha,beta,gamma,blob,sigma)
    return tr

def parseLigand_results():
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    #acr=acrOriginal

    procDict=dict()
    rhofitDict=dict()
    ligfitDict=dict()
    resDict=dict()
    for x in natsort.natsorted(glob.glob(path+"/fragmax/results/ligandfit/*")):
        procDict[x.split("/")[-1]]=x 

    for x in glob.glob(path+"/fragmax/results/ligandfit/*/rhofit"):
        rhofitDict[x.split("/")[-2]]=x 

    for x in glob.glob(path+"/fragmax/results/ligandfit/*/ligandfit"):
        ligfitDict[x.split("/")[-2]]=x 

    for key,value in procDict.items():
        if key in rhofitDict:
            with open(value+"/rhofit/merged.pdb","r") as inp:
                resDict[key]=[x.split(":")[-1].replace("\n","").replace(" ","") for x in inp.readlines() if "REMARK   3   RESOLUTION RANGE HIGH (ANGSTROMS) :" in x][0]

    rhofitScore=dict()
    ligfitScore=dict()
    for key,value in procDict.items():
        if key in ligfitDict:
            if os.path.exists(value+"/ligandfit/LigandFit_summary.dat"):
                with open(value+"/ligandfit/LigandFit_summary.dat","r") as inp:
                    a=inp.readlines()        
                ligfitScore[key]=a[6].split()[2]

        if key in rhofitDict:
            if os.path.exists(value+"/rhofit/Hit_corr.log"):
                with open(value+"/rhofit/Hit_corr.log","r") as inp:
                    a=inp.readlines()               
                rhofitScore[key]=a[0].split()[1]


    ligpng=dict()
    for key in procDict.keys():
        w=key.split(acr+"-")[-1].split("_")[0]
        ligpng[key]="/static/blog/fragment/JBS/"+w+"/image.png"

    with open(path+"/fragmax/process/panddarefsum.csv","r") as inp:
        a=inp.readlines()

    blobsDict=dict()
    for d in a:
        if "id=" in d:
            blobsDict[d.split('id="')[-1].split('_form">')[0]]=d.split("</td><td>")[-3].split("<br>")[0].replace(" ","")
        else:
            blobsDict[d.split("<tr><td>")[-1].split("</td><td>")[0]]=d.split("</td><td>")[-3].split("<br>")[0].replace(" ","")

    sortedList=list()
    for key,value in procDict.items():
        if key in resDict and rhofitScore and ligfitScore and ligpng:
            l='''<tr>
            <td>
            <form action="/dual_density/" method="get" id="%s_form" target="_blank">
            <button class="btn" type="submit" value="%s;%s" name="ligfit_dataset" size="1">Open Dual Viewer</button>
            </form>
            </td>
            <td>%s</td>
            <td>%s</td>
            <td>%s</td>
            <td>%s</td>
            <td>
              <a href=%s target="_blank">
                <object data=%s type="image/png" height="116" width="116">          
                </object>
              </a>
            </td>  
            </tr>
            '''.replace("","") % (key,key,blobsDict[key],key,resDict[key],rhofitScore[key],ligfitScore[key],ligpng[key],ligpng[key])


        sortedList.append(l)

    with open(path+"/fragmax/process/autolig.csv","w") as outp:
            outp.write("".join(sortedList))

def panddaResultSummary():
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()


    acr_list=glob.glob(subpath+"*/fragmax/results/"+acrOriginal+"*")
    pipeline_dict=dict()
    for acr in acr_list:
        pipeline_dict[acr.split("/")[-1]]=glob.glob(acr+"/*")

    dimple_dict=dict()
    fspipe_dict=dict()

    for key,value in pipeline_dict.items():
        l=list()
        for dtprc in value:        
            if os.path.exists(dtprc+"/dimple/dimple.log"):
                l.append(dtprc+"/dimple/dimple.log")
        dimple_dict[key]=l
        m=list()
        for dtprc in value:        
            if os.path.isdir(dtprc+"/fspipeline"):
                m.append(glob.glob(dtprc+"/fspipeline/final*pdb")[0])
        fspipe_dict[key]=m


    fspline=""
    dimpleline=""
    sortedline=""

    sortedacr=[x for x in natsort.natsorted(set(list(fspipe_dict.keys())+list(dimple_dict.keys()))) if "Apo" not in x and "DM" not in x]
    sortedacr+=[x for x in natsort.natsorted(set(list(fspipe_dict.keys())+list(dimple_dict.keys()))) if "Apo" in x or "DM" in x]



    for key,value in natsort.natsorted(fspipe_dict.items()):
        for f in value:
            fspline+=fsp_info(f)+"\n"

    for key,value in natsort.natsorted(dimple_dict.items()):
        for f in value:
            dimpleline+=dpl_info(f)+"\n"

    dl=fspline.split("\n")+dimpleline.split("\n")            
    for i in sortedacr:
        for j in dl:
            if i in j:
                sortedline+=j+"\n"            

    with open(path+"/fragmax/process/panddarefsum.csv","w") as outp:
        outp.write(sortedline)

def resultSummary():
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()


    acr_list=glob.glob(subpath+"*/fragmax/results/"+acrOriginal+"*")
    pipeline_dict=dict()
    for acr in acr_list:
        pipeline_dict[acr.split("/")[-1]]=glob.glob(acr+"/*")

    dimple_dict=dict()
    fspipe_dict=dict()

    for key,value in pipeline_dict.items():
        l=list()
        for dtprc in value:        
            if os.path.exists(dtprc+"/dimple/dimple.log"):
                l.append(dtprc+"/dimple/dimple.log")
        dimple_dict[key]=l
        m=list()
        for dtprc in value:        
            if os.path.isdir(dtprc+"/fspipeline"):
                m.append(glob.glob(dtprc+"/fspipeline/final*pdb")[0])
        fspipe_dict[key]=m


    fspline=""
    dimpleline=""
    sortedline=""

    sortedacr=[x for x in natsort.natsorted(set(list(fspipe_dict.keys())+list(dimple_dict.keys()))) if "Apo" not in x and "DM" not in x]
    sortedacr+=[x for x in natsort.natsorted(set(list(fspipe_dict.keys())+list(dimple_dict.keys()))) if "Apo" in x or "DM" in x]



    for key,value in natsort.natsorted(fspipe_dict.items()):
        for f in value:            
            fspline+=fsp_info_general(f)+"\n"

    for key,value in natsort.natsorted(dimple_dict.items()):
        for f in value:
            dimpleline+=dpl_info_general(f)+"\n"

    dl=fspline.split("\n")+dimpleline.split("\n")            
    for i in sortedacr:
        for j in dl:
            if i in j:
                sortedline+=j+"\n"            

    with open(path+"/fragmax/process/generalrefsum.csv","w") as outp:
        outp.write(sortedline)

def hdf2jpg(paramDict):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()

    #generate two diffraction JPG: 1st image, half-th dataset
    #saves in fragmax/process folder
    
    imgdir,frames,prefix=paramDict["imageDirectory"],paramDict["numberOfImages"],paramDict["imagePrefix"]
    if imgdir[-1]!="/":
        imgdir+="/"
    
    h5master=glob.glob(imgdir+"*master.h5")[0]
    imglist=[str(1),str(int(frames)/2)]
    print("Converting to JPG")
    def convert(imgnb):
       name=h5master.split("_master")[0]

       converto2cbf="eiger2cbf "+h5master+" "+imgnb+" "+name+"_"+imgnb+".cbf"
       subprocess.call(converto2cbf, shell=True)



       convert2jpeg="diff2jpeg "+name+"_"+imgnb+".cbf"
       subprocess.call(convert2jpeg, shell=True)


       clean_up="rm "+name+"_"+imgnb+".cbf"
       subprocess.call(clean_up, shell=True)
       
       mvtofragmax="mv "+imgdir+"*.jpg "+path+"/fragmax/process/"+acr+"/"+prefix+"/"
       subprocess.call(mvtofragmax, shell=True)


    for i in imglist:        
        t = Thread(target=convert, args=(i,))
        t.start()

def run_xdsapp(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()


    def listdir_fullpath(d):
        return [os.path.join(d, f) for f in os.listdir(d)]


    # In[5]:


    ##Start up definitions



    proteinNames      = dict() 
    proteinNames_path = dict()
    datasets          = dict()
    scriptList        = list()

    acronyms=os.listdir(path+"/raw/") #list acronym for collected data

    acronyms=[x for x in acronyms if "DS_Store" not in x]


    for acronym in acronyms: 
            #creat a dict of protein names
            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) 
            #create a dict of protein names with full path to the dir
            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) 

    for collectedProteins in proteinNames_path.values():
            for proteinName in collectedProteins:
                    #create a dict of keys:proteinNames, values:master files - 
                    datasets[proteinName] = glob.glob(proteinName+"/*master.h5") 


    # In[6]:



    def images_collected(h5image):
        f=h5py.File(h5image,"r")
        return int(f.get("entry/sample/goniometer/omega_range_total").value/f.get("entry/sample/goniometer/omega_increment").value)


    # In[7]:


    def split(a, n):
        k, m = divmod(len(a), n)
        return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))


    # In[8]:


    def createScript(ind, outd, fromImage, toImage,dataName):
            if "/Volumes/offline-visitors" in dataName:
                dataName =dataName.replace("/Volumes/offline-","/data/")
                ind      =ind.replace     ("/Volumes/offline-","/data/")
                outd     =outd.replace    ("/Volumes/offline-","/data/")

            fromImage=str(fromImage)
            toImage=str(toImage)
            #create empty string to start the script
            content=""
            content="\n"
            content="\n"

            xdsappcontent   = content



            # XDSAPP definitions 
            xdsappcontent+="cd "+outd+"/xdsapp"
            xdsappcontent+="\n"
            xdsappcontent+='xdsapp --cmd --dir='+outd+'/xdsapp -j 8 -c 6 -i '+ind+'  --fried='+friedel+' --range='+fromImage+'\ '+toImage+' '
            xdsappcontent+="\n"                    

            return xdsappcontent



    # In[9]:


    def create_headers():
        #init variables
        xdsappOut    = ""    

        #define env for script for XDSAPP
        xdsappOut+= """#!/bin/bash\n"""
        xdsappOut+= """#!/bin/bash\n"""
        xdsappOut+= """#SBATCH -t 99:55:00\n"""
        xdsappOut+= """#SBATCH -J XDSAPP\n"""
        xdsappOut+= """#SBATCH --exclusive\n"""
        xdsappOut+= """#SBATCH -N1\n"""
        xdsappOut+= """#SBATCH --cpus-per-task=48\n"""
        xdsappOut+= """#SBATCH --mem=220000\n""" 
        xdsappOut+= """#SBATCH -o """+path+"""/fragmax/logs/xdsapp_fragmax_%j.out\n"""
        xdsappOut+= """#SBATCH -e """+path+"""/fragmax/logs/xdsapp_fragmax_%j.err\n"""    
        xdsappOut+= """module purge\n\n"""
        xdsappOut+= """module load CCP4 XDSAPP\n\n"""


        return xdsappOut





    # In[10]:


    def prepareFolder(proteinDict=proteinNames): 

            os.makedirs(path+"/fragmax/process", exist_ok=True)
            os.makedirs(path+"/fragmax/scripts", exist_ok=True)
            os.makedirs(path+"/fragmax/logs"   , exist_ok=True)


    # In[11]:


    def processHDF5(userAcronym=None, userProtein=None):
            collectedImages=dict()

            if userAcronym and userProtein:
                if userAcronym in acronyms:
                    for acronym in userAcronym: 
                        try:
                            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) #creat a dict of protein names
                            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) #create a dict of protein names with full path to the dir

                            for collectedProteins in proteinNames_path.values():
                                    for proteinName in collectedProteins:
                                            if userProtein==proteinName:
                                                datasets[proteinName] = glob.glob(proteinName+"/*master.h5") #create a dict of keys:proteinNames, values:master files - 


                            for key,value in datasets.items():     
                                    for i in value:
                                            n = images_collected(i)
                                            if n>4:
                                                    collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way
                        except:
                            print("No dataset with the given name was found. Please check the list of datasets with the provided acronym:")
                            for i in os.listdir(path+"/raw/"+userAcronym):
                                print(i)
                            break
                else:
                    print("Acronym given is not valid. Please check the list of acronyms available")
                    print("for you proposal and date\n")
                    for i in acronyms:
                        print(i)


            else:
                for key,value in datasets.items():     
                        for i in value:
                                n = images_collected(i)
                                if n>4:
                                        collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way

            return collectedImages

    def runFragMAX(path=path):
        # FragMAX running script
        prepareFolder() # create folder system for reprocessing files
        nodes=3 #nodes per pipeline


        images = processHDF5()

        xdsappHeader=create_headers()

        scriptList=list()

        for masterFile, totalFrames in images.items():    
            #output dir for each protein separate
            outdir=masterFile.split("raw")[0]+"fragmax/process"+masterFile.split("raw")[1].split("_master.h5")[0]        
            os.makedirs(outdir+"/xdsapp",exist_ok=True)

            #get the real number of data existing in the directory
            dataN=outdir+"/"+outdir.split("/")[-1]

            #Create scripts for HPC for each dataset, with custom dataframe number and outdirs
            xdsappOut=createScript(masterFile,outdir, 1, totalFrames,dataN)    
            scriptList.append(xdsappOut)

        #Create partial HPC scripts to submmit to several nodes at same time
        #nodes=3
        chunkScripts=[xdsappHeader+"".join(x) for x in list(split(scriptList,nodes) )]


        for num,chunk in enumerate(chunkScripts):
            with open(path+"/fragmax/scripts/xdsapp_fragmax_part"+str(num)+".sh", "w") as outfile:
                outfile.write(chunk)
            
            script=path+"/fragmax/scripts/xdsapp_fragmax_part"+str(num)+".sh"
            command ='echo "module purge | module load CCP4 XDSAPP DIALS/1.12.3-PReSTO | sbatch '+script+' " | ssh -F ~/.ssh/ clu0-fe-1'
            subprocess.call(command,shell=True)



    runFragMAX()

def run_autoproc(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()


    def listdir_fullpath(d):
        return [os.path.join(d, f) for f in os.listdir(d)]


    ##Start up definitions

    proteinNames      = dict() 
    proteinNames_path = dict()
    datasets          = dict()
    scriptList        = list()

    acronyms=os.listdir(path+"/raw/") #list acronym for collected data

    acronyms=[x for x in acronyms if "DS_Store" not in x]


    for acronym in acronyms: 
            #creat a dict of protein names
            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) 
            #create a dict of protein names with full path to the dir
            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) 

    for collectedProteins in proteinNames_path.values():
            for proteinName in collectedProteins:
                    #create a dict of keys:proteinNames, values:master files - 
                    datasets[proteinName] = glob.glob(proteinName+"/*master.h5") 



    def images_collected(h5image):
        f=h5py.File(h5image,"r")
        return int(f.get("entry/sample/goniometer/omega_range_total").value/f.get("entry/sample/goniometer/omega_increment").value)


    def split(a, n):
        k, m = divmod(len(a), n)
        return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))



    def createScript(ind, outd, fromImage, toImage,dataName):
            if "/Volumes/offline-visitors" in dataName:
                dataName =dataName.replace("/Volumes/offline-","/data/")
                ind      =ind.replace     ("/Volumes/offline-","/data/")
                outd     =outd.replace    ("/Volumes/offline-","/data/")

            fromImage=str(fromImage)
            toImage=str(toImage)
            #create empty string to start the script
            content=""
            content="\n"
            content="\n"

            autoproccontent = content



            # autoPROC definitions             
            autoproccontent+="\n"
            autoproccontent+='''process -h5 '''+ind+''' -noANO autoPROC_XdsKeyword_LIB=\$EBROOTNEGGIA/lib/dectris-neggia.so autoPROC_XdsKeyword_ROTATION_AXIS='0  -1 0' autoPROC_XdsKeyword_MAXIMUM_NUMBER_OF_JOBS=8 autoPROC_XdsKeyword_MAXIMUM_NUMBER_OF_PROCESSORS=6 autoPROC_XdsKeyword_DATA_RANGE='''+fromImage+'''\ '''+toImage+''' autoPROC_XdsKeyword_SPOT_RANGE='''+fromImage+'''\ '''+toImage+''' -d '''+outd+'''/autoproc'''
            autoproccontent+="\n"                    

            
            
            
            return autoproccontent



    def create_headers():
        #init variables
        autoprocOut    = ""    

        #define env for script for autoPROC
        autoprocOut+= """#!/bin/bash\n"""
        autoprocOut+= """#!/bin/bash\n"""
        autoprocOut+= """#SBATCH -t 99:55:00\n"""
        autoprocOut+= """#SBATCH -J autoPRC\n"""
        autoprocOut+= """#SBATCH --exclusive\n"""
        autoprocOut+= """#SBATCH -N1\n"""
        autoprocOut+= """#SBATCH --cpus-per-task=48\n"""
        autoprocOut+= """#SBATCH --mem=220000\n""" 
        autoprocOut+= """#SBATCH -o """+path+"""/fragmax/logs/autoproc_fragmax_%j.out\n"""
        autoprocOut+= """#SBATCH -e """+path+"""/fragmax/logs/autoproc_fragmax_%j.err\n"""    
        autoprocOut+= """module purge\n\n"""
        autoprocOut+= """module load CCP4 autoPROC\n\n"""


        return autoprocOut



    def prepareFolder(proteinDict=proteinNames): 

            os.makedirs(path+"/fragmax/process", exist_ok=True)
            os.makedirs(path+"/fragmax/scripts", exist_ok=True)
            os.makedirs(path+"/fragmax/logs"   , exist_ok=True)



    def processHDF5(userAcronym=None, userProtein=None):
            collectedImages=dict()

            if userAcronym and userProtein:
                if userAcronym in acronyms:
                    for acronym in userAcronym: 
                        try:
                            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) #creat a dict of protein names
                            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) #create a dict of protein names with full path to the dir

                            for collectedProteins in proteinNames_path.values():
                                    for proteinName in collectedProteins:
                                            if userProtein==proteinName:
                                                datasets[proteinName] = glob.glob(proteinName+"/*master.h5") #create a dict of keys:proteinNames, values:master files - 


                            for key,value in datasets.items():     
                                    for i in value:
                                            n = images_collected(i)
                                            if n>4:
                                                    collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way
                        except:
                            print("No dataset with the given name was found. Please check the list of datasets with the provided acronym:")
                            for i in os.listdir(path+"/raw/"+userAcronym):
                                print(i)
                            break
                else:
                    print("Acronym given is not valid. Please check the list of acronyms available")
                    print("for you proposal and date\n")
                    for i in acronyms:
                        print(i)


            else:
                for key,value in datasets.items():     
                        for i in value:
                                n = images_collected(i)
                                if n>4:
                                        collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way

            return collectedImages


    # In[12]:


    def runFragMAX(path=path):
        # FragMAX running script
        prepareFolder() # create folder system for reprocessing files
        nodes=3 #nodes per pipeline

        images = processHDF5()

        autoPROCHeader=create_headers()

        scriptList=list()

        for masterFile, totalFrames in images.items():    
            #output dir for each protein separate
            outdir=masterFile.split("raw")[0]+"fragmax/process"+masterFile.split("raw")[1].split("_master.h5")[0]        
            os.makedirs(outdir,exist_ok=True)

            #get the real number of data existing in the directory
            dataN=outdir+"/"+outdir.split("/")[-1]

            #Create scripts for HPC for each dataset, with custom dataframe number and outdirs
            autoprocOut=createScript(masterFile,outdir, 1, totalFrames,dataN)    
            scriptList.append(autoprocOut)

        #Create partial HPC scripts to submmit to several nodes at same time
        nodes=3
        chunkScripts=[autoPROCHeader+"".join(x) for x in list(split(scriptList,nodes) )]

        for num,chunk in enumerate(chunkScripts):
            with open(path+"/fragmax/scripts/autoproc_fragmax_part"+str(num)+".sh", "w") as outfile:
                outfile.write(chunk)
            script=path+"/fragmax/scripts/autoproc_fragmax_part"+str(num)+".sh"
            command ='echo "module purge | module load CCP4 autoPROC DIALS/1.12.3-PReSTO | sbatch '+script+' " | ssh -F ~/.ssh/ clu0-fe-1'
            subprocess.call(command,shell=True)

    runFragMAX()

def run_xdsxscale(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()



    def listdir_fullpath(d):
        return [os.path.join(d, f) for f in os.listdir(d)]


    ##Start up definitions



    proteinNames      = dict() 
    proteinNames_path = dict()
    datasets          = dict()
    scriptList        = list()

    acronyms=os.listdir(path+"/raw/") #list acronym for collected data

    acronyms=[x for x in acronyms if "DS_Store" not in x]


    for acronym in acronyms: 
            #creat a dict of protein names
            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) 
            #create a dict of protein names with full path to the dir
            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) 

    for collectedProteins in proteinNames_path.values():
            for proteinName in collectedProteins:
                    #create a dict of keys:proteinNames, values:master files - 
                    datasets[proteinName] = glob.glob(proteinName+"/*master.h5") 





    def images_collected(h5image):
        f=h5py.File(h5image,"r")
        return int(f.get("entry/sample/goniometer/omega_range_total").value/f.get("entry/sample/goniometer/omega_increment").value)




    def split(a, n):
        k, m = divmod(len(a), n)
        return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))




    def createScript(ind, outd, fromImage, toImage,dataName):
            if "/Volumes/offline-visitors" in dataName:
                dataName =dataName.replace("/Volumes/offline-","/data/")
                ind      =ind.replace     ("/Volumes/offline-","/data/")
                outd     =outd.replace    ("/Volumes/offline-","/data/")

            fromImage=str(fromImage)
            toImage=str(toImage)
            #create empty string to start the script
            content=""
            content="\n"
            content="\n"

            dialscontent   = content



            #DIALS definitions


            dialscontent+="cd "+outd+"/xdsxscale "
            dialscontent+="\n"
            dialscontent+="xia2 goniometer.axes=0,1,0  "                
            dialscontent+="    pipeline=3dii failover=true  nproc=48"                
            dialscontent+="    image="+ind+":"+fromImage+":"+toImage+"  "                
            dialscontent+="    multiprocessing.mode=serial  "                
            dialscontent+="    multiprocessing.njob=1  "                
            dialscontent+='    multiprocessing.nproc=auto'                
            dialscontent+="\n"

            return dialscontent





    def create_headers():
        #init variables
        dialsOut    = ""    

        #define env for script for DIALS
        dialsOut+= """#!/bin/bash\n"""
        dialsOut+= """#!/bin/bash\n"""
        dialsOut+= """#SBATCH -t 99:55:00\n"""
        dialsOut+= """#SBATCH -J XDSXSCALE\n"""
        dialsOut+= """#SBATCH --exclusive\n"""
        dialsOut+= """#SBATCH -N1\n"""
        dialsOut+= """#SBATCH --cpus-per-task=48\n"""
        dialsOut+= """#SBATCH --mem=220000\n""" 
        dialsOut+= """#SBATCH -o """+path+"""/fragmax/logs/xdsxscale_fragmax_%j.out\n"""
        dialsOut+= """#SBATCH -e """+path+"""/fragmax/logs/xdsxscale_fragmax_%j.err\n"""    
        dialsOut+= """module purge\n\n"""
        dialsOut+= """module load CCP4 DIALS/1.12.3-PReSTO\n\n"""

        return dialsOut


    def prepareFolder(proteinDict=proteinNames): 

            os.makedirs(path+"/fragmax/process", exist_ok=True)
            os.makedirs(path+"/fragmax/scripts", exist_ok=True)
            os.makedirs(path+"/fragmax/logs"   , exist_ok=True)


    def processHDF5(userAcronym=None, userProtein=None):
            collectedImages=dict()

            if userAcronym and userProtein:
                if userAcronym in acronyms:
                    for acronym in userAcronym: 
                        try:
                            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) #creat a dict of protein names
                            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) #create a dict of protein names with full path to the dir

                            for collectedProteins in proteinNames_path.values():
                                    for proteinName in collectedProteins:
                                            if userProtein==proteinName:
                                                datasets[proteinName] = glob.glob(proteinName+"/*master.h5") #create a dict of keys:proteinNames, values:master files - 


                            for key,value in datasets.items():     
                                    for i in value:
                                            n = images_collected(i)
                                            if n>4:
                                                    collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way
                        except:
                            print("No dataset with the given name was found. Please check the list of datasets with the provided acronym:")
                            for i in os.listdir(path+"/raw/"+userAcronym):
                                print(i)
                            break
                else:
                    print("Acronym given is not valid. Please check the list of acronyms available")
                    print("for you proposal and date\n")
                    for i in acronyms:
                        print(i)


            else:
                for key,value in datasets.items():     
                        for i in value:
                                n = images_collected(i)
                                if n>4:
                                        collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way

            return collectedImages




    def runFragMAX(useDIALS=True, path=path):
        # FragMAX running script
        prepareFolder() # create folder system for reprocessing files
        nodes=3 #nodes per pipeline

        images = processHDF5()

        dialsOut=create_headers()

        scriptList=list()

        for masterFile, totalFrames in images.items():    
            #output dir for each protein separate
            outdir=masterFile.split("raw")[0]+"fragmax/process"+masterFile.split("raw")[1].split("_master.h5")[0]        
            os.makedirs(outdir+"/xdsxscale",exist_ok=True)

            #get the real number of data existing in the directory
            dataN=outdir+"/"+outdir.split("/")[-1]

            #Create scripts for HPC for each dataset, with custom dataframe number and outdirs
            dialsScript=createScript(masterFile,outdir, 1, totalFrames,dataN)    
            scriptList.append(dialsScript)

        #Create partial HPC scripts to submmit to several nodes at same time
        nodes=3
        chunkScripts=[dialsOut+"".join(x) for x in list(split(scriptList,nodes) )]


        for num,chunk in enumerate(chunkScripts):
            with open(path+"/fragmax/scripts/xdsxscale_fragmax_part"+str(num)+".sh", "w") as outfile:
                outfile.write(chunk)
            script=path+"/fragmax/scripts/xdsxscale_fragmax_part"+str(num)+".sh"
            command ='echo "module purge | module load CCP4 XDSAPP DIALS/1.12.3-PReSTO | sbatch '+script+' " | ssh -F ~/.ssh/ clu0-fe-1'
            subprocess.call(command,shell=True)

    runFragMAX()

def run_dials(usedials,usexdsxscale,usexdsapp,useautproc,spacegroup,cellparam,friedel,datarange,rescutoff,cccutoff,isigicutoff):
    proposal,shift,acr,proposal_type,path, subpath, static_datapath,panddaprocessed=project_definitions()



    def listdir_fullpath(d):
        return [os.path.join(d, f) for f in os.listdir(d)]


    ##Start up definitions



    proteinNames      = dict() 
    proteinNames_path = dict()
    datasets          = dict()
    scriptList        = list()

    acronyms=os.listdir(path+"/raw/") #list acronym for collected data

    acronyms=[x for x in acronyms if "DS_Store" not in x]


    for acronym in acronyms: 
            #creat a dict of protein names
            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) 
            #create a dict of protein names with full path to the dir
            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) 

    for collectedProteins in proteinNames_path.values():
            for proteinName in collectedProteins:
                    #create a dict of keys:proteinNames, values:master files - 
                    datasets[proteinName] = glob.glob(proteinName+"/*master.h5") 





    def images_collected(h5image):
        f=h5py.File(h5image,"r")
        return int(f.get("entry/sample/goniometer/omega_range_total").value/f.get("entry/sample/goniometer/omega_increment").value)




    def split(a, n):
        k, m = divmod(len(a), n)
        return (a[i * k + min(i, m):(i + 1) * k + min(i + 1, m)] for i in range(n))




    def createScript(ind, outd, fromImage, toImage,dataName):
            if "/Volumes/offline-visitors" in dataName:
                dataName =dataName.replace("/Volumes/offline-","/data/")
                ind      =ind.replace     ("/Volumes/offline-","/data/")
                outd     =outd.replace    ("/Volumes/offline-","/data/")

            fromImage=str(fromImage)
            toImage=str(toImage)
            #create empty string to start the script
            content=""
            content="\n"
            content="\n"

            dialscontent   = content



            #DIALS definitions


            dialscontent+="cd "+outd+"/dials "
            dialscontent+="\n"
            dialscontent+="xia2 goniometer.axes=0,1,0  "                
            dialscontent+="    pipeline=dials failover=true  nproc=48"                
            dialscontent+="    image="+ind+":"+fromImage+":"+toImage+"  "                
            dialscontent+="    multiprocessing.mode=serial  "                
            dialscontent+="    multiprocessing.njob=1  "                
            dialscontent+='    multiprocessing.nproc=auto'                
            dialscontent+="\n"

            return dialscontent





    def create_headers():
        #init variables
        dialsOut    = ""    

        #define env for script for DIALS
        dialsOut+= """#!/bin/bash\n"""
        dialsOut+= """#!/bin/bash\n"""
        dialsOut+= """#SBATCH -t 99:55:00\n"""
        dialsOut+= """#SBATCH -J DIALS\n"""
        dialsOut+= """#SBATCH --exclusive\n"""
        dialsOut+= """#SBATCH -N1\n"""
        dialsOut+= """#SBATCH --cpus-per-task=48\n"""
        dialsOut+= """#SBATCH --mem=220000\n""" 
        dialsOut+= """#SBATCH -o """+path+"""/fragmax/logs/dials_fragmax_%j.out\n"""
        dialsOut+= """#SBATCH -e """+path+"""/fragmax/logs/dials_fragmax_%j.err\n"""    
        dialsOut+= """module purge\n\n"""
        dialsOut+= """module load CCP4 DIALS/1.12.3-PReSTO\n\n"""

        return dialsOut


    def prepareFolder(proteinDict=proteinNames): 

            os.makedirs(path+"/fragmax/process", exist_ok=True)
            os.makedirs(path+"/fragmax/scripts", exist_ok=True)
            os.makedirs(path+"/fragmax/logs"   , exist_ok=True)


    def processHDF5(userAcronym=None, userProtein=None):
            collectedImages=dict()

            if userAcronym and userProtein:
                if userAcronym in acronyms:
                    for acronym in userAcronym: 
                        try:
                            proteinNames[acronym]=os.listdir(path+"/raw/"+acronym) #creat a dict of protein names
                            proteinNames_path[acronym]=listdir_fullpath(path+"/raw/"+acronym) #create a dict of protein names with full path to the dir

                            for collectedProteins in proteinNames_path.values():
                                    for proteinName in collectedProteins:
                                            if userProtein==proteinName:
                                                datasets[proteinName] = glob.glob(proteinName+"/*master.h5") #create a dict of keys:proteinNames, values:master files - 


                            for key,value in datasets.items():     
                                    for i in value:
                                            n = images_collected(i)
                                            if n>4:
                                                    collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way
                        except:
                            print("No dataset with the given name was found. Please check the list of datasets with the provided acronym:")
                            for i in os.listdir(path+"/raw/"+userAcronym):
                                print(i)
                            break
                else:
                    print("Acronym given is not valid. Please check the list of acronyms available")
                    print("for you proposal and date\n")
                    for i in acronyms:
                        print(i)


            else:
                for key,value in datasets.items():     
                        for i in value:
                                n = images_collected(i)
                                if n>4:
                                        collectedImages[i]=n #store in a dict how many images were collected. Maybe not optimal way

            return collectedImages




    def runFragMAX(useDIALS=True, path=path):
        # FragMAX running script
        prepareFolder() # create folder system for reprocessing files
        nodes=3 #nodes per pipeline

        images = processHDF5()

        dialsOut=create_headers()

        scriptList=list()

        for masterFile, totalFrames in images.items():    
            #output dir for each protein separate
            outdir=masterFile.split("raw")[0]+"fragmax/process"+masterFile.split("raw")[1].split("_master.h5")[0]        
            os.makedirs(outdir+"/dials",exist_ok=True)

            #get the real number of data existing in the directory
            dataN=outdir+"/"+outdir.split("/")[-1]

            #Create scripts for HPC for each dataset, with custom dataframe number and outdirs
            dialsScript=createScript(masterFile,outdir, 1, totalFrames,dataN)    
            scriptList.append(dialsScript)

        #Create partial HPC scripts to submmit to several nodes at same time
        nodes=3
        chunkScripts=[dialsOut+"".join(x) for x in list(split(scriptList,nodes) )]


        for num,chunk in enumerate(chunkScripts):
            with open(path+"/fragmax/scripts/dials_fragmax_part"+str(num)+".sh", "w") as outfile:
                outfile.write(chunk)
            
            script=path+"/fragmax/scripts/dials_fragmax_part"+str(num)+".sh"
            command ='echo "module purge | module load CCP4 XDSAPP DIALS/1.12.3-PReSTO | sbatch '+script+' " | ssh -F ~/.ssh/ clu0-fe-1'
            subprocess.call(command,shell=True)

    runFragMAX()



###############################

#################################
