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
#-----------------------------------------------------------------------------------
def calc_esun_dist(date_time):
    date = string.split(date_time,"T")[0]
    date = string.split(date,"-")
    doy=datetime.date(int(date[0]),int(date[1]),int(date[2])).timetuple().tm_yday
#    print doy
    return (1.0-0.01672*np.cos(np.deg2rad(0.9856*doy-4)))
    
EAI = np.asarray((1965.62,1890.03,1673.46,1105.24),dtype=np.float_)
print "EAI values\n", EAI
toa_gain = np.asarray((2.27776186635e-05,2.43266575543e-05,2.72028456842e-05,4.23388094544e-05),dtype=np.float_)
print "ps:reflectanceCoefficient\n", toa_gain
rad_gain = 0.01
print "ps:radiometricScaleFactor\n", rad_gain

date = "2017-04-09T10:10:33+00:00"
print "date and time\n", date

sun_elevation = 4.560461e+01
print "opt:illuminationElevationAngle\n",sun_elevation

DN = np.asarray((4681,4116,3068,7079),dtype=np.float_)
print "DN values blue,green,red,nir\n",DN

esun_dist = calc_esun_dist(date)
print "EarthSun Distance for doy 99\n",esun_dist
num = np.pi*(esun_dist*esun_dist)
den = EAI[:]*np.cos(np.radians(90.0-sun_elevation))

TOA_from_coeff = DN[:]*toa_gain[:]
print "TOA from ps:reflectanceCoefficient\n",TOA_from_coeff

RAD = DN[:]*rad_gain
print "Radiance values\n",RAD

TOA_from_calc = RAD[:]*(num/den[:])
print "TOA from calculations\n", TOA_from_calc

dif = TOA_from_coeff - TOA_from_calc
print "Difference",dif

ndvi_coeff = (TOA_from_coeff[3]-TOA_from_coeff[2])/(TOA_from_coeff[3]+TOA_from_coeff[2])
print "NDVI from TOA_coeff\n",ndvi_coeff
ndvi_calc = (TOA_from_calc[3]-TOA_from_calc[2])/(TOA_from_calc[3]+TOA_from_calc[2])
print "NDVI from TOA_calc\n",ndvi_calc

dif_ndvi = ndvi_coeff-ndvi_calc
print "NDVI difference\n", dif_ndvi
