#!/usr/bin/python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#******************************************************************************
#Script for TOA convertion for RapidEye
#version 1.0
#******************************************************************************

from osgeo import gdal
import numpy as np
import os
import sys
import re
import glob
import gc
import timeit
#from scipy import ndimage
import logging
from xml.dom import minidom
import datetime
import string

ESUN = [1997.8,1863.5,1560.4,1395.0,1124.4]

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_esun_dist(date_time):
    date = string.split(date_time,"T")[0]
    date = string.split(date,"-")
    doy=datetime.date(int(date[0]),int(date[1]),int(date[2])).timetuple().tm_yday
    return (1.0-0.01672*np.cos(np.deg2rad(0.9856*doy-4)))

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_path_radiance(data,esun,sun_zen,d,rad_scale,prc=0.01,pd=0.01):
    dn_min = np.percentile(data[data!=0],prc)*rad_scale
    num = np.float_(pd*(esun*np.cos(np.radians(sun_zen))))
    den = np.float_(np.pi*(d*d))
    return dn_min-(num/den)

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_toa_scale(date_time,rad_scale,sun_zen):
    ESd = calc_esun_dist(date_time)    
    Csz = np.cos(np.radians(sun_zen))
    toa_scale = np.zeros_like(rad_scale,dtype=np.float_)
    num = np.pi*(ESd*ESd)
    for b in range(len(rad_scale)):
        den = ESUN[b]*Csz
        if(den !=0):
            toa_scale[b] = rad_scale[b]*(num/den)
        else:
            return None
    return toa_scale

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def readmeta(name,nbands):
    scale = np.zeros(nbands,dtype=np.float_)
    aqdate = ""
    sun_zen = 0.0
    try:
        xmldoc = minidom.parse(name)
    except:
        return None
    try:
        cur_tag = xmldoc.getElementsByTagName('re:EarthObservationResult')[0]
    except:
        return None
    i = 0
    for child in cur_tag.getElementsByTagName('re:bandSpecificMetadata'):
        scale[i] = float(child.getElementsByTagName('re:radiometricScaleFactor')[0].firstChild.nodeValue)
        i+=1
    try:
        aqdate = xmldoc.getElementsByTagName('re:acquisitionDateTime')[0].firstChild.nodeValue
    except:
        return None
    try:
        sun_zen = 90.0-float(xmldoc.getElementsByTagName('opt:illuminationElevationAngle')[0].firstChild.nodeValue)
    except:
        return None
    xmldoc = None
    return scale, aqdate, sun_zen

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def gdal_write(oname,data,sds,nodata=-9999,OutDataType=gdal.GDT_Float32):    
    driver=gdal.GetDriverByName("Gtiff")
    nbands=1
    ods=driver.Create(oname,data.shape[1],data.shape[0],nbands,OutDataType)
    ods.SetGeoTransform(sds.GetGeoTransform())
    ods.SetProjection(sds.GetProjection())
    ob=ods.GetRasterBand(1)
    ob.SetNoDataValue(nodata)
    ob.WriteArray(data,0,0)
    ob = None
    ods= None

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
if __name__ == '__main__':
    tic = timeit.default_timer()
    gdal.AllRegister()
    gdal.UseExceptions()
    if (len(sys.argv)<2):
        print "Bad arguments"
        print "Usage:\nproc_planet_re [input_L3A.tif]"
        exit(1)
    print sys.argv
    prodname = sys.argv[1]
    dos = 0
    basename = os.path.basename(prodname)
    basename = re.sub(".tif","",basename)
    wrkdir = os.path.dirname(prodname)
    xmlname = wrkdir+"/"+basename+"_metadata.xml"
    print xmlname 
    if not (os.path.exists(wrkdir+"/toa")):
        os.mkdir(wrkdir+"/toa")
    logname = wrkdir+"/"+basename+".log"
    if(os.path.exists(logname)):
        os.remove(logname)
    logging.basicConfig(format='[%(asctime)s.%(msecs)03d] %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S.3', 
                    level=logging.DEBUG, 
                    filename=logname)
    logging.info("Start processing product: %s"%(basename))
    try:
        ds = gdal.Open(prodname,gdal.GA_ReadOnly)
    except:
        print "No input file"
        exit(2)
    nbands = ds.RasterCount
    rad_gain, date, sun_zen = readmeta(xmlname,nbands)
    dist = calc_esun_dist(date)
    toa_gain = calc_toa_scale(date,rad_gain,sun_zen)
    if(toa_gain is None):
        logging.info("Error, invalid metadata: %s"%(xmlname))
        exit(3)
    for b in range(nbands):
        oname = ("%s/toa/%s_TOA_B%d.TIF"%(wrkdir,basename,b+1))
        iband = ds.GetRasterBand(b+1)
        data = iband.ReadAsArray()
#        path_rad = calc_path_radiance(data,ESUN[b],sun_zen,dist,rad_gain[b])
#        logging.info("Band-%d path_radiance=%f"%(b+1,path_rad))
        ndmask = data==0
#        data = data*toa_gain[b]#-0.01
        if(dos==0):
            path_rad = 0
        data = (data-path_rad/rad_gain[b])*toa_gain[b]
        data[ndmask]=0
#        logging.info("Band-%d Min=%f"%(b+1,np.min(data[~ndmask])))
#        logging.info("Band-%d Max=%f"%(b+1,np.max(data[~ndmask])))
#        logging.info("Band-%d Mean=%f"%(b+1,np.mean(data[~ndmask])))
#        logging.info("Band-%d Std=%f"%(b+1,np.std(data[~ndmask])))
#        logging.info("Band-%d p0.01=%f"%(b+1,np.percentile(data[~ndmask],0.01)))
#        logging.info("Band-%d p1=%f"%(b+1,np.percentile(data[~ndmask],1)))
#        logging.info("Band-%d p99.9995=%f"%(b+1,np.percentile(data[~ndmask],99.9995)))
#        gdal_write(oname,data,ds,0,gdal.GDT_Float32)
        gdal_write(oname,data*10000,ds,0,gdal.GDT_UInt16)
#        gdal_write(oname,iband.ReadAsArray()*toa_gain[b],ds,0,gdal.GDT_Float32)
        iband = None
        del data, ndmask
    del ds,toa_gain
    gc.collect()
    logging.info("Processed by %f sec"%(timeit.default_timer()-tic))
    print "Processed by %f sec"%(timeit.default_timer()-tic)
    print "Done"
    exit(0)
