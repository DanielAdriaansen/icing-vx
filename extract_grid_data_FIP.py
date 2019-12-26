#!/usr/local/python3/bin/python

# Modules
import xarray as xr
import pandas as pd
import sys
import statistics as stat
import numpy as np
from scipy import stats
import subprocess, os, time

############################# User Config #################################

# TODO:
# 1. Spot check in NCL

# Model string
#mstring = "num25_hrrr"
#mid = "hrrr"
mstring = "num4_rap"
mid = "rap"

# Define chunks. Try to keep chunks ~ 1M pts
# Higher numbers = smaller chunks, lower numbers = bigger chunks
#chunks = {'y0':158,'x0':158} # HRRR (40x1059x1799), chunk = (40x158x158)
chunks = {'y0':160,'x0':160} # RAP (39x337x451), chunk = (39x160x160)
#chunks = {'y0':225,'x0':225}

# File with PIREP, matching model, and location info
#matchfile = "/home/dadriaan/projects/sae2019/data/match/hrrr/PIREPShrrr21600posneg.out"
#matchfile = "/home/dadriaan/projects/sae2019/data/match/hrrr/PIREPShrrr10800posneg.out"
#matchfile = "/home/dadriaan/projects/sae2019/data/match/rap/PIREPSrap21600posneg.out"
#matchfile = "/home/dadriaan/projects/sae2019/data/match/rap/PIREPSrap10800posneg.out"
matchfile = "/home/dadriaan/projects/sae2019/data/match/rap/pirepTest.out"
#matchfile = "/home/dadriaan/projects/sae2019/data/match/hrrr/pirepTest.out"

# Variable URL's
probURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/fip/pressure/conus_ICE_PROB"
sevURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/fip/pressure/conus_ICE_SEV"
sldURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/fip/pressure/conus_SLD"
sevscenURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/fip/diagnostic/conus_SEV_SCENARIO"
spcpURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/fip/diagnostic/conus_SURF_PRECIP"
hgtURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_HGT"
rhURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_RH"
slwURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_SLW"
tmpURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_TMP"
vvelURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_VVEL"
liqcURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_LIQ_COND"
icecURL = "/var/autofs/mnt/ahmose_d1/dadriaan/projects/sae2019/data/"+mstring+"/data/netcdf/model/"+mid+"/pressure_derived/conus_ICE_COND"

# Height offset to expand PIREP top/base. If this is zero, then the code works differently.
zOff = 0

# If zOff = 0, use this bubble to search for points around the PIREP within 1000 ft
bubble = 1000

# What's the dz of the dataset (if not constant altitude)?
dz = 25

# Column names in CSV file
colNames = ['id','unixObs','lat','lon','flvl','temp','ibase1','itop1','iint1','ityp1','ibase2','itop2','iint2','ityp2','acft','rawOb','unixFcst','forecast','minI','maxI','minJ','maxJ','homeI','homeJ','corner','npts','file_string']

# Threshold for probability to use for scoring
probthresh = 0.05 # (5%)

# Threshold for probability when scoring severity
probsevthresh = 0.05 # (5%)

# Threshold for scoring SLW
slwthresh = 1.0e-6

# Column names for dataframe of results that will be appended to the dataframe of the input data
vxCols = ['id','file_string','probFYOY','probFNON','probFNOY','probFYON','sevFYOY','sevFNON','sevFNOY','sevFYON','VVELnear','VVELmean','VVELmed','VVELstdev','RHnear','RHmean','RHmed','RHstdev','SLWnear','SLWmean','SLWmed','SLWstdev','TMPnear','TMPmean','TMPmed','TMPstdev','PCPnear','PCPmode','PCPuni','PCPs','SCENnear','SCENmode','SCENuni','SCENs','nPtsHood','nLevHood','nPtsStats','isMulti','levNear','zNear','badPirep','slwFYOY','slwFYON','slwFNOY','slwFNON','probMIN','probMAX','sevMIN','sevMAX','VVELmin','VVELmax','RHmin','RHmax','TMPmin','TMPmax','SLWmin','SLWmax','ICECmin','ICECmax','LIQCmin','LIQCmax','TOTCmin','TOTCmax','potMIN','potMAX','sldMIN','sldMAX']

# Debug flag
DEBUG = True

# Boolens for processing.
vNear = True
vMean = True
vMed = True
vStdev = True

# Number of seconds in forecast lead
nsecfcst = 10800

# Output dataframe
outfile = "/home/dadriaan/projects/sae2019/scripts/hrrr10800vx.csv"
#outfile = "/home/dadriaan/projects/sae2019/scripts/hrrr21600vx.csv"
#outfile = "/home/dadriaan/projects/sae2019/scripts/rap10800vx.csv"
#outfile = "/home/dadriaan/projects/sae2019/scripts/rap21600vx.csv"

############################################################################

# Open match file and store as pandas dataframe object
data = pd.read_csv(matchfile,header=None,names=colNames)
#print(data.columns.get_values())
#probPODy = list(range(0,len(data.index),1))
#print(len(probPODy))
#print(len(data.index))
#data['probPODy'] = probPODy
#print(data.columns.get_values())

# Set pandas options
pd.set_option('display.max_columns', 100)

# Create a new dataframe to hold output data
#vxData = pd.DataFrame(columns=vxCols,index=list(range(0,len(data.index),1)))
#vxData.astype('object')

# Read in dataframe from last processed file, and trim the input data to process based on the ID
foundInput = False
if os.path.exists(outfile):
  chkInput = pd.read_csv(outfile)
  #cmd = 'rm -rfv %s' % (outfile)
  #subprocess.call('%s' % (cmd), shell=True, executable='/bin/csh')
  foundInput = True
  #print(chkInput['id'])
  startID = chkInput['id'][len(chkInput)-1]+1
  #print(startID)
  procData = data[startID:].reset_index()
  #print(procData['id'][0])
  del(data)
  data = procData
  #print(data.shape)
  #print(data['id'])
  #sys.exit(0)

# Find unique forecast times. We can then group PIREPs using this key
unique_fcst = data.unixFcst.unique()

# Group the PIREPS using the forecast time. This creates a new dataframe
groups = data.groupby(data.unixFcst)

# Find unique files also, in case we're curious
unique_files = data.file_string.unique()

# Boolean for initializing output data
init = False
  
# Loop over each group of PIREPs (this will iterate once per file
for name, group in groups:
    
  # Create a dataframe for this group of PIREPs
  vxData = pd.DataFrame(columns=vxCols,index=list(range(0,len(group),1)))
  vxData.astype('object')
  vxcnt = 0
  
  # Print the first file_string (same for entire group)
  if DEBUG:
    print("")
    print("PROCESSING MODEL FILE:")
    print((group.file_string.iloc[0]))

  # Open multiple files so we have height info
  ncFiles = ['%s/%s' % (probURL,group.file_string.iloc[0]),'%s/%s' % (hgtURL,group.file_string.iloc[0]),'%s/%s' % (sevURL,group.file_string.iloc[0]),'%s/%s' % (sldURL,group.file_string.iloc[0]),'%s/%s' % (sevscenURL,group.file_string.iloc[0]),'%s/%s' % (spcpURL,group.file_string.iloc[0]),'%s/%s' % (vvelURL,group.file_string.iloc[0]),'%s/%s' % (rhURL,group.file_string.iloc[0]),'%s/%s' % (tmpURL,group.file_string.iloc[0]),'%s/%s' % (slwURL,group.file_string.iloc[0]),'%s/%s' % (icecURL,group.file_string.iloc[0]),'%s/%s' % (liqcURL,group.file_string.iloc[0])]
  ncData = xr.open_mfdataset(ncFiles,chunks=chunks,combine='by_coords')
  print(ncData)
  
  # Correct NA values in certain variables (do this before correcting to zero)
  ncData['ICE_SEV'] = ncData.ICE_SEV.fillna(0.0)
  ncData['ICE_PROB'] = ncData.ICE_PROB.fillna(0.0)
  ncData['SLD'] = ncData.SLD.fillna(0.0)
  ncData['SLW'] = ncData.SLW.fillna(0.0)
  ncData['ICE_COND'] = ncData.ICE_COND.fillna(0.0)
  ncData['LIQ_COND'] = ncData.LIQ_COND.fillna(0.0)
  ncData['SEV_SCENARIO'] = ncData.SEV_SCENARIO.fillna(-1.0)

  # Correct any INT16 values that are <0 to 0.0, in fields that shouldn't have negative data
  ncData['ICE_SEV'] = ncData.ICE_SEV.where(ncData.ICE_SEV>0.0,0.0)
  ncData['ICE_PROB'] = ncData.ICE_PROB.where(ncData.ICE_PROB>0.0,0.0)
  ncData['SLD'] = ncData.SLD.where(ncData.SLD>0.0,0.0)
  ncData['SLW'] = ncData.SLW.where(ncData.SLW>0.0,0.0)
  ncData['ICE_COND'] = ncData.ICE_COND.where(ncData.ICE_COND>0.0,0.0)
  ncData['LIQ_COND'] = ncData.LIQ_COND.where(ncData.LIQ_COND>0.0,0.0)

  # Back out the icing potential value
  ncData['ICE_POT'] = ncData['ICE_PROB']/((-0.033*(nsecfcst/3600)+0.84))

  # Add a total condensate variable
  ncData['TOT_COND'] = ncData['ICE_COND']+ncData['LIQ_COND']

  # Loop over each item in the series
  icnt = 0
  while icnt < len(group.minI):

    # Flag for whether PIREP is good or not
    vxData['badPirep'][vxcnt] = False
  
    # Start time
    start_time = time.time()

    # This is the index into the master pandas DF of the current object in the group being processed
    # We can use this to append info to a new dataframe? Or insert into the original dataframe?
    #print(group.index[icnt])

    # Store input info in the output dataframe
    vxData['id'][vxcnt] = group.id.iloc[icnt]
    vxData['file_string'][vxcnt] = group.file_string.iloc[icnt]

    # Print info
    print("")
    print("PROCESSING PIREP:")
    print((group.rawOb.iloc[icnt]))
    print("")
    print("PIREP ID:")
    print((group.id.iloc[icnt]))

    # Figure out the height bounds for this PIREP
    #pBot = (group.ibase1.iloc[icnt]*100.0)*.3048 # In meters
    #pTop = (group.itop1.iloc[icnt]*100.0)*.3048  # In meters
    pBot = (group.ibase1.iloc[icnt]*100)          # In feet
    pTop = (group.itop1.iloc[icnt]*100)           # In feet
    if DEBUG:
      print("")
      print("PIREP BASE/TOP:")
      print((pBot,pTop))
    if pBot > pTop:
      vxData['badPirep'][vxcnt] = True
      icnt = icnt + 1
      vxcnt = vxcnt + 1
      continue 

    # Subset the dataset at the specific indexes. Returns Dataset object.
    regionDS = ncData.isel(time=[0],y0=slice(group.minJ.iloc[icnt],group.maxJ.iloc[icnt]+1),x0=slice(group.minI.iloc[icnt],group.maxI.iloc[icnt]+1))
   
    # Convert height to feet inside the dataset (modify in place)
    regionDS['HGT'] = regionDS.HGT*3.281 # Convert gpm to feet to match with PIREP
    
    # Find data close to the PIREP in the vertical
    if pBot == pTop:
      isMulti = False
      # Find all the points where the height is within "bubble" distance from PIREP, and drop data outside
      donutBot = regionDS.where((abs(regionDS.HGT-pBot)<bubble),drop=True)
      if donutBot.z0.values.size==0:
        vxData['badPirep'][vxcnt] = True
        icnt = icnt + 1
        vxcnt = vxcnt + 1
        continue
      else:
        finalHood = regionDS.sel(z0=list(range(int(max(donutBot.z0.values)),int(min(donutBot.z0.values)-dz),-dz)))
        pNear = pBot
    else:
      isMulti = True
      # Find all the points where the height is within the "bubble" distance from the top and bottom of the PIREP,
      # and drop data outside
      donutBot = regionDS.where((abs(regionDS.HGT-pBot)<bubble),drop=True)
      donutTop = regionDS.where((abs(regionDS.HGT-pTop)<bubble),drop=True)

      # In the event an SKC PIREP goes to some absurd height, set the top of the neighborhood to the maxZ
      # If neither a top nor a base was found skip it
      if donutTop.z0.values.size==0 and donutBot.z0.values.size==0:
        # Entire PIREP above model range, just skip it
        vxData['badPirep'][vxcnt] = True
        icnt = icnt + 1
        vxcnt = vxcnt + 1
        continue
        #finalHood = regionDS.sel(z0=list(range(int(max(donutBot.z0.values)),int(min(ncData.z0.values)-dz),-dz)))
      # If no top was found but a base was found, use the maxZ as the top
      elif donutTop.z0.values.size==0 and donutBot.z0.values.size>0:   
        # Construct the vertical neighborhood using the pressure levels and dz
        finalHood = regionDS.sel(z0=list(range(int(max(donutBot.z0.values)),int(min(ncData.z0.values)-dz),-dz)))
      # Found a top but no bottom- just skip this unclear why it happens. I think it is if the PIREP base is really
      # high but no model levels are within 1000ft of it, but there are some model levels within 1000ft of the PIREP
      # top.
      elif donutBot.z0.values.size==0 and donutTop.z0.values.size>0:
        vxData['badPirep'][vxcnt] = True
        icnt = icnt + 1
        vxcnt = vxcnt + 1
        continue
        #finalHood = regionDS.sel(z0=list(range(int(max(ncData.z0
      # Both a top and a base were found
      else:
        # Construct the vertical neighborhood using the pressure levels and dz
        finalHood = regionDS.sel(z0=list(range(int(max(donutBot.z0.values)),int(min(donutTop.z0.values)-dz),-dz)))

      # Compute a representative height near the middle of the range between pBot and pTop
      pNear = stat.mean([pBot,pTop]) 
      
    # Find the closest z-level to the PIREP
    # Requires 2 steps: first, use sel to use the actual height values (coordinate indexing) then use isel to
    # get the correct i,j (positional indexing)
    nearSub = ncData.sel(z0=list(range(int(finalHood.z0.values[0]),int(finalHood.z0.values[-1])-dz,-dz)))
    nearestHood = nearSub.isel(time=[0],y0=group.homeJ.iloc[icnt],x0=group.homeI.iloc[icnt])
   
    # Just find the nearest K-level now to the height closest to the pNear value (meanZPirep)
    nearestFinal = nearestHood.isel(z0=[np.argmin(abs((nearestHood.HGT.values*3.281)-pNear))])
    
    # VARIABLES:
    # ncData: full dataset
    # regionDS: subset of full dataset containing all data within the X-Y region around the PIREP at all Z
    # finalHood: subset of the region dataset containing only those Z within 1000ft of PIREP
    # nearestHood: the closest X-Y point to the PIREP with all Z within 1000ft of PIREP
    # nearestFinal: the closest X-Y point to the PIREP and closest Z to the mean of the PIREP heights
 
    # Set some output data
    vxData['isMulti'][vxcnt] = isMulti
    vxData['levNear'][vxcnt] = nearestFinal.z0.values[0]
    vxData['zNear'][vxcnt] = nearestFinal.HGT.values[0][0]*3.281

    # VARnear: val
    if vNear:
      print("NEAR")
      vxData['VVELnear'][vxcnt] = nearestFinal.VVEL.values.flatten()[0]
      vxData['RHnear'][vxcnt] = nearestFinal.RH.values.flatten()[0]
      vxData['SLWnear'][vxcnt] = nearestFinal.SLW.values.flatten()[0]
      vxData['TMPnear'][vxcnt] = nearestFinal.TMP.values.flatten()[0]
    
    # VARmean: val
    if vMean:
      print("MEAN")
      vxData['VVELmean'][vxcnt] = finalHood.VVEL.mean(dim=list(finalHood.VVEL.dims)).values 
      vxData['RHmean'][vxcnt] = finalHood.RH.mean(dim=list(finalHood.RH.dims)).values 
      vxData['SLWmean'][vxcnt] = finalHood.SLW.mean(dim=list(finalHood.SLW.dims)).values 
      vxData['TMPmean'][vxcnt] = finalHood.TMP.mean(dim=list(finalHood.TMP.dims)).values 
    
    # VARmed: val
    if vMed:
      print("MED")
      #vxData['VVELmed'][vxcnt] = finalHood.VVEL.median(dim=list(finalHood.VVEL.dims)).values
      vxData['VVELmed'][vxcnt] = stat.median(finalHood.VVEL.values.flatten())
      vxData['RHmed'][vxcnt] = stat.median(finalHood.RH.values.flatten())
      vxData['SLWmed'][vxcnt] = stat.median(finalHood.SLW.values.flatten())
      vxData['TMPmed'][vxcnt] = stat.median(finalHood.TMP.values.flatten())
    
    # VARstdev: val
    if vStdev:
      print("STDEV")
      vxData['VVELstdev'][vxcnt] = finalHood.VVEL.std(dim=list(finalHood.VVEL.dims)).values
      vxData['RHstdev'][vxcnt] = finalHood.RH.std(dim=list(finalHood.RH.dims)).values
      vxData['SLWstdev'][vxcnt] = finalHood.SLW.std(dim=list(finalHood.SLW.dims)).values
      vxData['TMPstdev'][vxcnt] = finalHood.TMP.std(dim=list(finalHood.TMP.dims)).values

    # Mins/maxes
    print("MIN/MAX")
    vxData['probMIN'][vxcnt] = finalHood.ICE_PROB.min().values
    vxData['probMAX'][vxcnt] = finalHood.ICE_PROB.max().values
    vxData['sevMIN'][vxcnt] = finalHood.ICE_SEV.min(skipna=True).values
    vxData['sevMAX'][vxcnt] = finalHood.ICE_SEV.max(skipna=True).values
    vxData['VVELmin'][vxcnt] = finalHood.VVEL.min().values
    vxData['VVELmax'][vxcnt] = finalHood.VVEL.max().values
    vxData['RHmin'][vxcnt] = finalHood.RH.min().values
    vxData['RHmax'][vxcnt] = finalHood.RH.max().values
    vxData['TMPmin'][vxcnt] = finalHood.TMP.min().values
    vxData['TMPmax'][vxcnt] = finalHood.TMP.max().values
    vxData['SLWmin'][vxcnt] = finalHood.SLW.min().values
    vxData['SLWmax'][vxcnt] = finalHood.SLW.max().values
    vxData['ICECmin'][vxcnt] = finalHood.ICE_COND.min().values
    vxData['ICECmax'][vxcnt] = finalHood.ICE_COND.max().values
    vxData['LIQCmin'][vxcnt] = finalHood.LIQ_COND.min().values
    vxData['LIQCmax'][vxcnt] = finalHood.LIQ_COND.max().values
    vxData['TOTCmin'][vxcnt] = finalHood.TOT_COND.min().values
    vxData['TOTCmax'][vxcnt] = finalHood.TOT_COND.max().values
    vxData['sldMIN'][vxcnt] = finalHood.SLD.min().values
    vxData['sldMAX'][vxcnt] = finalHood.SLD.max().values
    vxData['potMIN'][vxcnt] = finalHood.ICE_POT.min().values
    vxData['potMAX'][vxcnt] = finalHood.ICE_POT.max().values
    
    # PCPnear: val
    print("PCP")
    vxData['PCPnear'][vxcnt] = ncData.SURF_PRECIP.isel(time=[0],z0=[-1],y0=group.homeJ.iloc[icnt],x0=group.homeI.iloc[icnt]).values.flatten()[0]
    
    # PCPuni/PCPmode:
    if min(regionDS.SURF_PRECIP.isel(z0=[-1]).values.flatten()) == max(regionDS.SURF_PRECIP.isel(z0=[-1]).values.flatten()):
      vxData['PCPuni'][vxcnt] = True
      vxData['PCPmode'][vxcnt] = regionDS.SURF_PRECIP.min().round().values
    else:
      vxData['PCPuni'][vxcnt] = False
      #print(np.unique(regionDS.SURF_PRECIP.isel(z0=[-1]).values.flatten().round()))
      vxData['PCPs'][vxcnt] = np.unique(regionDS.SURF_PRECIP.isel(z0=[-1]).values.flatten().round())
      vxData['PCPmode'][vxcnt] = stats.mode(regionDS.SURF_PRECIP.isel(z0=[-1]).values.flatten())[0][0]
    
    # SCENnear: val
    print("SCEN")
    vxData['SCENnear'][vxcnt] = nearestFinal.SEV_SCENARIO.values.flatten().round()[0]
    
    # SCENuni/SCENmode:
    # Since SEV_SCENARIO is initialized to NaN, the entire neighborhood could be NaN. Leave the SCENuni set to NaN if so.
    if not xr.ufuncs.isnan(finalHood.SEV_SCENARIO.values.flatten().round()).all():
      if min(finalHood.SEV_SCENARIO.values.flatten()).round() == max(finalHood.SEV_SCENARIO.values.flatten()).round():
        vxData['SCENuni'][vxcnt] = True
        vxData['SCENmode'][vxcnt] = finalHood.SEV_SCENARIO.min().round().values
      else:
        vxData['SCENuni'][vxcnt] = False
        #print(np.unique(finalHood.SEV_SCENARIO.values.flatten().round()))
        vxData['SCENs'][vxcnt] = np.unique(finalHood.SEV_SCENARIO.values.flatten().round())
        vxData['SCENmode'][vxcnt] = stats.mode(finalHood.SEV_SCENARIO.values.flatten())[0].round()[0]
    
    # nPtsHood: Number of total non-NaN points in the finalHood
    print("NPTS")
    vxData['nPtsHood'][vxcnt] = finalHood.HGT.size
    
    # nLevHood: Number of vertical levels comprising the finalHood
    vxData['nLevHood'][vxcnt] = finalHood.HGT.sizes['z0']
    
    # nPtsStats: Number of valid points in the neighborhood within 1000ft of PIREP
    #            This is total number of points minus all missing (NaN) points
    vxData['nPtsStats'][vxcnt] = vxData['nPtsHood'][vxcnt]-xr.ufuncs.isnan(finalHood.HGT).sum(dim='z0').sum().values

    # Print out a row of the dataframe to see all the data we've collected for this PIREP
    print("")
    print((vxData.loc[[vxcnt]]))

    # Exit after one PIREP
    #sys.exit(0)
    
    # When we get here, see if any of the levels are partially NaNs. This could occur where one gridpoint had
    # height values (or a few GP) that were lower than the rest on the level below or above where they all were
    # within 1000 ft
    # Sum in the z-dimension (smush, composite) and then take a sum of the composite to ensure no nan
    chk = xr.ufuncs.isnan(finalHood.HGT.sum(dim='z0',skipna=False).sum(skipna=False)).values
    if chk:
      print("WARNING! FOUND ODDBALL")
      print((finalHood.dims))
      print((finalHood.HGT.values))
      print((finalHood.ICE_PROB.values))
      #sys.exit(1)
    
    # Advance the PIREP counter
    icnt = icnt + 1
    
    # Advance the vxcnt
    vxcnt = vxcnt + 1
  
    # Print time
    print("")
    print("SECONDS TO PROCESS PIREP:")
    print((time.time()-start_time))
    print("")

  # After each model file, write out the dataframe to CSV, appending the input
  if os.path.exists(outfile):
    vxInput = pd.read_csv(outfile)
    vxInput = vxInput.append(vxData,ignore_index=True)
    print(vxInput)
    vxInput.to_csv(outfile,index=False,na_rep="NaN")
  else:
    vxData.to_csv(outfile,index=False,na_rep="NaN") 

  # Close the dataset
  ncData.close()

  # Exit after one model file
  #sys.exit(0)

