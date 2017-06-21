#!/usr/bin/python
#!/usr/bin/env python
# -*- coding: utf-8 -*-
#******************************************************************************
#Script for L8 collection RT and T1 to TOA
#Cloud and shadow pixel extraction from BQA
#extract codes 1111=61440, 1101=53248, 1110=57344, 0111=28672
#version 2.0
#******************************************************************************

from osgeo import gdal
import numpy as np
import os
import sys
import re
import glob
import gc
import timeit
from scipy import ndimage
import logging
import shutil
import errno


base_url = "http://landsat-pds.s3.amazonaws.com/L8"
base_url_g = "http://storage.cloud.google.com/gcp-public-data-landsat/LC08/PRE"

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def gdal_write_rgb(oname,r,g,b,sds,nodata=0,OutDataType=gdal.GDT_UInt16):
    OutDataType=gdal.GDT_UInt16
    driver=gdal.GetDriverByName("Gtiff")
    nbands=3
    ods=driver.Create(oname,r.shape[1],r.shape[0],nbands,OutDataType)
    ods.SetGeoTransform(sds.GetGeoTransform())
    ods.SetProjection(sds.GetProjection())
    ob=ods.GetRasterBand(1)
    ob.SetNoDataValue(nodata)
    ob.WriteArray(r,0,0)
    ob=ods.GetRasterBand(2)
    ob.SetNoDataValue(nodata)
    ob.WriteArray(g,0,0)
    ob=ods.GetRasterBand(3)
    ob.SetNoDataValue(nodata)
    ob.WriteArray(b,0,0)        
    ob = None
    ods= None
#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_toa(data,sun_zen,mult,add):
    out = (np.copy(data)*mult+add)/sun_zen
    out[data==0]=0
    return out

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def calc_kelvin(data,mtl,band):
    gain,bias,k1,k2 = get_thermal_gain(mtl,band)
    print gain,bias,k1,k2
#    K2 / ln (K1/Ll +1)
    out = np.copy(data)
    out[data==0]=0.000001
    out = k2/np.log(k1/(out*gain+bias)+1)
    out[data==0]=0
    return out

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def get_sun(mtl):
    searchfile = open(mtl, "r")
    sun_zen = None
    for line in searchfile:
        if "SUN_ELEVATION" in line:
            sun_zen = np.cos(np.radians(90.0-float(re.search("([0-9.-]+)",line.split()[2]).group(0))))
    searchfile.close()
    return sun_zen

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def get_sun_mat(fn,out):
    print fn, out
    if(os.path.exists(fn)):    
        basename = os.path.basename(fn)
        try:
            os.system("cp %s %s"%(fn,out+"/"+basename))
            os.chdir(out)
            os.system("l8_angles %s SOLAR 1 -b 4"%(out+"/"+basename))
            an = re.sub("_ANG.txt","_solar_B04.img",out+"/"+basename)
            ds = gdal.Open(an)
        except:
            print "shit happend"
            return None
        sun_mat = np.cos(np.radians(90.0-ds.GetRasterBand(2).ReadAsArray().astype(np.float32)*0.01))
        map(os.remove,glob.glob(out+"/*solar*"))
        return sun_mat
    return None

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def get_cloud_prc(mtl):
    searchfile = open(mtl, "r")
    value = 0
    for line in searchfile:
        if "CLOUD_COVER" in line:
            value = float(re.search("([0-9.-]+)",line.split()[2]).group(0))
    searchfile.close()
    return value

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def get_thermal_gain(mtl,band):
    searchfile = open(mtl, "r")
    gain = 1.0
    bias = 0.0
    k1 = 1.0
    k2 = 1.0
    nums2 = re.compile(r"[+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?")
    for line in searchfile:
        if "RADIANCE_MULT_BAND_%d"%band in line:
            gain = float(nums2.search(line.split()[2]).group(0))
        if "RADIANCE_ADD_BAND_%d"%band in line:
            bias = float(nums2.search(line.split()[2]).group(0))
        if "K1_CONSTANT_BAND_%d"%band in line:
            k1 = float(nums2.search(line.split()[2]).group(0))
        if "K2_CONSTANT_BAND_%d"%band in line:
            k2 = float(nums2.search(line.split()[2]).group(0))

    searchfile.close()
    return gain,bias,k1,k2

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def gdal_write(oname,data,sds,nodata=-9999,OutDataType=gdal.GDT_Float32,options=None):    
#    OutDataType=gdal.GDT_Float32
    driver=gdal.GetDriverByName("Gtiff")
    nbands=1
    ods=driver.Create(oname,data.shape[1],data.shape[0],nbands,OutDataType,options)
    ods.SetGeoTransform(sds.GetGeoTransform())
    ods.SetProjection(sds.GetProjection())
    ob=ods.GetRasterBand(1)
    ob.SetNoDataValue(nodata)
    ob.WriteArray(data,0,0)
    ob = None
    ods= None

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def remove_small_obj(data,minsize):    
#    lab,count = measure.label(data,return_num=True)
    lab,count = ndimage.measurements.label(data)
#    print count
    sizes = ndimage.sum(data,lab,range(count+1))
    mask_size = sizes < minsize
    rm = mask_size[lab]
    lab[rm] = 0
    return lab>0

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def parce_prod_name(prod):
    parse = re.search("LC8([0-9]{3})([0-9]{3})([0-9]{4})([0-9]{3})",prod)
    path = parse.group(1)
    row  = parse.group(2)
    year = parse.group(3)
    day  = parse.group(4)
    return path,row#,year,day

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def parce_prod_name_new(prod):
    #LC08_L1TP_009029_20170321_20170329_01_T1
    parse = prod.split("_")
    path = parse[2][:3]
    row  = parse[2][3:]
    return path,row#,year,day

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
def check_missed(wrkdir,basename,mask):
    path,row = parce_prod_name(mask)
    if(not os.path.exists(wrkdir+mask)):
        os.system("wget -c -t 0 -O %s %s"%(wrkdir+mask,url))
        url = "%s/%s/%s/%s/%s"%(base_url,path,row,basename,mask)
        if(os.stat(wrkdir+mask).st_size==0):
#            url = "%s/%s/%s/%s/%s"%(base_url_g,path,row,basename,mask)
#            os.system("wget -c -t 0 -O %s %s"%(wrkdir+mask,url))
#            if(os.stat(wrkdir+mask).st_size==0):
            os.remove(wrkdir+mask)
            logging.info("ERROR!!! Can't download missed file %s"%(url))
            return 1
    return 0

#-----------------------------------------------------------------------------------
#-----------------------------------------------------------------------------------
if __name__ == '__main__':
    tic = timeit.default_timer()
    gdal.AllRegister()
    gdal.UseExceptions()
    if (len(sys.argv)<2):
        print "Bad arguments"
        print "Usage:\nlandsat_toa [input_L8_dir] [output_TOA_dir]"
        exit(1)
    
    min_area = 30
    options= [ 'TILED=YES', 'BLOCKXSIZE=256', 'BLOCKYSIZE=256', 'COMPRESS=DEFLATE', 'PREDICTOR=2' ]
    wrkdir = sys.argv[1].rstrip('/')
    outdir_r = sys.argv[2].rstrip('/')    
    basename = os.path.basename(wrkdir)
    path, row = parce_prod_name_new(basename)
#    outdir = "/wrk"+"/%s/%s/%s"%(path,row,basename)
    outdir = "/wrk/%s"%(basename)
    print outdir
    mkdir_p(outdir)
    logname = outdir+"/"+basename+".log"
    if(os.path.exists(logname)):
        os.remove(logname)
    logging.basicConfig(format='[%(asctime)s.%(msecs)03d] %(message)s', 
                    datefmt='%Y-%m-%d %H:%M:%S.3', 
                    level=logging.DEBUG, 
                    filename=logname)
    logging.info("Start processing product: %s"%(basename))
#    logging.info("Start downloading MTL and BQA")
#    if(check_missed(wrkdir+"/",basename,basename+"_MTL.txt")!=0 or check_missed(wrkdir+"/",basename,basename+"_BQA.TIF")#!=0):
#        exit(1)
#    logging.info("Downloading MTL and BQA Done")
    outname_cl = outdir+"/"+basename+"_CLD.TIF"
    outname_sn = outdir+"/"+basename+"_SNW.TIF"
    outname_sw = outdir+"/"+basename+"_SDW.TIF"
    sun_zen = get_sun_mat(wrkdir+"/"+basename+"_ANG.txt",outdir)
    if(sun_zen is None):
        print "Single Sun Zenith mode"
        sun_zen = get_sun(wrkdir+"/"+basename+"_MTL.txt")
    if(sun_zen is None):
        logging.info("ERROR!!! Can't read sun zenith angle")
        exit(2)
    logging.info("Sun Zenith angle = %f"%(np.degrees(np.median(sun_zen))))
    mult = 2.0000E-05
    add = -0.100000
    scale = 10000
    for tif in glob.glob(wrkdir+"/*.TIF"):
#        if((tif[-7:] == "BQA.TIF") or (tif[-7:] == "B10.TIF") or (tif[-7:] == "B11.TIF")): continue
        if((tif[-7:] == "BQA.TIF")): continue        
        try:
            logging.info("Start processing band: %s"%(tif))
            ds = gdal.Open(tif,gdal.GA_ReadOnly)
        except:
            logging.info("ERROR!!! bad tif: %s"%(tif))
            continue
        if((tif[-7:] == "B10.TIF") or (tif[-7:] == "B11.TIF")):
            band = int(tif[-6:-4])
            data = calc_kelvin(ds.ReadAsArray().astype(np.float),wrkdir+"/"+basename+"_MTL.txt",band)
            oname = outdir+"/"+re.sub(".TIF", "_TPK.TIF",os.path.basename(tif),re.IGNORECASE)
            scale = 10
        else:
            data = calc_toa(ds.ReadAsArray().astype(np.float),sun_zen,mult,add)
            oname = outdir+"/"+re.sub(".TIF", "_TOA.TIF",os.path.basename(tif),re.IGNORECASE)
            scale = 10000
        try:
            gdal_write(oname,data*scale,ds,0,gdal.GDT_UInt16,options)
        except:
            logging.info("ERROR!!! Can't write output file %s"%(oname))
            continue
        logging.info("Finish processing band: %s"%(tif))
        del data, ds
    try:
        logging.info("Start reading BQA: %s"%(wrkdir+"/"+basename+"_BQA.TIF"))
        dsbqa = gdal.Open(wrkdir+"/"+basename+"_BQA.TIF",gdal.GA_ReadOnly)
        bqa = dsbqa.ReadAsArray()
        logging.info("Finish reading BQA: %s"%(basename+"_BQA.TIF"))
    except:
        logging.info("ERROR!!! Can't read BQA file %s"%(basename+"_BQA.TIF"))
        exit(3)
    
    logging.info("Start extraction CLOUD mask")
    cloud = np.logical_or(bqa==6816,np.logical_or(bqa==6820,np.logical_or(bqa==6824,np.logical_or(bqa==6828,np.logical_or(bqa==6896,np.logical_or(bqa==2752,np.logical_or(bqa==2800,np.logical_or(bqa==2804,np.logical_or(bqa==2808,bqa==2812)))))))))
    mask_g = remove_small_obj(cloud,min_area)
    mask_f = ndimage.morphology.binary_fill_holes(mask_g)
    try:
        gdal_write(outname_cl,mask_f,dsbqa,0,gdal.GDT_Byte,options)
    except:
        logging.info("ERROR!!! Can't write output file %s"%(outname_cl))
    del cloud, mask_g, mask_f
    logging.info("Finish extraction CLOUD mask")
    logging.info("Start extraction SNOW mask")
    snow = np.logical_or(bqa==3744,np.logical_or(bqa==3748,np.logical_or(bqa==3752,bqa==3756)))
    mask_g = remove_small_obj(snow,min_area)
    mask_f = ndimage.morphology.binary_fill_holes(mask_g)
    try:
        gdal_write(outname_sn,mask_f,dsbqa,0,gdal.GDT_Byte,options)
    except:
        logging.info("ERROR!!! Can't write output file %s"%(outname_sn))
    del snow, mask_g, mask_f
    logging.info("Finish extraction SNOW mask")

    logging.info("Start extraction SHADOW mask")
    shadow = np.logical_or(bqa==7072,bqa==2976)
    mask_g = remove_small_obj(shadow,min_area)
    mask_f = ndimage.morphology.binary_fill_holes(mask_g)
    try:
        gdal_write(outname_sw,mask_f,dsbqa,0,gdal.GDT_Byte,options)
    except:
        logging.info("ERROR!!! Can't write output file %s"%(outname_sw))
    del shadow, mask_g, mask_f
    logging.info("Finish extraction SHADOW mask")
    
    del bqa, dsbqa

    gc.collect()
    logging.info("Start copying MTL and BQA")
    shutil.copy(wrkdir+"/"+basename+"_MTL.txt",outdir)
    shutil.copy(wrkdir+"/"+basename+"_BQA.TIF",outdir)
    logging.info("Finish copying MTL and BQA")
    logging.info("Processed by %f sec"%(timeit.default_timer()-tic))
    print "Processed by %f sec"%(timeit.default_timer()-tic)
#    outdir = "/wrk"+"/%s/%s/%s"%(path,row,basename)
#    outdir = "/wrk/%s"%(basename)
    mkdir_p(outdir_r+"/%s/%s"%(path,row))
#    shutil.copytree("/wrk/%s"%(basename),outdir_r)
#    shutil.rmtree("/wrk/%s"%(basename))
    os.system("cp -r /wrk/%s %s"%(basename,outdir_r+"/%s/%s"%(path,row)))
    os.system("rm -r /wrk/%s"%(basename))
    print "Done"    
    exit(0)
    
