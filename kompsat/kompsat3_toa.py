#!/usr/bin/python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#******************************************************************************
#Script for TOA convertion for Kompsat-3e
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

#-----------------------------------------------------------------------------------
#KOMPSAT3_Image Data Manual_V2 0_20170207.pdf
#-----------------------------------------------------------------------------------
#BLUE,GREEN,RED,NIR,PAN
ESUN = [2001.0,1875.0,1525.0,1027.0,1472.0]
gain = [0.01811, 0.02541, 0.02023, 0.01300, 0.02023]
bias = [0.0, 0.0, 0.0, 0.0, 0.0]

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
def calc_toa_scale(date_time,rad_scale,sun_zen,band):
    ESd = calc_esun_dist(date_time)    
    Csz = np.cos(np.radians(sun_zen))
    toa_scale = 0.0
    num = np.pi*(ESd*ESd)
    den = ESUN[band]*Csz
    if(den !=0):
        toa_scale = rad_scale*(num/den)
    else:
        return None
    return toa_scale*10000

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def readmeta(name,bandname):
    gain = 1.0
    bias = 0.0
    aqdate = ""
    sun_zen = 0.0
    fdate = 0.0
    try:
        xmldoc = minidom.parse(name)
    except:
        return None
    try:
        cur_pos = xmldoc.getElementsByTagName('Image')[0]
        for elem in cur_pos.childNodes:
            if (elem.hasChildNodes()):
                vol = elem.getElementsByTagName('ImageFileName')[0].firstChild.nodeValue
                if(vol.lower()==bandname.lower()):
                    tbuf = elem.getElementsByTagName('ImagingCenterTime')[0].getElementsByTagName('UTC')[0].firstChild.nodeValue
                    fdate = float(tbuf)
                    aqdate = "%s-%s-%sT%s:%s:%s"%(tbuf[0:4],tbuf[4:6],tbuf[6:8],tbuf[8:10],tbuf[10:12],tbuf[12:])
                    gain = float(elem.getElementsByTagName('RadianceConversion')[0].getElementsByTagName('Gain')[0].firstChild.nodeValue)
                    bias = float(elem.getElementsByTagName('RadianceConversion')[0].getElementsByTagName('Offset')[0].firstChild.nodeValue)
                    break
    except:
        return None
    try:
        cur_pos = xmldoc.getElementsByTagName('Metadata')[0]
        for elem in cur_pos.childNodes:
            if (elem.hasChildNodes()):
                if(fdate <= float(elem.getElementsByTagName('Time')[0].firstChild.nodeValue)):
                    sun_zen = 90.0-float(elem.getElementsByTagName('Elevation')[0].firstChild.nodeValue)
                    break
    except:
        return None
    xmldoc = None
    return gain, bias, aqdate, sun_zen

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
        print "Usage:\nproc_K3 [input.tif]"
        exit(1)
    print sys.argv
    prodname = sys.argv[1]
    dos = 0
    ps_toa = 0
    use_ext_gain = 0
    basename = os.path.basename(prodname)
#    basename = re.sub(".TIF","",basename,flags=re.I)
    wrkdir = os.path.dirname(prodname)
    xmlname = glob.glob(wrkdir+"/*Aux.xml")#"_metadata.xml"
    if(len(xmlname)!=0):
        xmlname = xmlname[0]
    print xmlname 
    b = 0
    if(os.path.splitext(basename)[0][-1]=='G'):
        b = 1
    elif(os.path.splitext(basename)[0][-1]=='R'):
        b = 2
    elif(os.path.splitext(basename)[0][-1]=='N'):
        b = 3
    elif(os.path.splitext(basename)[0][-1]=='P'):
        b = 4
    
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

    rad_gain, rad_bias, date, sun_zen = readmeta(xmlname,basename)
    dist = calc_esun_dist(date)
    toa_gain = calc_toa_scale(date,rad_gain,sun_zen,b)
    if(toa_gain is None):
        logging.info("Error, invalid metadata: %s"%(xmlname))
        exit(3)
    oname = ("%s/toa/%s_TOA.TIF"%(wrkdir,os.path.splitext(basename)[0]))
    iband = ds.GetRasterBand(1)
    data = iband.ReadAsArray().astype(np.float32)
    ndmask = data==0
    if(ps_toa!=1):
        print "full eqation mode"
        #path_rad = calc_path_radiance(data,ESUN[b],sun_zen,dist,rad_gain)
        #logging.info("Band-%d path_radiance=%f"%(b,path_rad))
        #if(dos==0):
        #    path_rad = 0
        print toa_gain
        data = data*toa_gain#-0.01
        #print np.mean(data[~ndmask])
        #data = (data-path_rad/rad_gain)*toa_gain
        #print np.mean(data[~ndmask])
        #data = ext_tmean[b]+(data-ext_smean[b])*ext_gain[b]
#        if(use_ext_gain!=0):
#            print "use external gain"
#            data = data*ext_gain[b]+ext_bias[b]
#        print np.mean(data[~ndmask])
    else:
        print "simple eqation mode"
#        data = data*stoa_gain[b]
    data[ndmask]=0
#    logging.info("Band-%d Min=%f"%(b+1,np.min(data[~ndmask])))
#    logging.info("Band-%d Max=%f"%(b+1,np.max(data[~ndmask])))
#    logging.info("Band-%d Mean=%f"%(b+1,np.mean(data[~ndmask])))
#    logging.info("Band-%d Std=%f"%(b+1,np.std(data[~ndmask])))
#    logging.info("Band-%d p0.01=%f"%(b+1,np.percentile(data[~ndmask],0.01)))
#    logging.info("Band-%d p1=%f"%(b+1,np.percentile(data[~ndmask],1)))
#    logging.info("Band-%d p99.95=%f"%(b+1,np.percentile(data[~ndmask],99.95)))
    logging.info("Band-%d toa_gain=%.18f"%(b,toa_gain))
#    gdal_write(oname,iband.ReadAsArray()*toa_gain[b]-0.01,ds,0,gdal.GDT_Float32)
    gdal_write(oname,data,ds,0,gdal.GDT_UInt16)
    iband = None
    del data, ndmask
    del ds,toa_gain
    gc.collect()
    logging.info("Processed by %f sec"%(timeit.default_timer()-tic))
    print "Processed by %f sec"%(timeit.default_timer()-tic)
    print "Done"
    exit(0)
