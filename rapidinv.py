#!/usr/local/bin/python
#
#     RAPIDINV.PY
#
#     Copyright 2008 Simone Cesca
#
#     Developed by:
#     Simone Cesca, Sebastian Heimann
#     Institut fur Geophysik, University of Hamburg
#     simone.cesca@zmaw.de
#     March 2008
#     starting version, 07.03.2008
#     for previous versions, see kinherdinv.py
#
#     Version 10.0, 14.1.2010 Simone Cesca
#  
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#  
#         http://www.apache.org/licenses/LICENSE-2.0
#  
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.
# 

# Naming conventions
#   i* for counters
#   j* also for counters
#   k* also for counters
#   n* for quantities
#   f* for file names
#   d* for directory names



import re
import sys
import os
import shutil
import glob 
import operator
import math
import string
import random
import numpy
from datetime import datetime
from numpy import mean,std,var
from tunguska.phase import Phase,Timing


def readDefInputFile(fdefaults,inv_param):
   f=open(fdefaults,'r')
   for line in f:
      splittedline=line.split()
      if len(splittedline)==2:
	 cod,val=line.split()
         if cod[0]<>"#":
            inv_param[cod]=val
      elif len(splittedline)>0:
         cod=splittedline[0]
         if cod[0]<>"#":
            sys.exit("ERROR: "+param+" = "+param_value+". It should be: "+should_be) 
   f.flush()
   f.close()


def assignSpacing(inv_param):
   fast=os.path.join(inv_param['INVERSION_DIR'],"assignspacing.tmp")
   cmd="gfdb_info "+os.path.join(inv_param['GFDB_STEP1'],"db")+" >"+fast
   os.system(cmd)
   f=open(fast,'r')
   for line in f:
      splittedline=line.split("=")
      if splittedline[0]=="dx":
         dx=float(splittedline[1])
      if splittedline[0]=="dz":
         dz=float(splittedline[1])
   f.flush()
   f.close()
   cod="RADIUS0"
   val=str(max(dx,dz))
   inv_param[cod]=val
   print "radius 0 set to ",val


def readInputFile (filename,inv_param,active_comp):
   f = open(filename,'r')   
   for line in f:
      cv=line.split()
      if len(cv) == 2:
         cod,val=cv
	 if cod[0]<>"#":
	    if inv_param.has_key(cod):
               inv_param[cod]=val
   f.flush()
   f.close()
   for comp in ('a','c','r','l','d','u','n','s','e','w'):
      active_comp[comp]=False
   for letter in inv_param['COMP_2_USE']:
      active_comp[letter]=True


def errorInvParam (param,should_be,param_value):
   sys.exit("ERROR: "+param+" = "+param_value+". It should be: "+should_be) 


def checkInvParam (param,param_value,possible_values):
   param_ok = False
   should_be="["
   for possible_value in possible_values:
      should_be=should_be+" "+possible_value
      if param_value == possible_value:
         param_ok = True
   if not param_ok:
      should_be=should_be+" ]"
      errorInvParam (param,should_be,param_value)  


def checkAccInputFile(facceptables,inv_param):
   f = open(facceptables,'r')   
   for line in f:
      cv=line.split()
      if len(cv) == 2:
         cod,val=cv
	 if inv_param.has_key(cod):
            values = val.split('|')
	    if len(values) == 1:
	       val0=values
	       if (val0=='float'):
	          if (str(float(val0))!=val0):
		     errorInvParam (cod,should_be,val0)
	       elif (val0=='integer'): 
	          if (str(int(val0))!=val0):
		     errorInvParam (cod,should_be,val0)
	       elif (val0=='boolean'): 
	          if (val0.upper()!='TRUE') and (val0.upper()!='FALSE'):
		     errorInvParam (cod,should_be,val0)
	       elif (val0=='positive'): 
	          if (float(val0)<=0):
		     errorInvParam (cod,should_be,val0)
	       elif (val0=='negative'): 
	          if (float(val0)>=0):
		     errorInvParam (cod,should_be,val0)
	       elif (val0=='nonegative'): 
	          if (float(val0)<0):
		     errorInvParam (cod,should_be,val0)
	       elif (val0=='nopositive'): 
	          if (float(val0)>0):
		     errorInvParam (cod,should_be,val0)
	    else:
	       actual_value=inv_param[cod]
	       checkInvParam(cod,actual_value,values)
   f.flush()
   f.close()


def assignChannels(active_comp,active_chan,inv_param):
   for comp in ('a','c'):
      if active_comp[comp]:
         active_chan[comp]=inv_param['CHANNEL']+"R"
   for comp in ('r','l'):
      if active_comp[comp]:
         active_chan[comp]=inv_param['CHANNEL']+"T"
   for comp in ('d','u'):
      if active_comp[comp]:
         active_chan[comp]=inv_param['CHANNEL']+"Z"
   for comp in ('n','s'):
      if active_comp[comp]:
         active_chan[comp]=inv_param['CHANNEL']+"N"
   for comp in ('e','w'):
      if active_comp[comp]:
         active_chan[comp]=inv_param['CHANNEL']+"E"


def assignCompNames(comp_names):
   comp_names['n']='North'
   comp_names['s']='South'
   comp_names['e']='East'
   comp_names['w']='West'
   comp_names['u']='Up'
   comp_names['d']='Down'
   comp_names['a']='RadAway'
   comp_names['c']='RadBack'
   comp_names['r']='TraRight'
   comp_names['l']='TraLeft'


def copyFiles(src, dst):
   names = os.listdir(src)
   for name in names:
      srcname = os.path.join(src, name)
      dstname = os.path.join(dst, name)
      shutil.copy(srcname,dstname)      


def removeLocalDataFiles(inv_param,traces):
   halfname = os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
   halfnamet = os.path.join(inv_param['INVERSION_DIR'],'taper')
   halfnamed = os.path.join(inv_param['INVERSION_DIR'],'d')
   halfnames = os.path.join(inv_param['INVERSION_DIR'],'s')
   form = inv_param['DATA_FORMAT']
   for i in range(len(traces)):
     stat = str(i+1)
     for comp in inv_param['COMP_2_USE']:
        fnametmp=halfname+'-'+stat+'-'+comp+'.'+form
	fnamettmp=halfnamet+'-'+stat+'-'+comp
	if os.path.exists(fnametmp):
           os.remove(fnametmp)
	if os.path.exists(fnamettmp):
  	   os.remove(fnamettmp)
           for tplot in ('amsp','seis','seif','seit'):             
	      for trun in ('1','2','3'):
	         fnamedtmp=halfnamed+tplot+trun+'-'+stat+'-'+comp+'.table'
		 fnamestmp=halfnames+tplot+trun+'-'+stat+'-'+comp+'.table'
		 if os.path.exists(fnamedtmp):
		    os.remove(fnamedtmp)
		 if os.path.exists(fnamestmp):
		    os.remove(fnamestmp)
		  

def getTime():
   localyear=datetime.utcnow().toordinal()
   tt=datetime.utcnow().timetuple()
   localtime=tt[3]*3600+tt[4]*60+tt[5]
   return(localtime,localyear)


def plotDelay(time0,year0,time1,year1,time2,year2,time3,year3,time4,year4):
   if year1>year0:
      time1=time1+(year1-year0)*86400
   if year2>year0:
      time2=time2+(year2-year0)*86400
   if year3>year0:
      time3=time3+(year3-year0)*86400
   if year4>year0:
      time4=time4+(year4-year0)*86400
   ttime=time4-time0
   ttime1=time1-time0
   ttime2=time2-time1
   ttime3=time3-time2
   ttime4=time4-time3
   print "Total time      : "+str(ttime)
   print "  Preprocessing : "+str(ttime1)
   print "  Step 1        : "+str(ttime2)
   print "  Step 2        : "+str(ttime3)
   print "  Step 3        : "+str(ttime4)
   mttime=float(ttime/60)
   mttime1=float(ttime1/60)
   mttime2=float(ttime2/60)
   mttime3=float(ttime3/60)
   mttime4=float(ttime4/60)
   fdelay=os.path.join(inv_param['INVERSION_DIR'],"delay.dat")
   f=open(fdelay,'w')
   f.write("Total time      : "+strDecim(mttime,2)+"\n")
   f.write(" Prepreocessing : "+strDecim(mttime1,2)+"\n")
   f.write(" Step1          : "+strDecim(mttime2,2)+"\n")
   f.write(" Step2          : "+strDecim(mttime3,2)+"\n")
   f.write(" Step3          : "+strDecim(mttime4,2)+"\n")
   f.flush()
   f.close()
   
   
def m0tomw(m0):
   lm0 = math.log10(m0)
   mw = lm0*2/3-6.1 
   return(mw)


def vel2lame(alfa,beta,rho):
   lame_mu=rho*((beta)**2)
   lame_lambda=(((alfa)**2)*rho)-(2*lame_mu)
   return(lame_lambda,lame_mu)


def calculateAreaCircSegment(radius,z_dist_boundary,dip):
   dist_boundary=z_dist_boundary/math.sin(dip)
   area_section=radius*radius*math.acos(dist_boundary/radius)
   area_triangle=dist_boundary*math.sqrt((radius*radius)+(dist_boundary*dist_boundary))
   area_segment=area_section-area_triangle
   return(area_segment)


def calculateArea(inv_param,sdep,srad,sdip):
   depth,radius=float(sdep),float(srad)
   dip=math.radians(float(sdip))
   a0=math.pi*radius*radius
   a1=a2=0.
   moho_depth=30000.
   surface_depth=0.
   if (depth <= surface_depth) or (depth >= moho_depth):
      area = 0.
      print "WARNING, rupture area can not be calculated for this depth",depth
   else:
      projected_radius=radius*math.sin(dip)
      if (depth-projected_radius<surface_depth):
         z_dist_boundary=depth-surface_depth
	 a1=calculateAreaCircSegment(radius,z_dist_boundary,dip)
      if (depth+projected_radius>moho_depth):
         z_dist_boundary=moho_depth-depth
         a2=calculateAreaCircSegment(radius,z_dist_boundary,dip)    
      area=a0-a1-a2
   return(area)
   

def calculateAverageSlip(smom,area_m2,mu):
   av_slip=(float(smom))/(area_m2*mu)
   return(av_slip)


def sdisl2mt(strike_gra,dip_gra,rake_gra):
#  based on sdisl2mt.f Fortran code from MT inversion student course
#  by T. Dahm and F. Krueger
   strike = math.radians(strike_gra)
   dip    = math.radians(dip_gra)
   rake   = math.radians(rake_gra)
   sstr,sdip,srak = math.sin(strike),math.sin(dip),math.sin(rake)
   cstr,cdip,crak = math.cos(strike),math.cos(dip),math.cos(rake)
   s2str,s2dip=math.sin(2*strike),math.sin(2*dip)
   c2str,c2dip=math.cos(2*strike),math.cos(2*dip)
   m11 = (-sdip*crak*s2str)+(-s2dip*srak*sstr*sstr)
   m12 = (sdip*crak*c2str)+(s2dip*srak*s2str/2.)
   m13 = (-cdip*crak*cstr)+(-c2dip*srak*sstr)
   m22 = (sdip*crak*s2str)+(-s2dip*srak*cstr*cstr)
   m23 = (-cdip*crak*sstr)+(c2dip*srak*cstr)
   m33 = s2dip*srak
   return(m11,m12,m13,m22,m23,m33)


#def mtdecomp():
#  based on mtdecomp.f Fortran code from MT inversion student course
#  by T. Dahm and F. Krueger
#  References: A Students Guide to and Review of Moment Tensor
#              M.L.Jost and R.B.Hermann SeisResLetters, Vol60, 1989
  


def relativeMisfit(misfit,ref):
      rmisf=(misfit-ref)/ref
      if (rmisf < 0.):
         print "WARNING: negative relative misfit found!"
         print "misfit reference ",misfit,ref
         rmisf=0.
      return(rmisf)


def getTrapez(tim,wil,wis,wit,wgt):
   x1=tim-(wil*wis)
   x2=x1+(wil*wit)
   x3=x1+wil-(x2-x1)
   x4=x1+wil
   if (wit<0):
      x2=x1
      x1=x2+(wil*wit)
      x3=x2+wil
      x4=x3+(x2-x1)
   y1=y4=0
   y2=y3=wgt
   trapezoid=((x1,y1),(x2,y2),(x3,y3),(x4,y4))
   return trapezoid


def ytrapez(x,trapezoid):
   if len(trapezoid)==0:
      y=0
   else:
      if x<trapezoid[0][0]:
         y=0
      elif x<trapezoid[1][0]:
         y=trapezoid[1][1]*((x-trapezoid[0][0])/(trapezoid[1][0]-trapezoid[0][0]))
      elif x<trapezoid[2][0]:
         y=trapezoid[2][1]
      elif x<trapezoid[3][0]:
         y=trapezoid[2][1]*((trapezoid[3][0]-x)/(trapezoid[3][0]-trapezoid[2][0]))
      else:
         y=0
   return y


def callTimeCalc(inv_param,phasetyp,phasedep,phasedis):
#   fphase=os.path.join(inv_param['ARR_TIMES_DIR'],phasetyp+"phases_"+phasedep+".ttt")
#   f = open(fphase,'r')   
#   dist1,time1=0.,0.
#   for line in f:
#      sdist,stime=line.split()
#      ldist,ltime=float(sdist),float(stime)
#      if (ldist>phasedis):
#         dist2,time2=ldist,ltime
#	 continue
#      else:
#         dist1,time1=ldist,ltime     
#   f.flush()
#   f.close()
#   phasetim=(((phasedis-dist1)/(dist2-dist1))*(time2-time1))+time1
#   return phasetim
   depth=float(phasedep)*1000
   dist=float(phasedis)*1000
   if phasetyp=="p":
      p1,p2,p3=Phase('P'),Phase('Pn'),Phase('begin')
      t1,t2=p1(dist,depth),p2(dist,depth)
      if t1 and t2:
         phasetim=min(t1,t2)
      elif t1:
         phasetim=t1
      elif t2:
         phasetim=t2
      else:
         t3=p3(dist,depth)
         if t3:
	    phasetim=t3
	 else:
	    phasetim=0     
   else:
      s1,s2,p3=Phase('S'),Phase('Sn'),Phase('begin')
      t1,t2=s1(dist,depth),s2(dist,depth)
      if t1 and t2:
         phasetim=min(t1,t2)
      elif t1:
         phasetim=t1
      elif t2:
         phasetim=t2
      else:
         t3=p3(dist,depth)
         if t3:
	    phasetim=t3*1.75
	 else:
	    phasetim=0
   print "TIME:",phasetyp,depth,dist,phasetim
   return phasetim


def getWindowsTaper(comp,depth,edist,inv_param,inv_step):
#   print "Get windows taper"
   err_taper="ERROR: Wrong phase name chosen. P2US: "+inv_param['PHASES_2_USE_ST'+inv_step]   
   if not os.path.exists(inv_param['ARR_TIMES_DIR']):
      print "Directory not existing: "+inv_param['ARR_TIMES_DIR']
      sys.exit("ERROR: wrong Earth model for arrival times: "+inv_param['ARR_TIMES_MODEL'])
   if "x" in inv_param['PHASES_2_USE_ST'+inv_step]:
      ptimes=[]
      tp=0.
      ptimes.append(tp)
   if "a" in inv_param['PHASES_2_USE_ST'+inv_step]:
      phasetyp,phasedep,phasedis="p",str(int(round(depth))),edist 
      tp=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
   if ("p") in inv_param['PHASES_2_USE_ST'+inv_step]:
      phasetyp,phasedep,phasedis="p",str(int(round(depth))),edist 
      tp=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
   if ("s") in inv_param['PHASES_2_USE_ST'+inv_step]:
      phasetyp,phasedep,phasedis="s",str(int(round(depth))),edist 
      ts=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
   if ("r") in inv_param['PHASES_2_USE_ST'+inv_step]:
      phasetyp,phasedep,phasedis="s",str(int(round(depth))),edist 
      ts=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
      tr=ts/0.95
   if ("b") in inv_param['PHASES_2_USE_ST'+inv_step]:
      phasetyp,phasedep,phasedis="p",str(int(round(depth))),edist 
      tp=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
      phasetyp,phasedep,phasedis="s",str(int(round(depth))),edist
      ts=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
      tr=ts/0.95
   if ("f") in inv_param['PHASES_2_USE_ST'+inv_step]:
      phasetyp,phasedep,phasedis="p",str(int(round(depth))),edist 
      tp=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
      phasetyp,phasedep,phasedis="s",str(int(round(depth))),edist 
      ts=callTimeCalc(inv_param,phasetyp,phasedep,phasedis)
      tr=ts/0.95
   if inv_param['SW_FIXTAPER_ST'+inv_step].upper()=='TRUE':
      wisa=float(inv_param['WIN_START_A_ST'+inv_step])
      wita,wgta=float(inv_param['WIN_TAPER_A_ST'+inv_step]),float(inv_param['WEIGHT_A_ST'+inv_step])
      wila=((3600./10000.)*float(edist))+60
      wila=(1+(2*wita))*wila
   else:
      wila,wisa=float(inv_param['WIN_LENGTH_A_ST'+inv_step]),float(inv_param['WIN_START_A_ST'+inv_step])
      wita,wgta=float(inv_param['WIN_TAPER_A_ST'+inv_step]),float(inv_param['WEIGHT_A_ST'+inv_step])
   wilx,wisx=float(inv_param['WIN_LENGTH_X_ST'+inv_step]),float(inv_param['WIN_START_X_ST'+inv_step])
   wilp,wils,wilr=float(inv_param['WIN_LENGTH_P_ST'+inv_step]),float(inv_param['WIN_LENGTH_S_ST'+inv_step]),float(inv_param['WIN_LENGTH_R_ST'+inv_step])
   wisp,wiss,wisr=float(inv_param['WIN_START_P_ST'+inv_step]),float(inv_param['WIN_START_S_ST'+inv_step]),float(inv_param['WIN_START_R_ST'+inv_step])
   witp,wits,witr=float(inv_param['WIN_TAPER_P_ST'+inv_step]),float(inv_param['WIN_TAPER_S_ST'+inv_step]),float(inv_param['WIN_TAPER_R_ST'+inv_step])
   wgtp,wgts,wgtr=float(inv_param['WEIGHT_P_ST'+inv_step]),float(inv_param['WEIGHT_S_ST'+inv_step]),float(inv_param['WEIGHT_R_ST'+inv_step])
   trapez1=trapez2=trapez3=()
#   print len(inv_param['PHASES_2_USE_ST'+inv_step])
   if len(inv_param['PHASES_2_USE_ST'+inv_step])==1:
      if "x" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=((-0.1+float(wisx),0.),(float(wisx),1.),\
	         (float(wilx)+float(wisx),1.),(0.1+float(wilx)+float(wisx),0.))
      elif "a" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=getTrapez(tp,wila,wisa,wita,wgta)
      elif "p" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=getTrapez(tp,wilp,wisp,witp,wgtp)
      elif "s" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=getTrapez(ts,wils,wiss,wits,wgts)
      elif "r" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=getTrapez(tr,wilr,wisr,witr,wgtr)
      elif "b" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 if (comp == "u") or (comp == "d"):
	    trapez1=getTrapez(tp,wilp,wisp,witp,wgtp) 
	 else:
	    trapez1=getTrapez(ts,wils,wiss,wits,wgts)
      elif "f" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 if (comp == "u") or (comp == "d"):
	    if (edist>1200):
	       trapez1=getTrapez(tp,wilp,wisp,witp,wgtp) 
	    else:
	       trapez1=getTrapez(tp,wila,wisa,wita,wgta)
	 else:
	    if (edist>2400):
	       trapez1=getTrapez(tp,wilp,wisp,witp,wgtp)
	    elif (edist>1200):
	       trapez1=getTrapez(ts,wils,wiss,wits,wgts)
	    else:
	       trapez1=getTrapez(tp,wila,wisa,wita,wgta)
      else:
         sys.exit(err_taper)	 
   elif len(inv_param['PHASES_2_USE_ST'+inv_step])==2:
      if "x" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=((-0.1+float(wisx),0.),(float(wisx),1.),\
	         (float(wilx)+float(wisx),1.),(0.1+float(wilx)+float(wisx),0.))
      if ("a") in inv_param['PHASES_2_USE_ST'+inv_step]:
         sys.exit(err_taper)
      if ("b") in inv_param['PHASES_2_USE_ST'+inv_step]:
         sys.exit(err_taper)
      if ("f") in inv_param['PHASES_2_USE_ST'+inv_step]:
         sys.exit(err_taper)
      if ("p" in inv_param['PHASES_2_USE_ST'+inv_step]):
         trapez1=getTrapez(tp,wilp,wisp,witp,wgtp)
         if ("s" in inv_param['PHASES_2_USE_ST'+inv_step]):
	    trapez2=getTrapez(ts,wils,wiss,wits,wgts)
	 elif ("r" in inv_param['PHASES_2_USE_ST'+inv_step]):
	    trapez2=getTrapez(tr,wilr,wisr,witr,wgtr)
         else:
            sys.exit(err_taper)
      elif ("s" in inv_param['PHASES_2_USE_ST'+inv_step]):
         trapez1=getTrapez(ts,wils,wiss,wits,wgts)
         if ("r" in inv_param['PHASES_2_USE_ST'+inv_step]):
	    trapez2=getTrapez(tr,wilr,wisr,witr,wgtr)
	 else:
	    sys.exit(err_taper)  
      else:
         sys.exit(err_taper) 	    
   elif len(inv_param['PHASES_2_USE_ST'+inv_step])==3:
      if "x" in inv_param['PHASES_2_USE_ST'+inv_step]:
	 trapez1=((-0.1+float(wisx),0.),(float(wisx),1.),\
	         (float(wilx)+float(wisx),1.),(0.1+float(wilx)+float(wisx),0.))
      if ("a") in inv_param['PHASES_2_USE_ST'+inv_step]:
         sys.exit(err_taper)
      if ("b") in inv_param['PHASES_2_USE_ST'+inv_step]:
         sys.exit(err_taper)
      if ("f") in inv_param['PHASES_2_USE_ST'+inv_step]:
         sys.exit(err_taper)
      if ("p" in inv_param['PHASES_2_USE_ST'+inv_step]) \
       & ("s" in inv_param['PHASES_2_USE_ST'+inv_step]) \
       & ("r" in inv_param['PHASES_2_USE_ST'+inv_step]):
         trapez1=getTrapez(tp,wilp,wisp,witp,wgtp)
         trapez2=getTrapez(ts,wils,wiss,wits,wgts)
         trapez3=getTrapez(tr,wilr,wisr,witr,wgtr)
      else:
	 sys.exit(err_taper)
   else:
      sys.exit(err_taper)

   listx=[]
   for coor in trapez1:
      listx.append(coor[0])
   for coor in trapez2:
      if coor[0] not in listx:
         listx.append(coor[0])
   for coor in trapez3:
      if coor[0] not in listx:
         listx.append(coor[0])
   listx.sort()

   str_taper=""
   for x in listx:
      y=max(ytrapez(x,trapez1),ytrapez(x,trapez2),ytrapez(x,trapez3))
      if (inv_param['SW_WEIGHT_DIST'].upper()=='TRUE'):
         print "Distance-dipendent weight applied"
         y=y*(float(edist)/float(inv_param['EPIC_DIST_MAX']))
#      if (inv_step=='3'):
#         edistmax=float(inv_param['EPIC_DIST_MAXKIN']) 
#         if (float(edist)>edistmax):
#	    y=y*0.001
      str_taper=str_taper+" "+str(x)+" "+str(y)+" "
   return str_taper


def strDecim(num,decim):
   i=1
   for j in range(decim):
     i=i*10
   str_decim=str(float(int(float(num)*i))/float(i))
   return str_decim


def writeDCSolutions(inv_step,ps,n_sol,dinv,filename):
   fptsolutions=os.path.join(dinv,filename)
   f=open(fptsolutions,'w')
   for i in range(n_sol):
	 linsol=str(ps[i].misfit)+" "+str(ps[i].depth)+" "+str(ps[i].smom)+" "+\
	        str(ps[i].strike)+" "+str(ps[i].dip)+" "+str(ps[i].rake)+" "+\
	        str(ps[i].time)+" "+str(ps[i].rest)+" "+str(ps[i].rnor)+" "+\
		strDecim(ps[i].risetime,2)+"\n"
	 f.write(linsol)
   f.flush()
   f.close()


def writeMTSolutions(inv_step,mts,n_sol,dinv,filename):
   fptsolutions=os.path.join(dinv,filename)
   f=open(fptsolutions,'w')
   for i in range(n_sol):
      if (mts[i].inv_step == inv_step):
         linsol=str(mts[i].misfit)+" "+str(mts[i].depth)+" "+str(mts[i].m11)+" "
         linsol=linsol+str(mts[i].m12)+" "+str(mts[i].m13)+" "+str(mts[i].m22)+" "
	 linsol=linsol+str(mts[i].m23)+" "+str(mts[i].m33)+"\n"
         f.write(linsol)
   f.flush()
   f.close()


def writeEikSolutions(inv_step,eiko,n_sol,dinv,filename):
   feiksolutions=os.path.join(dinv,filename)
   f=open(feiksolutions,'w')
   print "NUMBER_EIKO",n_sol
   for i in range(n_sol):
      if (eiko[i].inv_step == inv_step):
         linsol=str(eiko[i].misfit)+" "+str(eiko[i].depth)+" "+str(eiko[i].smom)+" "
         linsol=linsol+str(eiko[i].strike)+" "+str(eiko[i].dip)+" "+str(eiko[i].rake)+" "
	 linsol=linsol+str(eiko[i].radius)+" "+str(eiko[i].nuklx)+" "+str(eiko[i].nukly)+" "
	 linsol=linsol+str(eiko[i].relruptvel)+" "+strDecim(eiko[i].risetime,2)+"\n"
         f.write(linsol)
	 print "EIKO",i,linsol
   f.flush()
   f.close()


def prepInvDir(inv_param):
   if os.path.exists(inv_param['INVERSION_DIR']):
      shutil.rmtree(inv_param['INVERSION_DIR'])
   os.mkdir(inv_param['INVERSION_DIR'])
   copyFiles(inv_param['DATA_DIR'],inv_param['INVERSION_DIR'])
   print 'copied data from '+inv_param['DATA_DIR']


def prepStations(inv_param,traces):
# Check range of distances
   fstations=os.path.join(inv_param['INVERSION_DIR'],inv_param['STAT_INP_FILE'])
   fstationsok=fstations+'.tmp' 
   f = open(fstations,'r')   
   f2 = open(fstationsok,'w')
   for line in f:
      trial=line.split()
      if len(trial) == 4:
         code,stat,lat,lon = line.split()
         f2.write(lat+' '+lon+' '+'d\n')
   f2.flush()
   f2.close()
   f.flush()
   f.close()
   
   fdistazi=os.path.join(inv_param['INVERSION_DIR'],inv_param['DIST_AZI_FILE'])
   fdistazitmp=fdistazi+'.tmp'
   fmininptmp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp.dist')
   fminouttmp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out.dist')
   f = open(fmininptmp,'w')
   f.write('set_receivers '+fstationsok+'\n')
   f.write('set_source_location '+inv_param['LATITUDE_NORTH']+' '+inv_param['LONGITUDE_EAST']+' 0\n')
   f.write('set_source_constraints 0 0 0 0 0 -1\n')
   f.write('output_distances '+fdistazitmp+'\n')
   f.flush()   
   f.close()
   callMinimizer(fmininptmp,fminouttmp)
   
   statok=[]
   distances=[]
   azimuths=[]
   istatall=istatok=0
   f = open(fdistazitmp,'r')
   for line in f:
      dist_gr,dist_m,azim_gr=line.split()
      dist_km=float(dist_m)/1000
      if ((dist_km >= float(inv_param['EPIC_DIST_MIN'])) and (dist_km <= float(inv_param['EPIC_DIST_MAX']))):       
         statok.append(True)
         distances.append(dist_km)
         azimuths.append(float(azim_gr))
	 istatok=istatok+1
      else:
         statok.append(False)
      istatall=istatall+1
   f.flush()   
   f.close()
   nstatok=istatok+1
   
   fstatinp=os.path.join(inv_param['INVERSION_DIR'],inv_param['STAT_INP_FILE'])
   fstatout=os.path.join(inv_param['INVERSION_DIR'],inv_param['STAT_OUT_FILE']) 
   f = open(fstatinp,'r')   
   f2 = open(fstatout,'w')
   istatok=0
   for line in f:
      trial=line.split()
      if len(trial) == 4:
         code,stat,lat,lon = line.split()
         if statok[istatok]:
	    f2.write(line)
         istatok=istatok+1
   f2.flush()
   f2.close()
   f.flush()
   f.close()
   
# Check available traces, build traces as a list of Metatrace objects
   fstations=os.path.join(inv_param['INVERSION_DIR'],inv_param['STAT_OUT_FILE'])
   i=j=k=istatok=0
   f = open(fstations,'r')   
   for line in f:
      trial=line.split()
      if len(trial) == 4:
         code,stat,lat,lon = line.split()
         dist=distances[istatok]
         azim=azimuths[istatok]
	 quality="ok"
	 istatok=istatok+1
         trace_comp=""
         for comp in inv_param['COMP_2_USE']:
	    trace_name="DISPL."+stat+"."+active_chan[comp]
            ftrace=os.path.join(inv_param['INVERSION_DIR'],trace_name)
            if os.path.isfile(ftrace):
               trace_comp=trace_comp + comp
               j=j+1  
         if len(trace_comp)>0:
	    for comp in trace_comp:
               traces.append(Metatrace(code,stat,lat,lon,dist,azim,comp,quality))
               i=i+1	 
      else:
         k=k+1
   f.flush()
   f.close()
   if k>0:
      print "WARNING: File "+fstations+" has wrong format, "+k+" lines have been skipped!"

# Rename data files and build SAC macros

   traces.sort(key=operator.attrgetter('dist'))
   i=j=0
   for trace in traces:
      i=i+1
      trace.num=i
      for comp in trace.comp:
         j=j+1
         fbefore="DISPL."+trace.stat+"."+active_chan[comp]
         fafter=inv_param['DATA_FILE']+"-"+str(i)+"-"+comp+"."+inv_param['DATA_FORMAT']
         file1=os.path.join(inv_param['INVERSION_DIR'],fbefore)
         file2=os.path.join(inv_param['INVERSION_DIR'],fafter)
         shutil.move(file1,file2)


def buildSacMacros(inv_param,traces):
   f1 = open('resamp05.mac','w')
   f2 = open('fitorigintime.mac','w')
   i=0
   j=0
   for trace in traces:
      i=i+1
      for comp in trace.comp:
         j=j+1
         fafter=inv_param['DATA_FILE']+"-"+str(i)+"-"+comp+"."+inv_param['DATA_FORMAT']
	 file2=os.path.join(inv_param['INVERSION_DIR'],fafter)
         line="r "+file2+"\n"
         f1.write(line)
         f1.write("IF &1,DELTA EQ 0.01\n")
         f1.write("decimate 2\n")
         f1.write("decimate 5\n")
         f1.write("decimate 5\n")
         f1.write("chnhdr DELTA 0.5\n")
         f1.write("ELSEIF &1,DELTA EQ 0.0125\n")
         f1.write("decimate 4\n")
         f1.write("decimate 2\n")
         f1.write("decimate 5\n")
         f1.write("chnhdr DELTA 0.5\n")
         f1.write("ELSEIF &1,DELTA EQ 0.025\n")
         f1.write("decimate 2\n")
         f1.write("decimate 2\n")
         f1.write("decimate 5\n")
         f1.write("chnhdr DELTA 0.5\n")
         f1.write("ELSEIF &1,DELTA EQ 0.05\n")
         f1.write("decimate 2\n")
         f1.write("decimate 5\n")
         f1.write("chnhdr DELTA 0.5\n")
         f1.write("ELSEIF &1,DELTA EQ 0.1\n")
         f1.write("decimate 5\n")
         f1.write("chnhdr DELTA 0.5\n")
         f1.write("ELSE\n")
         f1.write("chnhdr DELTA 0.5\n")
         f1.write("ENDIF\n")
	 ortime=inv_param['YEAR']+" "+inv_param['JULIAN']+" "+inv_param['HOUR']+" "
	 ortime=ortime+inv_param['MIN']+" "+inv_param['SEC']+" "+inv_param['MSEC']
         f1.write("chnhdr O GMT "+ortime+"\n")
         f1.write("evaluate to rtime &1,O * (-1)\n")
	 f1.write("chnhdr ALLT %rtime IZTYPE IO\n")
         f1.write("w "+file2+".tmp\n")
	 f1.write("r "+file2+".tmp\n")
	 f1.write("w over\n")
	 f2.write("r "+file2+".tmp\n")
         f2.write("setbb vbeg &1,B\n")
         f2.write("setbb vdel &1,DELTA\n")
         f2.write("evaluate to fnpts %vbeg / %vdel \n")
         f2.write("evaluate to inpts (INTEGER %fnpts%) \n")
         f2.write("evaluate to corrb &1,DELTA * %inpts \n")
         f2.write("chnhdr b %corrb\n")
         f2.write("w "+file2+"\n")
         f2.write("r "+file2+"\n")
         f2.write("w over\n")
   f1.write("quit\n")
   f2.write("quit\n")
   f1.flush()
   f1.close()
   f2.flush()
   f2.close()

   f = open('sac.inp.tmp1','w')
   f.write("macro resamp05.mac\n")
   f.flush()
   f.close()
   f = open('sac.inp.tmp2','w')
   f.write("macro fitorigintime.mac\n")
   f.flush()
   f.close()
 

def runSacMacros():
   os.system('sac2000 < sac.inp.tmp1')
   os.system('sac2000 < sac.inp.tmp2')


def checkDataQuality(inv_step,inv_param,traces,freceivers,fdata):
   stype='bilateral'
   mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp-qualitycheck')
   minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out-qualitycheck')
   f = open (mininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_misfit_method peak\n")
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "\
           +inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mf)
   stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
   ccshift1,ccshift2=inv_param['CC_SHIFT1'],inv_param['CC_SHIFT2']
   localdepth=int(float(inv_param['DEPTH_1']))
   sdep=str(int(localdepth*1000.))
   for trace in traces:
      taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
      f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   for evaluatesds in [('0','90','0'),('0','45','90'),('45','45','90'),('90','45','90'),('135','45','90'),\
                       ('45','90','0'),('0','90','90'),('45','90','90'),('90','90','90'),('135','90','90')]: 
      sevstr,sevdip,sevrak=evaluatesds[0],evaluatesds[1],evaluatesds[2]
      line = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" "+sevstr+" "+sevdip+" "+sevrak+\
             " 0 0 0 0 0 "+inv_param['RADIUS0']+" 1\n"
      f.write(line)
      f.write("get_misfits\n")
   line = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" 0 0 0 0 0 0 0 0 "+inv_param['RADIUS0']+" 1\n"
   f.write(line)
   f.write("get_misfits\n")
   it=0
   for trace in traces:
      it=it+1
      taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
      splittedtaper=taper.split()
      if inv_param['NOISE_WINDOW'].upper()=="BEFORE":
         t1=float(stim)-(float(splittedtaper[6])-float(splittedtaper[0]))
         t2=float(stim)-(float(splittedtaper[6])-float(splittedtaper[2]))
         t3=float(stim)-(float(splittedtaper[6])-float(splittedtaper[4]))
         t4=float(stim)
      elif inv_param['NOISE_WINDOW'].upper()=="AFTER":
         t1=float(splittedtaper[6])
         t2=float(splittedtaper[6])+(float(splittedtaper[2])-float(splittedtaper[0]))
         t3=float(splittedtaper[6])+(float(splittedtaper[4])-float(splittedtaper[0]))
         t4=float(splittedtaper[6])+(float(splittedtaper[6])-float(splittedtaper[0]))    
      elif inv_param['NOISE_WINDOW'].upper()=="4MINTOT0":
         t1,t2,t3,t4=-240,-220,-20,0
      else:
         sys.exit("ERROR: unknown method to remove noisy traces, "+inv_param['NOISE_WINDOW'])
      a1,a2,a3,a4=splittedtaper[1],splittedtaper[3],splittedtaper[5],splittedtaper[7]   
      noisetaper=str(t1)+" "+a1+" "+str(t2)+" "+a2+" "+str(t3)+" "+a3+" "+str(t4)+" "+a4
      f.write("set_misfit_taper "+str(trace.num)+" "+noisetaper+"\n")
   f.write("get_misfits\n")
   f.flush()
   f.close()
   callMinimizer(mininp,minout)
   f = open (minout,'r')
   text=[]
   i=0
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer.out - checkquality)')
      else:
         if not re.search('ok',line):
            text.append(line) 
	    i=i+1
   f.flush()
   f.close()
   if i<>12:
      sys.exit('ERROR: quality check, 12 lines expected, founded: '+str(i))
   else:
      averagedmisfits,averagedmisfitsapp=[],[]
      for i in range(it):
         averagedmisfits.append(0.)
      for iline in range(10):
         splittedline=text[iline].split()
         for i in range(it):
            averagedmisfits[i]=averagedmisfits[i]+0.1*float(splittedline[i*2+1])
      median_avmisf=numpy.median(averagedmisfits)
      splittedline11=text[10].split()  
      splittedline12=text[11].split()  
      ncoef1=[]
      ncoef2=[]
      for i in range(it):
         ncoef1.append(float(splittedline11[i*2+1]))
	 ncoef2.append(float(splittedline12[i*2+1])/float(splittedline11[i*2+1]))
      min_accepted=median_avmisf/float(inv_param['LEVEL_RELAMP'])
      max_accepted=median_avmisf*float(inv_param['LEVEL_RELAMP'])
      print "median",median_avmisf 
      print "min-ac",min_accepted
      print "max-ac",max_accepted
      print "traces",it
      for i in range(it):
         averagedmisfit=averagedmisfits[i]
	 signaltonoise=ncoef2[i]
	 if averagedmisfit<min_accepted:
	    traces[i].quality="nok-small"
	 elif averagedmisfit>max_accepted:
	    traces[i].quality="nok-large"
	 elif signaltonoise>float(inv_param['LEVEL_S2N']):
	    traces[i].quality="nok-noise"
      fnok = open (os.path.join(inv_param['INVERSION_DIR'],'stations.unused'),'w')
      for i in range(it):
	 print "trace",str(i+1),traces[i].quality
         if traces[i].quality<>"ok":
   	    fnok.write(traces[i].stat+" "+traces[i].comp+" "+traces[i].quality+" \n")
      fnok.flush()
      fnok.close()
	 
# old version
#      splittedline11=text[10].split()  
#      splittedline12=text[11].split()  
#      ncoef1=[]
#      ncoef2=[]
#      ncoef1app=[]
#      for i in range(it):
#         ncoef1.append(float(splittedline11[i*2+1]))
#	 ncoef1app.append(float(splittedline11[i*2+1]))
#	 ncoef2.append(float(splittedline12[i*2+1])/float(splittedline11[i*2+1]))
#      ncoef1app.sort()
#      mediann1=ncoef1app[int(round(it/2))]
#      min_accepted=mediann1/100
#      max_accepted=mediann1*100
#      print "median",mediann1 
#      print "min-ac",min_accepted
#      print "max-ac",max_accepted
#      print "traces",it
#      for i in range(it):
#         peakamplitude=ncoef1[i]
#	 signaltonoise=ncoef2[i]
#	 if peakamplitude<min_accepted:
#	    traces[i].quality="nok-small"
#	 elif peakamplitude>max_accepted:
#	    traces[i].quality="nok-large"
#	 elif signaltonoise>0.666:
#	    traces[i].quality="nok-noise"
#      for i in range(it):
#	 print "trace",str(i+1),traces[i].quality


def prepData(inv_step,inv_param,traces,apply_taper):
# ASCII or SAC processing (DELTA MUST BE 0.5!!!)
#   if inv_param['SW_DATA_SAMPLING'].upper()=="TRUE":
#      if (inv_param['DATA_FORMAT']=='sac'):
#         delta=float(inv_param['SAMPLING_RATE'])
#         if (delta == 0.5):
#            buildSacMacros(inv_param,traces) 
#            runSacMacros()
#         else:
#            print "Delta is ",inv_param['SAMPLING_RATE']
#            print "Ascii data resampling process is not yet fixed"
#	    sys.exit("ERROR: Delta must be 0.5")
#      else:
#         print "ascii data!"
# Prepare file stations.table
   freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table')
   f = open (freceivers,'w')
   for trace in traces:
      if len(trace.comp) >= 1:
         f.write(trace.lat+" "+trace.lon+" "+trace.comp+"\n")
   f.flush()
   f.close()
   tracesquality=[]
   if inv_param['SW_FILTERNOISY'].upper()=="TRUE":
      fdata=os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
      checkDataQuality(inv_step,inv_param,traces,freceivers,fdata)
   freceiverz=os.path.join(inv_param['INVERSION_DIR'],'stations.table.z')
   freceiver1=os.path.join(inv_param['INVERSION_DIR'],'stations.table.mec')
   freceiver2=os.path.join(inv_param['INVERSION_DIR'],'stations.table.loc')
   freceiver3=os.path.join(inv_param['INVERSION_DIR'],'stations.table.kin')
   fz = open (freceiverz,'w')
   f1 = open (freceiver1,'w')
   f2 = open (freceiver2,'w')
   f3 = open (freceiver3,'w')
   latlon=[]
   for trace in traces:
      if len(trace.comp) >= 1:
#         f.write(trace.lat+" "+trace.lon+" "+trace.comp+"\n")
         if 'u' in (trace.comp):
	    if (trace.quality=="ok"):
               fz.write(trace.lat+" "+trace.lon+" u\n")
	    else:
	       fz.write(trace.lat+" "+trace.lon+"\n")
         elif 'd' in (trace.comp) and (trace.quality=="ok"):
	    if (trace.quality=="ok"):
               fz.write(trace.lat+" "+trace.lon+" d\n")
	    else:
	       fz.write(trace.lat+" "+trace.lon+"\n")
	 if (trace.dist <= float(inv_param['EPIC_DIST_MAX'])):
	    if (trace.quality=="ok"):
               f1.write(trace.lat+" "+trace.lon+" "+trace.comp+"\n")
	       ll=(trace.lat,trace.lon)
	       if ll not in latlon and len(trace.comp)>0:
	          latlon.append(ll)
	    else:
	       f1.write(trace.lat+" "+trace.lon+"\n")
	 if (trace.dist <= float(inv_param['EPIC_DIST_MAXLOC'])):
	    if (trace.quality=="ok"):
               f2.write(trace.lat+" "+trace.lon+" "+trace.comp+"\n")
	    else:
	       f2.write(trace.lat+" "+trace.lon+"\n")
	 if (trace.dist <= float(inv_param['EPIC_DIST_MAXKIN'])):
	    if (trace.quality=="ok"):
               f3.write(trace.lat+" "+trace.lon+" "+trace.comp+"\n")
	    else:
	       f3.write(trace.lat+" "+trace.lon+"\n")
   fz.flush()
   fz.close()
   f1.flush()
   f1.close()
   f2.flush()
   f2.close()
   f3.flush()
   f3.close()
   numberlatlons=len(latlon)
   f1 = open (freceiver1,'r')
   ill=0
   if (inv_param['SW_APPDURATION'].upper()=="TRUE"):
      for ll in latlon:
         ill=ill+1
         freceiver4=os.path.join(inv_param['INVERSION_DIR'],'stations.table.dur.'+str(ill))
         f1 = open (freceiver1,'r')
         f4 = open (freceiver4,'w')
         for line in f1:
            spline=line.split()
	    lll=(spline[0],spline[1])
            if len(spline)==3 and ll==lll:
	       f4.write(ll[0]+" "+ll[1]+" "+spline[2]+"\n") 
	    else:
	       f4.write(ll[0]+" "+ll[1]+"\n") 
         f4.flush()
         f4.close()
         f1.flush()
         f1.close()
   

def processInvParam(finput,fdefaults,facceptables,inv_param,active_comp,active_chan,comp_names):
   readDefInputFile(fdefaults,inv_param)
   readInputFile(finput,inv_param,active_comp)
   checkAccInputFile(facceptables,inv_param)
   assignChannels(active_comp,active_chan,inv_param)
   assignCompNames(comp_names)


def checkTaper(inv_param,inv_step):
# Check if taper is required and well formatted
   apply_taper=False
   if inv_param['SW_APPLY_TAPER']:
      apply_taper=True
      print "Taper applied"
   if 'a' in inv_param['PHASES_2_USE_ST'+inv_step]:
      if len(inv_param['PHASES_2_USE_ST'+inv_step]) > 1:
         sys.exit("ERROR: if all trace to be fit (P2US=a), no other phases should be chosen")
   return apply_taper


def checkStrDipRak(smom,str1,dip1,rak1):
   if (float(smom)<0):
      smom=str(abs(float(smom)))
      if (rak1<=0):
         rak1=rak1+180
      else:
         rak1=rak1-180
   if (dip1<0):
      dip1=-dip1
      str1=str1+180
      rak1=rak1+180
   while (dip1>=360):
      dip1=dip1-360        
   if (dip1>=180):
      dip1=dip1-180
      rak1=-rak1+180      
   if (dip1>90):
      dip1=180-dip1
      str1=str1+180
      rak1=-rak1     
   while (str1>=360):
      str1=str1-360 
   while (str1<0):
      str1=str1+360 
   while (rak1>180):
      rak1=rak1-360 
   while (rak1<=(-180)):
      rak1=rak1+360 
   str2,dip2,rak2=str1,dip1,rak1
   return(smom,str2,dip2,rak2)


def callMinimizer(fmininp,fminout):
   print "Calling minimizer",fmininp
   cmd = 'minimizer < '+fmininp+' > '+fminout
   print '1',fmininp,fminout
   print '2',cmd
   os.system(cmd)

def callParallelizedMinimizer(fmininp,fminout,nproc):
   print "Calling minimizer",fmininp
   print "   parallelized, number of processors: "+str(nproc)
   for i in range(nproc):
      cmd = 'minimizer < '+fmininp+"-proc"+str(i+1)+' > '+fminout+"-proc"+str(i+1)+'&'
      print '1',fmininp,fminout
      print '2',cmd
      os.system(cmd) 
   #check all have finished
   os.system("whoami > whoami.tmp")
   f=open("whoami.tmp","r")
   for line in f:
      splittedline=line.split()
      whoami=splittedline[0]
   f.flush()
   f.close()
   ongoingprocesses=True
   while ongoingprocesses:
      os.system("ps -fC minimizer > checkminimizers.tmp")
      f=open("checkminimizers.tmp","r")
      for line in f:
         splittedline=line.split()
	 ongoingprocesses=False
	 if splittedline[0]==whoami:
	    ongoingprocesses=True
      f.flush()
      f.close()
      

def line_mask(sourcetype,true_parameters):
   list_switches=[]
   if sourcetype=='bilateral':
      all_parameters=['time','north-shift','east-shift','depth','moment',
                      'strike','dip','slip-rake','rupture-rake','length-a','length-b',
                      'width','rupture-velocity','rise-time']
   elif sourcetype=='eikonal':
      all_parameters=['time','north-shift','east-shift','depth','moment',
                      'strike','dip','slip-rake','bordx','bordy','radius',
                      'nuklx','nukly','relruptvel','rise-time']
   elif sourcetype=='moment_tensor':
      all_parameters=['time','north-shift','east-shift','depth',
                      'm11','m12','m13','m22','m23','m33','rise-time']
   else:
      sys.exit('ERROR: source type not implemented: '+sourcetype)
   for parameter in true_parameters:
      if parameter not in all_parameters:
         sys.exit("ERROR: chosen source parameter has wrong name: "+parameter)
   for parameter in all_parameters:
      if parameter in true_parameters:
         list_switches.append('T')
      else:
         list_switches.append('F')
   str_switches=string.join(list_switches)
   line="set_source_params_mask     "+str_switches+"\n"
   return line


def point2eikonal(point_solution,inv_param,predef_inv_step):
   inv_step = predef_inv_step
   misfit = 99999.
   if (inv_param['SW_RELOCATE'].upper()=='TRUE'):
      rnor = point_solution.rnor
      rest = point_solution.rest
      time = point_solution.time
   else:
      rnor = inv_param['ORIG_NORTH_SHIFT']
      rest = inv_param['ORIG_EAST_SHIFT']
      time = inv_param['ORIG_TIME']
   depth = point_solution.depth
   strike = point_solution.strike
   dip = point_solution.dip
   rake = point_solution.rake
   smom = point_solution.smom
   misf_shift = point_solution.misf_shift
   bordx = '0'
   bordy = '0'
   radius = '0'
   nuklx = '0'
   nukly = '0'
   relruptvel = inv_param['REL_RUPT_VEL_1']
   if (inv_param['SW_AUTORISETIME'].upper()=='TRUE'):
      risetime = point_solution.risetime
   else:
      risetime = inv_param['KIN_RISETIME']
   return Eikonalsource(inv_step, misfit, rnor, rest, time, depth, strike, dip, rake, smom, \
                        misf_shift, bordx, bordy, radius, nuklx, nukly, relruptvel, risetime)


def cpEikonal(orig_eikonal):
   inv_step = orig_eikonal.inv_step
   misfit = orig_eikonal.misfit
   depth = orig_eikonal.depth
   strike = orig_eikonal.strike
   dip = orig_eikonal.dip
   rake = orig_eikonal.rake
   smom = orig_eikonal.smom
   rnor = orig_eikonal.rnor
   rest = orig_eikonal.rest
   time = orig_eikonal.time
   misf_shift = orig_eikonal.misf_shift
   bordx = orig_eikonal.bordx
   bordy = orig_eikonal.bordy
   radius = orig_eikonal.radius
   nuklx = orig_eikonal.nuklx
   nukly = orig_eikonal.nukly
   relruptvel = orig_eikonal.risetime
   risetime = orig_eikonal.risetime
   return Eikonalsource(inv_step, misfit, rnor, rest, time, depth, strike, dip, rake, smom, \
                        misf_shift, bordx, bordy, radius, nuklx, nukly, relruptvel, risetime)


def point2mt(point_solution,inv_param,predef_inv_step):
   inv_step = predef_inv_step
   misfit = 99999.
   rnor = point_solution.rnor
   rest = point_solution.rest
   time = point_solution.time
   strise = point_solution.risetime 
   depth = point_solution.depth
   misf_shift = point_solution.misf_shift
   strike_gra = float(point_solution.strike)
   dip_gra = float(point_solution.dip)
   rake_gra = float(point_solution.rake)
   smom = point_solution.smom
   m11,m12,m13,m22,m23,m33=sdisl2mt(strike_gra,dip_gra,rake_gra)
   m11,m12,m13=m11*float(smom),m12*float(smom),m13*float(smom)
   m22,m23,m33=m22*float(smom),m23*float(smom),m33*float(smom)   
   iso=0.
   dc=100.
   clvd=0.
   return MTsource(inv_step, misfit, rnor, rest, time, depth, m11, m12, m13, m22, m23, m33, \
                   iso, dc, clvd, misf_shift, strise)
#   fmtdecompinp=os.path.join(inv_param['INVERSION_DIR'],'mtdecomp.inp'+inv_step)
#   fmtdecompout=os.path.join(inv_param['INVERSION_DIR'],'mtdecomp.out'+inv_step)
#   f = open (fmtdecompinp,'w')
#   f2 = open (fmtdecompout,'r') 
#   f.write(str(int(float(strike)))+'\n')
#   f.write(str(int(float(dip)))+'\n')
#   f.write(str(int(float(rake)))+'\n')
#   f.close()
#   cmd = 'rapidmtdecomp < '+fmtdecompinp+' > '+fmtdecompout
#   os.system(cmd)
#   f = open (fmtdecompout,'r') 
#   text=[]
#   for line in f:
#      text.append(line)   
#   f.close()
#   mstrike,mdip,mrake=text[0].split()
#   miso,mdc,mclvd=text[1].split()
#   strike=float(mstrike)
#   dip=float(mdip)
#   rake=float(mrake)
#   iso=float(miso)
#   dc=float(mdc)
#   clvd=float(mclvd)
#   return MTsource(inv_step, misfit, rnor, rest, time, depth, m11, m12, m13, m22, m23, m33, \
#                   iso, dc, clvd, misf_shift)
		   
		   
def defineGridWalkDCsource(inv_step,start_point_solutions,point_solutions,inv_param):
   if (inv_step == '1'):
      stmis=stmsh=99999
      stnor,stest=inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
      sttim=inv_param['ORIG_TIME']
      strise=inv_param['RISE_TIME_1']
      dep1=int(float(inv_param['DEPTH_1'])*1000)
      dep2=int(float(inv_param['DEPTH_2'])*1000)
      depstep=int(float(inv_param['DEPTH_STEP'])*1000)
      mom1,mom2,momstep = float(inv_param['SCAL_MOM_1']),float(inv_param['SCAL_MOM_2']),float(inv_param['SCAL_MOM_STEP'])
      str1,str2,strstep = int(inv_param['STRIKE_1']),int(inv_param['STRIKE_2']),int(inv_param['STRIKE_STEP'])
      dip1,dip2,dipstep = int(inv_param['DIP_1']),int(inv_param['DIP_2']),int(inv_param['DIP_STEP'])
      rak1,rak2,rakstep = int(inv_param['RAKE_1']),int(inv_param['RAKE_2']),int(inv_param['RAKE_STEP'])
#      ris1,ris2,risstep = float(inv_param['RISE_TIME_1']),float(inv_param['RISE_TIME_2']),float(inv_param['RISE_TIME_STEP'])
      ris1,ris2,risstep = float(inv_param['RISE_TIME_1']),float(inv_param['RISE_TIME_1']),float(inv_param['RISE_TIME_STEP'])
      depu,depl=float(inv_param['DEPTH_UPPERLIM']),float(inv_param['DEPTH_BOTTOMLIM'])
      if (depu>depl):
         sys.exit("ERROR: upper limit for depths is below lower limit")  
      if inv_param['SW_RAPIDSTEP1'].upper()=='TRUE':
         print "Step 1: Rapid mode activated"
         stdep,stmom=str(dep1),str(mom1)
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'0','90','0',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'0','45','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'45','45','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'90','45','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'135','45','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'45','90','0',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'0','90','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'45','90','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'90','90','90',stmom,stmsh,strise))
	 start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,'135','90','90',stmom,stmsh,strise))
      else:
         if dep1==dep2 and depstep==0:
             depstep = 1
         for depth in range(dep1,dep2+1,depstep):   
            mom=mom1
            while (mom<=mom2):
	       ris=ris1
	       while (ris<=ris2):
	          strise=str(ris)
                  for strike in range(str1,str2+1,strstep):
                     for dip in range(dip1,dip2+1,dipstep):
                        for rake in range(rak1,rak2+1,rakstep):
	  	           stdep,ststr,stdip,strak,stmom=str(depth),str(strike),str(dip),str(rake),str(mom)
		           start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,\
	                                                         ststr,stdip,strak,stmom,stmsh,strise))
                  ris=ris+risstep
	       mom=mom*momstep   
      start_point_solutions.sort(key=operator.attrgetter('depth'))
   elif (inv_step == '2'):
      start_point_solutions.append(point_solutions[0])
      nor1=int(inv_param['ORIG_NORTH_SHIFT'])+int(inv_param['REL_NORTH_1'])
      nor2=int(inv_param['ORIG_NORTH_SHIFT'])+int(inv_param['REL_NORTH_2'])
      norstep=int(inv_param['REL_NORTH_STEP'])
      est1=int(inv_param['ORIG_EAST_SHIFT'])+int(inv_param['REL_EAST_1'])
      est2=int(inv_param['ORIG_EAST_SHIFT'])+int(inv_param['REL_EAST_2'])
      eststep=int(inv_param['REL_EAST_STEP'])
#      tim1=int(inv_param['ORIG_TIME'])+int(inv_param['REL_TIME_1'])
#      tim2=int(inv_param['ORIG_TIME'])+int(inv_param['REL_TIME_2'])
#      timstep=int(inv_param['REL_TIME_STEP'])
      tim1=float(inv_param['ORIG_TIME'])+float(inv_param['REL_TIME_1'])
      tim2=float(inv_param['ORIG_TIME'])+float(inv_param['REL_TIME_2'])
      if tim2<tim1:
         sys.exit("ERROR: max_relative_time < min_relative_time") 
      timstep=float(inv_param['REL_TIME_STEP'])
      relativetimes=[]
      loctim=tim1
      while loctim<=tim2:
         relativetimes.append(loctim)
	 loctim=loctim+timstep
      print "times",tim1,tim2,timstep
#      refdep=1000*int(round(0.001*float(point_solutions[0].depth)))
      refdep=int(round(float(point_solutions[0].depth)))
      dep1=refdep+int(float(inv_param['REL_DEPTH_1']))
      dep2=refdep+int(float(inv_param['REL_DEPTH_2']))
      depstep=int(float(inv_param['REL_DEPTH_STEP']))     
      print "DEPs ",dep1,dep2,depstep,point_solutions[0].depth
      sttim,stmis,stmsh=point_solutions[0].time,99999,99999
#      stdep=point_solutions[0].depth
      stmom=point_solutions[0].smom
      ststr=point_solutions[0].strike
      stdip=point_solutions[0].dip
      strak=point_solutions[0].rake
      strise=point_solutions[0].risetime
      depu,depl=float(inv_param['DEPTH_UPPERLIM']),float(inv_param['DEPTH_BOTTOMLIM'])
      if (depu>depl):
         sys.exit("ERROR: upper limit for depths is below lower limit")  
      for time in relativetimes:
         for north in range(nor1,nor2+1,norstep):
            for east in range(est1,est2+1,eststep):
	       for localdepth in range(dep1,dep2+1,depstep):
       	          sttim,stnor,stest,stdep=str(time),str(north),str(east),str(localdepth)
	          start_point_solutions.append(DCsource(inv_step,stmis,stnor,stest,sttim,stdep,ststr,stdip,strak,\
	                                             stmom,stmsh,strise))
#      start_point_solutions.sort(key=operator.attrgetter('depth'))


def calcScMoment(m1,m2,m3,m4,m5,m6):
   smom=math.sqrt(m1*m1+m2*m2+m3*m3+m4*m4+m5*m5+m6*m6)
   return(smom)


def defineGridWalkMTsource(inv_step,start_mt_solutions,mt_solutions,inv_param):
   if (inv_step == '1'):
      stmis,stmsh=str(mt_solutions[0].misfit),str(mt_solutions[0].misf_shift)
      sttim,stnor,stest=str(mt_solutions[0].time),str(mt_solutions[0].rnor),str(mt_solutions[0].rest)
      stdep,strise=str(mt_solutions[0].depth),str(mt_solutions[0].risetime)
      scmoment=calcScMoment(mt_solutions[0].m11,mt_solutions[0].m12,mt_solutions[0].m13,\
                            mt_solutions[0].m22,mt_solutions[0].m23,mt_solutions[0].m33)
      mt_coefficients=[-1,0]
      for i11 in mt_coefficients:
       for i12 in [-1,0]:
        for i13 in [-1,0]:
         for i22 in [-1,0]:
          for i23 in [-1,0]:
           for i33 in [-1,0]:
            print "MOMTEN",i11,i12,i13,i22,i23,i33
	    stm11=str(float(mt_solutions[0].m11)+float(i11)*float(scmoment))
	    stm12=str(float(mt_solutions[0].m12)+float(i12)*float(scmoment))
	    stm13=str(float(mt_solutions[0].m13)+float(i13)*float(scmoment))
	    stm22=str(float(mt_solutions[0].m22)+float(i22)*float(scmoment))
	    stm23=str(float(mt_solutions[0].m23)+float(i23)*float(scmoment))
	    stm33=str(float(mt_solutions[0].m33)+float(i33)*float(scmoment))
            stiso=0.
	    stdc=100.
	    stclvd=0.
	    start_mt_solutions.append(MTsource(inv_step,stmis,stnor,stest,sttim,stdep,stm11,stm12,stm13,\
	                                       stm22,stm23,stm33,stiso,stdc,stclvd,stmsh,strise))
   elif (inv_step == '2'):
      stmis,stmsh=str(mt_solutions[0].misfit),str(mt_solutions[0].misf_shift)
      sttim,stnor,stest=str(mt_solutions[0].time),str(mt_solutions[0].rnor),str(mt_solutions[0].rest)
      stdep,strise=str(mt_solutions[0].depth),str(mt_solutions[0].risetime)
      stiso=0.
      stdc=100.
      stclvd=0.
      stm11=str(mt_solutions[0].m11)
      stm12=str(mt_solutions[0].m12)
      stm13=str(mt_solutions[0].m13)
      stm22=str(mt_solutions[0].m22)
      stm23=str(mt_solutions[0].m23)
      stm33=str(mt_solutions[0].m33)  
      start_mt_solutions.append(MTsource(inv_step,stmis,stnor,stest,sttim,stdep,stm11,stm12,stm13,\
                                         stm22,stm23,stm33,stiso,stdc,stclvd,stmsh,strise))
   else:
      sys.exit("ERROR: defineGridWalkMTsource called unexpectedly at step ",inv_step)


def defineGridWalkEikonalsource(inv_step,start_eikonals,eikonals,inv_param):
   if (inv_step == '3'):
      mw = m0tomw(float(inv_param['SCALING_FACTOR'])*float(eikonals[0].smom))
      max_risetime=2/float(inv_param['BP_F3_STEP3'])
      min_risetime=1/(3*float(inv_param['BP_F3_STEP3']))
      if (inv_param['SW_AUTORISETIME'].upper()=='TRUE'):
         ref_risetime=(1./3.)*float(eikonals[0].risetime)
      else:
         ref_risetime=float(eikonals[0].risetime)
      if (inv_param['SW_BPRISETIME'].upper()=='TRUE'):
         if (ref_risetime<min_risetime):
            ref_risetime=min_risetime
         if (ref_risetime>max_risetime):
            ref_risetime=max_risetime
      risetimes=[ref_risetime]
      if (mw<3.0):
         radiuses=[50.,100.,150.,200.,250.,350.]
#	 risetimes=[1]
      elif (mw<5.1):
         radiuses=[500.,1000.,2000.,3000.,5000.]
#	 risetimes=[1]
      elif (mw<5.6):
         radiuses=[500.,1000.,2000.]
#	 risetimes=[2]
      elif (mw <6.1):
#         radiuses=[2500.,5000.,7500.,10000.,12500.,15000.,20000.]
         radiuses=[1000.,2500.,5000.,7500.,10000.,15000.]
#	 risetimes=[1]
      elif (mw <6.6):
#         radiuses=[2500.,5000.,7500.,10000.,12500.,15000.,20000.]
         radiuses=[2000.,5000.,7500.,10000.,15000.,20000.,25000.]
#	 risetimes=[1]
      elif (mw <7.1):
#         radiuses=[5000., 10000.,20000., 50000.]
         radiuses=[2500.,5000.,10000.]
#         radiuses=[5000.,10000.,15000.,20000.,25000.,35000.]
#	 risetimes=[1]
      elif (mw <7.6):
#         radiuses=[5000., 10000.,20000., 50000.]
         radiuses=[7500.,15000.,25000.,35000.,50000.]
#	 risetimes=[1]
      else:
#         radiuses=[5000., 10000.,20000., 50000.]
         radiuses=[10000.,25000.,50000.,100000.]
#	 risetimes=[1]
      if inv_param['SW_INVSMOM_ST3'].upper()=='TRUE':
         locsmom1=0.5*float(eikonals[0].smom)
         locsmom2=1.5*float(eikonals[0].smom)
         locsmoms=0.1*float(eikonals[0].smom)
      for iref in range(2):
        for risetime in risetimes:
          for radius in radiuses:
	    centerdepth=float(eikonals[0].depth)
	    modradius=radius
	    if (centerdepth<radius):
	       modradius=centerdepth
 	    moho=getCrustalDepth(inv_param)
	    maxlowradius=abs(moho-centerdepth)
	    if (maxlowradius<modradius):
	       modradius=maxlowradius	       
	    bx1=-0.9*radius
            bx2=-0.45*radius
            bx3=0
            bx4=0.45*radius
            bx5=0.9*radius
	    by1=-0.9*modradius
	    by2=-0.45*modradius
	    by3=0
	    by4=0.45*modradius
	    by5=0.9*modradius
# 	    bx1=by1=-0.9*radius
#            bx2=by2=-0.45*radius
#            bx3=by3=0
#            bx4=by4=0.45*radius
#            bx5=by5=0.9*radius
	    if (mw<5.6):         
#               nucleations=[(bx1,by3),(bx3,by3),(bx5,by3),(bx3,by1),(bx3,by5)]
               nucleations=[(bx1,by3),(bx3,by3),(bx5,by3)]
            elif (mw<6.1):
	       nucleations=[(bx1,by3),(bx2,by3),(bx3,by3),(bx4,by3),(bx5,by3)]
	    else:
               nucleations=[(bx3,by1),(bx1,by3),(bx2,by3),(bx3,by3),\
	                    (bx4,by3),(bx5,by3),(bx3,by5)]
#               nucleations=[(bx1,by3),(bx2,by3),(bx3,by3),(bx4,by3),(bx5,by3)]
	    for nukl in nucleations:
  	       r_rupt_vel=float(inv_param['REL_RUPT_VEL_1'])
  	       while r_rupt_vel <= float(inv_param['REL_RUPT_VEL_2']): 
		  if inv_param['SW_INVSMOM_ST3'].upper()=='TRUE':
    	             locsmom=locsmom1
		     while locsmom<=locsmom2:
                        start_eikonals.append(Eikonalsource(inv_step, eikonals[iref].misfit, \
		           eikonals[iref].rnor, eikonals[iref].rest, eikonals[iref].time, \
			   eikonals[iref].depth, eikonals[iref].strike, eikonals[iref].dip, \
			   eikonals[iref].rake, str(locsmom), eikonals[iref].misf_shift,\
                           eikonals[iref].bordx, eikonals[iref].bordy, \
			   str(radius), str(nukl[0]), str(nukl[1]), str(r_rupt_vel), \
			   str(risetime)))
		        locsmom=locsmom+locsmoms
		  else:
		     start_eikonals.append(Eikonalsource(inv_step, eikonals[iref].misfit, \
		           eikonals[iref].rnor, eikonals[iref].rest, eikonals[iref].time, \
			   eikonals[iref].depth, eikonals[iref].strike, eikonals[iref].dip, \
			   eikonals[iref].rake, eikonals[iref].smom, eikonals[iref].misf_shift,\
                           eikonals[iref].bordx, eikonals[iref].bordy, \
			   str(radius), str(nukl[0]), str(nukl[1]), str(r_rupt_vel), \
			   str(risetime)))
	          r_rupt_vel=r_rupt_vel+float(inv_param['REL_RUPT_VEL_S'])
      del eikonals[1]
      del eikonals[0]


def updateGridWalkDCsource(inv_step,point_solutions,start_point_solutions,inv_param,irun):
   if (inv_step == '1'):
#      depth=point_solutions[0].depth
      smom=point_solutions[0].smom
      misfit=stmsh=99999
#      strise=point_solutions[0].risetime
      strise=inv_param['RISE_TIME_1']
      rnor,rest=inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
      time=inv_param['ORIG_TIME']
#      str1=int(point_solutions[0].strike)-int(inv_param['STRIKE_STEP'])
#      str2=int(point_solutions[0].strike)+int(inv_param['STRIKE_STEP'])
#      strs=int(float(inv_param['STRIKE_STEP'])/(irun*float(inv_param['REDUCE_SDS_CONF'])))
#      dip1=int(point_solutions[0].dip)-int(inv_param['DIP_STEP'])
#      dip2=int(point_solutions[0].dip)+int(inv_param['DIP_STEP'])
#      dips=int(float(inv_param['DIP_STEP'])/(irun*float(inv_param['REDUCE_SDS_CONF'])))
#      rak1=int(point_solutions[0].rake)-int(inv_param['RAKE_STEP'])
#      rak2=int(point_solutions[0].rake)+int(inv_param['RAKE_STEP'])
#      raks=int(float(inv_param['RAKE_STEP'])/(irun*float(inv_param['REDUCE_SDS_CONF'])))
      dep1=round(float(point_solutions[0].depth))-round(float(inv_param['DEPTH_STEP'])/irun)
      dep2=round(float(point_solutions[0].depth))+round(float(inv_param['DEPTH_STEP'])/irun)
      deps=round(float(inv_param['DEPTH_STEP'])/(irun*float(inv_param['REDUCE_DEP_CONF'])))
      dep1=dep2=int(point_solutions[0].depth)
      deps=round(float(inv_param['DEPTH_STEP']))
      str1=round(float(point_solutions[0].strike))-round(float(inv_param['STRIKE_STEP'])/irun)
      str2=round(float(point_solutions[0].strike))+round(float(inv_param['STRIKE_STEP'])/irun)
      strs=round(float(inv_param['STRIKE_STEP'])/(irun*float(inv_param['REDUCE_SDS_CONF'])))
      dip1=round(float(point_solutions[0].dip))-round(float(inv_param['DIP_STEP'])/irun)
      dip2=round(float(point_solutions[0].dip))+round(float(inv_param['DIP_STEP'])/irun)
      dips=round(float(inv_param['DIP_STEP'])/(irun*float(inv_param['REDUCE_SDS_CONF'])))
      rak1=round(float(point_solutions[0].rake))-round(float(inv_param['RAKE_STEP'])/irun)
      rak2=round(float(point_solutions[0].rake))+round(float(inv_param['RAKE_STEP'])/irun)
      raks=round(float(inv_param['RAKE_STEP'])/(irun*float(inv_param['REDUCE_SDS_CONF'])))
      if deps<1:
         deps=1
      if strs<1:
         strs=1
      if dips<1:
         dips=1
      if raks<1:
         raks=1
      for depth in range(dep1,dep2+1,deps):
         for strike in range(str1,str2+1,strs):
            for dip in range(dip1,dip2+1,dips):
               for rake in range(rak1,rak2+1,raks):
                  start_point_solutions.append(DCsource(inv_step,misfit,rnor,rest,time,depth,strike,dip,rake,\
	                                                smom,stmsh,strise))
#     start_point_solutions.sort(key=operator.attrgetter('depth'))
   elif (inv_step == '2'):
      smom=point_solutions[0].smom
      misfit=stmsh=99999
      strike=point_solutions[0].strike
      dip=point_solutions[0].dip
      rake=point_solutions[0].rake
      time=point_solutions[0].time
      strise=point_solutions[0].risetime
      dep1=int(float(point_solutions[0].depth))-int(float(inv_param['DEPTH_STEP']))
      dep2=int(float(point_solutions[0].depth))+int(float(inv_param['DEPTH_STEP']))
      deps=int(float(inv_param['DEPTH_STEP'])/(irun*float(inv_param['REDUCE_LOC_CONF'])))      
      nor1=int(float(point_solutions[0].rnor))-int(float(inv_param['REL_NORTH_STEP']))
      nor2=int(float(point_solutions[0].rnor))+int(float(inv_param['REL_NORTH_STEP']))
      nors=int(float(inv_param['REL_NORTH_STEP'])/(irun*float(inv_param['REDUCE_LOC_CONF'])))
      est1=int(float(point_solutions[0].rest))-int(float(inv_param['REL_EAST_STEP']))
      est2=int(float(point_solutions[0].rest))+int(float(inv_param['REL_EAST_STEP']))
      ests=int(float(inv_param['REL_EAST_STEP'])/(irun*float(inv_param['REDUCE_LOC_CONF'])))
      if (deps<=0):
         deps=1
      for depth in range(dep1,dep2+1,deps):
         for rnor in range(nor1,nor2+1,nors):
            for rest in range(est1,est2+1,ests):
               start_point_solutions.append(DCsource(inv_step,misfit,rnor,rest,time,depth,strike,dip,rake,\
	                                             smom,stmsh,strise))


def updateGridWalkEikonalsource(inv_step,eikonals,start_eikonals,inv_param,irun):
   if (inv_step == '3'):
      local_eikonal=eikonals[0]
      local_eikonal.misfit=local_eikonal.stmsh=99999
      rad1=int(float(eikonals[0].radius))-int(inv_param['RADIUS_STEP'])
      rad2=int(float(eikonals[0].radius))+int(inv_param['RADIUS_STEP'])
      rads=int(float(inv_param['RADIUS_STEP'])/(irun*float(inv_param['REDUCE_EIK_CONF'])))
      nx1=int(float(eikonals[0].nuklx))-int(inv_param['NUKL_X_STEP'])
      nx2=int(float(eikonals[0].nuklx))+int(inv_param['NUKL_X_STEP'])
      nxs=int(float(inv_param['NUKL_X_STEP'])/(irun*float(inv_param['REDUCE_EIK_CONF'])))
      ny1=int(float(eikonals[0].nukly))-int(inv_param['NUKL_Y_STEP'])
      ny2=int(float(eikonals[0].nukly))+int(inv_param['NUKL_Y_STEP'])
      nys=int(float(inv_param['NUKL_Y_STEP'])/(irun*float(inv_param['REDUCE_EIK_CONF'])))
      for radius in range(rad1,rad2+1,rads):
         for nuklx in range(nx1,nx2+1,nxs):
            for nukly in range(ny1,ny2+1,nys):
	       r_rupt_vel=float(inv_param['REL_RUPT_VEL_1'])
	       while r_rupt_vel <= float(inv_param['REL_RUPT_VEL_2']): 
	          local_eikonal.radius = radius
	          local_eikonal.nuklx = nuklx
		  local_eikonal.nukly = nukly
		  local_eikonal.relruptvel = r_rupt_vel
		  start_eikonals.append(local_eikonal)
	          r_rupt_vel=r_rupt_vel+float(inv_param['REL_RUPT_VEL_S'])


def fault2aux(str1,dip1,rak1):
   str1,dip1,rak1=math.radians(str1),math.radians(dip1),math.radians(rak1)
   sstr1,sdip1,srak1=math.sin(str1),math.sin(dip1),math.sin(rak1)
   cstr1,cdip1,crak1=math.cos(str1),math.cos(dip1),math.cos(rak1)
   n1,n2,n3=-sdip1*sstr1,sdip1*cstr1,-cdip1
   l1=crak1*cstr1+cdip1*srak1*sstr1
   l2=crak1*sstr1-cdip1*srak1*cstr1
   l3=-srak1*sdip1
   an1,an2,an3,al1,al2,al3=l1,l2,l3,n1,n2,n3
   dip2=math.acos(-an3)
   str2=math.acos(an2/math.sin(dip2))
   rak2=math.asin(-al3/math.sin(dip2))
   while (str2 < 0.):
      str2=str2+2*math.pi
   while (str2 >= (2*math.pi)):
      str2=str2-2*math.pi
   while (dip2 < 0.):
      dip2=dip2+2*math.pi
   while (dip2 >= (2*math.pi)):
      dip2=dip2-2*math.pi
   while (rak2 < 0.):
      rak2=rak2+2*math.pi
   while (rak2 >= (2*math.pi)):
      rak2=rak2-2*math.pi
   dip21,dip22,str21,str22,rak21,rak22=dip2,2*math.pi-dip2,str2,2*math.pi-str2,rak2,math.pi-rak2
   if (rak22 < 0.):
      rak22=rak22+2*math.pi
   for ii in range(2):
      i=ii+1
      if (i == 1):
         st=str21
      elif (i == 2): 
         st=str22
      for jj in range(2):
         j=jj+1
         if (j == 1):
	    di=dip21
  	 if (j == 2):
	    di=dip22
         for kk in range(2):
	    k=kk+1
 	    if (k == 1):
	       sl=rak21
	    elif (k == 2):
	       sl=rak22
            an1,an2,an3=-math.sin(di)*math.sin(st),math.sin(di)*math.cos(st),-math.cos(di)
            al1=math.cos(sl)*math.cos(st)+math.cos(di)*math.sin(sl)*math.sin(st)
            al2= math.cos(sl)*math.sin(st)-math.cos(di)*math.sin(sl)*math.cos(st)
            al3=-math.sin(sl)*math.sin(di)
            misf0=abs(al1-n1)+abs(al2-n2)+abs(al3-n3)
	    misf0=misf0+abs(an1-l1)+abs(an2-l2)+abs(an3-l3)	
            ijk=i*j*k
	    if (ijk <= 1):
 	       str2=st
	       dip2=di
	       rak2=sl
	       misf=misf0
	    else:
	       if (misf0 < misf):
   	          str2=st
	          dip2=di
	          rak2=sl
	          misf=misf0
   if (dip2 > math.pi):
      dip2=dip2-math.pi
      rak2=rak2+math.pi
      if (rak2 >= (2*math.pi)):
         rak2=rak2-2*math.pi
   if (dip2 > (math.pi/2)):
      dip2=math.pi/2-(dip2-math.pi/2)
      str2=str2+math.pi      
      rak2=-rak2 
      if (str2 >= (2*math.pi)):
         str2=str2-2*math.pi
   if (rak2 >= math.pi):
       rak2=rak2-2*math.pi
   str2,dip2,rak2=math.degrees(str2),math.degrees(dip2),math.degrees(rak2)
   return str2,dip2,rak2


def calcAuxFaultPlane(inv_step,inv_param,point_solutions,best_point_solutions):
   misfit=point_solutions[0].misfit
   depth=point_solutions[0].depth
   strike=point_solutions[0].strike
   dip=point_solutions[0].dip
   rake=point_solutions[0].rake
   smom=point_solutions[0].smom
   rnor=point_solutions[0].rnor
   rest=point_solutions[0].rest
   time=point_solutions[0].time
   strise=point_solutions[0].risetime
   misf_shift=point_solutions[0].misf_shift
   print "using "+str(strike)+" "+str(dip)+" "+str(rake)
   if (inv_step == '1'):
      for i in range (4):
         best_point_solutions.append(DCsource(inv_step,misfit,rnor,rest,time,depth,strike,dip,rake,\
	                                      smom,misf_shift,strise))
   elif (inv_step == '2'):
      for i in range (2):
         best_point_solutions.append(DCsource(inv_step,misfit,rnor,rest,time,depth,strike,dip,rake,\
	                                      smom,misf_shift,strise))
   str1,dip1,rak1=float(point_solutions[0].strike),float(point_solutions[0].dip),float(point_solutions[0].rake)
   str2,dip2,rak2=fault2aux(str1,dip1,rak1)
   if (inv_step == '1'):
      best_point_solutions[1].strike,best_point_solutions[1].dip,best_point_solutions[1].rake=str2,dip2,rak2 
      if (best_point_solutions[2].rake <= 0):
         best_point_solutions[2].rake=best_point_solutions[2].rake + 180
      else:
         best_point_solutions[2].rake=best_point_solutions[2].rake - 180
      best_point_solutions[3].strike=best_point_solutions[1].strike
      best_point_solutions[3].dip=best_point_solutions[1].dip
      best_point_solutions[3].rake=best_point_solutions[1].rake
      if (best_point_solutions[3].rake <= 0):
         best_point_solutions[3].rake=best_point_solutions[3].rake + 180
      else:
         best_point_solutions[3].rake=best_point_solutions[3].rake - 180
      print "best 4 solutions"
      for point_solution in best_point_solutions:   
         ostr,odip,orak=point_solution.strike,point_solution.dip,point_solution.rake
         omom=point_solution.smom
         cmom,cstr,cdip,crak=checkStrDipRak(omom,ostr,odip,orak)
         point_solution.strike,point_solution.dip,point_solution.rake=cstr,cdip,crak
         point_solution.smom=cmom
      print "best 4 step 1 solutions"
      for point_solution in best_point_solutions:   
         print point_solution.misfit,point_solution.strike,point_solution.dip,point_solution.rake
   elif (inv_step == '2'):
      best_point_solutions[1].strike,best_point_solutions[1].dip,best_point_solutions[1].rake=str2,dip2,rak2 
      print "best 2 step 2 solutions"
      for point_solution in best_point_solutions:   
         if ( point_solution.inv_step == inv_step ):
	    ostr,odip,orak=point_solution.strike,point_solution.dip,point_solution.rake
            omom=point_solution.smom
            cmom,cstr,cdip,crak=checkStrDipRak(omom,ostr,odip,orak)
            point_solution.strike,point_solution.dip,point_solution.rake=cstr,cdip,crak
            point_solution.smom=cmom


def calcAuxMTsolutions(inv_step,inv_param,mt_solutions,best_mt_solutions):
   misfit=mt_solutions[0].misfit
   depth=mt_solutions[0].depth
   m11,m12,m13=mt_solutions[0].m11,mt_solutions[0].m12,mt_solutions[0].m13
   m22,m23,m33=mt_solutions[0].m22,mt_solutions[0].m23,mt_solutions[0].m33
   rnor=mt_solutions[0].rnor
   rest=mt_solutions[0].rest
   time=mt_solutions[0].time
   strise=mt_solutions[0].risetime
   misf_shift=mt_solutions[0].misf_shift
   iso=mt_solutions[0].iso
   dc=mt_solutions[0].dc
   clvd=mt_solutions[0].dc
   if (inv_step == '1'):
      best_mt_solutions.append(MTsource(inv_step,misfit,rnor,rest,time,depth,m11,m12,m13,m22,m23,m33,\
                                        iso,dc,clvd,misf_shift,strise))
      m11n,m12n,m13n=str(-float(m11)),str(-float(m12)),str(-float(m13))
      m22n,m23n,m33n=str(-float(m22)),str(-float(m23)),str(-float(m33))
      best_mt_solutions.append(MTsource(inv_step,misfit,rnor,rest,time,depth,m11n,m12n,m13n,m22n,m23n,m33n,\
                                        iso,dc,clvd,misf_shift,strise))
   elif (inv_step == '2'):
      best_mt_solutions.append(MTsource(inv_step,misfit,rnor,rest,time,depth,m11,m12,m13,m22,m23,m33,\
                                        iso,dc,clvd,misf_shift,strise))
   

def relMisfitCurves(inv_step,inv_param,point_solutions,best_point_solutions,n_point_solutions,apply_taper,fdata,freceivers):
   print "Evaluating misfit curves for Depth-Strike-Dip-Rake..."
   slat,slon=inv_param['LATITUDE_NORTH'],inv_param['LONGITUDE_EAST']  
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp1-relmis')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out1-relmis')
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)  
   depth0=best_point_solutions[0].depth
   strike0=best_point_solutions[0].strike
   dip0=best_point_solutions[0].dip
   rake0=best_point_solutions[0].rake
   smom0=best_point_solutions[0].smom
#   strise=best_point_solutions[0].risetime
   strise=inv_param['RISE_TIME_1']
   localdepth=int(float(depth0)/1000)
   if apply_taper:
      for trace in traces:
         taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   dep1=localdepth-float(inv_param['MISFIT_DEP_RANGE'])
   if dep1<float(inv_param['DEPTH_UPPERLIM']):
      dep1=float(inv_param['DEPTH_UPPERLIM'])
   dep2=localdepth+float(inv_param['MISFIT_DEP_RANGE'])   
   if dep2>float(inv_param['DEPTH_BOTTOMLIM']):
      dep2=float(inv_param['DEPTH_BOTTOMLIM'])   
   deps=float(inv_param['MISFIT_DEP_TICK'])
   str1=strike0-float(inv_param['MISFIT_SDS_RANGE'])
   str2=strike0+float(inv_param['MISFIT_SDS_RANGE'])
   dip1=dip0-float(inv_param['MISFIT_SDS_RANGE'])
   dip2=dip0+float(inv_param['MISFIT_SDS_RANGE'])
   rak1=rake0-float(inv_param['MISFIT_SDS_RANGE'])
   rak2=rake0+float(inv_param['MISFIT_SDS_RANGE'])
   strs=dips=raks=float(inv_param['MISFIT_SDS_TICK'])
   snor,sest,stim=inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT'],inv_param['ORIG_TIME']
   dsds = []
   nang=int((2*float(inv_param['MISFIT_SDS_RANGE']))/float(inv_param['MISFIT_SDS_TICK']))+1
   print str1,strike0,str2
   print dip1,dip0,dip2
   print rak1,rake0,rak2
   depthkm=dep1-deps
   for idep in range(nang):
      depthkm=depthkm+deps
      if (depthkm>float(inv_param['DEPTH_UPPERLIM'])) and (depthkm<float(inv_param['DEPTH_BOTTOMLIM'])):
         odep=depthkm*1000
         ostr=strike0
         odip=dip0
         orak=rake0
         if ( ostr != depth0):
            cdep,cstr,cdip,crak=odep,ostr,odip,orak
            dsds.append(DepthStrikeDipRake(cdep,cstr,cdip,crak))
            line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(cdep)+" "+str(smom0)+" "
            line = line+str(cstr)+" "+str(cdip)+" "+str(crak)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
            f.write(line)
            f.write("get_global_misfit\n")  
   strike=str1-strs
   for istr in range(nang):
      strike=strike+strs
      ostr=strike
      odip=dip0
      orak=rake0
      if ( ostr != strike0):
         cstr,cdip,crak=ostr,odip,orak
         dsds.append(DepthStrikeDipRake(depth0,cstr,cdip,crak))
         line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(int(depth0))+" "+str(smom0)+" "
         line = line+str(cstr)+" "+str(cdip)+" "+str(crak)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
         f.write(line)
         f.write("get_global_misfit\n")
   dip=dip1-dips
   for idip in range(nang):
      dip=dip+strs
      ostr=strike0
      odip=dip
      orak=rake0
      if (odip != dip0):
         cstr,cdip,crak=ostr,odip,orak
         dsds.append(DepthStrikeDipRake(depth0,cstr,cdip,crak))
         line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(int(depth0))+" "+str(smom0)+" "
         line = line+str(cstr)+" "+str(cdip)+" "+str(crak)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
         f.write(line_mm)
         f.write(line_mf)
         f.write(line)
         f.write("get_global_misfit\n")
   rake=rak1-raks
   for irak in range(nang):
      rake=rake+raks
      ostr=strike0
      odip=dip0
      orak=rake
      if (orak != rake0):
         cstr,cdip,crak=ostr,odip,orak
         dsds.append(DepthStrikeDipRake(depth0,cstr,cdip,crak))
         line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(int(depth0))+" "+str(smom0)+" "
         line = line+str(cstr)+" "+str(cdip)+" "+str(crak)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
         f.write(line_mm)
         f.write(line_mf)
         f.write(line)
         f.write("get_global_misfit\n") 
   f.flush()
   f.close()
   print "Calling minimizer",fmininp
   cmd = 'minimizer < '+fmininp+' > '+fminout
   os.system(cmd)
   i=0
   f = open (fminout,'r')
   text=[]
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer2.out)')
      else:
         if not re.search('ok',line):
            text.append(line)
            i=i+1
   n_new_point_solutions = i
   f.flush()
   f.close()
   rnor,rest,rtim=inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT'],inv_param['ORIG_TIME']
   misf_shift=99999
   for i in range(n_new_point_solutions):
      line1=text[i]
      misfit=float(line1)
      depth=dsds[i].depth
      strike=dsds[i].strike
      dip=dsds[i].dip
      rake=dsds[i].rake      
      point_solutions.append(DCsource(inv_step,misfit,rnor,rest,rtim,depth,strike,dip,rake,\
                             smom0,misf_shift,strise))
   n_point_solutions=n_point_solutions+n_new_point_solutions
   print "final set of point solutions"
   for point_sol in point_solutions:
      print point_sol.misfit,point_sol.depth,point_sol.strike,point_sol.dip,point_sol.rake


def analyseResultsDCsource(inv_step,inv_param,point_solutions,n_point_solutions,fminout,\
                           start_point_solutions,lines_singlemisfits):
   print 'Analysing results inversion step '+inv_step+'...'
   n_start_solutions=n_point_solutions
   i=0
   f = open (fminout,'r')
   text=[]
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer1.out)')
      else:
         if not re.search('ok',line):
            text.append(line) 
            i=i+1
   if (inv_step == '1'):	    
      if inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdsok':
         n_point_solutions = int(i/9)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsds':
         n_point_solutions = int(i/5)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdst':
         n_point_solutions = int(i/5)
#         n_point_solutions = int(i/7)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdst2x':
#         n_point_solutions = int(i/9)
         n_point_solutions = int(i/7)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_msds':
         n_point_solutions = int(i/5)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dm':
         n_point_solutions = int(i/3)
#         n_point_solutions = int(i/5)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmt':
         n_point_solutions = int(i/3)
#         n_point_solutions = int(i/5)
#         n_point_solutions = int(i/7)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dsds':
         n_point_solutions = int(i/5)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_sds':
         n_point_solutions = int(i/3)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_m':
         n_point_solutions = int(i/3)
      else:                                    #'grid'
         n_point_solutions = i
   elif (inv_step == '2'):
      if inv_param['INV_MODE_STEP'+inv_step]=='invert_tnem':
         n_point_solutions = int(i/7)      
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_tne':
         n_point_solutions = int(i/5)      
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_m':
         n_point_solutions = int(i/3)
      else:                                    #'grid'
         n_point_solutions = int(i/2)
   f.flush()
   f.close()
   if (n_start_solutions!=n_point_solutions):
      print n_start_solutions,n_point_solutions
      sys.exit('ERROR 1: n start sol <> n point sol (minimizer.out)')
   for i in range(n_point_solutions):
      if (inv_step == '1'):
         depth=float(start_point_solutions[i].depth)
         strike=float(start_point_solutions[i].strike)  
         dip=float(start_point_solutions[i].dip)  
         rake=float(start_point_solutions[i].rake)  
	 strise=start_point_solutions[i].risetime
	 misf_shift=99999
	 if inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdsok': 
            line8,line9=text[i*9+7],text[i*9+8]
            sdepth,smom,strike,dip,rake=line8.split()
	    depth=str(int(round(float(sdepth))))
	    misfit=float(line9)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsds': 
            line4,line5=text[i*5+3],text[i*5+4]
            sdepth,smom,strike,dip,rake=line4.split()
	    depth=str(int(round(float(sdepth))))
            misfit=float(line5)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdst': 
            line4,line5=text[i*5+3],text[i*5+4]
            sdepth,smom,strike,dip,rake=line4.split()
	    depth=str(int(round(float(sdepth))))
            misfit=float(line5)    
#            line4,line6,line7=text[i*7+3],text[i*7+5],text[i*7+6]
#            sdepth,smom,strike,dip,rake=line4.split()
#            depth=str(int(round(float(sdepth))))
#            risetime=float(line6)
#            strise=str(risetime)
#            misfit=float(line7)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdst2x': 
#            line4,line6,line8,line9=text[i*9+3],text[i*9+5],text[i*9+7],text[i*9+8]
#            sdepth,smom,strike,dip,rake=line4.split()
#            depth=str(int(round(float(sdepth))))
#            strike,dip,rake=line6.split()
#            risetime=float(line8)
#            strise=str(risetime)
#            misfit=float(line9)    
            line4,line6,line7=text[i*7+3],text[i*7+5],text[i*7+6]
            sdepth,smom,strike,dip,rake=line4.split()
            depth=str(int(round(float(sdepth))))
            strike,dip,rake=line6.split()
            misfit=float(line7)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_msds': 
            line4,line5=text[i*5+3],text[i*5+4]
            smom,strike,dip,rake=line4.split()
            misfit=float(line5)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dm': 
            line2,line3=text[i*3+1],text[i*3+2]
            sdepth,smom=line2.split()
	    depth=str(int(round(float(sdepth))))
            misfit=float(line3)    
##            line4,line5=text[i*5+3],text[i*5+4]
##            sdepth,smom=line4.split()
##            depth=str(int(round(float(sdepth))))
##            misfit=float(line5)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmt': 
            line2,line3=text[i*3+1],text[i*3+2]
            sdepth,smom=line2.split()
	    depth=str(int(round(float(sdepth))))
            misfit=float(line3)    
##            line4,line5=text[i*5+3],text[i*5+4]
##            sdepth,smom=line4.split()
##	    depth=str(int(round(float(sdepth))))
##            misfit=float(line5)    
#           line4,line6,line7=text[i*7+3],text[i*7+5],text[i*7+6]
#           sdepth,smom=line4.split()
#	    depth=str(int(round(float(sdepth))))
#           risetime=float(line6)
#           strise=str(risetime)
#           misfit=float(line7)
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dsds': 
            line4,line5=text[i*5+3],text[i*5+4]
            sdepth,strike,dip,rake=line4.split()
            depth=str(int(round(float(sdepth))))
	    misfit=float(line5)    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_sds': 
            line2,line3=text[i*3+1],text[i*3+2]
            strike,dip,rake=line2.split()
	    misfit=float(line3)    
	    smom=str(start_point_solutions[i].smom)
	 else:
            strike=str(start_point_solutions[i].strike)
	    dip=str(start_point_solutions[i].dip)
	    rake=str(start_point_solutions[i].rake)
            if inv_param['INV_MODE_STEP'+inv_step]=='invert_m':
               line2,line3=text[i*3+1],text[i*3+2]	 
               smom=str(float(line2))
   	       misfit=float(line3)
            else:                                  #'grid'
               line1=text[i]
               misfit=float(line1)
	       smom=str(start_point_solutions[i].smom)        
            print i,depth,smom,strike,dip,rake,misfit
         omom,ostr,odip,orak=smom,float(strike),float(dip),float(rake)
	 smom,strike,dip,rake=checkStrDipRak(omom,ostr,odip,orak)
         rnor,rest,time=start_point_solutions[i].rnor,start_point_solutions[i].rest,start_point_solutions[i].time
      elif (inv_step == '2'):
	 strike=start_point_solutions[i].strike
	 dip=start_point_solutions[i].dip
	 rake=start_point_solutions[i].rake
         misf_shift=start_point_solutions[i].misf_shift   
         strise=start_point_solutions[i].risetime
         if inv_param['INV_MODE_STEP'+inv_step]=='invert_tnem': 
   	    depth=start_point_solutions[i].depth
	    line1,line2,line3,line4,line5,line6,line7=text[i*7],text[i*7+1],text[i*7+2],text[i*7+3],text[i*7+4],text[i*7+5],text[i*7+6]
	    time=float(line2)
	    rnor,rest=line4.split()
	    smom=str(float(line6))
            misfit=float(line7)
	 elif inv_param['INV_MODE_STEP'+inv_step]=='invert_tne': 
   	    depth=start_point_solutions[i].depth
	    line1,line2,line3,line4,line5=text[i*5],text[i*5+1],text[i*5+2],text[i*5+3],text[i*5+4]
	    time=float(line2)
	    rnor,rest=line4.split()
            misfit=float(line5)
            smom=str(start_point_solutions[i].smom)
         else:
   	    depth=start_point_solutions[i].depth
            rnor=str(start_point_solutions[i].rnor)
	    rest=str(start_point_solutions[i].rest)
	    time=str(start_point_solutions[i].time)
            if inv_param['INV_MODE_STEP'+inv_step]=='invert_m':
               line2,line3=text[i*3+1],text[i*3+2]	 
               smom=str(float(line2))
   	       misfit=float(line3)
            else:                                  #'grid'
	       lines_singlemisfits.append(text[i*2])
               line1=text[i*2+1]
               misfit=float(line1)
	       smom=str(start_point_solutions[i].smom)        	 
      smom,strike,dip,rake=checkStrDipRak(smom,strike,dip,rake)
      depthkm=float(depth)/1000.
      if (depthkm<float(inv_param['DEPTH_UPPERLIM'])) or (depthkm>float(inv_param['DEPTH_BOTTOMLIM'])):
         misfit=misfit+99999. 
      point_solutions.append(DCsource(inv_step,misfit,rnor,rest,time,depth,strike,dip,rake,smom,misf_shift,strise))


def analyseResultsMTsource(inv_step,inv_param,mt_solutions,n_mt_solutions,fminout,start_mt_solutions):
   print 'Analysing results inversion step '+inv_step+'...'
   n_start_solutions=n_mt_solutions
   i=0
   f = open (fminout,'r')
   text=[]
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer1.out)')
      else:
         if not re.search('ok',line):
            text.append(line) 
            i=i+1
   if (inv_step == '1'):	    
      n_mt_solutions = i/3
   elif (inv_step == '2'):
      n_mt_solutions = i
   f.flush()
   f.close()
   if (n_start_solutions!=n_mt_solutions):
      print n_start_solutions,n_mt_solutions
      sys.exit('ERROR-here: n start sol <> n MT point sol - inv_step'+inv_step)
   for i in range(n_mt_solutions):
      time=start_mt_solutions[i].time
      rnor,rest=start_mt_solutions[i].rnor,start_mt_solutions[i].rest
      depth=start_mt_solutions[i].depth
      strise=start_mt_solutions[i].risetime
      iso="0"
      dc="100"
      clvd="0"
      if (inv_step == '1'):
	 misf_shift=99999
         m11,m12,m13,m22,m23,m33=text[i*3+1].split()
	 misfit=float(text[i*3+2])
      elif (inv_step == '2'):
         misfit=99999
	 misf_shift=float(text[i])
         m11,m12,m13=start_mt_solutions[i].m11,start_mt_solutions[i].m12,start_mt_solutions[i].m13
	 m22,m23,m33=start_mt_solutions[i].m22,start_mt_solutions[i].m23,start_mt_solutions[i].m33
      mt_solutions.append(MTsource(inv_step,misfit,rnor,rest,time,depth,m11,m12,m13,m22,m23,m33,\
                                   iso,dc,clvd,misf_shift,strise))


def analyseResultsEikonalsource(inv_step,inv_param,eikonals,n_eikonals,fminout,start_eikonals,lines_singlemisfits):
   print 'Analysing results inversion step '+inv_step+'...'
   n_start_eikonals=n_eikonals
   i=0
   f = open (fminout,'r')
   text=[]
   for line in f:
      if re.search('nok',line):
         if re.search ('get_global_misfit: nok',line):
            print line
	    print 'continue anyway - large misfit given by default'
	 else:
            print line
	    sys.exit('ERROR: minimizer internal error (minimizer1.out)')
      else:
         if not re.search('ok',line):
            if not re.search('nucleation point is outside',line):
               text.append(line) 
            else:
	       defline='9.9\n'
	       text.append(defline)
	    i=i+1
   if (inv_step == '3'):	    
      print "lines",i
      if inv_param['INV_MODE_STEP'+inv_step]=='invert_rnv':
         n_eikonals = int(i/3)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_r':
         n_eikonals = int(i/3)
      elif inv_param['INV_MODE_STEP'+inv_step]=='invert_rt':
         n_eikonals = int(i/3)
      elif inv_param['INV_MODE_STEP'+inv_step]=='ccgrid':
         n_eikonals = int(i/3)
      else:                                    #'grid'
         n_eikonals = int(i/2)
      print "lines",i,n_eikonals,inv_step,inv_param['INV_MODE_STEP'+inv_step]
   f.flush()
   f.close()
   if (n_start_eikonals!=n_eikonals):
      print n_start_eikonals,n_eikonals
      sys.exit('ERROR 2: n start sol <> n point sol (minimizer.out)')
   for i in range(n_eikonals):
      if (inv_step == '3'):
         local_eikonal=start_eikonals[i]
	 local_eikonal.misf_shift=99999
         if inv_param['INV_MODE_STEP'+inv_step]=='invert_rnv': 
            radius,nuklx,nukly,relruptvel=text[i*3+1].split()
	    misfit=float(text[i*3+2])
            local_eikonal.radius=radius
	    local_eikonal.nuklx=nuklx
	    local_eikonal.nukly=nukly
	    local_eikonal.relruptvel=relruptvel
            local_eikonal.misfit=misfit
         if inv_param['INV_MODE_STEP'+inv_step]=='invert_r': 
            radius=float(text[i*3+1])
	    misfit=float(text[i*3+2])
            local_eikonal.radius=radius
            local_eikonal.misfit=misfit
         if inv_param['INV_MODE_STEP'+inv_step]=='invert_rt': 
            sradius,srisetime=text[i*3+1].split()
	    radius=float(sradius)
	    risetime=float(srisetime)
	    misfit=float(text[i*3+2])
            local_eikonal.radius=radius
            local_eikonal.misfit=misfit
	    local_eikonal.risetime=risetime
         elif inv_param['INV_MODE_STEP'+inv_step]=='ccgrid': 
            lines_singlemisfits.append(text[i*3+1])            
	    misfit=float(text[i*3+2])
            local_eikonal.misfit=misfit
	 else:                                  #'grid'
            lines_singlemisfits.append(text[i*2])
	    misfit=float(text[i*2+1])
            local_eikonal.misfit=misfit
	 print "EIKO-SOLUTION",i+1,local_eikonal.misfit,\
	                       local_eikonal.nuklx,local_eikonal.nukly
	 eikonals.append(local_eikonal)
	 iref=len(eikonals)-1
	 print "EIKO-SOLUTION",i+1,eikonals[iref].misfit,\
	                       eikonals[iref].nuklx,eikonals[iref].nukly


def calculateDCSynthetics(inv_step,inv_param,point_solutions,traces,apply_taper,freceivers,fdata):
   print 'Calculating synthetic seismograms...'
   slat,slon=inv_param['LATITUDE_NORTH'],inv_param['LONGITUDE_EAST']  
   stim0,snor0,sest0=point_solutions[0].time,point_solutions[0].rnor,point_solutions[0].rest
   depth0,smom0=point_solutions[0].depth,point_solutions[0].smom
   strike0,dip0,rake0=point_solutions[0].strike,point_solutions[0].dip,point_solutions[0].rake
   srise= inv_param['RISE_TIME_1']
#   srise= point_solutions[0].risetime
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-best')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-best')
   sseis=os.path.join(inv_param['INVERSION_DIR'],'dcsseis'+inv_step)
   dseis=os.path.join(inv_param['INVERSION_DIR'],'dcdseis'+inv_step)
   sseif=os.path.join(inv_param['INVERSION_DIR'],'dcsseif'+inv_step)
   dseif=os.path.join(inv_param['INVERSION_DIR'],'dcdseif'+inv_step)
   sseit=os.path.join(inv_param['INVERSION_DIR'],'dcsseit'+inv_step)
   dseit=os.path.join(inv_param['INVERSION_DIR'],'dcdseit'+inv_step)
   samsp=os.path.join(inv_param['INVERSION_DIR'],'dcsamsp'+inv_step)
   damsp=os.path.join(inv_param['INVERSION_DIR'],'dcdamsp'+inv_step)
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write(line_mf)
   localdepth=int(float(depth0)/1000)
   if apply_taper:
      for trace in traces:        
         taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
         taper_points=taper.split()
         for comp in trace.comp:
            ftaper=os.path.join(inv_param['INVERSION_DIR'],"taper-"+str(trace.num)+"-"+comp)
            ftap = open (ftaper,'w')
	    ftap.write("-100000 0\n")
            for ipt in range(int((len(taper_points))/2)):
	       icorr=ipt*2
	       ftap.write(str(taper_points[icorr])+" "+str(taper_points[icorr+1])+"\n")
	    ftap.write("100000 0\n")
	    ftap.flush()
            ftap.close()
   line = "set_source_params bilateral "+str(stim0)+" "+str(snor0)+" "+str(sest0)+" "+str(int(float(depth0)))+" "
   line = line+str(smom0)+" "+str(strike0)+" "+str(dip0)+" "+str(rake0)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+str(srise)+"\n"
   f.write(line)
   f.write("output_seismograms "+sseis+" table synthetics plain\n")
   f.write("output_seismograms "+dseis+" table references plain\n")
   f.write("output_seismograms "+sseif+" table synthetics filtered\n")
   f.write("output_seismograms "+dseif+" table references filtered\n")
   f.write("output_seismograms "+sseit+" table synthetics tapered\n")
   f.write("output_seismograms "+dseit+" table references tapered\n")
   f.write("output_seismogram_spectra "+samsp+" synthetics filtered\n")
   f.write("output_seismogram_spectra "+damsp+" references filtered\n")
   f.flush()
   f.close()
   callMinimizer(fmininp,fminout)


def calculateMTSynthetics(inv_step,inv_param,mt_solutions,traces,apply_taper,freceivers,fdata):
   print 'Calculating synthetic seismograms...'
   slat,slon=inv_param['LATITUDE_NORTH'],inv_param['LONGITUDE_EAST']  
   stim0,snor0,sest0=mt_solutions[0].time,mt_solutions[0].rnor,mt_solutions[0].rest
   m110,m120,m130=mt_solutions[0].m11,mt_solutions[0].m12,mt_solutions[0].m13
   m220,m230,m330=mt_solutions[0].m22,mt_solutions[0].m23,mt_solutions[0].m33
   depth0=mt_solutions[0].depth
   srise=mt_solutions[0].risetime 
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-best')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-best')
   sseis=os.path.join(inv_param['INVERSION_DIR'],'mtsseis'+inv_step)
   dseis=os.path.join(inv_param['INVERSION_DIR'],'mtdseis'+inv_step)
   sseif=os.path.join(inv_param['INVERSION_DIR'],'mtsseif'+inv_step)
   dseif=os.path.join(inv_param['INVERSION_DIR'],'mtdseif'+inv_step)
   sseit=os.path.join(inv_param['INVERSION_DIR'],'mtsseit'+inv_step)
   dseit=os.path.join(inv_param['INVERSION_DIR'],'mtdseit'+inv_step)
   samsp=os.path.join(inv_param['INVERSION_DIR'],'mtsamsp'+inv_step)
   damsp=os.path.join(inv_param['INVERSION_DIR'],'mtdamsp'+inv_step)
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write(line_mf)
   localdepth=int(float(depth0)/1000)
   if apply_taper:
      for trace in traces:        
         taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
         taper_points=taper.split()
         for comp in trace.comp:
            ftaper=os.path.join(inv_param['INVERSION_DIR'],"taper-"+str(trace.num)+"-"+comp)
            ftap = open (ftaper,'w')
	    ftap.write("-100000 0\n")
            for ipt in range(int((len(taper_points))/2)):
	       icorr=ipt*2
	       ftap.write(str(taper_points[icorr])+" "+str(taper_points[icorr+1])+"\n")
	    ftap.write("100000 0\n")
	    ftap.flush()
            ftap.close()
   line = "set_source_params moment_tensor "+str(stim0)+" "+str(snor0)+" "+str(sest0)+" "\
          +str(int(float(depth0)))+" "+str(m110)+" "+str(m120)+" "+str(m130)+" "\
	  +str(m220)+" "+str(m230)+" "+str(m330)+str(srise)+"\n"
   f.write(line)
   f.write("output_seismograms "+sseis+" table synthetics plain\n")
   f.write("output_seismograms "+dseis+" table references plain\n")
   f.write("output_seismograms "+sseif+" table synthetics filtered\n")
   f.write("output_seismograms "+dseif+" table references filtered\n")
   f.write("output_seismograms "+sseit+" table synthetics tapered\n")
   f.write("output_seismograms "+dseit+" table references tapered\n")
   f.write("output_seismogram_spectra "+samsp+" synthetics filtered\n")
   f.write("output_seismogram_spectra "+damsp+" references filtered\n")
   f.flush()
   f.close()
   callMinimizer(fmininp,fminout)


def calculateEikSynthetics(inv_step,inv_param,eikonals,traces,apply_taper,freceivers,fdata,mohodepth):
   print 'Calculating synthetic seismograms...'
   stype='eikonal'
   slat,slon=inv_param['LATITUDE_NORTH'],inv_param['LONGITUDE_EAST']  
   stim,snor,sest=str(eikonals[0].time),str(eikonals[0].rnor),str(eikonals[0].rest)
   sdep,smom=str(eikonals[0].depth),str(eikonals[0].smom)
   sstr,sdip,srak=str(eikonals[0].strike),str(eikonals[0].dip),str(eikonals[0].rake)
   sbx,sby,srad=str(eikonals[0].bordx),str(eikonals[0].bordy),str(eikonals[0].radius)
   snx,sny=str(eikonals[0].nuklx),str(eikonals[0].nukly)
   srrv,srise=str(eikonals[0].relruptvel),str(eikonals[0].risetime)
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-best')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-best')
   sseis=os.path.join(inv_param['INVERSION_DIR'],'sseis'+inv_step)
   dseis=os.path.join(inv_param['INVERSION_DIR'],'dseis'+inv_step)
   sseif=os.path.join(inv_param['INVERSION_DIR'],'sseif'+inv_step)
   dseif=os.path.join(inv_param['INVERSION_DIR'],'dseif'+inv_step)
   sseit=os.path.join(inv_param['INVERSION_DIR'],'sseit'+inv_step)
   dseit=os.path.join(inv_param['INVERSION_DIR'],'dseit'+inv_step)
   samsp=os.path.join(inv_param['INVERSION_DIR'],'samsp'+inv_step)
   damsp=os.path.join(inv_param['INVERSION_DIR'],'damsp'+inv_step)
   feikomodel=os.path.join(inv_param['INVERSION_DIR'],'best_eikonal')
   feikoptmodel=os.path.join(inv_param['INVERSION_DIR'],'best_eikonalpt')
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write(line_mf)
   localdepth=int(float(sdep)/1000)
   fdep=float(sdep)
   if (fdep>=mohodepth):
      line_depth_constraints="set_source_constraints 0 0 0 0 0 -1 0 0 95000 0 0 1\n"
      f.write(line_depth_constraints)
   if apply_taper:
      for trace in traces:        
         taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
         taper_points=taper.split()
         for comp in trace.comp:
            ftaper=os.path.join(inv_param['INVERSION_DIR'],"taper-"+str(trace.num)+"-"+comp)
            ftap = open (ftaper,'w')
	    ftap.write("-100000 0\n")
            for ipt in range(int((len(taper_points))/2)):
	       icorr=ipt*2
	       ftap.write(str(taper_points[icorr])+" "+str(taper_points[icorr+1])+"\n")
	    ftap.write("100000 0\n")
	    ftap.flush()
            ftap.close()
   line = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" "+smom+" "+sstr+" "\
          +sdip+" "+srak+" "+sbx+" "+sby+" "+srad+" "+snx+" "+sny+" "+srrv+" "+srise+"\n"
   f.write(line)
   f.write("output_seismograms "+sseis+" table synthetics plain\n")
   f.write("output_seismograms "+dseis+" table references plain\n")
   f.write("output_seismograms "+sseif+" table synthetics filtered\n")
   f.write("output_seismograms "+dseif+" table references filtered\n")
   f.write("output_seismograms "+sseit+" table synthetics tapered\n")
   f.write("output_seismograms "+dseit+" table references tapered\n")
   f.write("output_seismogram_spectra "+samsp+" synthetics filtered\n")
   f.write("output_seismogram_spectra "+damsp+" references filtered\n")
   f.write("output_source_model "+feikomodel+"\n")
   f.flush()
   f.close()
   callMinimizer(fmininp,fminout)


def getCrustalDepth(inv_param):
   lat,lon=inv_param['LATITUDE_NORTH'],inv_param['LONGITUDE_EAST']
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp-checkdepth')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out-checkdepth')
   f = open (fmininp,'w')
   f.write("set_source_location "+lat+" "+lon+" 0\n")
   f.write("get_source_crustal_thickness\n")
   f.flush()
   f.close()
   callMinimizer(fmininp,fminout)
   f = open (fminout,'r')
   text=[]
   i=0
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error ('+fminout+')')
      else:
         if not re.search('ok',line):
            text.append(line)
	    i=i+1 
   f.flush()
   f.close()
   if (i<>1):
      print i,'1'
      sys.exit('ERROR 3: n start sol <> n point sol ('+fminout+')')
   mohodepth=float(text[0])
   return mohodepth   


def prepMinimizerInputDCsource(inv_step,fmininp,fminout,inv_param,freceivers,\
                                  fdata,apply_taper,irun,start_point_solutions):
   num_processors=int(float(inv_param['NUM_PROCESSORS']))
   num_startsolutions=len(start_point_solutions)
   nsol_x_proc=[]
   for iproc in range(num_processors):
      num_allocatedsolutions=int(num_startsolutions/num_processors)
      nsol_x_proc.append(num_allocatedsolutions)
      num_startsolutions=num_startsolutions-num_allocatedsolutions
   if (num_startsolutions<>0):
      sys.exit('ERROR: something wrong with splitting solutions between processors, '\
               +str(num_startsolutions))
   stype='bilateral'
   istartsol=0
   for iproc in range(num_processors):
      if num_processors==1:
         f = open (fmininp,'w')   
      else:
         f = open (fmininp+"-proc"+str(iproc+1),'w')
      f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
      f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
      f.write("set_receivers "+freceivers+"\n")
      f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
      f.write("set_source_constraints 0 0 0 0 0 -1\n")
      f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
      f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#      f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
      line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
      line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "\
              +inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
      line_mf_risetime="set_misfit_filter "+inv_param['BP_F1_STEP3']+" 0 "+inv_param['BP_F2_STEP3']+" 1 "\
              +inv_param['BP_F3_STEP3']+" 1 "+inv_param['BP_F4_STEP3']+" 0\n"
      f.write(line_mm)
      f.write(line_mf)
      stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
      ccshift1,ccshift2=inv_param['CC_SHIFT1'],inv_param['CC_SHIFT2']
      i=0
      prevdepth = '-1'
      for isolxproc in range(nsol_x_proc[iproc]):   
         startsol=start_point_solutions[istartsol]
	 istartsol=istartsol+1
	 sdep,smom=str(startsol.depth),str(startsol.smom)
         stim,snor,sest=str(startsol.time),str(startsol.rnor),str(startsol.rest)
         sstr,sdip,srak=str(startsol.strike),str(startsol.dip),str(startsol.rake)
         strise=str(startsol.risetime)
         if apply_taper:
            if (prevdepth!=sdep):
               for trace in traces:
                  if inv_step == '1':
   	             depth=float(sdep)
	             localdepth=int(float(sdep)/1000)
	             taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
                     f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
                     prevdepth=sdep
	          else:
                     if (trace.dist <= float(inv_param['EPIC_DIST_MAXLOC'])):
      	                depth=float(sdep)
	                localdepth=int(float(sdep)/1000)
	                taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
                        f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
                        prevdepth=sdep	          	        
         line = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" "
         line = line+smom+" "+sstr+" "+sdip+" "+srak+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
         f.write(line)
         if (inv_step == '1'):
            if inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdsok':
               f.write(line_mask(stype,['moment']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
               f.write(line_mask(stype,['moment','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
               f.write(line_mask(stype,['depth','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
               f.write(line_mask(stype,['moment','depth','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsds':
               f.write(line_mask(stype,['moment']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
               f.write(line_mask(stype,['moment','depth','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdst':
#               f.write(line_mask(stype,['moment','strike','dip','slip-rake']))
               f.write(line_mask(stype,['moment','depth']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
               f.write(line_mask(stype,['moment','depth','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmsdst2x':
               f.write(line_mask(stype,['moment','depth']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
               f.write(line_mask(stype,['moment','depth','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
#               f.write(line_mf_risetime)
               f.write(line_mask(stype,['strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
#               f.write(line_mf_risetime)
#               f.write(line_mask(stype,['rise-time']))
#               f.write("minimize_lm\n")
#               f.write("get_source_subparams\n")	    	    
#               f.write(line_mf)
	    elif inv_param['INV_MODE_STEP'+inv_step]=='invert_msds':
               f.write(line_mask(stype,['moment']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
               f.write(line_mask(stype,['moment','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dm':
               f.write(line_mask(stype,['moment','depth']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dmt':
               f.write(line_mask(stype,['moment','depth']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_dsds':
               f.write(line_mask(stype,['depth']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
               f.write(line_mask(stype,['depth','strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_sds':
               f.write(line_mask(stype,['strike','dip','slip-rake']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_m':
               f.write(line_mask(stype,['moment']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            else:                                    #'grid'
	       print "grid ",i,sdep,smom,sstr,sdip,srak
            f.write("get_global_misfit\n")
            i=i+1
         elif (inv_step == '2'):
	    if inv_param['INV_MODE_STEP'+inv_step]=='invert_tnem':
  	       f.write(line_mask(stype,['time']))
	       f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
	       f.write(line_mask(stype,['north-shift','east-shift']))
	       f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
	       f.write(line_mask(stype,['moment']))
	       f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
	    if inv_param['INV_MODE_STEP'+inv_step]=='invert_tne':
  	       f.write(line_mask(stype,['time']))
	       f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
	       f.write(line_mask(stype,['north-shift','east-shift']))
	       f.write("minimize_lm\n")
	       f.write("get_source_subparams\n")
            elif inv_param['INV_MODE_STEP'+inv_step]=='invert_m':
               f.write(line_mask(stype,['moment']))
               f.write("minimize_lm\n")
               f.write("get_source_subparams\n")	    
            else:                                    #'grid'
	       print "grid ",i,stim,snor,sest,sdep,smom
               f.write("get_misfits\n")
            f.write("get_global_misfit\n")
	    i=i+1
      f.flush()
      f.close()


def prepMinimizerInputMTsource(inv_step,fmininp,fminout,inv_param,freceivers,\
                                  fdata,apply_taper,irun,start_mt_solutions):
   stype='moment_tensor'
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "\
           +inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)
   stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
   ccshift1,ccshift2=inv_param['CC_SHIFT1'],inv_param['CC_SHIFT2']
   i=0
   prevdepth='-1'
   print "length of starting solutions ",len(start_mt_solutions)
   for startsol in start_mt_solutions:   
      print "start_solution ",str(startsol.m11),str(startsol.m12),str(startsol.m13),\
                              str(startsol.m22),str(startsol.m23),str(startsol.m33)
      sdep=str(startsol.depth)
      stim,snor,sest=str(startsol.time),str(startsol.rnor),str(startsol.rest)
      sm11,sm12,sm13=str(startsol.m11),str(startsol.m12),str(startsol.m13)
      sm22,sm23,sm33=str(startsol.m22),str(startsol.m23),str(startsol.m33)
      strise=str(startsol.risetime)
      if apply_taper:
         if (prevdepth!=sdep):
            for trace in traces:
               depth=float(sdep)
	       localdepth=int(float(sdep)/1000)
	       taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
	       f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
               prevdepth=sdep      
      line = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" "
      line = line+" "+sm11+" "+sm12+" "+sm13+" "+sm22+" "+sm23+" "+sm33+" "+strise+"\n"
      f.write(line)
      if (inv_step == '1'):
         f.write(line_mask(stype,['m11','m12','m13','m22','m23','m33']))
         f.write("minimize_lm\n")
         f.write("get_source_subparams\n")	    
         f.write("get_global_misfit\n")
         i=i+1
      elif (inv_step == '2'):
         f.write("get_global_misfit\n")
	 i=i+1
   f.flush()
   f.close()


def prepMinimizerInputEikonalsource(inv_step,fmininp,fminout,inv_param,freceivers,\
                                  fdata,apply_taper,irun,start_eikonals,mohodepth):
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "\
           +inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)
   stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
   ccshift1,ccshift2=inv_param['KIN_CC_SHIFT1'],inv_param['KIN_CC_SHIFT2']
   i=0
   prevdepth = '-1'
   for startsol in start_eikonals:
      stim,snor,sest=str(startsol.time),str(startsol.rnor),str(startsol.rest)
      sdep,smom=str(startsol.depth),str(startsol.smom)
      sstr,sdip,srak=str(startsol.strike),str(startsol.dip),str(startsol.rake)
      srad,snukx,snuky=str(startsol.radius),str(startsol.nuklx),str(startsol.nukly)
      srrv,srise=str(startsol.relruptvel),str(startsol.risetime)
      if (prevdepth!=sdep):      
         fdep=float(sdep)
	 if (fdep>=mohodepth):
	    line_depth_constraints="set_source_constraints 0 0 0 0 0 -1 0 0 95000 0 0 1\n"
	    f.write(line_depth_constraints)
	 else:
	    bottomdep=2*fdep
	    minbottomdep=1000.*float(inv_param['MIN_KIN_BOTTOM'])
	    if bottomdep<minbottomdep:
	       bottomdep=minbottomdep
	    if bottomdep<mohodepth:
	       line_depth_constraints="set_source_constraints 0 0 0 0 0 -1 0 0 "+str(bottomdep)+" 0 0 1\n"
	       f.write(line_depth_constraints)   
         if apply_taper:
	    itrac=0
            for trace in traces:
               if (trace.dist <= float(inv_param['EPIC_DIST_MAXKIN'])):
      	          depth=float(sdep)
	          localdepth=int(float(sdep)/1000)
	          taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
#                  if (inv_param['SW_GOODSTATIONS'].upper()=='TRUE'):
#		     weight=qualityweights[itrac]
#		     loctaper=taper.split()
#		     newtaper=""
#		     for itap in range(int(len(loctaper)/2)):
#		        loctaper[itap*2+1]=str(float(loctaper[itap*2+1])*weight)
#                     for itap in range(len(loctaper)):
#		        newtaper=newtaper+" "+loctaper[itap]
#		     f.write("set_misfit_taper "+str(trace.num)+" "+newtaper+"\n")
#		  else:
                  f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
		  itrac=itrac+1
		  prevdepth=sdep 	            
      line = "set_source_params eikonal "+stim+" "+snor+" "+sest+" "+sdep+" "+smom+" "
      line = line+sstr+" "+sdip+" "+srak+" 0 0 "+srad+" "+snukx+" "+snuky+" "+srrv+" "+srise+"\n"
      f.write(line)
      if (inv_step == '3'):
         if inv_param['INV_MODE_STEP'+inv_step]=='invert_rnv':
#            f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
            f.write(line_mask('eikonal',['radius','nuklx','nukly','relruptvel']))
            f.write("minimize_lm\n")
            f.write("get_source_subparams\n")	    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_r':
#            f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
            f.write(line_mask('eikonal',['radius']))
            f.write("minimize_lm\n")
            f.write("get_source_subparams\n")	    
         elif inv_param['INV_MODE_STEP'+inv_step]=='invert_rt':
#            f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
            f.write(line_mask('eikonal',['radius','rise-time']))
            f.write("minimize_lm\n")
            f.write("get_source_subparams\n")	    
         elif inv_param['INV_MODE_STEP'+inv_step]=='ccgrid':
	    print "grid ",i,sstr,srad,snukx,snuky,srrv         
#010610	    f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
            f.write("get_misfits \n")   
	 else:                                    #'grid'
	    print "grid ",i,sstr,srad,snukx,snuky,srrv         
            f.write("get_misfits \n")   
         f.write("get_global_misfit\n")
         i=i+1
      else:
         sys.exit('ERROR: wrong step number: '+inv_step)
   f.flush()
   f.close()


def switchPointSolutions(point_solutions,i,j):
   point_sol_buffer=[]
   point_sol_buffer.append(point_solutions[i])
   point_solutions[i] = point_solutions[j]
   point_solutions[j] = point_sol_buffer[0]


def compareBestDCSourceInTime(inv_step,point_solutions,inv_param,freceivers,fdata):
   mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-compare')
   minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-compare')
   f = open (mininp,'w')
   for startsol in point_solutions:   
      f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
      f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
      f.write("set_receivers "+freceivers+"\n")
      f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
      f.write("set_source_constraints 0 0 0 0 0 -1\n")
      f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
      f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#      f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
      line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
      line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
      line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
      f.write(line_mm)
      f.write(line_mf)
      stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
      ccshift1,ccshift2=inv_param['CC_SHIFT1'],inv_param['CC_SHIFT2']
      sdep,smom=str(startsol.depth),str(startsol.smom)
      stim,snor,sest=str(startsol.time),str(startsol.rnor),str(startsol.rest)
      sstr,sdip,srak=str(startsol.strike),str(startsol.dip),str(startsol.rake)
      strise=str(startsol.risetime)
      if apply_taper:
         for trace in traces:
	    if (inv_step == '2'):
	       if (trace.dist <= float(inv_param['EPIC_DIST_MAXLOC'])):
	          depth=float(sdep)
                  localdepth=int(float(sdep)/1000)
	          taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
                  f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
            else:
	       depth=float(sdep)
               localdepth=int(float(sdep)/1000)
	       taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
               f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
      line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+sdep+" "
      line = line+smom+" "+sstr+" "+sdip+" "+srak+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
      f.write(line)
      f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
      f.write("get_global_misfit\n")
   f.flush()
   f.close()
   callMinimizer(mininp,minout)
   f = open (minout,'r')
   text=[]
   i=0
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error ('+minout+')')
      else:
         if not re.search('ok',line):
            text.append(line)
	    i=i+1 
   if (i<>4):
      print i,'2'
      sys.exit('ERROR 4: n start sol <> n point sol ('+minout+')')
   for isol in range(2):
      point_solutions[isol].misfit=99999.  
      point_solutions[isol].misf_shift=float(text[(isol*2)+1])
   point_solutions.sort(key=operator.attrgetter('misf_shift'))


def calcDuration(inv_step,inv_param,bests,apply_taper,fdata,freceivers):
   checkedrisetimes=[]
   mw = m0tomw(float(inv_param['SCALING_FACTOR'])*float(bests[0].smom))
   coeff_appdur=0.5
   if mw<3.0:
      coeff_appdur=0.01
#   if mw>7.0:
   if mw>8.0:
      coeff_appdur=1.0
   if (inv_param['SW_APPDURATION'].upper()=="TRUE"):
      for i in range(40):
         j=coeff_appdur*(i+1)
         checkedrisetimes.append(str(j))
   else:
      checkedrisetimes.append(str(bests[0].risetime))
   mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-duration')
   minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-duration')
   f = open (mininp,'w')
   stype='bilateral'
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf_risetime="set_misfit_filter "+inv_param['BP_F1_STEP3']+" 0 "+inv_param['BP_F2_STEP3']+" 1 "\
           +inv_param['BP_F3_STEP3']+" 1 "+inv_param['BP_F4_STEP3']+" 0\n"
   f.write(line_mm)
   f.write(line_mf_risetime)
   stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
   ccshift1,ccshift2=inv_param['CC_SHIFT1'],inv_param['CC_SHIFT2']
   sdep,smom=str(bests[0].depth),str(bests[0].smom)
   stim,snor,sest=str(bests[0].time),str(bests[0].rnor),str(bests[0].rest)
   sstr,sdip,srak=str(bests[0].strike),str(bests[0].dip),str(bests[0].rake)
   strise=str(bests[0].risetime)
# s.c. added few lines for better retrieval of duration, using proper starting value   
   bestmw=float(m0tomw(float(inv_param['SCALING_FACTOR'])*float(bests[0].smom)))
   if (bestmw>6):
      strise="5"
   if (bestmw>6.5):
      strise="10"
# til here (temporary fixed to 5, see below)   
   if apply_taper:
      for trace in traces:
         depth=float(sdep)
         localdepth=int(float(sdep)/1000)
	 taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   for chrise in checkedrisetimes:
      linest = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" "
      linest = linest+smom+" "+sstr+" "+sdip+" "+srak+" 0 0 0 0 "+inv_param['RADIUS0']+" "+chrise+"\n"
      f.write(linest)
      f.write("get_global_misfit\n")	    	    
   latlon=[]
   if (inv_param['SW_APPDURATION'].upper()=="TRUE"):
      f1 = open (freceivers,'r')
      iline=0
      for line in f1:
         spline=line.split()
         ll=(spline[0],spline[1])
         for trace in traces:
            if trace.lat==spline[0] and trace.lon==spline[1]: 
	       lat=trace.lat
	       lon=trace.lon
	       stat=trace.stat
	       azi=trace.azi
         llong=(stat,lat,lon,azi)
         iline=iline+1
         if iline==1 and len(spline)>2:
  	    latlon.append(llong)
         else:
            if llong not in latlon and len(spline)>2:
               latlon.append(llong) 
      f1.flush()
      f1.close()
      nreceivers=len(latlon)
      for irec in range(len(latlon)):
         locfreceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.dur.'+str(irec+1))
         f.write("set_receivers "+locfreceivers+"\n")
         f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
         for chrise in checkedrisetimes:
            linest = "set_source_params "+stype+" "+stim+" "+snor+" "+sest+" "+sdep+" "
            linest = linest+smom+" "+sstr+" "+sdip+" "+srak+" 0 0 0 0 "+inv_param['RADIUS0']+" "+chrise+"\n"
            f.write(linest)
            f.write("get_global_misfit\n")	    	    
   f.flush()
   f.close()
   callMinimizer(mininp,minout)
   f = open (minout,'r')
   text=[]
   i=0
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error ('+minout+')')
      else:
         if not re.search('ok',line):
            text.append(line)
	    i=i+1 
   f.flush()
   f.close()
   if (inv_param['SW_APPDURATION'].upper()=="TRUE"):
      iexpected=(1+len(latlon))*len(checkedrisetimes)
   else:
      iexpected=len(checkedrisetimes)
   if (i<>iexpected):
      print i,iexpected
      sys.exit('ERROR: wrong number of solutions ('+minout+')')
   risetimes=[]
   nrisetimes=len(checkedrisetimes)
   for iris in range(nrisetimes):
      locrisetime=(checkedrisetimes[iris],text[iris])
      risetimes.append(locrisetime)      
   risetimes.sort(key=operator.itemgetter(1))
   besttuple=risetimes[0]
   risetime=besttuple[0]
   
   if (inv_param['SW_APPDURATION'].upper()=="TRUE"):
      nreceivers=len(latlon)
      bestrisetimes=[]
      for irec in range(nreceivers):
         risetimes=[]
         for iris in range(nrisetimes):
            j=((irec+1)*nrisetimes)+iris
            locrisetime=(checkedrisetimes[iris],text[j])
            risetimes.append(locrisetime)      
         risetimes.sort(key=operator.itemgetter(1))      
         besttuple=risetimes[0]
         bestrisetimes.append(besttuple[0])
      fappdur1=os.path.join(inv_param['INVERSION_DIR'],'apparentdurations.xyt')
      fappdur2=os.path.join(inv_param['INVERSION_DIR'],'apparentdurations.loc')
      fappdur3=os.path.join(inv_param['INVERSION_DIR'],'apparentdurations.dat')
      fcurve1=os.path.join(inv_param['INVERSION_DIR'],'apparentshape1.dat')
      fcurve2=os.path.join(inv_param['INVERSION_DIR'],'apparentshape2.dat')
      f1 = open (fappdur1,'w')
      f2 = open (fappdur2,'w')
      f3 = open (fappdur3,'w')
      fc1 = open (fcurve1,'w')
      fc2 = open (fcurve2,'w')
      irec=0
      risetimesonly=[]
      x1,x2,x3,x4,x5,x6,x7,x8,x9,x10=[],[],[],[],[],[],[],[],[],[]
      y1,y2,y3,y4,y5,y6,y7,y8,y9,y10=[],[],[],[],[],[],[],[],[],[]
      a1,a2,a3,a4,a5,a6,a7,a8,a9,a10=[],[],[],[],[],[],[],[],[],[]
      for ll in latlon:
         f1.write(str(ll[0])+" "+str(ll[3])+" "+str(bestrisetimes[irec])+"\n")
         f2.write(str(ll[2])+" "+str(ll[1])+" "+str(bestrisetimes[irec])+"\n")
         risetimesonly.append(float(bestrisetimes[irec]))
	 y1.append(float(bestrisetimes[irec]))
	 y2.append(float(bestrisetimes[irec]))
	 y3.append(float(bestrisetimes[irec]))
	 y4.append(float(bestrisetimes[irec]))
	 y5.append(float(bestrisetimes[irec]))
	 y6.append(float(bestrisetimes[irec]))
	 y7.append(float(bestrisetimes[irec]))
	 y8.append(float(bestrisetimes[irec]))
	 y9.append(float(bestrisetimes[irec]))
	 y10.append(float(bestrisetimes[irec]))
         x1.append(-math.cos((math.pi/180)*(float(ll[3])-float(bests[0].strike))))
         x2.append(-math.cos((math.pi/180)*(float(ll[3])-float(bests[1].strike))))
         x3.append(-math.cos((math.pi/180)*(float(ll[3])-(float(bests[0].strike)+90))))
         x4.append(-math.cos((math.pi/180)*(float(ll[3])-(float(bests[1].strike)+90))))
#         x5.append(2*math.cos((math.pi/180)*(float(ll[3])-float(bests[0].strike))))
#         x6.append(2*math.cos((math.pi/180)*(float(ll[3])-float(bests[1].strike))))
         x5.append(abs(math.cos((math.pi/180)*(float(ll[3])-float(bests[0].strike)))))
         x6.append(abs(math.cos((math.pi/180)*(float(ll[3])-float(bests[1].strike)))))
         x7.append(-math.cos((math.pi/180)*(float(ll[3])-(float(bests[0].strike)+45))))
         x8.append(-math.cos((math.pi/180)*(float(ll[3])-(float(bests[1].strike)+45))))
         x9.append(-math.cos((math.pi/180)*(float(ll[3])-(float(bests[0].strike)+135))))
         x10.append(-math.cos((math.pi/180)*(float(ll[3])-(float(bests[1].strike)+135))))
         a1=numpy.vstack([x1,numpy.ones(len(x1))]).T
         a2=numpy.vstack([x2,numpy.ones(len(x2))]).T
         a3=numpy.vstack([x3,numpy.ones(len(x3))]).T
         a4=numpy.vstack([x4,numpy.ones(len(x4))]).T
         a5=numpy.vstack([x5,numpy.ones(len(x5))]).T
         a6=numpy.vstack([x6,numpy.ones(len(x6))]).T
         a7=numpy.vstack([x7,numpy.ones(len(x7))]).T
         a8=numpy.vstack([x8,numpy.ones(len(x8))]).T
         a9=numpy.vstack([x9,numpy.ones(len(x9))]).T
         a10=numpy.vstack([x10,numpy.ones(len(x10))]).T
	 irec=irec+1
      m1,q1=numpy.linalg.lstsq(a1,y1)[0]
      m2,q2=numpy.linalg.lstsq(a2,y2)[0]
      m3,q3=numpy.linalg.lstsq(a3,y3)[0]
      m4,q4=numpy.linalg.lstsq(a4,y4)[0]
      m5,q5=numpy.linalg.lstsq(a5,y5)[0]
      if m5<0:
         m5=-m5
	 q5=q5-m5
      m6,q6=numpy.linalg.lstsq(a6,y6)[0]
      if m6<0:
         m6=-m6
	 q6=q5-m6
      m7,q7=numpy.linalg.lstsq(a7,y7)[0]
      m8,q8=numpy.linalg.lstsq(a8,y8)[0]
      m9,q9=numpy.linalg.lstsq(a9,y9)[0]
      m10,q10=numpy.linalg.lstsq(a10,y10)[0]
      print "mq1",m1,q1	 
      print "mq2",m2,q2	 
      print "mq3",m3,q3	 
      print "mq4",m4,q4	 
      print "mq5",m5,q5 
      print "mq6",m6,q6	 
      print "mq3",m7,q7	 
      print "mq4",m8,q8	 
      print "mq5",m9,q9 
      print "mq6",m10,q10	 
      average_apparentrisetime=mean(risetimesonly)
      stdev_apparentrisetime=std(risetimesonly)
      min_apparentrisetime,max_apparentrisetime=confidenceInterval(risetimesonly,inv_param)
      if min_apparentrisetime<0.5:
         min_apparentrisetime=0.5
      misfav=0
      misfx1=0
      misfx2=0
      misfx3=0
      misfx4=0
      misfx5=0
      misfx6=0
      misfx7=0
      misfx8=0
      misfx9=0
      misfx10=0
      irec=0
      for ll in latlon:
         appdur=float(bestrisetimes[irec])
         anglegra=float(ll[3])
	 anglerad1=float(anglegra-float(bests[0].strike))*math.pi/180.
         anglerad2=float(anglegra-float(bests[1].strike))*math.pi/180.
	 anglerad3=float(anglegra-(float(bests[0].strike)+90))*math.pi/180.
         anglerad4=float(anglegra-(float(bests[1].strike)+90))*math.pi/180.
         anglerad5=float(anglegra-float(bests[0].strike))*math.pi/180.
         anglerad6=float(anglegra-float(bests[1].strike))*math.pi/180.
	 anglerad7=float(anglegra-(float(bests[0].strike)+45))*math.pi/180.
         anglerad8=float(anglegra-(float(bests[1].strike)+45))*math.pi/180.
	 anglerad9=float(anglegra-(float(bests[0].strike)+135))*math.pi/180.
         anglerad10=float(anglegra-(float(bests[1].strike)+135))*math.pi/180.
	 misfav=misfav+(appdur-average_apparentrisetime)**2
         misfx1=misfx1+(appdur-(m1*(-math.cos(anglerad1))+q1))**2
         misfx2=misfx2+(appdur-(m2*(-math.cos(anglerad2))+q2))**2
         misfx3=misfx3+(appdur-(m3*(-math.cos(anglerad3))+q3))**2
         misfx4=misfx4+(appdur-(m4*(-math.cos(anglerad4))+q4))**2
#         misfx5=misfx5+(appdur-(m5*(math.cos(2*anglerad5))+q5))**2
#         misfx6=misfx6+(appdur-(m6*(math.cos(2*anglerad6))+q6))**2
         misfx5=misfx5+(appdur-(m5*(abs(math.cos(anglerad5)))+q5))**2
         misfx6=misfx6+(appdur-(m6*(abs(math.cos(anglerad6)))+q6))**2
         misfx7=misfx7+(appdur-(m7*(-math.cos(anglerad7))+q7))**2
         misfx8=misfx8+(appdur-(m8*(-math.cos(anglerad8))+q8))**2
         misfx9=misfx9+(appdur-(m9*(-math.cos(anglerad9))+q9))**2
         misfx10=misfx10+(appdur-(m10*(-math.cos(anglerad10))+q10))**2
	 print "CHECK  ",-math.cos(anglerad1),-math.cos(anglerad2)
	 print "CHECK-AVERAGE",appdur,average_apparentrisetime,anglegra,misfav
	 print "CHECK-STRIKE1",appdur,m1,q1,(m1*(-math.cos(anglerad1))+q1),anglegra,misfx1
	 print "CHECK-STRIKE2",appdur,m2,q2,(m2*(-math.cos(anglerad2))+q2),anglegra,misfx2
	 print "CHECK-DIP1   ",appdur,m3,q3,(m3*(-math.cos(anglerad3))+q3),anglegra,misfx3
	 print "CHECK-DIP2   ",appdur,m4,q4,(m4*(-math.cos(anglerad4))+q4),anglegra,misfx4
#	 print "CHECK-BILSTR1   ",appdur,m5,q5,(m5*(math.cos(2*anglerad5))+q5),anglegra,misfx5
#	 print "CHECK-BILSTR2   ",appdur,m6,q6,(m6*(math.cos(2*anglerad6))+q6),anglegra,misfx6
	 print "CHECK-BILSTR1   ",appdur,m5,q5,(m5*abs(math.cos(anglerad5))+q5),anglegra,misfx5
	 print "CHECK-BILSTR2   ",appdur,m6,q6,(m6*abs(math.cos(anglerad6))+q6),anglegra,misfx6
	 irec=irec+1
#      misfx=min(misfx1,misfx2,misfx3,misfx4,misfx5,misfx6,misfx7,misfx8,misfx9,misfx10)
      if (bests[0].dip<30) and (bests[1].dip<30):
         misfx=min(misfx1,misfx2,misfx3,misfx4,misfx5,misfx6,misfx7,misfx8,misfx9,misfx10)
      elif (bests[0].dip<30) and (bests[1].dip>=30):
         misfx=min(misfx1,misfx2,misfx3,misfx5,misfx6,misfx7,misfx9)
      elif (bests[0].dip>=30) and (bests[1].dip<30):
         misfx=min(misfx1,misfx2,misfx4,misfx5,misfx6,misfx8,misfx10)
      else:
         misfx=min(misfx1,misfx2,misfx5,misfx6)      
      if misfx==misfx1:
         ftest=(misfav-misfx1)/(misfx1/(len(ll)-2))	 
         mm=m1
	 qq=q1
	 print "MISFIT 1 CHOSEN",ftest
      elif misfx==misfx2:
         ftest=(misfav-misfx2)/(misfx2/(len(ll)-2))	 
         mm=m2
	 qq=q2
	 print "MISFIT 2 CHOSEN",ftest
      elif misfx==misfx3:
         ftest=(misfav-misfx3)/(misfx3/(len(ll)-2))	 
         mm=m3
	 qq=q3
	 print "MISFIT 3 CHOSEN",ftest
      elif misfx==misfx4:
         ftest=(misfav-misfx4)/(misfx4/(len(ll)-2))	 
         mm=m4
	 qq=q4
	 print "MISFIT 4 CHOSEN",ftest
      elif misfx==misfx5:
         ftest=(misfav-misfx5)/(misfx5/(len(ll)-2))	 
         mm=m5
	 qq=q5
	 print "MISFIT 5 CHOSEN",ftest
      elif misfx==misfx6:
         ftest=(misfav-misfx6)/(misfx6/(len(ll)-2))	 
         mm=m6
	 qq=q6
	 print "MISFIT 6 CHOSEN",ftest
      elif misfx==misfx7:
         ftest=(misfav-misfx7)/(misfx7/(len(ll)-2))	 
         mm=m7
	 qq=q7
	 print "MISFIT 7 CHOSEN",ftest
      elif misfx==misfx8:
         ftest=(misfav-misfx8)/(misfx8/(len(ll)-2))	 
         mm=m8
	 qq=q8
	 print "MISFIT 8 CHOSEN",ftest
      elif misfx==misfx9:
         ftest=(misfav-misfx9)/(misfx9/(len(ll)-2))	 
         mm=m9
	 qq=q9
	 print "MISFIT 9 CHOSEN",ftest
      else:
         ftest=(misfav-misfx10)/(misfx10/(len(ll)-2))	 
         mm=m10
	 qq=q10
	 print "MISFIT 10 CHOSEN",ftest
#      if ftest<=0.05:
#         mm,qq=0.,average_apparentrisetime
      f3.write("AVERAGE "+str(average_apparentrisetime)+"\n")   
      f3.write("ST.DEV. "+str(stdev_apparentrisetime)+"\n")   
      f3.write("CONFINT "+str(min_apparentrisetime)+" "+str(max_apparentrisetime)+"\n")   
      f3.write("MINMAX1 "+str(m1)+" "+str(q1)+"\n")
      f3.write("MINMAX2 "+str(m2)+" "+str(q2)+"\n")
      f3.write("MINMAX3 "+str(m3)+" "+str(q3)+"\n")
      f3.write("MINMAX4 "+str(m4)+" "+str(q4)+"\n")
      f3.write("MINMAX5 "+str(m5)+" "+str(q5)+"\n")
      f3.write("MINMAX6 "+str(m6)+" "+str(q6)+"\n")
      f3.write("MINMAX7 "+str(m7)+" "+str(q7)+"\n")
      f3.write("MINMAX8 "+str(m8)+" "+str(q8)+"\n")
      f3.write("MINMAX9 "+str(m9)+" "+str(q9)+"\n")
      f3.write("MINMAX10"+str(m10)+" "+str(q10)+"\n")
      f3.write("MISF1   "+str(misfx1)+"\n")
      f3.write("MISF2   "+str(misfx2)+"\n")
      f3.write("MISF3   "+str(misfx3)+"\n")
      f3.write("MISF4   "+str(misfx4)+"\n")
      f3.write("MISF5   "+str(misfx5)+"\n")
      f3.write("MISF6   "+str(misfx6)+"\n")
      f3.write("MISF7   "+str(misfx7)+"\n")
      f3.write("MISF8   "+str(misfx8)+"\n")
      f3.write("MISF9   "+str(misfx9)+"\n")
      f3.write("MISF10  "+str(misfx10)+"\n")
      f3.write("MISFA   "+str(misfav)+"\n")
      f3.write("F-TEST  "+str(ftest)+"\n")
      for ag in range(361):
         anglegra=ag-180
	 if misfx==misfx1:
	    anglerad=float(anglegra-float(bests[0].strike))*math.pi/180.
	    ycurve1=m1*(-math.cos(anglerad))+q1
	 elif misfx==misfx2:
	    anglerad=float(anglegra-float(bests[1].strike))*math.pi/180.
	    ycurve1=m2*(-math.cos(anglerad))+q2
	 elif misfx==misfx3:
	    anglerad=float(anglegra-(float(bests[0].strike)+90))*math.pi/180.
	    ycurve1=m3*(-math.cos(anglerad))+q3
         elif misfx==misfx4:
	    anglerad=float(anglegra-(float(bests[1].strike)+90))*math.pi/180.
	    ycurve1=m4*(-math.cos(anglerad))+q4
         elif misfx==misfx5:
	    anglerad=float(anglegra-float(bests[0].strike))*math.pi/180.
#	    ycurve1=m5*(math.cos(2*anglerad))+q5
	    ycurve1=m5*abs(math.cos(anglerad))+q5
         elif misfx==misfx6:
	    anglerad=float(anglegra-float(bests[1].strike))*math.pi/180.
#	    ycurve1=m6*(math.cos(2*anglerad))+q6	    
	    ycurve1=m6*abs(math.cos(anglerad))+q6	    
	 elif misfx==misfx7:
	    anglerad=float(anglegra-(float(bests[0].strike)+45))*math.pi/180.
	    ycurve1=m7*(-math.cos(anglerad))+q7
         elif misfx==misfx8:
	    anglerad=float(anglegra-(float(bests[1].strike)+45))*math.pi/180.
	    ycurve1=m8*(-math.cos(anglerad))+q8
	 elif misfx==misfx9:
	    anglerad=float(anglegra-(float(bests[0].strike)+135))*math.pi/180.
	    ycurve1=m9*(-math.cos(anglerad))+q9
         else:
	    anglerad=float(anglegra-(float(bests[1].strike)+135))*math.pi/180.
	    ycurve1=m10*(-math.cos(anglerad))+q10
	 ycurve2=average_apparentrisetime
	 fc1.write(str(anglegra)+" "+str(ycurve1)+"\n")
	 fc2.write(str(anglegra)+" "+str(ycurve2)+"\n")
      f1.flush()
      f1.close()
      f2.flush()
      f2.close()
      f3.flush()
      f3.close()
      fc1.flush()
      fc1.close()
      fc2.flush()
      fc2.close()



def compareBestMTSourceInTime(inv_step,mt_solutions,inv_param,freceivers,fdata):
   mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-comparemt')
   minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-comparemt')
   f = open (mininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)
   stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
   ccshift1,ccshift2=inv_param['CC_SHIFT1'],inv_param['CC_SHIFT2']
   prevdepth = '-1'
   for startsol in mt_solutions:   
      sdep,strise=str(startsol.depth),str(startsol.risetime)
      stim,snor,sest=str(startsol.time),str(startsol.rnor),str(startsol.rest)
      sm11,sm12,sm13=str(startsol.m11),str(startsol.m12),str(startsol.m13)
      sm22,sm23,sm33=str(startsol.m22),str(startsol.m23),str(startsol.m33)
      if apply_taper:
         if (prevdepth!=sdep):
            for trace in traces:
               depth=float(sdep)
	       localdepth=int(float(sdep)/1000)
	       taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
               f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
               prevdepth=sdep      
      line = "set_source_params moment_tensor "+stim+" "+snor+" "+sest+" "+sdep+" "\
             +sm11+" "+sm12+" "+sm13+" "+sm22+" "+sm23+" "+sm33+" "+strise+"\n"
      f.write(line)
      f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
      f.write("get_global_misfit\n")
   f.flush()
   f.close()
   callMinimizer(mininp,minout)
   f = open (minout,'r')
   text=[]
   i=0
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error ('+minout+')')
      else:
         if not re.search('ok',line):
            text.append(line)
	    i=i+1 
   if (i<>4):
      print i,'2'
      sys.exit('ERROR 5: n start sol <> n point sol ('+minout+')')
   for isol in range(2):
      mt_solutions[isol].misfit=99999.  
      mt_solutions[isol].misf_shift=float(text[(isol*2)+1])
   mt_solutions.sort(key=operator.attrgetter('misf_shift'))


def confidenceInterval(distribution,inv_param):
   distribution.sort()
   if (inv_param['DISTRIBUTION'].upper()=='NORMAL'):
      meanval=mean(distribution)
      stdev=std(distribution)
      if (int(inv_param['CONFIDENCE_INT'])==68):
         nstdev=stdev
      elif (int(inv_param['CONFIDENCE_INT'])==95):
         nstdev=2*stdev
      elif (int(inv_param['CONFIDENCE_INT'])==99):
         nstdev=3*stdev
      else:
         sys.exit('ERROR: unknown confidence interval, '+str(inv_param['DISTRIBUTION']))
      stdev1=meanval-nstdev
      stdev2=meanval+nstdev
   elif (inv_param['DISTRIBUTION'].upper()=='UNKNOWN'):
      if (int(inv_param['CONFIDENCE_INT'])==68):
         extract1=int(round(0.16*len(distribution)))-1
         extract2=len(distribution)-int(round(0.16*len(distribution)))
      elif (int(inv_param['CONFIDENCE_INT'])==95):
         extract1=int(round(0.025*len(distribution)))-1
         extract2=len(distribution)-int(round(0.025*len(distribution)))
      elif (int(inv_param['CONFIDENCE_INT'])==99):
         extract1=int(round(0.005*len(distribution)))-1
         extract2=len(distribution)-int(round(0.005*len(distribution)))
      else:
         sys.exit('ERROR: unknown confidence interval, '+str(inv_param['DISTRIBUTION']))
      if extract1<0:
         extract1=0
      if extract1>=len(distribution):
         extract2=len(distribution)-1
      stdev1=distribution[extract1]
      stdev2=distribution[extract2]
   else:
      sys.exit('ERROR: unknown distribution type, '+inv_param['DISTRIBUTION'])
   return stdev1,stdev2


def runBootstrapStep1(inv_step,inv_param,point_solutions,n_point_solutions,minout,\
                             start_point_solutions,freceivers,fdata,apply_taper):
   point_solutions.sort(key=operator.attrgetter('misfit'))
   ref_solution=point_solutions[0]
   stim,snor,sest=ref_solution.time,ref_solution.rnor,ref_solution.rest
   strise=ref_solution.risetime
   ssmom,sstrike,sdip,srake=checkStrDipRak(ref_solution.smom,ref_solution.strike,\
                                       ref_solution.dip,ref_solution.rake)
   refsmom,refdepth=float(ssmom),float(ref_solution.depth)
   refdepthkm=round(refdepth/1000)
   refstrike,refdip,refrake=float(sstrike),float(sdip),float(srake)
   slat,slon=inv_param['LATITUDE_NORTH'],inv_param['LONGITUDE_EAST']  

#  Loop over depths
   testeddepths=[]
   bootptsolutions1=[]
   lines_localmisfits1=[]
   n_sol_to_check=0
   localsstrike=str(refstrike)
   localsdip=str(refdip)
   localsrake=str(refrake)
   localssmom=str(refsmom)
   for idep in range(7):
#      fdepth=refdepth+((idep-5)*10000)
      fdepth=refdepth+((idep-3)*1000)
      fdepthkm=round(fdepth/1000)
      if (fdepthkm>float(inv_param['DEPTH_UPPERLIM'])) and (fdepthkm<float(inv_param['DEPTH_BOTTOMLIM'])):
         testeddepths.append(fdepth)
         localsdepth=str(fdepth)
         bootptsolutions1.append(DCsource(inv_step,ref_solution.misfit,ref_solution.rnor,\
	                    ref_solution.rest,ref_solution.time,localsdepth,localsstrike,\
			    localsdip,localsrake,localssmom,ref_solution.misf_shift,
			    ref_solution.risetime))
	 n_sol_to_check = n_sol_to_check + 1
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp1-bootdep')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out1-bootdep')
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)  
   print "LOOP DEPTH"
   if apply_taper:
      for trace in traces:
         taper=getWindowsTaper(trace.comp,refdepthkm,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   for ib in range(n_sol_to_check): 
      line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(bootptsolutions1[ib].depth)+" "+\
             str(bootptsolutions1[ib].smom)+" "+str(bootptsolutions1[ib].strike)+" "+str(bootptsolutions1[ib].dip)+" "+\
             str(bootptsolutions1[ib].rake)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
      f.write(line)
      f.write("get_misfits\n")  
      print str(bootptsolutions1[ib].depth)+" "+str(bootptsolutions1[ib].smom)+" "+\
            str(bootptsolutions1[ib].strike)+" "+str(bootptsolutions1[ib].dip)+" "+\
	    str(bootptsolutions1[ib].rake)
   f.flush()
   f.close()
   print "Calling minimizer",fmininp
   cmd = 'minimizer < '+fmininp+' > '+fminout
   os.system(cmd)
   i=0
   f = open (fminout,'r')
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer2.out)')
      else:
         if not re.search('ok',line):
            lines_localmisfits1.append(line)
            i=i+1
   n_new_point_solutions = i
   f.flush()
   f.close()   
   localbestptsolutions1=[]
   firstlinecomp=lines_localmisfits1[0]
   firstline=firstlinecomp.split()
   numberoftraces=int(len(firstline)/2)
   for iboot in range(int(float(inv_param['NUM_BOOTSTRAP']))):
      randomindexes=[]
      for jboot in range(numberoftraces):
         randomindex=random.randint(0,numberoftraces-1)
	 randomindexes.append(randomindex)
      localptsolutions1=[]
#      if iboot==0:
#	 print "NSOL",n_new_point_solutions
      for isol in range(n_new_point_solutions):
         localptsolution=bootptsolutions1[isol]
	 locallinemisfits=lines_localmisfits1[isol]
	 localmisfit = calcBootstrapMisfit(locallinemisfits,randomindexes)
	 localptsolution.misfit = localmisfit
         localptsolutions1.append(localptsolution)
#	 if iboot<3:
#	    print iboot,"SOL",isol,localmisfit
#	 isol=isol+1
      localptsolutions1.sort(key=operator.attrgetter('misfit'))
      localbestptsolutions1.append(localptsolutions1[0])

   depths=[]
   probdepths=[]  
   fbootdep=os.path.join(inv_param['INVERSION_DIR'],'depth.boot')
   fprobdep=os.path.join(inv_param['INVERSION_DIR'],'depth.prob')
   fboot = open (fbootdep,'w')
   fprob = open (fprobdep,'w')
   for ib in range(len(localbestptsolutions1)):
      depths.append(float(localbestptsolutions1[ib].depth))
      fboot.write(str(localbestptsolutions1[ib].depth)+"\n")
      if localbestptsolutions1[ib].depth not in probdepths:
         probdepths.append(localbestptsolutions1[ib].depth)
#   for checkdepth in probdepths:
   for checkdepth in testeddepths:
      iprob=0
      for ib in range(len(localbestptsolutions1)):
         if checkdepth==float(localbestptsolutions1[ib].depth):
	    iprob=iprob+1
      prob=100*(float(iprob)/float(len(localbestptsolutions1)))
      fprob.write(str(round(float(checkdepth)))+" "+str(prob)+"\n")	    
   fboot.flush()
   fboot.close()
   fprob.flush()
   fprob.close()
   stdev1_depth,stdev2_depth=confidenceInterval(depths,inv_param)
#   average_depth,stdev_depth = mean(depths),std(depths)
#   print "DEPTH       ",average_depth,stdev_depth

#  Loop over scalar moments
   testedsmoms=[]
   bootptsolutions1=[]
   lines_localmisfits1=[]
   n_sol_to_check=0
   localsstrike=str(refstrike)
   localsdip=str(refdip)
   localsrake=str(refrake)
   localsdepth=str(refdepth)
   for ismom in range(21):
      localssmom=refsmom+((ismom-10)*(refsmom/10))
      testedsmoms.append(localssmom)
      bootptsolutions1.append(DCsource(inv_step,ref_solution.misfit,ref_solution.rnor,\
	                    ref_solution.rest,ref_solution.time,localsdepth,localsstrike,\
			    localsdip,localsrake,localssmom,ref_solution.misf_shift,
			    ref_solution.risetime))
      n_sol_to_check = n_sol_to_check + 1
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp1-bootsmom')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out1-bootsmom')
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)  
   print "LOOP MOM"
   if apply_taper:
      for trace in traces:
         taper=getWindowsTaper(trace.comp,refdepthkm,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   for ib in range(n_sol_to_check): 
      line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(bootptsolutions1[ib].depth)+" "+\
             str(bootptsolutions1[ib].smom)+" "+str(bootptsolutions1[ib].strike)+" "+str(bootptsolutions1[ib].dip)+" "+\
             str(bootptsolutions1[ib].rake)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
      f.write(line)
      f.write("get_misfits\n")  
      print str(bootptsolutions1[ib].depth)+" "+str(bootptsolutions1[ib].smom)+" "+\
            str(bootptsolutions1[ib].strike)+" "+str(bootptsolutions1[ib].dip)+" "+\
	    str(bootptsolutions1[ib].rake)
   f.flush()
   f.close()
   print "Calling minimizer",fmininp
   cmd = 'minimizer < '+fmininp+' > '+fminout
   os.system(cmd)
   i=0
   f = open (fminout,'r')
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer2.out)')
      else:
         if not re.search('ok',line):
            lines_localmisfits1.append(line)
            i=i+1
   n_new_point_solutions = i
   f.flush()
   f.close()   
   localbestptsolutions1=[]
   firstlinecomp=lines_localmisfits1[0]
   firstline=firstlinecomp.split()
   numberoftraces=int(len(firstline)/2)
   for iboot in range(int(float(inv_param['NUM_BOOTSTRAP']))):
      randomindexes=[]
      for jboot in range(numberoftraces):
         randomindex=random.randint(0,numberoftraces-1)
	 randomindexes.append(randomindex)
      localptsolutions1=[]
      for isol in range(n_new_point_solutions):
         localptsolution=bootptsolutions1[isol]
	 locallinemisfits=lines_localmisfits1[isol]
	 localmisfit = calcBootstrapMisfit(locallinemisfits,randomindexes)
	 localptsolution.misfit = localmisfit
         localptsolutions1.append(localptsolution)
#	 isol=isol+1
      localptsolutions1.sort(key=operator.attrgetter('misfit'))
      localbestptsolutions1.append(localptsolutions1[0])
   smoms=[]
   probsmoms=[]
   fbootsmom=os.path.join(inv_param['INVERSION_DIR'],'scalarmoment.boot')
   fprobsmom=os.path.join(inv_param['INVERSION_DIR'],'scalarmoment.prob')
   fboot = open (fbootsmom,'w')
   fprob = open (fprobsmom,'w')
   for ib in range(len(localbestptsolutions1)):
      smoms.append(float(localbestptsolutions1[ib].smom))
      fboot.write(str(localbestptsolutions1[ib].smom)+"\n")
      if localbestptsolutions1[ib].smom not in probsmoms:
         probsmoms.append(localbestptsolutions1[ib].smom)
#   for checksmom in probsmoms:
   for checksmom in testedsmoms:
      iprob=0
      for ib in range(len(localbestptsolutions1)):
         if checksmom==float(localbestptsolutions1[ib].smom):
	    iprob=iprob+1
      prob=100*(float(iprob)/float(len(localbestptsolutions1)))
#      fprob.write(str(checksmom)+" "+strDecim(prob,2)+"\n")	    
      fprob.write(str(checksmom)+" "+str(prob)+"\n")	    
   fboot.flush()
   fboot.close()
   fprob.flush()
   fprob.close()
   stdev1_smom,stdev2_smom=confidenceInterval(smoms,inv_param)
#   average_smom,stdev_smom = mean(smoms),std(smoms)
#   print "SCALAR MOM  ",average_smom,stdev_smom

#  Loop over strike, dip, rake       
   testedsdss=[]
   bootptsolutions2=[]
   lines_localmisfits2=[]
   n_sol_to_check=0
   localsdepth=str(refdepth)
   localssmom=str(refsmom)
   for istr in range(7):
      localsstrike=str(refstrike+((istr-3)*20))
      for idip in range(7):
         localsdip=str(refdip+((idip-3)*20))
         for irak in range(7):
            localsrake=str(refrake+((irak-3)*20))
	    testedsdss.append(StrikeDipRake(localsstrike,localsdip,localsrake))
	    bootptsolutions2.append(DCsource(inv_step,ref_solution.misfit,ref_solution.rnor,\
	                    ref_solution.rest,ref_solution.time,localsdepth,localsstrike,\
			    localsdip,localsrake,localssmom,ref_solution.misf_shift,
			    ref_solution.risetime))
	    n_sol_to_check = n_sol_to_check + 1
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp1-bootsds')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out1-bootsds')
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+slat+" "+slon+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+slat+" "+slon+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+inv_step]+" 0 "+inv_param['BP_F2_STEP'+inv_step]+" 1 "
   line_mf=line_mf+inv_param['BP_F3_STEP'+inv_step]+" 1 "+inv_param['BP_F4_STEP'+inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)  
   print "LOOP SDS"
   if apply_taper:
      for trace in traces:
         taper=getWindowsTaper(trace.comp,refdepthkm,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   for ib in range(n_sol_to_check): 
      line = "set_source_params bilateral "+stim+" "+snor+" "+sest+" "+str(bootptsolutions2[ib].depth)+" "+\
             str(bootptsolutions2[ib].smom)+" "+str(bootptsolutions2[ib].strike)+\
	     " "+str(bootptsolutions2[ib].dip)+" "+\
             str(bootptsolutions2[ib].rake)+" 0 0 0 0 "+inv_param['RADIUS0']+" "+strise+"\n"
      f.write(line)
      f.write("get_misfits\n")  
      print str(bootptsolutions2[ib].depth)+" "+str(bootptsolutions2[ib].smom)+" "+\
            str(bootptsolutions2[ib].strike)+" "+str(bootptsolutions2[ib].dip)+" "+\
	    str(bootptsolutions2[ib].rake)
   f.flush()
   f.close()
   print "Calling minimizer",fmininp
   cmd = 'minimizer < '+fmininp+' > '+fminout
   os.system(cmd)
   i=0
   f = open (fminout,'r')
   for line in f:
      if re.search('nok',line):
         print line
         sys.exit('ERROR: minimizer internal error (minimizer2.out)')
      else:
         if not re.search('ok',line):
            lines_localmisfits2.append(line)
            i=i+1
   n_new_point_solutions = i
   f.flush()
   f.close()
   localbestptsolutions2=[]
   firstlinecomp=lines_localmisfits2[0]
   firstline=firstlinecomp.split()
   numberoftraces=int(len(firstline)/2)
   for iboot in range(int(float(inv_param['NUM_BOOTSTRAP']))):
      randomindexes=[]
      for jboot in range(numberoftraces):
         randomindex=random.randint(0,numberoftraces-1)
	 randomindexes.append(randomindex)
#      print "IBOOT",iboot
#      print "indexes",randomindexes
      localptsolutions2=[]
      for isol in range(n_new_point_solutions):
         localptsolution=bootptsolutions2[isol]
	 locallinemisfits=lines_localmisfits2[isol]
	 localmisfit = calcBootstrapMisfit(locallinemisfits,randomindexes)
	 localptsolution.misfit = localmisfit
         localptsolutions2.append(localptsolution)
#	 isol=isol+1
	 if iboot==0:
	    print iboot,"SOL",isol,localptsolution.strike,localptsolution.dip,localptsolution.rake,localmisfit
      localptsolutions2.sort(key=operator.attrgetter('misfit'))
#      print "BESTSOL",localptsolutions2[0].misfit,localptsolutions2[0].strike,\
#                      localptsolutions2[0].dip,localptsolutions2[0].rake
      localbestptsolutions2.append(localptsolutions2[0])
#      if iboot==0:
#	 print "CHOSENSOL",localptsolutions2[0].strike,localptsolutions2[0].dip,localptsolutions2[0].rake,localptsolutions2[0].misfit

   strikes=[]
   dips=[]
   rakes=[]
   probsds=[]
   fbootsds=os.path.join(inv_param['INVERSION_DIR'],'strikediprake.boot')
   fprobsds=os.path.join(inv_param['INVERSION_DIR'],'strikediprake.prob')
   fboot = open (fbootsds,'w')
   fprob = open (fprobsds,'w')
   for ib in range(len(localbestptsolutions2)):
      strikes.append(float(localbestptsolutions2[ib].strike))
      dips.append(float(localbestptsolutions2[ib].dip))
      rakes.append(float(localbestptsolutions2[ib].rake))
      fboot.write(str(localbestptsolutions2[ib].strike)+" "+str(localbestptsolutions2[ib].dip)+\
                  " "+str(localbestptsolutions2[ib].rake)+"\n")
      locsds=str(localbestptsolutions1[ib].strike)+" "+str(localbestptsolutions1[ib].dip)+" "+\
	         str(localbestptsolutions1[ib].rake)
      if locsds not in probsds:
         probsds.append(locsds)
   for checksds in testedsdss:
      print "CHECK ",checksds
      iprob=0     
      for ib in range(len(localbestptsolutions2)):
	 if (checksds.strike==localbestptsolutions2[ib].strike) and \
	    (checksds.dip==localbestptsolutions2[ib].dip) and \
	    (checksds.rake==localbestptsolutions2[ib].rake):
	    iprob=iprob+1
      prob=100*(float(iprob)/float(len(localbestptsolutions2)))
      fprob.write(checksds.strike+" "+checksds.dip+" "+checksds.rake+" "+str(prob)+"\n")	    
   fboot.flush()
   fboot.close()    
   fprob.flush()
   fprob.close()    
   stdev1_strike,stdev2_strike=confidenceInterval(strikes,inv_param)
   stdev1_dip,stdev2_dip=confidenceInterval(dips,inv_param)
   stdev1_rake,stdev2_rake=confidenceInterval(rakes,inv_param)
#   average_strike,stdev_strike = mean(strikes),std(strikes)
#   average_dip,stdev_dip = mean(dips),std(dips)
#   average_rake,stdev_rake = mean(rakes),std(rakes)
#   print "STRIKE      ",average_strike,stdev_strike
#   print "DIP         ",average_dip,stdev_dip
#   print "RAKE        ",average_rake,stdev_rake

#Print output to bootstrap file
   fbootstrap=os.path.join(inv_param['INVERSION_DIR'],"bootstrap.dat")
   if os.path.exists(fbootstrap):
      f=open(fbootstrap,'a') 
   else:
      f=open(fbootstrap,'w')
   f.write("INVERSION STEP 1\n")
   sdep1,sdep2=strDecim(stdev1_depth/1000,1),strDecim(stdev2_depth/1000,1)
   ssmom1,ssmom2=str(stdev1_smom),str(stdev2_smom)
   str1,str2=strDecim(stdev1_strike,1),strDecim(stdev2_strike,1)
   dip1,dip2=strDecim(stdev1_dip,1),strDecim(stdev2_dip,1)
   rak1,rak2=strDecim(stdev1_rake,1),strDecim(stdev2_rake,1)   
#   sdep1,sdep2=strDecim((average_depth-stdev_depth)/1000,1),strDecim((average_depth+stdev_depth)/1000,1)
#   ssmom1,ssmom2=str(average_smom-stdev_smom),str(average_smom+stdev_smom)
#   str1,str2=strDecim(average_strike-stdev_strike,1),strDecim(average_strike+stdev_strike,1)
#   dip1,dip2=strDecim(average_dip-stdev_dip,1),strDecim(average_dip+stdev_dip,1)
#   rak1,rak2=strDecim(average_rake-stdev_rake,1),strDecim(average_rake+stdev_rake,1)   
   f.write("DEPTH      "+strDecim(refdepth/1000,1)+" ["+sdep1+", "+sdep2+"] km\n")
   f.write("SC.MOMENT  "+str(refsmom)+" ["+ssmom1+", "+ssmom2+"] Nm\n")
   f.write("STRIKE     "+strDecim(refstrike,1)+" ["+str1+", "+str2+"] deg\n")
   f.write("DIP        "+strDecim(refdip,1)+" ["+dip1+", "+dip2+"] deg\n")
   f.write("RAKE       "+strDecim(refrake,1)+" ["+rak1+", "+rak2+"] deg\n")
   f.flush()
   f.close()


def inversionDCsource(inv_step,inv_param,point_solutions,best_point_solutions,traces,apply_taper):
   if inv_step == '2':
      if inv_param['SW_VERTICAL_ST2'].upper()=='TRUE':
         freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.z')
      else:
         freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.loc')
   else:
      freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.mec')
   fdata=os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
   if (inv_step == '1'):
      print 'Inversion step 1'
      n_local_loops=int(inv_param['LOOPS_SDS_CONF'])
   elif (inv_step == '2'):
      print 'Inversion step 2'
      compareBestDCSourceInTime(inv_step,point_solutions,inv_param,freceivers,fdata)
      n_local_loops=int(inv_param['LOOPS_LOC_CONF'])
   else:
      sys.exit("ERROR: something went wrong with the starting configurations, "+inv_step)
#  Define first grid walk
   start_point_solutions=[]   
   defineGridWalkDCsource(inv_step,start_point_solutions,point_solutions,inv_param)
#  Prepare point source inversion, looping over starting configurations
   print 'sss ',len(start_point_solutions)
   for iloop in range(n_local_loops): 
      irun=iloop+1
      mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-run'+str(irun))
      minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-run'+str(irun))
      prepMinimizerInputDCsource(inv_step,mininp,minout,inv_param,freceivers,fdata,\
                                    apply_taper,irun,start_point_solutions)
      n_point_solutions = len(start_point_solutions) 
      print 'check',irun,n_point_solutions     
#  Calling minimizer for point source inversion
      if inv_param['NUM_PROCESSORS']=='1':
         callMinimizer(mininp,minout)
      else:
         callParallelizedMinimizer(mininp,minout,num_processors)
#  Analysing point source inversion results
      lines_singlemisfits=[]
      analyseResultsDCsource(inv_step,inv_param,point_solutions,n_point_solutions,minout,\
                             start_point_solutions,lines_singlemisfits)
      if (inv_step=="1"):
         runBootstrapStep1(inv_step,inv_param,point_solutions,n_point_solutions,minout,\
                             start_point_solutions,freceivers,fdata,apply_taper)
      else:
         runBootstrapStep2(inv_step,inv_param,point_solutions,n_point_solutions,minout,\
                          start_point_solutions,freceivers,fdata,apply_taper,lines_singlemisfits)
#         runBootstrapStep2(inv_step,point_solutions,n_point_solutions,lines_singlemisfits)
      point_solutions.sort(key=operator.attrgetter('misfit'))
      if (irun < n_local_loops):
         start_point_solutions=[]
      updateGridWalkDCsource(inv_step,point_solutions,start_point_solutions,inv_param,irun)
#  Possible fault planes & Misfit curves for strike,dip,rake
   point_solutions.sort(key=operator.attrgetter('misfit'))
   calcAuxFaultPlane(inv_step,inv_param,point_solutions,best_point_solutions) 
#   if 't' in inv_param['INV_MODE_STEP'+inv_step]:
   if (inv_step=="1"):
      if (inv_param['SW_APPDURATION'].upper()=="TRUE"):
         calcDuration(inv_step,inv_param,best_point_solutions,apply_taper,fdata,freceivers)
   for best_point_solution in best_point_solutions:
      if (best_point_solution.inv_step == inv_step):
         smom,strike,dip,rake=checkStrDipRak(best_point_solution.smom,best_point_solution.strike,best_point_solution.dip,best_point_solution.rake)
         best_point_solution.strike,best_point_solution.dip,best_point_solution.rake=strike,dip,rake
         best_point_solution.smom=smom
         point_solutions.append(best_point_solution)
   if (inv_step == '1'):
      point_solutions.sort(key=operator.attrgetter('misfit'))   
      best_point_solutions.sort(key=operator.attrgetter('strike'))
      relMisfitCurves(inv_step,inv_param,point_solutions,best_point_solutions,n_point_solutions,apply_taper,fdata,freceivers)
      point_solutions.sort(key=operator.attrgetter('misfit'))
#  Output point solutions to extra file
   n_point_solutions=len(point_solutions)
   writeDCSolutions(inv_step,point_solutions,n_point_solutions,inv_param['INVERSION_DIR'],'step'+inv_step+'-ptsolutions.dat')
#  Calculates synthetics for best strike-dip-slip solution
   calculateDCSynthetics(inv_step,inv_param,point_solutions,traces,apply_taper,freceivers,fdata)
#  Plot point source solution 1
   point_solutions.sort(key=operator.attrgetter('misfit'))


def inversionMTsource(inv_step,inv_param,mt_solutions,best_mt_solutions,traces,apply_taper):
   freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table')
   fdata=os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
   freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table')
   fdata=os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
   if (inv_step == '1'):
      print 'Inversion step 1b'
   elif (inv_step == '2'):
      print 'Inversion step 2b'
      compareBestMTSourceInTime(inv_step,mt_solutions,inv_param,freceivers,fdata)
   else:
      sys.exit("ERROR: something went wrong with the starting configurations, "+inv_step)
#  Define first grid walk
   start_mt_solutions=[]   
   defineGridWalkMTsource(inv_step,start_mt_solutions,mt_solutions,inv_param)
#  Prepare point source inversion, looping over starting configurations
   mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-runmt')
   minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-runmt')
   irun=1
   prepMinimizerInputMTsource(inv_step,mininp,minout,inv_param,freceivers,fdata,\
                                       apply_taper,irun,start_mt_solutions)
   n_mt_solutions = len(start_mt_solutions) 
#  Calling minimizer for point source inversion
   callMinimizer(mininp,minout)
#  Analysing point source inversion results
   analyseResultsMTsource(inv_step,inv_param,mt_solutions,n_mt_solutions,minout,start_mt_solutions)
#  Adding best solutions
   calcAuxMTsolutions(inv_step,inv_param,mt_solutions,best_mt_solutions) 
#  Output point solutions to extra file
   n_mt_solutions=len(mt_solutions)
   writeMTSolutions(inv_step,mt_solutions,n_mt_solutions,inv_param['INVERSION_DIR'],'step'+inv_step+'-mtsolutions.dat')
#  Calculates synthetics for best strike-dip-slip solution
   calculateMTSynthetics(inv_step,inv_param,mt_solutions,traces,apply_taper,freceivers,fdata)
#  Plot point source solution 1
   mt_solutions.sort(key=operator.attrgetter('misfit'))


def findUnfittingStations(inv_step,inv_param,eikonals,traces,apply_taper,best_point,mohodepth):
   if (inv_step == '3'):
      print 'Choosing good fitting stations only!'
   else:
      sys.exit("ERROR: something went wrong with station fit evaluation procedure, "+inv_step) 
   comp_inv_step=inv_param['ST_GOODSTATIONS']
   fmininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-evalstat')
   fminout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-evalstat')
#  Prepare minimizer input
   freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.kin')
   fdata=os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
   f = open (fmininp,'w')
   f.write("set_database "+inv_param['GFDB_STEP'+inv_step]+"/db\n")
   f.write("set_effective_dt "+inv_param['EFFECTIVE_DT_ST'+comp_inv_step]+"\n")
   f.write("set_receivers "+freceivers+"\n")
   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   f.write("set_source_constraints 0 0 0 0 0 -1\n")
   f.write("set_ref_seismograms "+fdata+" "+inv_param['DATA_FORMAT']+"\n")
   f.write("set_local_interpolation "+inv_param['GF_INTERPOLATION']+"\n")
#   f.write("set_source_location "+inv_param['LATITUDE_NORTH']+" "+inv_param['LONGITUDE_EAST']+" 0\n")
   line_mm="set_misfit_method "+inv_param['MISFIT_MET_STEP'+comp_inv_step]+"\n"
   line_mf="set_misfit_filter "+inv_param['BP_F1_STEP'+comp_inv_step]+" 0 "\
           +inv_param['BP_F2_STEP'+comp_inv_step]+" 1 "\
           +inv_param['BP_F3_STEP'+comp_inv_step]+" 1 "\
	   +inv_param['BP_F4_STEP'+comp_inv_step]+" 0\n"
   f.write(line_mm)
   f.write(line_mf)
   stim,snor,sest=inv_param['ORIG_TIME'],inv_param['ORIG_NORTH_SHIFT'],inv_param['ORIG_EAST_SHIFT']
   ccshift1,ccshift2=inv_param['KIN_CC_SHIFT1'],inv_param['KIN_CC_SHIFT2']
   stim,snor,sest=str(eikonals[0].time),str(eikonals[0].rnor),str(eikonals[0].rest)
   sdep,smom=str(eikonals[0].depth),str(eikonals[0].smom)
   sstr,sdip,srak=str(eikonals[0].strike),str(eikonals[0].dip),str(eikonals[0].rake)
   srise=str(eikonals[0].risetime)
   fdep=float(sdep)
   if (fdep>=mohodepth):
      line_depth_constraints="set_source_constraints 0 0 0 0 0 -1 0 0 95000 0 0 1\n"
      f.write(line_depth_constraints)
   for trace in traces:
      if (trace.dist <= float(inv_param['EPIC_DIST_MAXKIN'])):
         depth=float(sdep)
         localdepth=int(float(sdep)/1000)
         taper=getWindowsTaper(trace.comp,localdepth,trace.dist,inv_param,inv_step)
         f.write("set_misfit_taper "+str(trace.num)+" "+taper+"\n")
   line = "set_source_params eikonal "+stim+" "+snor+" "+sest+" "+sdep+" "+smom+" "
   line = line+sstr+" "+sdip+" "+srak+" 0 0 0 0 0 0.9 "+srise+"\n"
   f.write(line)
   f.write("autoshift_ref_seismogram 0 "+ccshift1+" "+ccshift2+" \n")
   f.write("get_misfits \n")   
   f.flush()
   f.close()
#  Call minimizer
   print "call minimizer here"
   callMinimizer(fmininp,fminout)   
#  Analyze minimizer results   
   print 'Analysing stations fit, before '+inv_step+'...'
   i=0
   f = open (fminout,'r')
   text=[]
   for line in f:      
      if re.search('nok',line):
         if re.search ('get_global_misfit: nok',line):
            print line
	    print 'continue anyway - large misfit given by default'
	 else:
            print line
	    sys.exit('ERROR: minimizer internal error (minimizer1.out)')
      else:
         if not re.search('ok',line):
            if not re.search('nucleation point is outside',line):
               text.append(line) 
            else:
	       defline='9.9\n'
	       text.append(defline)
	    i=i+1
   f.flush()
   f.close()
#   correlations=text[0].split()
   textmisfits=text[1].split()
   singlemisfits=[]
   for imis in range(int(len(textmisfits)/2)):
#      singlemisfits.append(float(textmisfits[imis*2]))
      singlemisfits.append(float(textmisfits[imis*2])/float(textmisfits[imis*2+1]))
   averagemisfit=mean(singlemisfits)
   standarddev=std(singlemisfits)
   maxadmittedmisfit=averagemisfit+standarddev
   print "singlemisfits",singlemisfits
   print "average",averagemisfit
   print "bad above",maxadmittedmisfit
#  Build new station file (only traces which here fit when lowpassed will be later used for kinematic inversion)
   finp=os.path.join(inv_param['INVERSION_DIR'],'stations.table.kin')
   fout=os.path.join(inv_param['INVERSION_DIR'],'stations.table.kin.good')
   f1 = open (finp,'r')
   f2 = open (fout,'w')
   itrace=0
   for line in f1:
      splittedline=line.split()
      if len(splittedline)==3:
         if singlemisfits[itrace]<=maxadmittedmisfit:
            f2.write(line)
         else:
            f2.write(splittedline[0]+" "+splittedline[1]+"\n")
         itrace=itrace+1
      else:
         f2.write(line)
   f1.flush()
   f1.close()
   f2.flush()
   f2.close()
   
   
def calcBootstrapMisfit(locallinemisfits,randomindexes):
# now L2 norm as external norm
   misfandnormcoefs=locallinemisfits.split()
   misfits=[]
   normcoefs=[]
   for i in range(int(len(misfandnormcoefs)/2)):
      misfits.append(float(misfandnormcoefs[i*2]))
      normcoefs.append(float(misfandnormcoefs[i*2+1]))
   misfit=0
   normcoef=0
   for iri in range(len(randomindexes)):
      misfit=misfit+(misfits[randomindexes[iri]]*misfits[randomindexes[iri]])
      normcoef=normcoef+(normcoefs[randomindexes[iri]]*normcoefs[randomindexes[iri]])
   misfit=math.sqrt(misfit/normcoef)
   return misfit


def runBootstrapStep2(inv_step,inv_param,point_solutions,n_point_solutions,minout,\
                      ptsolutions,freceivers,fdata,apply_taper,lines_singlemisfits):
   if (inv_step == '2'):
      print 'Bootstrap inversion step 2'
   else:
      sys.exit("ERROR: something went wrong with the bootstrap, "+inv_step)
   n_solutions_to_check=len(ptsolutions)
   if len(lines_singlemisfits) <> n_solutions_to_check:
      print "ERROR: inconsistent number of lines", len(lines_singlemisfits),len(ptsolutions)
      print len(lines_singlemisfits),len(ptsolutions)
      sys.exit("ERROR: runDCBootstrap failed, step "+inv_step)
   
   testedcentroids=[]   
   bestmisfit=99999.
   for pointsolution in point_solutions:
      rnor,rest,time=pointsolution.rnor,pointsolution.rest,pointsolution.time
      testedcentroids.append(Centroid(rnor,rest,time))
      if float(pointsolution.misfit) <= bestmisfit:
         bestmisfit=float(pointsolution.misfit)
	 refnorth=float(pointsolution.rnor)
	 refeast=float(pointsolution.rest)
	 reftime=float(pointsolution.time)
   if bestmisfit==99999:
      sys.exit("ERROR: runDCBootstrap failed with large misfit, step "+inv_step)   
   localbestptsolutions=[]
   firstlinecomp=lines_singlemisfits[0]
   firstline=firstlinecomp.split()
   numberoftraces=int(len(firstline)/2)
   for iboot in range(int(float(inv_param['NUM_BOOTSTRAP']))):
      randomindexes=[]
      for jboot in range(numberoftraces):
         randomindex=random.randint(0,numberoftraces-1)
	 randomindexes.append(randomindex)
      localptsolutions=[]
      for isol in range(n_solutions_to_check):
         localptsolution=ptsolutions[isol]
	 locallinemisfits=lines_singlemisfits[isol]
	 localmisfit = calcBootstrapMisfit(locallinemisfits,randomindexes)
	 localptsolution.misfit = localmisfit
         localptsolutions.append(localptsolution)
	 isol=isol+1
      localptsolutions.sort(key=operator.attrgetter('misfit'))
      localbestptsolutions.append(localptsolutions[0])

   rests=[]
   rnors=[]
   times=[]
   fbootloc=os.path.join(inv_param['INVERSION_DIR'],'centroid.boot')
   fprobloc=os.path.join(inv_param['INVERSION_DIR'],'centroid.prob')
   fboot = open (fbootloc,'w')
   fprob = open (fprobloc,'w')
   for ilb in range(len(localbestptsolutions)):
      rests.append(float(localbestptsolutions[ilb].rest))
      rnors.append(float(localbestptsolutions[ilb].rnor))
      times.append(float(localbestptsolutions[ilb].time))
      fboot.write(str(localbestptsolutions[ilb].rest)+" "+str(localbestptsolutions[ilb].rnor)\
                  +" "+str(localbestptsolutions[ilb].time)+"\n")
      loccentroid=str(localbestptsolutions[ilb].rest)+" "+str(localbestptsolutions[ilb].rnor)+" "+\
	         str(localbestptsolutions[ilb].time)
   for checkcentroid in testedcentroids:
      iprob=0     
      for ilb in range(len(localbestptsolutions)):
	 if (checkcentroid.rnor==localbestptsolutions[ilb].rnor) and \
	    (checkcentroid.rest==localbestptsolutions[ilb].rest) and \
	    (checkcentroid.time==localbestptsolutions[ilb].time):
	    iprob=iprob+1
      prob=100*(float(iprob)/float(len(localbestptsolutions)))
      fprob.write(checkcentroid.rnor+" "+checkcentroid.rest+" "+checkcentroid.time+" "+str(prob)+"\n")	    
   fboot.flush()
   fboot.close()
   fprob.flush()
   fprob.close()    
   stdev1_rest,stdev2_rest=confidenceInterval(rests,inv_param)
   stdev1_rnor,stdev2_rnor=confidenceInterval(rnors,inv_param)
   stdev1_time,stdev2_time=confidenceInterval(times,inv_param)
#      average_rest,stdev_rest = mean(rests),std(rests)
#      average_rnor,stdev_rnor = mean(rnors),std(rnors)
#      average_time,stdev_time = mean(times),std(times)
   fbootstrap=os.path.join(inv_param['INVERSION_DIR'],"bootstrap.dat")
   if os.path.exists(fbootstrap):
      f=open(fbootstrap,'a') 
   else:
      f=open(fbootstrap,'w')
   f.write("INVERSION STEP 2\n")      
   nor1,nor2=strDecim(stdev1_rnor/1000,1),strDecim(stdev2_rnor/1000,1)
   est1,est2=strDecim(stdev1_rest/1000,1),strDecim(stdev2_rest/1000,1)
   tim1,tim2=strDecim(stdev1_time,1),strDecim(stdev2_time,1)
   f.write("REL LAT N  "+strDecim(refnorth/1000,1)+" ["+nor1+", "+nor2+"] km\n")
   f.write("REL LON E  "+strDecim(refeast/1000,1)+" ["+est1+", "+est2+"] km\n")
   f.write("REL TIME   "+strDecim(reftime,1)+" ["+tim1+", "+tim2+"] s\n")
   f.flush()
   f.close()
   

def runEIKBootstrap(inv_step,result_eikonals,n_eikonals,eikonals,lines_singlemisfits):
   if (inv_step == '3'):
      print 'Bootstrap inversion step 3'
   else:
      sys.exit("ERROR: something went wrong with the bootstrap, "+inv_step)
   if len(lines_singlemisfits) <> len(eikonals):
      print "ERROR: inconsistent number of lines", len(lines_singlemisfits),len(eikonals)
      sys.exit("ERROR: runEIKBootstrap failed")

   bestmisfit1=99999.
   for eiksolution in result_eikonals:
      if float(eiksolution.misfit) <= bestmisfit1:
         bestmisfit1=float(eiksolution.misfit)
         refstrike1=float(eiksolution.strike)
         refdip1=float(eiksolution.dip)
         refrake1=float(eiksolution.rake)
	 refradius1=float(eiksolution.radius)
         refrelruptvel1=float(eiksolution.relruptvel)
	 refnuklx1=float(eiksolution.nuklx)
         refnukly1=float(eiksolution.nukly)
   bestmisfit2=99999.
   for eiksolution in result_eikonals:
      if (eiksolution.strike<>refstrike1):
         if float(eiksolution.misfit) <= bestmisfit2:
            bestmisfit2=float(eiksolution.misfit)
	    refstrike2=float(eiksolution.strike)
	    refdip2=float(eiksolution.dip)
	    refrake2=float(eiksolution.rake)      
   	    refradius2=float(eiksolution.radius)
            refrelruptvel2=float(eiksolution.relruptvel)
	    refnuklx2=float(eiksolution.nuklx)
            refnukly2=float(eiksolution.nukly)
   if (bestmisfit1+bestmisfit2>=99999):
      sys.exit("ERROR: runDCBootstrap failed with large misfit, step "+inv_step)   
   localbesteikonals1=[]
   localbesteikonals2=[]
   localbesteikonals3=[]
   firstlinecomp=lines_singlemisfits[0]
   firstline=firstlinecomp.split()
   numberoftraces=int(len(firstline)/2)
   for iboot in range(int(float(inv_param['NUM_BOOTSTRAP']))):
      randomindexes=[]
      for jboot in range(numberoftraces):
         randomindex=random.randint(0,numberoftraces-1)
	 randomindexes.append(randomindex)
      localeikonals1=[]      
      localeikonals2=[]      
      localeikonals3=[]
      for isol in range(n_eikonals):
         localeikonal=cpEikonal(eikonals[isol])
	 locallinemisfits=lines_singlemisfits[isol]
	 localmisfit = calcBootstrapMisfit(locallinemisfits,randomindexes)
	 localeikonal.misfit = localmisfit
         if (localeikonal.strike==refstrike1):
	    localeikonals1.append(localeikonal)
	 else:
	    localeikonals2.append(localeikonal)
	 localeikonals3.append(localeikonal)   	 
	 isol=isol+1
      localeikonals1.sort(key=operator.attrgetter('misfit'))
      localeikonals2.sort(key=operator.attrgetter('misfit'))
      localeikonals3.sort(key=operator.attrgetter('misfit'))
      localbesteikonals1.append(localeikonals1[0])
      localbesteikonals2.append(localeikonals2[0])
      localbesteikonals3.append(localeikonals3[0])
   radiuses1=[]
   relruptvels1=[]
   nuklxs1=[]
   nuklys1=[]
   radiuses2=[]
   relruptvels2=[]
   nuklxs2=[]
   nuklys2=[]
   if len(localbesteikonals1)<>len(localbesteikonals2):
      sys.exit("ERROR: runDCBootstrap failed with 2 sets of bootstraps")
   for ilb in range(len(localbesteikonals1)):
      radiuses1.append(float(localbesteikonals1[ilb].radius))
      relruptvels1.append(float(localbesteikonals1[ilb].relruptvel))
      nuklxs1.append(float(localbesteikonals1[ilb].nuklx))
      nuklys1.append(float(localbesteikonals1[ilb].nukly))      
      radiuses2.append(float(localbesteikonals2[ilb].radius))
      relruptvels2.append(float(localbesteikonals2[ilb].relruptvel))
      nuklxs2.append(float(localbesteikonals2[ilb].nuklx))
      nuklys2.append(float(localbesteikonals2[ilb].nukly))      
   fbooteik=os.path.join(inv_param['INVERSION_DIR'],'eikonal.boot')
   fprobeik=os.path.join(inv_param['INVERSION_DIR'],'eikonal.prob')
   fboot = open (fbooteik,'w')
   fprob = open (fprobeik,'w')
   for ib in range(len(localbesteikonals3)):
      fboot.write(str(localbesteikonals3[ib].strike)+" "+str(localbesteikonals3[ib].dip)+" "\
                 +str(localbesteikonals3[ib].rake)+" "+str(localbesteikonals3[ib].radius)+" "\
                 +str(localbesteikonals3[ib].relruptvel)+" "+str(localbesteikonals3[ib].nuklx)\
		 +" "+str(localbesteikonals3[ib].nukly)+"\n")
   for testedeiko in result_eikonals:
      iprob=0     
      for ib in range(len(localbesteikonals3)):
	 if (testedeiko.strike==localbesteikonals3[ib].strike) and \
	    (testedeiko.dip==localbesteikonals3[ib].dip) and \
	    (testedeiko.rake==localbesteikonals3[ib].rake) and \
	    (testedeiko.relruptvel==localbesteikonals3[ib].relruptvel) and \
	    (testedeiko.radius==localbesteikonals3[ib].radius) and \
	    (testedeiko.nuklx==localbesteikonals3[ib].nuklx) and \
	    (testedeiko.nukly==localbesteikonals3[ib].nukly):
	    iprob=iprob+1
      prob=100*(float(iprob)/float(len(localbesteikonals3)))
      fprob.write(str(testedeiko.strike)+" "+str(testedeiko.dip)+" "+\
                  str(testedeiko.rake)+" "+str(testedeiko.relruptvel)+" "+\
		  str(testedeiko.radius)+" "+str(testedeiko.nuklx)+" "+\
		  str(testedeiko.nukly)+" "+str(prob)+"\n")	    
   fboot.flush()
   fboot.close()
   fprob.flush()
   fprob.close()
   stdev1_radius1,stdev2_radius1=confidenceInterval(radiuses1,inv_param)
   if stdev1_radius1<0:
      stdev1_radius1=0
   if stdev2_radius1<1:
      stdev2_radius1=1
   stdev1_relruptvel1,stdev2_relruptvel1=confidenceInterval(relruptvels1,inv_param)
   stdev1_nuklx1,stdev2_nuklx1=confidenceInterval(nuklxs1,inv_param)
   stdev1_nukly1,stdev2_nukly1=confidenceInterval(nuklys1,inv_param)
   stdev1_radius2,stdev2_radius2=confidenceInterval(radiuses2,inv_param)
   if stdev1_radius2<0:
      stdev1_radius2=0
   if stdev2_radius2<1:
      stdev2_radius2=1
   stdev1_relruptvel2,stdev2_relruptvel2=confidenceInterval(relruptvels2,inv_param)
   stdev1_nuklx2,stdev2_nuklx2=confidenceInterval(nuklxs2,inv_param)
   stdev1_nukly2,stdev2_nukly2=confidenceInterval(nuklys2,inv_param)
   fbootstrap=os.path.join(inv_param['INVERSION_DIR'],"bootstrap.dat")
   if os.path.exists(fbootstrap):
      f=open(fbootstrap,'a') 
   else:
      f=open(fbootstrap,'w')
   f.write("INVERSION STEP 3\n")
   f.write("SOLUTION 1 > "+str(refstrike1)+" "+str(refdip1)+" "+str(refrake1)+"\n")
   rad1=strDecim(stdev1_radius1/1000,1)
   rad2=strDecim(stdev2_radius1/1000,1)
   f.write("RADIUS     "+strDecim(float(refradius1)/1000,1)+" ["+rad1+", "+rad2+"] km\n")
   rrv1=strDecim(stdev1_relruptvel1,1)
   rrv2=strDecim(stdev2_relruptvel1,1)
   f.write("RELRUPTVEL "+strDecim(float(refrelruptvel1),1)+" ["+rrv1+", "+rrv2+"]\n")
   nkx1=strDecim(stdev1_nuklx1/1000,1)
   nkx2=strDecim(stdev2_nuklx1/1000,1)
   f.write("NUCLEAT X  "+strDecim(float(refnuklx1)/1000,1)+" ["+nkx1+", "+nkx2+"] km\n")
   nky1=strDecim(stdev1_nukly1/1000,1)
   nky2=strDecim(stdev2_nukly1/1000,1)
   f.write("NUCLEAT Y  "+strDecim(float(refnukly1)/1000,1)+" ["+nky1+", "+nky2+"] km\n")
   f.write("SOLUTION 2 > "+str(refstrike2)+" "+str(refdip2)+" "+str(refrake2)+"\n")
   rad1=strDecim(stdev1_radius2/1000,1)
   rad2=strDecim(stdev2_radius2/1000,1)
   f.write("RADIUS     "+strDecim(float(refradius2)/1000,1)+" ["+rad1+", "+rad2+"] km\n")
   rrv1=strDecim(stdev1_relruptvel2,1)
   rrv2=strDecim(stdev2_relruptvel2,1)
   f.write("RELRUPTVEL "+strDecim(float(refrelruptvel2),1)+" ["+rrv1+", "+rrv2+"]\n")
   nkx1=strDecim(stdev1_nuklx2/1000,1)
   nkx2=strDecim(stdev2_nuklx2/1000,1)
   f.write("NUCLEAT X  "+strDecim(float(refnuklx2)/1000,1)+" ["+nkx1+", "+nkx2+"] km\n")
   nky1=strDecim(stdev1_nukly2/1000,1)
   nky2=strDecim(stdev2_nukly2/1000,1)
   f.write("NUCLEAT Y  "+strDecim(float(refnukly2)/1000,1)+" ["+nky1+", "+nky2+"] km\n")
   f.flush()
   f.close()


def inversionEIKsource(inv_step,inv_param,start_eikonals,eikonals,best_eikonals,traces,apply_taper,best_point):
   freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.kin')
   if inv_param['SW_GOODSTATIONS'].upper()=='TRUE':
      freceivers=os.path.join(inv_param['INVERSION_DIR'],'stations.table.kin.good')
   fdata=os.path.join(inv_param['INVERSION_DIR'],inv_param['DATA_FILE'])
   if (inv_step == '3'):
      print 'Inversion step 3'
#      n_local_loops=int(inv_param['LOOPS_EIK_CONF'])
      n_local_loops=1  
   else:
      sys.exit("ERROR: something went wrong with the starting configurations, "+inv_step)
#  Check Moho depth
   mohodepth=getCrustalDepth(inv_param)
#  Choose only well fitting stations
   if (inv_param['SW_GOODSTATIONS'].upper()=='TRUE'):
      findUnfittingStations(inv_step,inv_param,eikonals,traces,apply_taper,best_point,mohodepth)
#  Define first grid walk
   print 'BEFORE APPENDING ',len(start_eikonals)
   defineGridWalkEikonalsource(inv_step,start_eikonals,eikonals,inv_param)
   print 'STARTING EIKONALS ',len(start_eikonals)
   for eikonal in start_eikonals:
      print eikonal.strike,eikonal.dip,eikonal.rake,\
            eikonal.nuklx,eikonal.nukly,eikonal.radius,eikonal.relruptvel

#  Prepare eikonal source inversion, looping over starting configurations
   print 'number of eikonal starting sources ',len(start_eikonals)
   for iloop in range(n_local_loops): 
      irun=iloop+1
      mininp=os.path.join(inv_param['INVERSION_DIR'],'minimizer.inp'+inv_step+'-run'+str(irun))
      minout=os.path.join(inv_param['INVERSION_DIR'],'minimizer.out'+inv_step+'-run'+str(irun))
      prepMinimizerInputEikonalsource(inv_step,mininp,minout,inv_param,freceivers,fdata,\
                                      apply_taper,irun,start_eikonals,mohodepth)
      n_eikonals = len(start_eikonals) 
      print 'check',irun,n_eikonals     
#  Calling minimizer for point source inversion
      callMinimizer(mininp,minout)
#  Analysing eikonal source inversion results
      lines_singlemisfits=[]
      analyseResultsEikonalsource(inv_step,inv_param,eikonals,n_eikonals,minout,start_eikonals,lines_singlemisfits)
      runEIKBootstrap(inv_step,eikonals,n_eikonals,start_eikonals,lines_singlemisfits)
      eikonals.sort(key=operator.attrgetter('misfit'))
      print 'best eiko',eikonals[0].misfit,eikonals[0].radius,eikonals[0].strike
      if (irun < n_local_loops):
         start_eikonals=[]
         updateGridWalkEikonalsource(inv_step,eikonals,start_eikonals,inv_param,irun)
#  Possible fault planes & Misfit curves for strike,dip,rake
   eikonals.sort(key=operator.attrgetter('misfit'))
   best_eikonals.append(eikonals[0])
##   if (inv_step == '1'):
##      point_solutions.sort(key=operator.attrgetter('misfit'))   
##      best_point_solutions.sort(key=operator.attrgetter('strike'))
##      relMisfitCurves(inv_step,inv_param,point_solutions,best_point_solutions,n_point_solutions,apply_taper,fdata,freceivers)
##      point_solutions.sort(key=operator.attrgetter('misfit'))
#  Output point solutions to extra file
   n_eikonals=len(eikonals)
   writeEikSolutions(inv_step,eikonals,n_eikonals,inv_param['INVERSION_DIR'],'step'+inv_step+'-eiksolutions.dat')
#  Calculates synthetics for best strike-dip-slip solution
   calculateEikSynthetics(inv_step,inv_param,eikonals,traces,apply_taper,freceivers,fdata,mohodepth)
#  Plot point source solution 1
   eikonals.sort(key=operator.attrgetter('misfit'))


def plotDCSolution(inv_step,inv_param,all,best,traces):
   print "Plotting results inversion step "+inv_step+"..."
   slat=inv_param['LATITUDE_NORTH']
   slon=inv_param['LONGITUDE_EAST']
   dinv=inv_param['INVERSION_DIR']
   fmeca=os.path.join(dinv,'step'+inv_step+'.meca.dat')
   fallmeca=os.path.join(dinv,'step'+inv_step+'.meca.all')
   fselmeca=os.path.join(dinv,'step'+inv_step+'.meca.sel')
   feqinfo=os.path.join(dinv,'step'+inv_step+'.earthquakeinfo.dat')
   fgmtplot=os.path.join(dinv,'step'+inv_step+'.ptsolution.gmt')
   fplot=os.path.join(dinv,'step'+inv_step+'.ptsolution.ps')
   if (inv_step == '1'):
      fdepmis=os.path.join(dinv,'step'+inv_step+'.dep_mis.dat')
      fstrmis=os.path.join(dinv,'step'+inv_step+'.str_mis.dat')
      fdipmis=os.path.join(dinv,'step'+inv_step+'.dip_mis.dat')
      frakmis=os.path.join(dinv,'step'+inv_step+'.rak_mis.dat')
      fazi=os.path.join(dinv,'step'+inv_step+'.azimuths.dat')
   if (inv_step == '2'):
      ftimmis=os.path.join(dinv,'step'+inv_step+'.tim_mis.dat')
      fenmis=os.path.join(dinv,'step'+inv_step+'.en_mis.dat')
      fznmis=os.path.join(dinv,'step'+inv_step+'.zn_mis.dat')
      fezmis=os.path.join(dinv,'step'+inv_step+'.ez_mis.dat')
   fallsyndat=os.path.join(dinv,'step'+inv_step+'.amsp-all.table')
#  Maximal value (file amsp-all.table)
   amaxf = 0
   istat=0
   cmd=""
#  Magnitude
   mw = m0tomw(float(inv_param['SCALING_FACTOR'])*float(best[0].smom))

   ntr=0
   nst=0
   localstations=[]
   for trace in traces:
      ntr=ntr+len(trace.comp)
      if trace.stat not in localstations:
         localstations.append(trace.stat)	 
         nst=nst+1
      istat=istat+1
      for component in trace.comp:
         for syndat in ('s','d'):
	    if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
               fsyndat=os.path.join(dinv,syndat+"amsp"+inv_step+"-"+str(istat)+"-"+component+".table")
            elif inv_param['DATA_PLOT_STEP'+inv_step]=="seis":
               if inv_param['FILT_PLOT_STEP'+inv_step]=="plain":
	          fsyndat=os.path.join(dinv,syndat+"seis"+inv_step+"-"+str(istat)+"-"+component+".table")
               elif inv_param['FILT_PLOT_STEP'+inv_step]=="tapered":
	          fsyndat=os.path.join(dinv,syndat+"seit"+inv_step+"-"+str(istat)+"-"+component+".table")
               elif inv_param['FILT_PLOT_STEP'+inv_step]=="filtered":
	          fsyndat=os.path.join(dinv,syndat+"seif"+inv_step+"-"+str(istat)+"-"+component+".table")
	    cmd = cmd+"cat "+fsyndat+" >> "+fallsyndat+"\n"
   os.system(cmd)
   f=open(fallsyndat,'r')
   for line in f:
      x,y=line.split()
      dat=abs(float(y))
      if (dat>=amaxf):
         amaxf=dat 
   f.flush()
   f.close()
#  File meca.dat
   f=open(fmeca,'w')
   line="0 0 "+str(round(float(best[0].strike)))+" "+str(round(float(best[0].dip)))+" "+str(round(float(best[0].rake)))+" 1 0 0 N"
   f.write(line)
   f.flush()
   f.close()
#  File meca.all & meca.sel
   fall=open(fallmeca,'w')
   fsel=open(fselmeca,'w')
   depths=[]
   nofdepths=5
   sdepth=float((float(inv_param['DEPTH_BOTTOMLIM'])-float(inv_param['DEPTH_UPPERLIM']))/nofdepths)
   for sol in all:
      rmisf=relativeMisfit(sol.misfit,best[0].misfit)
      if (len(depths)<5):   
         tdepth=float(inv_param['DEPTH_UPPERLIM'])
	 for idepth in range(nofdepths):
            if (sol.depth>tdepth):
	       adepth=tdepth
	    tdepth=tdepth+sdepth
         if not adepth in depths:
	    depths.append(adepth)
            line=str(float(sol.depth)/1000)+" "+str(rmisf)+" "+str(round(float(sol.strike)))+" "
	    line=line+str(round(float(sol.dip)))+" "+str(round(float(sol.rake)))+" 1 0 0\n" 
            fsel.write(line)
      line=str(sol.depth)+" "+str(rmisf)+" \n" 
      fall.write(line)
   fsel.flush() 
   fsel.close()
   fall.flush()
   fall.close()
#  File earthquakeinfo.dat
   f=open(feqinfo,'w')
   f.write("0 18 12 0 0 5 Event\n")
   f.write("3 18 10 0 0 5 "+inv_param['DATA_FILE']+"\n")
   f.write("8 18 10 0 0 5 "+dinv+"\n")
   f.write("0 16 10 0 0 5 Lat Lon\n")
   f.write("3 16 10 0 0 5 "+strDecim(slat,2)+" N "+strDecim(slon,2)+" E\n")
   f.write("0 15 10 0 0 5 Strike\n")
   f.write("0 14 10 0 0 5 Dip\n")
   f.write("0 13 10 0 0 5 Rake\n")
   if (inv_step == '1'):
      isol=4
   elif (inv_step == '2'):
      isol=2
   else:
      isol=1
   for i in range (isol):
      x=str(3+(i*2)) 
      f.write(str(x)+" 15 10 0 0 5 "+str(round(best[i].strike))+"\n")
      f.write(str(x)+" 14 10 0 0 5 "+str(round(best[i].dip))+"\n")
      f.write(str(x)+" 13 10 0 0 5 "+str(round(best[i].rake))+"\n")
   f.write("0 12 10 0 0 5 M@-0@-\n")
   ssmom=str(float(inv_param['SCALING_FACTOR'])*float(best[0].smom))
   if ('E' in ssmom.upper()):
     strsmom=string.split(ssmom.upper(),'E')
#     strsmom1,strsmom2=str(round(float(strsmom[0][0:4]))),strsmom[1]
     strsmom1,strsmom2=str(float(strsmom[0][0:4])),strsmom[1]
     f.write("3 12 10 0 0 5 "+strsmom1+"E"+strsmom2+"Nm\n")
   else:
     f.write("3 12 10 0 0 5 "+ssmom+"Nm\n")
   f.write("0 11 10 0 0 5 M@-w@-\n")
   f.write("3 11 10 0 0 5 "+strDecim(mw,1)+"\n")
   f.write("0 10 10 0 0 5 Depth\n")  
   f.write("3 10 10 0 0 5 "+strDecim((0.001*float(best[0].depth)),1)+"km\n")
   f.write("0 9 10 0 0 5 Duration\n")
   f.write("3 9 10 0 0 5 "+strDecim(best[0].risetime,2)+"s\n")
   f.write("0 8 10 0 0 5 Misfit\n")
   f.write("3 8 10 0 0 5 "+strDecim(best[0].misfit,3)+"\n")
   f.write("0 6 10 0 0 5 Method\n")
   if 'ampspec' in inv_param['MISFIT_MET_STEP'+inv_step]:
      f.write("3 6 10 0 0 5 Amplitude spectra\n")
   else:
      f.write("3 6 10 0 0 5 Time domain\n")
   f.write("0 5 10 0 0 5 Components\n")
   f.write("3 5 10 0 0 5 "+inv_param['COMP_2_USE']+"\n") 
   f.write("0 4 10 0 0 5 Phases\n")
   text_phases=""
   if 'p' in inv_param['PHASES_2_USE_ST'+inv_step]:
      text_phases=text_phases+"P "
   if 's' in inv_param['PHASES_2_USE_ST'+inv_step]:
      text_phases=text_phases+"S "
   if 'r' in inv_param['PHASES_2_USE_ST'+inv_step]:
      text_phases=text_phases+"Surface"
   if 'a'==inv_param['PHASES_2_USE_ST'+inv_step]:      
      text_phases="Whole trace"
   f.write("3 4 10 0 0 5 "+text_phases+"\n")
   f.write("0 3 10 0 0 5 Bandpass\n")
   f.write("3 3 10 0 0 5 "+inv_param['BP_F2_STEP'+inv_step]+" - "+inv_param['BP_F3_STEP'+inv_step]+" Hz\n")
   f.write("0 2 10 0 0 5 Traces\n")
   f.write("3 2 10 0 0 5 "+str(ntr)+" ("+str(nst)+" stations)\n")
   f.flush()
   f.close()
#  File ptsolution.gmt
#  General info
   f=open(fgmtplot,'w')
   line="pstext <"+feqinfo+" -X2 -Y21 -JX10/6 -R0/14/0/21 -K -P >"+fplot+"\n"
   f.write(line)
   if (inv_step == '1'):
#     Misfit vs Depth 
      fdep=open(fdepmis,'w')
      rmisfmax=0
      for sol in all:
         if (sol.strike == best[0].strike) & (sol.dip == best[0].dip) & (sol.rake == best[0].rake):
  	    rmisf=relativeMisfit(sol.misfit,best[0].misfit)
            if (rmisf > rmisfmax):
	       rmisfmax = rmisf
            line=str(float(sol.depth)/1000)+" "+str(rmisf)+"\n"
	    fdep.write(line)
      fdep.flush()      
      fdep.close()
      mmmax=strDecim(rmisfmax*1.2,3)
      mmm=strDecim(rmisfmax*0.2,3)
      mmmin=strDecim(-rmisfmax*0.2,3)
      if (abs(float(mmmin))<0.001):
         mmmin='-0.001'
         mmmax='0.011'
         mmm='0.001'
      line="psmeca "+fmeca+" -X0 -Y-3.5 -JX3/3 -R-1/1/-1/1 -P -V -W3/255/0/0 -T0"
      line=line+" -G255 -Sa14 -o -K -O >>"+fplot+"\n"
      f.write(line)
      rd1=str(float(inv_param['DEPTH_UPPERLIM'])-float(inv_param['DEPTH_STEP']))
      rd2=str(float(inv_param['DEPTH_BOTTOMLIM'])+float(inv_param['DEPTH_STEP']))
      deps=str(inv_param['DEPTH_STEP'])
      line="psxy < "+fdepmis+" -X10 -Y5 -JX7/2.5 -R"+rd1+"/"+rd2
      line=line+"/"+mmmin+"/"+mmmax+" -K -Sc0.1 -W1/0 -G255 -O -P "
      line=line+"-BSneWa"+deps+"f"+deps+":'Depth [km]':/f"+mmm+"a"+mmm+":'Rel.Misfit': >>"+fplot+"\n"
      f.write(line)
      line="psmeca "+fselmeca+" -X0 -Y0 -JX -R -K -O -Sa2 -o"
      line=line+" -T0 -W2/255/0/0 -G255 -P >>"+fplot+"\n"
      f.write(line)
#     Misfit vs strike-dip-slip (copying to files)    
      rmisfmax=0
      fstr=open(fstrmis,'w')
      fdip=open(fdipmis,'w')
      frak=open(frakmis,'w')
      for sol in all:
         if (sol.depth == best[0].depth) & (sol.dip == best[0].dip) & (sol.rake == best[0].rake):
  	    rmisf=relativeMisfit(sol.misfit,best[0].misfit)
            if (rmisf > rmisfmax):
	       rmisfmax = rmisf
            line=str(sol.strike)+" "+str(rmisf)+"\n"
	    fstr.write(line)
         if (sol.depth == best[0].depth) & (sol.strike == best[0].strike) & (sol.rake == best[0].rake):
	    rmisf=relativeMisfit(sol.misfit,best[0].misfit)
            if (rmisf > rmisfmax):
	       rmisfmax = rmisf
            line=str(sol.dip)+" "+str(rmisf)+"\n"
	    fdip.write(line)
         if (sol.depth == best[0].depth) & (sol.strike == best[0].strike) & (sol.dip == best[0].dip):
	    rmisf=relativeMisfit(sol.misfit,best[0].misfit)
            if (rmisf > rmisfmax):
	       rmisfmax = rmisf
            line=str(sol.rake)+" "+str(rmisf)+"\n"
	    frak.write(line)
      fstr.flush()
      fstr.close()
      fdip.flush()
      fdip.close()
      frak.flush()   
      frak.close()
      mmmax=strDecim(rmisfmax*1.2,3)
      mmm=strDecim(rmisfmax*0.2,3)
      mmmin=strDecim(-rmisfmax*0.2,3)
      if (abs(float(mmmin))<0.001):
         mmmin='-0.001'
         mmmax='0.011'
         mmm='0.001'
#     Misfit vs Strike   
      plstr1=str(best[0].strike-float(inv_param['MISFIT_SDS_RANGE'])-float(inv_param['MISFIT_SDS_TICK']))
      plstr2=str(best[0].strike+float(inv_param['MISFIT_SDS_RANGE'])+float(inv_param['MISFIT_SDS_TICK']))
      mcrg=str(inv_param['MISFIT_SDS_RANGE'])
      mctk=str(inv_param['MISFIT_SDS_TICK'])
      line="psxy < "+fstrmis+" -X-4.5 -Y-4.5 -JX3.5/2.5 -R"+plstr1+"/"+plstr2
      line=line+"/"+mmmin+"/"+mmmax+" -K -Sc0.1 -W1/0 -G255 -O -P -BSneWa"+mcrg+"f"+mctk
      line=line+":'Strike [deg]':/f"+mmm+"a"+mmm+":'Rel.Misfit': >>"+fplot+"\n"
      f.write(line)
      line="psxy <<beststrike -X0 -Y0 -JX -R -K -Sc0.1 -W1/0 -G0 -O -P >>"+fplot+"\n"
      f.write(line)
      f.write(str(best[0].strike)+" 0\n")
      f.write("beststrike\n")
#     Misfit vs Dip
      pldip1=str(best[0].dip-float(inv_param['MISFIT_SDS_RANGE'])-float(inv_param['MISFIT_SDS_TICK']))
      pldip2=str(best[0].dip+float(inv_param['MISFIT_SDS_RANGE'])+float(inv_param['MISFIT_SDS_TICK']))
      line="psxy < "+fdipmis+" -X4 -Y0 -JX -R"+pldip1+"/"+pldip2
      line=line+"/"+mmmin+"/"+mmmax+" -K -Sc0.1 -W1/0 -G255 -O -P -BSnewa"+mcrg+"f"+mctk
      line=line+":'Dip [deg]':/f"+mmm+"a"+mmm+":'': >>"+fplot+"\n"
      f.write(line)
      line="psxy <<bestdip -X0 -Y0 -JX -R -K -Sc0.1 -W1/0 -G0 -O -P >>"+fplot+"\n"
      f.write(line)
      f.write(str(best[0].dip)+" 0\n")
      f.write("bestdip\n")
#     Misfit vs Rake
      plrak1=str(best[0].rake-float(inv_param['MISFIT_SDS_RANGE'])-float(inv_param['MISFIT_SDS_TICK']))
      plrak2=str(best[0].rake+float(inv_param['MISFIT_SDS_RANGE'])+float(inv_param['MISFIT_SDS_TICK']))
      line="psxy < "+frakmis+" -X4 -Y0 -JX -R"+plrak1+"/"+plrak2
      line=line+"/"+mmmin+"/"+mmmax+" -K -Sc0.1 -W1/0 -G255 -O -P -BSnewa"+mcrg+"f"+mctk
      line=line+":'Rake [deg]':/f"+mmm+"a"+mmm+":'': >>"+fplot+"\n"
      f.write(line)
      line="psxy <<bestrake -X0 -Y0 -JX -R -K -Sc0.1 -W1/0 -G0 -O -P >>"+fplot+"\n"
      f.write(line)
      f.write(str(best[0].rake)+" 0\n")
      f.write("bestrake\n")
      shiftx,shifty="-13.5","-4"
   elif (inv_step == '2'):
      line="psmeca "+fmeca+" -X0 -Y-3.5 -JX3/3 -R-1/1/-1/1 -P -V -W3/255/0/0 "
      line=line+"-G255/0/0 -Sa14 -o -K -O >>"+fplot+"\n"
      f.write(line)
#     Misfit vs Location
      rmisfmax=0
      rmi=0.2
      fen=open(fenmis,'w')
      ftim=open(ftimmis,'w')
      eastmin=float(inv_param['ORIG_EAST_SHIFT'])+float(inv_param['REL_EAST_1'])
      eastmax=float(inv_param['ORIG_EAST_SHIFT'])+float(inv_param['REL_EAST_2'])
      northmin=float(inv_param['ORIG_NORTH_SHIFT'])+float(inv_param['REL_NORTH_1'])
      northmax=float(inv_param['ORIG_NORTH_SHIFT'])+float(inv_param['REL_NORTH_2'])
      plen=str(1.2*int(0.001*max(1000,abs(float(best[0].rest)),abs(float(best[0].rnor)),\
           abs(eastmin),abs(eastmax),abs(northmin),abs(northmax))))
#      plen=str(1.2*int(0.001*max(abs(float(best[0].rest)),abs(float(best[0].rnor)),\
#           abs(eastmin),abs(eastmax),abs(northmin),abs(northmax))))
      locrgl=loctkl=str(float(plen)/3)     
      ptimemin=float(inv_param['ORIG_TIME'])+float(inv_param['REL_TIME_1'])
      ptimemax=float(inv_param['ORIG_TIME'])+float(inv_param['REL_TIME_2'])
      ptime1=str(-2+round(min(float(best[0].time),ptimemin)))
      ptime2=str(2+round(max(float(best[0].time),ptimemax)))
      timrgl=timtkl=str(round((float(ptime2)-float(ptime1))/4))
      for sol in all:
         if (sol.strike == best[0].strike) & (sol.dip == best[0].dip) & (sol.rake == best[0].rake):
	    rmisf=relativeMisfit(sol.misfit,best[0].misfit)
            if (rmisf > rmisfmax):
	       rmisfmax = rmisf
	    if (rmisf > rmi):
	       rmisf=rmi
	    prmisf=(0.2-rmisf)*1.25
	    if (prmisf <= 0):
	       prmisf=0
            line=str(float(sol.rest)/1000)+" "+str(float(sol.rnor)/1000)+" "+str(prmisf)+"\n"
	    fen.write(line)
	    ftim.write("0 "+str(sol.time)+" "+str(prmisf)+"\n")
      fen.flush()
      fen.close()
      ftim.flush()
      ftim.close()
      line="psxy <<startpoints -X7.5 -Y1.5 -JX6/6 -R-"+plen+"/"+plen
      line=line+"/-"+plen+"/"+plen+" -K -Sx0.3 -W2/100 -G100 -O -P -BSWnea"+locrgl+"f"+loctkl
      line=line+":'East [km]':/f"+locrgl+"a"+loctkl+":'North [km]': >>"+fplot+"\n"
      f.write(line)
      f.write("0 0\n")
      f.write("startpoints\n")
      line="psxy <"+fenmis+" -X0 -Y0 -JX -R -K -Sc -W1/100 -G100 -O -P >>"+fplot+"\n"
      f.write(line)
      line="psxy << bestsol -X0 -Y0 -JX -R -K -Sc0.25 -W5/255/0/0 -O -P >>"+fplot+"\n"
      f.write(line)
      f.write(str(0.001*float(best[0].rest))+" "+str(0.001*float(best[0].rnor))+"\n")
      f.write("bestsol\n")
      line="psxy <"+ftimmis+" -X8.5 -Y0 -JX1/6 -Sc -R-2/2/"+ptime1+"/"+ptime2+" -K -O -P -BWsne:'':"
      line=line+"/f"+timrgl+"a"+timtkl+":'Time [s]': >>"+fplot+"\n"
      f.write(line)
      line="psxy << bestsolt -X0 -Y0 -JX -R -K -Sc0.25 -W5/255/0/0 -O -P >>"+fplot+"\n"
      f.write(line)
      f.write("0 "+str(float(best[0].time))+"\n")
      f.write("bestsolt\n")
      shiftx,shifty="-16","-5"
   else:
      shiftx,shifty="0","-7"
#  Fit header
   maxstatplot = int(inv_param['MAX_STAT_2_PLOT'])
   f.write("pstext <<fits -X"+shiftx+" -Y"+shifty+" -JX17/2 -R0/17/0/3 -K -O >>"+fplot+"\n")
   nstatplot=len(traces)
   ncomp=len(inv_param['COMP_2_USE'])
   spacex=0.5
   jumpx=((13-((ncomp-1)*spacex))/ncomp)+spacex
   if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
      fitdata_type="Amplitude Spectra"
   else:
      fitdata_type="Seismograms"
   if (nst > maxstatplot):
      nstatplot=maxstatplot
      f.write("0 2 12 0 0 5 Fit of "+fitdata_type+" (Closest "+str(maxstatplot)+" stations)\n")
   else:
      f.write("0 2 12 0 0 5 Fit of "+fitdata_type+"\n")
   f.write("0 1 10 0 0 5 Stat Dist Az Amax\n")
   usedcomp = inv_param['COMP_2_USE']
   i=0
   for letter in usedcomp:
      f.write(str(4.5+(i*jumpx))+" 1 10 0 0 5 "+comp_names[letter]+"\n")
      i=i+1
   f.write("fits\n")
#  Fit spectra or seismograms
   checkInvParam('DATA_PLOT_STEP1',inv_param['DATA_PLOT_STEP'+inv_step],('amsp','seis'))
   checkInvParam('FILT_PLOT_STEP1',inv_param['FILT_PLOT_STEP'+inv_step],('plain','tapered','filtered'))
   checkInvParam('AMPL_PLOT_STEP1',inv_param['AMPL_PLOT_STEP'+inv_step],('amax','norm'))

   if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
      x1,x2,y1,y2="0",inv_param['BP_F4_STEP'+inv_step],"0",str(amaxf)
      scale = asp_r = "/".join((x1,x2,y1,y2))
      asp_rd = asp_rs = asp_r
      tr_name=inv_param['DATA_PLOT_STEP'+inv_step]
   else:
      x1,x2=inv_param['START_PLOT_STEP'+inv_step],str(float(inv_param['LEN_PLOT_STEP'+inv_step])-float(inv_param['START_PLOT_STEP'+inv_step]))
      y1,y2=str(-amaxf),str(amaxf)
      scale = asp_r = "/".join((x1,x2,y1,y2))
      if inv_param['FILT_PLOT_STEP'+inv_step]=="plain":
         tr_name=inv_param['DATA_PLOT_STEP'+inv_step]
      elif inv_param['FILT_PLOT_STEP'+inv_step]=="tapered":   
         tr_name="seit"
      else:   
         tr_name="seif"
   tr_name=tr_name+inv_step

   asp_jxx = str(float(jumpx-(2*spacex)))
   asp_jxy = str(float(12.0/float(nstatplot)))
   asp_jx = asp_jxx+"/"+asp_jxy
   last_x=last_y=0
   istat=0
   jumpy=float(12.0/float(nstatplot))

   amax=amaxf
   amaxstat=[]
   for i in range(nstatplot):
      istat=istat+1
      amaxst=0
      for component in usedcomp:
         fdtrace=os.path.join(dinv,"dcd"+tr_name+"-"+str(istat)+"-"+component+".table")
         fstrace=os.path.join(dinv,"dcs"+tr_name+"-"+str(istat)+"-"+component+".table")
	 if os.path.isfile(fdtrace):
            fdat=open(fdtrace,'r')
            for line in fdat:
               x,y=line.split()
               dat=abs(float(y))
               if (dat>=amaxst):
                  amaxst=dat 
	    fdat.flush()     
            fdat.close()
            fsyn=open(fstrace,'r')
            for line in fsyn:
               x,y=line.split()
               dat=abs(float(y))
               if (dat>=amaxst):
                  amaxst=dat 
	    fsyn.flush()   
            fsyn.close()
      amaxstat.append(amaxst)  

   f.write("pstext <<disaz -K -O -X0 -Y-12 -JX17/12 -R0/17/0/"+str(nstatplot)+" -P >>"+fplot+"\n") 
   for i in range(nstatplot):
      line="0 "+str(nstatplot-i-0.5)+" 8 0 0 5 "+str(i+1)+" "+traces[i].stat
      line=line+" "+strDecim(traces[i].dist,1)+" "+strDecim(traces[i].azi,1)
      if ['AMPL_PLOT_STEP'+inv_step]=='amax':
         line=line+" "+strDecim((amax/100000),3)+"\n"
      else:
         line=line+" "+strDecim(((amaxstat[i])/100000),3)+"\n"
      f.write(line)
   f.write("disaz\n")
   if (inv_step == '1'):
      faz=open(fazi,"w")
      for trace in traces:
         faz.write(str(trace.azi)+" "+str(trace.stat)+" "+str(trace.comp)+" "+str(trace.quality)+"\n")
      faz.flush()
      faz.close()
   istat=0
   for i in range(nstatplot):
      if inv_param['AMPL_PLOT_STEP'+inv_step]=="amax":
         if inv_param['DATA_PLOT_STEP'+inv_step]=="seis":
            asp_rd = "/".join((x1,x2,str(-amaxf*3),str(amaxf)))
            asp_rs = "/".join((x1,x2,str(-amaxf*2),str(amaxf*2)))
            asp_rt = "/".join((x1,x2,"0","4")) 
      else:
         if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
            asp_rd = asp_rs = asp_r = "/".join((x1,x2,"0",str(float(amaxstat[i]))))
         else:
            asp_rd = "/".join((x1,x2,str(-float(amaxstat[i])*3),str(float(amaxstat[i]))))
            asp_rs = "/".join((x1,x2,str(-float(amaxstat[i])*2),str(float(amaxstat[i])*2)))
            asp_rt = "/".join((x1,x2,"0","4"))
      istat=istat+1
      icomp=0
      for component in usedcomp:
         icomp=icomp+1   
	 fdtrace=os.path.join(dinv,"dcd"+tr_name+"-"+str(istat)+"-"+component+".table")
	 fstrace=os.path.join(dinv,"dcs"+tr_name+"-"+str(istat)+"-"+component+".table")
	 fttrace=os.path.join(dinv,"taper-"+str(istat)+"-"+component)
	 if os.path.isfile(fdtrace):
            next_x=4.5+((icomp-1)*jumpx)
            next_y=0.05+((nstatplot-istat)*jumpy)
            asp_x=str(next_x-last_x)
            asp_y=str(next_y-last_y)
            last_x=next_x
            last_y=next_y
	    if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
               line="psxy <"+fdtrace+" -X"+asp_x+" -Y"+asp_y+" -BWSNE -JX"+asp_jx
               linedata=line+" -R"+asp_rd+" -P -K -O -W1/255/0/0 -G200/0/0 >>"+fplot+"\n"
            else:
	       line="psxy <"+fdtrace+" -X"+asp_x+" -Y"+asp_y+" -BWSNE -JX"+asp_jx
               linedata=line+" -R"+asp_rd+" -P -K -O -W2/255/0/0 >>"+fplot+"\n"
	    f.write(linedata)
            linesynt="psxy <"+fstrace+" -R"+asp_rs+" -BWSNE -X0 -Y0 -JX -P -K -O -W1/0 >>"+fplot+"\n"
            f.write(linesynt)
            if inv_param['DATA_PLOT_STEP'+inv_step]=="seis":
	       linesynt="psxy <"+fttrace+" -R"+asp_rt+" -BWSNE -X0 -Y0 -JX -P -K -O -W1/100 -G150 >>"+fplot+"\n"
               f.write(linesynt)
         else:
	    print fdtrace+" not found"
   icomp=0
   for comp in usedcomp:
       icomp=icomp+1
       next_x=4.5+((icomp-1)*jumpx)
       next_y=0.0
       asp_x=str(next_x-last_x)
       asp_y=str(next_y-last_y)
       last_x=next_x
       last_y=next_y
       if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
          line="psxy <<xscale -X"+asp_x+" -Y"+asp_y+" -JX"+asp_jx+" -R -P -K -O "\
               +"-BSa"+inv_param['BP_F4_STEP'+inv_step]+"f"+inv_param['BP_F4_STEP'+inv_step]\
	       +":'Frequency [Hz]': >>"+fplot+"\n"
       else:
          line="psxy <<xscale -X"+asp_x+" -Y"+asp_y+" -JX"+asp_jx+" -R -P -K -O -BSa"\
               +inv_param['TICK_PLOT_STEP'+inv_step]+"f"+inv_param['TICK_PLOT_STEP'+inv_step]\
	       +":'Time [s]': >>"+fplot+"\n"
       f.write(line)
       f.write("0 0\n0 0\nxscale\n")
   f.write("pstext <<endplot -O -X0 -Y0 -JX -R -P >>"+fplot+"\n")
   f.write("endplot\n")
   f.flush()
   f.close()
   cmd = "source "+fgmtplot
   os.system(cmd)


def plotEikSolution(inv_step,inv_param,all,best,traces):
   print "Plotting results inversion step "+inv_step+"..."
   slat=inv_param['LATITUDE_NORTH']
   slon=inv_param['LONGITUDE_EAST']
   dinv=inv_param['INVERSION_DIR']
   fmeca=os.path.join(dinv,'step'+inv_step+'.meca.dat')
   fallmeca=os.path.join(dinv,'step'+inv_step+'.meca.all')
   fselmeca=os.path.join(dinv,'step'+inv_step+'.meca.sel')
   feqinfo=os.path.join(dinv,'step'+inv_step+'.earthquakeinfo.dat')
   fgmtplot=os.path.join(dinv,'step'+inv_step+'.eiksolution.gmt')
   fplot=os.path.join(dinv,'step'+inv_step+'.eiksolution.ps')
   if (inv_step == '3'):
      fcolor=os.path.join(dinv,'step'+inv_step+'.color.cpt')
      fborder=os.path.join(dinv,'step'+inv_step+'.border.dat')
      fdiscrete=os.path.join(dinv,'step'+inv_step+'.discrete.dat')
      fradmis=os.path.join(dinv,'step'+inv_step+'.rad_mis.dat')
      frrvmis=os.path.join(dinv,'step'+inv_step+'.rrv_mis.dat')
      fnukmis=os.path.join(dinv,'step'+inv_step+'.nuk_mis.dat')
      frismis=os.path.join(dinv,'step'+inv_step+'.ris_mis.dat')
   fallsyndat=os.path.join(dinv,'step'+inv_step+'.amsp-all.table')
#  Maximal value (file amsp-all.table)
   amaxf = 0
   istat=0
   cmd=""
#  Magnitude
   mw = m0tomw(float(inv_param['SCALING_FACTOR'])*float(best[0].smom))

   ntr=0
   nst=0
   localstations=[]
   for trace in traces:
      ntr=ntr+len(trace.comp)
      if trace.stat not in localstations:
         localstations.append(trace.stat)	 
         nst=nst+1
      istat=istat+1
      for component in trace.comp:
         for syndat in ('s','d'):
	    if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
               fsyndat=os.path.join(dinv,syndat+"amsp"+inv_step+"-"+str(istat)+"-"+component+".table")
            elif inv_param['DATA_PLOT_STEP'+inv_step]=="seis":
               if inv_param['FILT_PLOT_STEP'+inv_step]=="plain":
	          fsyndat=os.path.join(dinv,syndat+"seis"+inv_step+"-"+str(istat)+"-"+component+".table")
               elif inv_param['FILT_PLOT_STEP'+inv_step]=="tapered":
	          fsyndat=os.path.join(dinv,syndat+"seit"+inv_step+"-"+str(istat)+"-"+component+".table")
               elif inv_param['FILT_PLOT_STEP'+inv_step]=="filtered":
	          fsyndat=os.path.join(dinv,syndat+"seif"+inv_step+"-"+str(istat)+"-"+component+".table")
	    cmd = cmd+"cat "+fsyndat+" >> "+fallsyndat+"\n"
   os.system(cmd)
   f=open(fallsyndat,'r')
   for line in f:
      x,y=line.split()
      dat=abs(float(y))
      if (dat>=amaxf):
         amaxf=dat 
   f.flush()
   f.close()
#  File meca.dat
   f=open(fmeca,'w')
   line="0 0 "+str(round(best[0].strike))+" "+str(round(best[0].dip))+" "+str(round(best[0].rake))+" 1 0 0 N"
   f.write(line)
   f.flush()
   f.close()
#  File meca.all & meca.sel
   fall=open(fallmeca,'w')
   fsel=open(fselmeca,'w')
   depths=[]
   nofdepths=5
   sdepth=float((float(inv_param['DEPTH_BOTTOMLIM'])-float(inv_param['DEPTH_UPPERLIM']))/nofdepths)
   for sol in all:
      rmisf=relativeMisfit(sol.misfit,best[0].misfit)
      if (len(depths)<5):   
         tdepth=float(inv_param['DEPTH_UPPERLIM'])
	 for idepth in range(nofdepths):
            if (sol.depth>tdepth):
	       adepth=tdepth
	    tdepth=tdepth+sdepth
         if not adepth in depths:
	    depths.append(adepth)
            line=str(float(sol.depth)/1000)+" "+str(rmisf)+" "+str(round(float(sol.strike)))+" "
	    line=line+str(round(float(sol.dip)))+" "+str(round(float(sol.rake)))+" 1 0 0\n" 
            fsel.write(line)
      line=str(sol.depth)+" "+str(rmisf)+" \n" 
      fall.write(line)
   fsel.flush() 
   fsel.close()
   fall.flush()
   fall.close()
#  get Eikonal Source Model
   outline=[]
   tdsm=[]
   origin=[]
   center=[]
   area_m2,average_slip_m=-1e6,0.
   feikomodel=os.path.join(inv_param['INVERSION_DIR'],'best_eikonal-psm.info')
   f = open(feikomodel,'r')
   lineorigin=linecenter=lineoutline=lineeikonalgrid=linearea=False
   discrete_source_tmin=99999.
   discrete_source_tmax=-99999.
   for line in f:
      splittedline=line.split()
      if (len(splittedline)==1) and (splittedline[0]=='origin'):
         lineorigin=True
      else:
         if lineorigin:
	    origin=splittedline
	    lineorigin=False
      if (len(splittedline)==1) and (splittedline[0]=='center'):
         linecenter=True
      else:
         if linecenter:
	    center=splittedline
	    linecenter=False
      if (len(splittedline)==1) and (splittedline[0]=='outline'):
         lineoutline=True
      else:
         if lineoutline:
	    if len(splittedline)==5:
	       north,east,down,along_strike,down_dip=splittedline
	       outline.append(Spatial_coordinates(east,north,down))
	    else:
 	       lineoutline=False
      if (len(splittedline)==1) and (splittedline[0]=='eikonal-grid'):
         lineeikonalgrid=True
      else:
         if lineeikonalgrid:
	    if len(splittedline)<2:
	       lineeikonalgrid=False
	    if len(splittedline)==9:
	       north,east,down,alongstrike,downdip,time,alfa,beta,rho=splittedline
               ftime=float(time)
	       if (int(float(time))==-1):
	          print "skipped discrete source"
	       else:
  	          if (ftime<discrete_source_tmin):
	             discrete_source_tmin=ftime
	          if (ftime>discrete_source_tmax):
	             discrete_source_tmax=ftime	 
                  tdsm.append(Discretesource(north,east,down,alongstrike,downdip,time,alfa,beta,rho))	           
      if (len(splittedline)==1) and (splittedline[0]=='area'):
         linearea=True
      else:
         if linearea:
	    area_m2=float(line)
	    linearea=False
   f.flush()
   f.close() 
   duration=discrete_source_tmax-discrete_source_tmin
   summed_shear_modulus=0.
   idiscretesource=0
   for discretesource in tdsm:
      idiscretesource=idiscretesource+1
      lame_lambda,lame_mu=vel2lame(float(discretesource.alfa),\
                                   float(discretesource.beta),\
				   float(discretesource.rho))
      summed_shear_modulus=summed_shear_modulus+lame_mu
   average_shear_modulus=summed_shear_modulus/idiscretesource
   truesmom=float(inv_param['SCALING_FACTOR'])*float(best[0].smom)
   average_slip_m=calculateAverageSlip(truesmom,area_m2,average_shear_modulus)
   if area_m2<0:
      print "WARNING: wrong area value from best_eikonal file: ",area_m2
      area_m2=calculateArea(inv_param,best[0].depth,best[0].radius,best[0].dip)
      print "recalculated to :",area_m2
   area_km2=area_m2/1000000.
   fixed_shear_modulus=36.e9
   old_average_slip_m=calculateAverageSlip(best[0].smom,area_m2,fixed_shear_modulus)
   if (average_slip_m <> old_average_slip_m):
      print "WARNING: old average slip in meters: ",old_average_slip_m
      print "         new average slip in meters: ",average_slip_m     
#  Build rupture plot
   f=open(fcolor,'w')
   if duration <=0.05:
      tstep=0.01   
   if duration <=0.1:
      tstep=0.02
   elif duration <=0.5:
      tstep=0.1
   elif duration<=1:
      tstep=0.2
#   elif duration<=5:
#      tstep=1
   elif duration<=10:
      tstep=1
   elif duration<=30:
      tstep=5
   else:
      tstep=10
   nsteps=int(duration/tstep)+1   
   stepcolor=int(255/nsteps)-1
   dstart,dend,white,red,blue=0.,tstep," 255 255 255 ",255,0
   while (dstart<duration):
#      f.write(str(dstart)+white+str(dend)+white+"\n")
      actualcolor=str(red)+" 255 "+str(blue)
      f.write(" "+str(dstart)+" "+actualcolor+" "+str(dend)+" "+actualcolor+" \n")
      dstart=dend
      dend=dstart+tstep
      red,blue=red-stepcolor,blue+stepcolor
   f.write("B	236	140	255\n")
   f.write("F	255	255	255\n")
   f.write("N	255	0	255")
   f.flush()   
   f.close()
#  File earthquakeinfo.dat
   f=open(feqinfo,'w')
   f.write("0 18 12 0 0 5 Event\n")
   f.write("3 18 10 0 0 5 "+inv_param['DATA_FILE']+"\n")
   f.write("8 18 10 0 0 5 "+dinv+"\n")
   f.write("0 16 10 0 0 5 Lat Lon\n")
   f.write("3 16 10 0 0 5 "+strDecim(slat,2)+" N "+strDecim(slon,2)+" E\n")
   f.write("0 15 10 0 0 5 Strike\n")
   f.write("0 14 10 0 0 5 Dip\n")
   f.write("0 13 10 0 0 5 Rake\n")
   if (inv_step == '1'):
      isol=4
   elif (inv_step == '2'):
      isol=2
   else:
      isol=1
   for i in range (isol):
      x=str(3+(i*2)) 
      f.write(str(x)+" 15 10 0 0 5 "+str(round(best[i].strike))+"\n")
      f.write(str(x)+" 14 10 0 0 5 "+str(round(best[i].dip))+"\n")
      f.write(str(x)+" 13 10 0 0 5 "+str(round(best[i].rake))+"\n")
   f.write("0 12 10 0 0 5 M@-0@-\n")
   ssmom=str(float(inv_param['SCALING_FACTOR'])*float(best[0].smom))
   if ('E' in ssmom.upper()):
     strsmom=string.split(ssmom.upper(),'E')
#     strsmom1,strsmom2=str(round(float(strsmom[0][0:4]))),strsmom[1]
     strsmom1,strsmom2=str(float(strsmom[0][0:4])),strsmom[1]
     f.write("3 12 10 0 0 5 "+strsmom1+"E"+strsmom2+"Nm\n")
   else:
     f.write("3 12 10 0 0 5 "+ssmom+"Nm\n")
   f.write("0 11 10 0 0 5 M@-w@-\n")
   f.write("3 11 10 0 0 5 "+strDecim(mw,1)+"\n")
   f.write("0 10 10 0 0 5 Depth\n")  
   f.write("3 10 10 0 0 5 "+strDecim((0.001*float(best[0].depth)),1)+"km\n")
   f.write("6 10 10 0 0 5 Duration\n")  
   f.write("9 10 10 0 0 5 "+strDecim(best[0].risetime,1)+"+"+strDecim(duration,1)+"s\n")
   f.write("0 9 10 0 0 5 Radius\n")  
   f.write("3 9 10 0 0 5 "+strDecim((0.001*float(best[0].radius)),1)+"km\n")
   f.write("6 9 10 0 0 5 Area\n")  
   f.write("9 9 10 0 0 5 "+strDecim(area_km2,1)+"km@+2@+\n")
   f.write("0 8 10 0 0 5 Average Slip\n")  
   f.write("3 8 10 0 0 5 "+strDecim(average_slip_m,3)+"m\n")
   f.write("6 8 10 0 0 5 RelRuptVel\n")  
   f.write("9 8 10 0 0 5 "+strDecim(float(best[0].relruptvel),1)+"\n")
   f.write("0 7 10 0 0 5 Nucleation\n")  
   f.write("3 7 10 0 0 5 x: "+strDecim((0.001*float(best[0].nuklx)),2)+"km\n")
   f.write("6 7 10 0 0 5 y: "+strDecim((0.001*float(best[0].nukly)),2)+"km\n")
   f.write("0 6 10 0 0 5 Misfit\n")
   f.write("3 6 10 0 0 5 "+strDecim(best[0].misfit,3)+"\n")
   f.write("0 5 10 0 0 5 Method\n")
   if 'ampspec' in inv_param['MISFIT_MET_STEP'+inv_step]:
      f.write("3 5 10 0 0 5 Amplitude spectra\n")
   else:
      f.write("3 5 10 0 0 5 Time domain\n")
   f.write("0 4 10 0 0 5 Components\n")
   f.write("3 4 10 0 0 5 "+inv_param['COMP_2_USE']+"\n") 
   f.write("0 3 10 0 0 5 Phases\n")
   text_phases=""
   if 'p' in inv_param['PHASES_2_USE_ST'+inv_step]:
      text_phases=text_phases+"P "
   if 's' in inv_param['PHASES_2_USE_ST'+inv_step]:
      text_phases=text_phases+"S "
   if 'r' in inv_param['PHASES_2_USE_ST'+inv_step]:
      text_phases=text_phases+"Surface"
   if 'a'==inv_param['PHASES_2_USE_ST'+inv_step]:      
      text_phases="Whole trace"
   f.write("3 3 10 0 0 5 "+text_phases+"\n")
   f.write("0 2 10 0 0 5 Bandpass\n")
   f.write("3 2 10 0 0 5 "+inv_param['BP_F2_STEP'+inv_step]+" - "+inv_param['BP_F3_STEP'+inv_step]+" Hz\n")
   f.write("0 1 10 0 0 5 Traces\n")
   f.write("3 1 10 0 0 5 "+str(ntr)+" ("+str(nst)+" stations)\n")
   f.flush()
   f.close()
#  File ptsolution.gmt
#  General info
   f=open(fgmtplot,'w')
   line="pstext <"+feqinfo+" -X2 -Y21 -JX10/6 -R0/14/0/21 -K -P >"+fplot+"\n"
   f.write(line)
   if (inv_step == '3'):
      line="psmeca "+fmeca+" -X0 -Y-3.5 -JX3/3 -R-1/1/-1/1 -P -V -W3/255/0/0 "
      line=line+"-G255/0/0 -Sa14 -o -K -O >>"+fplot+"\n"
      f.write(line)
      line="psmeca "+fmeca+" -X0 -Y0 -T1 -JX -R -P -V -W10/0 -Sa14 -o -K -O >>"+fplot+"\n"
      f.write(line)
#     Outline (copying to file)
      fbord=open(fborder,'w')
      center_north,center_east,center_down=center[0],center[1],center[2]
      ipob=0
      for point_on_border in outline:       
	ipob=ipob+1
	north=0.001*(float(point_on_border.north)-float(center_north))
	east=0.001*(float(point_on_border.east)-float(center_east))
	up=-0.001*(float(point_on_border.down)-float(center_down))
        distance=math.sqrt(north*north+east*east+up*up)
        gamma=math.acos((east*math.sin(math.radians(best[0].strike))+\
	      north*math.cos(math.radians(best[0].strike)))/distance)
	alongstrike=distance*math.cos(gamma)
	downdip=distance*math.sin(gamma)
	if (up<0):
	   downdip=-downdip
	fbord.write(str(alongstrike)+" "+str(downdip)+"\n")
        if (ipob==1):
	   last_bordline=str(alongstrike)+" "+str(downdip)+"\n"
      fbord.write(last_bordline)
      fbord.flush()
      fbord.close()      
#     Discretized source (copying to file)
      fdisc=open(fdiscrete,'w')
      print "DISCRETE_TIME"
      print "DURATION "+str(duration)
      print "START    "+str(discrete_source_tmin)
      print "END      "+str(discrete_source_tmax)
      for point_inside in tdsm:       
#	north=0.001*(float(point_inside.north)-float(center_north))
#	east=0.001*(float(point_inside.east)-float(center_east))
#	up=-0.001*(float(point_inside.down)-float(center_down))
#        time=float(point_inside.time)-discrete_source_tmin
#	print"point inside "+str(point_inside.time)+" "+str(time)
#        distance=math.sqrt(north*north+east*east+up*up)
#        gamma=math.acos((east*math.sin(math.radians(best[0].strike))+\
#	      north*math.cos(math.radians(best[0].strike)))/distance)
#	alongstrike=distance*math.cos(gamma)
#	downdip=distance*math.sin(gamma)
#	if (up<0):
#	   downdip=-downdip
#	fdisc.write(str(alongstrike)+" "+str(downdip)+" "+str(time)+"\n")
	salongstrike=str(0.001*float(point_inside.alongstrike))
	supdip=str(-0.001*float(point_inside.downdip))
	stime=str(point_inside.time)
	fdisc.write(salongstrike+" "+supdip+" "+stime+"\n")
      fdisc.flush()
      fdisc.close()      
#     Misfit vs radius-rrv-nukl-risetime (copying to files)    
      rmisfmax=0
      frad=open(fradmis,'w')
      frrv=open(frrvmis,'w')
      fnuk=open(fnukmis,'w')
      fris=open(frismis,'w')
      for sol in all:
         if (sol.depth == best[0].depth) & (sol.strike == best[0].strike) & \
	    (sol.dip == best[0].dip) & (sol.rake == best[0].rake):
	    rmisf=relativeMisfit(sol.misfit,best[0].misfit)
	    if (sol.relruptvel == best[0].relruptvel) & (sol.risetime == best[0].risetime):
	       bestrnkx=float(best[0].nuklx)/float(best[0].radius)
	       bestrnky=float(best[0].nukly)/float(best[0].radius)
	       solnkx=float(sol.nuklx)/float(sol.radius)
	       solnky=float(sol.nukly)/float(sol.radius)       
	       rnklim=0.1
#	       if (abs(bestrnkx-solnkx)<rnklim) and (abs(bestrnky-solnky)<rnklim):
#   	          frad.write(str(0.001*float(sol.radius))+" "+str(rmisf)+"\n")
#                 if (rmisf > rmisfmax):
#	             rmisfmax = rmisf
	       frad.write(str(0.001*float(sol.radius))+" "+str(rmisf)+"\n")
               if (rmisf > rmisfmax):
	          rmisfmax = rmisf
	    if (sol.radius == best[0].radius) & (sol.nuklx == best[0].nuklx) & \
	       (sol.nukly == best[0].nukly) & (sol.risetime == best[0].risetime):	    
	       frrv.write(str(sol.relruptvel)+" "+str(rmisf)+"\n")
               if (rmisf > rmisfmax):
	          rmisfmax = rmisf
	    if (sol.radius == best[0].radius) & (sol.nuklx == best[0].nuklx) & \
	       (sol.nukly == best[0].nukly) & (sol.relruptvel == best[0].relruptvel):	    
	       fris.write(str(sol.risetime)+" "+str(rmisf)+"\n")
               if (rmisf > rmisfmax):
	          rmisfmax = rmisf
            if (sol.radius == best[0].radius) & (sol.relruptvel == best[0].relruptvel) & \
	       (sol.risetime == best[0].risetime):
	       rrmisf=(0.1-rmisf)*2
   	       if (rrmisf>0):
  	          fnuk.write(str(0.001*float(sol.nuklx))+" "+str(0.001*float(sol.nukly))+" "+str(rrmisf)+"\n")
      fris.flush()   
      fris.close()
      frad.flush()   
      frad.close()
      frrv.flush()
      frrv.close()
      fnuk.flush()
      fnuk.close()
      mmmax=strDecim(rmisfmax*1.2,3)
      mmm=strDecim(rmisfmax*0.2,3)
      mmmin=strDecim(-rmisfmax*0.2,3)
      if (abs(float(mmmin))<0.001):
         mmmin='-0.001'
         mmmax='0.011'
         mmm='0.002'
#     Misfit vs Radius   
      f.write("psxy < "+fradmis+" -X9.5 -Y0.5 -JX3.5l/2.5 -R0.1/1000/"+mmmin+"/"+mmmax+" -K -Sc0.1 -W1/0\
               -G255 -O -P -BSneWa10f10:'Radius [km]':/f"+mmm+"a"+mmm+":'Rel.Misfit': >>"+fplot+"\n")
      f.write("psxy <<bestradius -X0 -Y0 -JX -R -K -Sc0.1 -W1/0 -G0 -O -P >>"+fplot+"\n")
      f.write(str(0.001*float(best[0].radius))+" 0\n")
      f.write("bestradius\n")
#     Misfit vs RelRuptVel
      f.write("psxy < "+frrvmis+" -X4.0 -Y0 -JX3.5/2.5 -R0.0/1.5/"+mmmin+"/"+mmmax+" -K -Sc0.1 -W1/0\
               -G255 -O -P -BSnewa0.5f0.5:'RelRuptVel':/f"+mmm+"a"+mmm+":'Rel.Misfit': >>"+fplot+"\n")
      f.write("psxy <<bestrrv -X0 -Y0 -JX -R -K -Sc0.1 -W1/0 -G0 -O -P >>"+fplot+"\n")
      f.write(str(float(best[0].relruptvel))+" 0\n")
      f.write("bestrrv\n")
#     Misfit vs Nucleation
      plnuk=str((3.5/3)*float(best[0].radius))
      plnuko=str(0.1*round(0.01*float(plnuk)))
      nukrg=nuktk=str(0.001*int(0.5*float(best[0].radius)))
#      f.write("psxy << circ_fault -X-2 -Y4.5 -JX3.5/3.5 -R-"+plnuko+"/"+plnuko+"/-"+plnuko+"/"+plnuko\
#              +" -K -Sc3 -W1/225 -G225 -O -P -BSWna"+nukrg+"f"+nuktk+":'along strike [km]':/f"\
#	      +nukrg+"a"+nuktk+":'downdip [km]': >>"+fplot+"\n")
#      f.write("0 0\n")	      
#      f.write("circ_fault\n")	      
      f.write("psxy < "+fborder+" -X-2 -Y4.5 -JX3.5/3.5 -R-"+plnuko+"/"+plnuko+"/-"+plnuko+"/"+plnuko\
              +" -K -W1/0 -G255 -O -P -BSWna"+nukrg+"f"+nuktk+":'along strike [km]':/f"\
	      +nukrg+"a"+nuktk+":'downdip [km]': >>"+fplot+"\n")
#      f.write("psxy < "+fnukmis+" -X0 -Y0 -R -JX -K -Sc -W1/0 -G255 -O -P >>"+fplot+"\n")   
      f.write("pscontour <"+fdiscrete+" -C"+fcolor+" -W1/0 -I -Gd2 -X0 -Y0 -R -JX -K -O -P >>"+fplot+"\n")
      f.write("#psxy < "+fdiscrete+" -X0 -Y0 -R -JX -K -Sx.025 -W1/0 -G0 -O -P >>"+fplot+"\n")
      f.write("psxy <<bestnukl -X0 -Y0 -JX -R -K -Sx0.2 -W2/0 -O -P >>"+fplot+"\n")
      f.write(str(0.001*float(best[0].nuklx))+" "+str(-0.001*float(best[0].nukly))+" \n")
      f.write("bestnukl\n")
      plnukz1=str(0.001*(-float(best[0].depth)-math.sin(math.radians(float(best[0].dip)))*float(plnuk)))
      plnukz2=str(0.001*(-float(best[0].depth)+math.sin(math.radians(float(best[0].dip)))*float(plnuk)))
      nukrgz=nuktkz=str(0.1*round(0.01*0.5*float(best[0].radius)*math.sin(math.radians(float(best[0].dip)))))
      f.write("psxy << z_axis -X0 -Y0 -JX -R-"+plnuk+"/"+plnuk+"/"+plnukz1+"/"+plnukz2\
              +" -K -Sc0.3 -W1/225 -G225 -O -P -BE"+nukrg+"f"+nuktk+":' ':/f"\
	      +nukrgz+"a"+nuktkz+":'depth [km]': >>"+fplot+"\n")      
      f.write("100 100\n")	      
      f.write("z_axis\n")	      
      shiftx,shifty="-11.5","-8.5"
   else:
      shiftx,shifty="0","-7"
#  Fit header
   maxstatplot = int(inv_param['MAX_STAT_2_PLOT'])
   f.write("pstext <<fits -X"+shiftx+" -Y"+shifty+" -JX17/2 -R0/17/0/3 -K -O >>"+fplot+"\n")
   nstatplot=len(traces)
   ncomp=len(inv_param['COMP_2_USE'])
   spacex=0.5
   jumpx=((13-((ncomp-1)*spacex))/ncomp)+spacex
   if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
      fitdata_type="Amplitude Spectra"
   else:
      fitdata_type="Seismograms"
   if (nst > maxstatplot):
      nstatplot=maxstatplot
      f.write("0 2 12 0 0 5 Fit of "+fitdata_type+" (Closest "+str(maxstatplot)+" stations)\n")
   else:
      f.write("0 2 12 0 0 5 Fit of "+fitdata_type+"\n")
   f.write("0 1 10 0 0 5 Stat Dist Az Amax\n")
   usedcomp = inv_param['COMP_2_USE']
   i=0
   for letter in usedcomp:
      f.write(str(4.5+(i*jumpx))+" 1 10 0 0 5 "+comp_names[letter]+"\n")
      i=i+1
   f.write("fits\n")
#  Fit spectra or seismograms
   checkInvParam('DATA_PLOT_STEP1',inv_param['DATA_PLOT_STEP'+inv_step],('amsp','seis'))
   checkInvParam('FILT_PLOT_STEP1',inv_param['FILT_PLOT_STEP'+inv_step],('plain','tapered','filtered'))
   checkInvParam('AMPL_PLOT_STEP1',inv_param['AMPL_PLOT_STEP'+inv_step],('amax','norm'))

   if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
      x1,x2,y1,y2="0",inv_param['BP_F4_STEP'+inv_step],"0",str(amaxf)
      scale = asp_r = "/".join((x1,x2,y1,y2))
      asp_rd = asp_rs = asp_r
      tr_name=inv_param['DATA_PLOT_STEP'+inv_step]
   else:
      x1,x2=inv_param['START_PLOT_STEP'+inv_step],str(float(inv_param['LEN_PLOT_STEP'+inv_step])-float(inv_param['START_PLOT_STEP'+inv_step]))
      y1,y2=str(-amaxf),str(amaxf)
      scale = asp_r = "/".join((x1,x2,y1,y2))
      if inv_param['FILT_PLOT_STEP'+inv_step]=="plain":
         tr_name=inv_param['DATA_PLOT_STEP'+inv_step]
      elif inv_param['FILT_PLOT_STEP'+inv_step]=="tapered":   
         tr_name="seit"
      else:   
         tr_name="seif"
   tr_name=tr_name+inv_step

   asp_jxx = str(float(jumpx-(2*spacex)))
   asp_jxy = str(float(12.0/float(nstatplot)))
   asp_jx = asp_jxx+"/"+asp_jxy
   last_x=last_y=0
   istat=0
   jumpy=float(12.0/float(nstatplot))

   amax=amaxf
   amaxstat=[]
   for i in range(nstatplot):
      istat=istat+1
      amaxst=0
      for component in usedcomp:
         fdtrace=os.path.join(dinv,"d"+tr_name+"-"+str(istat)+"-"+component+".table")
         fstrace=os.path.join(dinv,"s"+tr_name+"-"+str(istat)+"-"+component+".table")
	 if os.path.isfile(fdtrace):
            fdat=open(fdtrace,'r')
            for line in fdat:
               x,y=line.split()
               dat=abs(float(y))
               if (dat>=amaxst):
                  amaxst=dat 
	    fdat.flush()     
            fdat.close()
            fsyn=open(fstrace,'r')
            for line in fsyn:
               x,y=line.split()
               dat=abs(float(y))
               if (dat>=amaxst):
                  amaxst=dat 
	    fsyn.flush()   
            fsyn.close()
      amaxstat.append(amaxst)  

   f.write("pstext <<disaz -K -O -X0 -Y-12 -JX17/12 -R0/17/0/"+str(nstatplot)+" -P >>"+fplot+"\n") 
   for i in range(nstatplot):
      line="0 "+str(nstatplot-i-0.5)+" 8 0 0 5 "+str(i+1)+" "+traces[i].stat
      line=line+" "+strDecim(traces[i].dist,1)+" "+strDecim(traces[i].azi,1)
      if ['AMPL_PLOT_STEP'+inv_step]=='amax':
         line=line+" "+strDecim((amax/100000),3)+"\n"
      else:
         line=line+" "+strDecim(((amaxstat[i])/100000),3)+"\n"
      f.write(line)
   f.write("disaz\n")

   istat=0
   for i in range(nstatplot):
      if inv_param['AMPL_PLOT_STEP'+inv_step]=="amax":
         if inv_param['DATA_PLOT_STEP'+inv_step]=="seis":
            asp_rd = "/".join((x1,x2,str(-amaxf*3),str(amaxf)))
            asp_rs = "/".join((x1,x2,str(-amaxf*2),str(amaxf*2)))
            asp_rt = "/".join((x1,x2,"0","4")) 
      else:
         if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
            asp_rd = asp_rs = asp_r = "/".join((x1,x2,"0",str(float(amaxstat[i]))))
         else:
            asp_rd = "/".join((x1,x2,str(-float(amaxstat[i])*3),str(float(amaxstat[i]))))
            asp_rs = "/".join((x1,x2,str(-float(amaxstat[i])*2),str(float(amaxstat[i])*2)))
            asp_rt = "/".join((x1,x2,"0","4"))
      istat=istat+1
      icomp=0
      for component in usedcomp:
         icomp=icomp+1   
	 fdtrace=os.path.join(dinv,"d"+tr_name+"-"+str(istat)+"-"+component+".table")
	 fstrace=os.path.join(dinv,"s"+tr_name+"-"+str(istat)+"-"+component+".table")
	 fttrace=os.path.join(dinv,"taper-"+str(istat)+"-"+component)
	 if os.path.isfile(fdtrace):
            next_x=4.5+((icomp-1)*jumpx)
            next_y=0.05+((nstatplot-istat)*jumpy)
            asp_x=str(next_x-last_x)
            asp_y=str(next_y-last_y)
            last_x=next_x
            last_y=next_y
	    if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
               line="psxy <"+fdtrace+" -X"+asp_x+" -Y"+asp_y+" -BWSNE -JX"+asp_jx
               linedata=line+" -R"+asp_rd+" -P -K -O -W1/255/0/0 -G200/0/0 >>"+fplot+"\n"
            else:
	       line="psxy <"+fdtrace+" -X"+asp_x+" -Y"+asp_y+" -BWSNE -JX"+asp_jx
               linedata=line+" -R"+asp_rd+" -P -K -O -W2/255/0/0 >>"+fplot+"\n"
	    f.write(linedata)
            linesynt="psxy <"+fstrace+" -R"+asp_rs+" -BWSNE -X0 -Y0 -JX -P -K -O -W1/0 >>"+fplot+"\n"
            f.write(linesynt)
            if inv_param['DATA_PLOT_STEP'+inv_step]=="seis":
	       linesynt="psxy <"+fttrace+" -R"+asp_rt+" -BWSNE -X0 -Y0 -JX -P -K -O -W1/100 -G150 >>"+fplot+"\n"
               f.write(linesynt)
         else:
	    print fdtrace+" not found"
   icomp=0
   for comp in usedcomp:
       icomp=icomp+1
       next_x=4.5+((icomp-1)*jumpx)
       next_y=0.0
       asp_x=str(next_x-last_x)
       asp_y=str(next_y-last_y)
       last_x=next_x
       last_y=next_y
       if inv_param['DATA_PLOT_STEP'+inv_step]=="amsp":
          line="psxy <<xscale -X"+asp_x+" -Y"+asp_y+" -JX"+asp_jx+" -R -P -K -O "+\
               "-BSa"+inv_param['BP_F4_STEP'+inv_step]+"f"+inv_param['BP_F4_STEP'+inv_step]+\
	       ":'Frequency [Hz]': >>"+fplot+"\n"
       else:
          line="psxy <<xscale -X"+asp_x+" -Y"+asp_y+" -JX"+asp_jx+" -R -P -K -O -BSa"
          line=line+inv_param['TICK_PLOT_STEP'+inv_step]+"f"+inv_param['TICK_PLOT_STEP'+inv_step]+":'Time [s]': >>"+fplot+"\n"
       f.write(line)
       f.write("0 0\n0 0\nxscale\n")
   f.write("pstext <<endplot -O -X0 -Y0 -JX -R -P >>"+fplot+"\n")
   f.write("endplot\n")
   f.flush()
   f.close()
   cmd = "source "+fgmtplot
   os.system(cmd)




class Metatrace:
   def __init__(self, code, station, lat, lon, dist, azim, components, quality):
      self.num = code
      self.stat = station
      self.lat = lat
      self.lon = lon
      self.dist = dist
      self.azi = azim
      self.comp = components
      self.quality = quality


class DCsource:
   def __init__(self, inv_step, misfit, rnor, rest, time, depth, strike, dip, rake, smom, \
                misf_shift,risetime):
      self.inv_step = inv_step
      self.misfit = misfit
      self.rnor = rnor
      self.rest = rest
      self.time = time
      self.depth = depth
      self.strike = strike
      self.dip = dip
      self.rake = rake
      self.smom = smom
      self.misf_shift = misf_shift
      self.risetime = risetime


class MTsource:
   def __init__(self, inv_step, misfit, rnor, rest, time, depth, m11, m12, m13, m22, m23, m33, \
                iso,dc,clvd,misf_shift,risetime):
      self.inv_step = inv_step
      self.misfit = misfit
      self.rnor = rnor
      self.rest = rest
      self.time = time
      self.depth = depth
      self.m11 = m11
      self.m12 = m12
      self.m13 = m13
      self.m22 = m22
      self.m23 = m23
      self.m33 = m33
      self.iso = iso
      self.dc  = dc
      self.clvd = clvd
      self.misf_shift = misf_shift
      self.risetime = risetime


class Eikonalsource:
   def __init__(self, inv_step, misfit, rnor, rest, time, depth, strike, dip, rake, smom, misf_shift,\
                      bordx, bordy, radius, nuklx, nukly, relruptvel, risetime):
      self.inv_step = inv_step
      self.misfit = misfit
      self.rnor = rnor
      self.rest = rest
      self.time = time
      self.depth = depth
      self.strike = strike
      self.dip = dip
      self.rake = rake
      self.smom = smom
      self.misf_shift = misf_shift
      self.bordx = bordx
      self.bordy = bordy
      self.radius = radius
      self.nuklx = nuklx
      self.nukly = nukly
      self.relruptvel = relruptvel
      self.risetime = risetime


class DepthStrikeDipRake:
   def __init__(self, depth, strike, dip, rake):
      self.depth = depth
      self.strike = strike
      self.dip = dip
      self.rake = rake


class StrikeDipRake:
   def __init__(self, strike, dip, rake):
      self.strike = strike
      self.dip = dip
      self.rake = rake


class Centroid:
   def __init__(self, rnor, rest, time):
      self.rnor = rnor
      self.rest = rest
      self.time = time


class Spatial_coordinates:
   def __init__(self, east, north, down):
      self.east = east
      self.north = north
      self.down = down


class Discretesource:
   def __init__(self, north, east, down, alongstrike, downdip, time, alfa, beta, rho):
      self.north = north
      self.east = east
      self.down = down
      self.alongstrike = alongstrike
      self.downdip = downdip
      self.time = time
      self.alfa = alfa
      self.beta = beta
      self.rho = rho





#######################

#      MAIN CODE      #

#######################
def run_rapidinv(finput):
    # Initializing
    time0,year0=getTime()
    print 'Initializing'
    inv_param,active_comp,active_chan,comp_names={},{},{},{}
    traces = []
    point_solutions_1,best_point_solutions_1=[],[]
    point_solutions_2,best_point_solutions_2=[],[]
    mt_solutions_1,best_mt_solutions_1=[],[]
    mt_solutions_2,best_mt_solutions_2=[],[]
    start_eikonals,eikonal_solutions_3,best_eikonal_solutions_3=[],[],[]

    # Read input file, check and prepare inversion parameters
    print 'Read input file, check and prepare inversion parameters'
    fdefaults,facceptables = 'rapidinv.defaults','rapidinv.acceptables'
    if ( not finput ):
       print "Correct usage: python rapidinv.py <input_filename>"
       sys.exit("ERROR: Wrong input file name")
    processInvParam(finput,fdefaults,facceptables,inv_param,active_comp,active_chan,comp_names)

    # Prepare inversion directory, choose stations, prepare data
    print 'Prepare inversion directory, choose stations, prepare data'
    inv_step='1'
    apply_taper=checkTaper(inv_param,inv_step)
    prepInvDir(inv_param)
    assignSpacing(inv_param)
    prepStations(inv_param,traces)
    prepData(inv_step,inv_param,traces,apply_taper)

    # Point source inversion (freq domain) - step 1
    time1,year1=getTime()
    if (int(float(inv_param['NUM_INV_STEPS']))>=1) and (int(float(inv_param['NUM_INV_STEPS']))<=3):
       inv_step='1'
       apply_taper=checkTaper(inv_param,inv_step)
       print 'Double couple source inversion (freq domain) - step 1'
       inversionDCsource(inv_step,inv_param,point_solutions_1,best_point_solutions_1,traces,apply_taper)
       print 'Point source inversion (freq domain) - plotting'
       plotDCSolution(inv_step,inv_param,point_solutions_1,best_point_solutions_1,traces)
    #   print 'Moment tensor inversion (freq domain) - step 1b'
    #   mt_solutions_1.append(point2mt(best_point_solutions_1[0],inv_param,inv_step))
    #   inversionMTsource(inv_step,inv_param,mt_solutions_1,best_mt_solutions_1,traces,apply_taper)

    # Point source inversion (time domain) - step 2
    time2,year2=getTime()
    if (int(float(inv_param['NUM_INV_STEPS']))>=2) and (int(float(inv_param['NUM_INV_STEPS']))<=3):
       inv_step='2'
       print 'Double couple source inversion (time domain) - step 2'
       point_solutions_2.append(best_point_solutions_1[0])
       point_solutions_2.append(best_point_solutions_1[1])
       inversionDCsource(inv_step,inv_param,point_solutions_2,best_point_solutions_2,traces,apply_taper) 
       print 'Point source inversion (time domain) - plotting'
       plotDCSolution(inv_step,inv_param,point_solutions_2,best_point_solutions_2,traces)
    #   print 'Moment tensor source inversion (time domain) - step 2b'
    #   mt_solutions_2.append(best_mt_solutions_1[0])
    #   mt_solutions_2.append(best_mt_solutions_1[1])
    #   inversionMTsource(inv_step,inv_param,mt_solutions_2,best_mt_solutions_2,traces,apply_taper) 

    # Eikonal source inversion (time domain) - step 3
    time3,year3=getTime()
    if int(float(inv_param['NUM_INV_STEPS']))==3:
       inv_step='3'
       print 'Eikonal source inversion (time domain) - step 3'
       eikonal_solutions_3.append(point2eikonal(best_point_solutions_2[0],inv_param,inv_step))
       eikonal_solutions_3.append(point2eikonal(best_point_solutions_2[1],inv_param,inv_step))
       inversionEIKsource(inv_step,inv_param,start_eikonals,eikonal_solutions_3,best_eikonal_solutions_3,traces,\
                          apply_taper,best_point_solutions_2)
       print 'Eikonal source inversion (time domain) - plotting'
       plotEikSolution(inv_step,inv_param,eikonal_solutions_3,best_eikonal_solutions_3,traces)

    # Clean inversion directory
    # removeLocalDataFiles(inv_param,traces)
    time4,year4=getTime()
    plotDelay(time0,year0,time1,year1,time2,year2,time3,year3,time4,year4)
    print "Ho finito!" 

if '__name__'=='__main__':
    run_rapidinv(sys.argv[1])
