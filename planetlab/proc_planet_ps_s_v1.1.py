#!/usr/bin/python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#******************************************************************************
#Script for TOA convertion for PlantScope
#version 1.1
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

ESUN = [1966.337,1862.98,1661.282,1084.879]
#---------------------------------------------
#PS support
ESUN = [1965.62,1890.03,1673.46,1105.24]
#Calculated by Thuilier model
ESUN = [1931.7345610752202,1833.4847890866072,1647.2382233151675,1090.601286841304]
#ext_gain = [0.01179177844680463/0.01195218824998958, 0.01941704018399999/0.01547512294380843, 0.04103159131495192/0.0267573249080201, 0.04653325127467878/0.0351221565318624]
ext_smean = [0.09040993496694198, 0.09400612059797561, 0.09469399011682791, 0.210152372120211]
ext_tmean = [0.0925991489062442, 0.09132116154298681, 0.1004438953824952, 0.2137721414405249]
#ext_bias = [0.0034026, -0.02663077, -0.04476663, -0.06465817]

#-----------------------------------------------------------------------------------
#PS-0e30 bordeaux
#-----------------------------------------------------------------------------------
ext_gain = [1.1423221 ,  1.29661017,  1.36568339,  1.25678416]
ext_bias = [-0.02380174, -0.04091987, -0.04105692, -0.06517764]

#-----------------------------------------------------------------------------------
#PS-0e20 bordeaux
#-----------------------------------------------------------------------------------
ext_gain = [1.061435, 1.250310, 1.511816, 1.293499]
ext_bias = [-0.004900, -0.027622, -0.046845, -0.062834]

#-----------------------------------------------------------------------------------
#PS-0e0f bordeaux
#-----------------------------------------------------------------------------------
ext_gain = [1.111316, 1.374217, 1.480797, 1.261420]
ext_bias = [-0.015883, -0.039941, -0.046380, -0.070343]

#-----------------------------------------------------------------------------------
#lm 
#-----------------------------------------------------------------------------------
ext_gain = [0.9699585831439155, 1.0915923111642590, 1.2135084112482360, 1.1795711173512990]
ext_bias = [0.001955271339649294, -0.01051769050073884, -0.01991399670830339, -0.02481394082238930]

ext_gain = [1.074781,1.167351,1.296551,1.242378]
ext_bias = [-0.008754,-0.017545,-0.026742,-0.037765]


#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_esun_dist(date_time):
    date = string.split(date_time,"T")[0]
    date = string.split(date,"-")
    doy=datetime.date(int(date[0]),int(date[1]),int(date[2])).timetuple().tm_yday
#    doy-=1 #assume first day equal 0
    return (1.0-0.01672*np.cos(np.deg2rad(0.9856*doy-4)))

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
        cur_tag = xmldoc.getElementsByTagName('ps:EarthObservationResult')[0]
    except:
        return None
    i = 0
    for child in cur_tag.getElementsByTagName('ps:bandSpecificMetadata'):
        scale[i] = float(child.getElementsByTagName('ps:radiometricScaleFactor')[0].firstChild.nodeValue)
        i+=1
    try:
        aqdate = xmldoc.getElementsByTagName('ps:acquisitionDateTime')[0].firstChild.nodeValue
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
def readmeta_toa(name,nbands):
    scale = np.zeros(nbands,dtype=np.float_)
    try:
        xmldoc = minidom.parse(name)
    except:
        return None
    try:
        cur_tag = xmldoc.getElementsByTagName('ps:EarthObservationResult')[0]
    except:
        return None
    i = 0
    for child in cur_tag.getElementsByTagName('ps:bandSpecificMetadata'):
        scale[i] = float(child.getElementsByTagName('ps:reflectanceCoefficient')[0].firstChild.nodeValue)
        i+=1
    xmldoc = None
    return scale
 
#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_path_radiance(data,esun,sun_zen,d,rad_scale,prc=0.01,pd=0.01):
    dn_min = np.percentile(data[data!=0],prc)*rad_scale
    print dn_min
    num = np.float_(pd*(esun*np.cos(np.radians(sun_zen))))
    den = np.float_(np.pi*(d*d))
    return dn_min-(num/den)

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def gdal_write(oname,data,sds,nodata=-9999,OutDataType=gdal.GDT_Float32):    
#    OutDataType=gdal.GDT_Float32
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
        print "Usage:\nproc_planet [input_L3B.tif]"
        exit(1)
    print sys.argv
    prodname = sys.argv[1]
    dos = 0
    ps_toa = 0
    use_ext_gain = 1
    basename = os.path.basename(prodname)
    basename = re.sub(".tiff","",basename)
    wrkdir = os.path.dirname(prodname)
    xmlname = wrkdir+"/"+basename+".xml"#"_metadata.xml"
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
    stoa_gain = readmeta_toa(xmlname,nbands)
    if(toa_gain is None):
        logging.info("Error, invalid metadata: %s"%(xmlname))
        exit(3)
    for b in range(nbands):
        oname = ("%s/toa/%s_TOA_B%d.TIF"%(wrkdir,basename,b+1))
        iband = ds.GetRasterBand(b+1)
        data = iband.ReadAsArray()
        ndmask = data==0
        if(ps_toa!=1):
            print "full eqation mode"
            path_rad = calc_path_radiance(data,ESUN[b],sun_zen,dist,rad_gain[b])
            logging.info("Band-%d path_radiance=%f"%(b+1,path_rad))
            if(dos==0):
                path_rad = 0
    #        data = data*toa_gain[b]#-0.01
            print np.mean(data[~ndmask])
            data = (data-path_rad/rad_gain[b])*toa_gain[b]
            print np.mean(data[~ndmask])
            #data = ext_tmean[b]+(data-ext_smean[b])*ext_gain[b]
            if(use_ext_gain!=0):
                print "use external gain"
                data = data*ext_gain[b]+ext_bias[b]
            print np.mean(data[~ndmask])
        else:
            print "simple eqation mode"
            data = data*stoa_gain[b]
        data[ndmask]=0
#        logging.info("Band-%d Min=%f"%(b+1,np.min(data[~ndmask])))
#        logging.info("Band-%d Max=%f"%(b+1,np.max(data[~ndmask])))
#        logging.info("Band-%d Mean=%f"%(b+1,np.mean(data[~ndmask])))
#        logging.info("Band-%d Std=%f"%(b+1,np.std(data[~ndmask])))
#        logging.info("Band-%d p0.01=%f"%(b+1,np.percentile(data[~ndmask],0.01)))
#        logging.info("Band-%d p1=%f"%(b+1,np.percentile(data[~ndmask],1)))
#        logging.info("Band-%d p99.95=%f"%(b+1,np.percentile(data[~ndmask],99.95)))
        logging.info("Band-%d toa_gain=%.18f"%(b+1,toa_gain[b]))
#        gdal_write(oname,iband.ReadAsArray()*toa_gain[b]-0.01,ds,0,gdal.GDT_Float32)
        gdal_write(oname,data,ds,0,gdal.GDT_Float32)
        iband = None
        del data, ndmask
    del ds,toa_gain
    gc.collect()
    logging.info("Processed by %f sec"%(timeit.default_timer()-tic))
    print "Processed by %f sec"%(timeit.default_timer()-tic)
    print "Done"
    exit(0)
