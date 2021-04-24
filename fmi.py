import requests
import datetime as dt
import requests
import time
import re
import log
import os
import io
import pandas as pd
from lxml import etree
import xml.etree.ElementTree as ET
import dateutil
import pytz

local_tz = pytz.timezone('Europe/Helsinki') # use your local timezone name here

def now():
    return dt.datetime.now(tz=local_tz)
# end def

class weather:
    def __init__ ( self, hour, temp, wind, moist):
        self.hour = hour
        self.temp = temp
        self.wind = wind
        self.moist = moist
    def __str__ ( self):
        return "%02d.00: %3d C, %2d m/s, %d %%" % (self.hour, self.temp, self.wind, self.moist)
    def __repr__ ( self):
        return "%02d.00: %3d C, %2d m/s, %d %%" % (self.hour, self.temp, self.wind, self.moist)
    
        
class weatherForecast:

    def __init__ ( self, log, useDummyData):
        self.useDummyData = useDummyData
        self.log = log
        self.lastFetch = None
        self.forecastDate = None

        self.sunrise = None
        self.sunset = None
        
        self.weatherSeq = {}


    def fetchUrl ( self, targetDate):

        self.log.log ( 10, "weatherForecast.fetchUrl(): targetDate %s\n" % targetDate)
        
        # Check if we already have forecast fetch
        if self.forecastDate is None:
            self.log.log ( 5, "weatherForecast.fetchUrl(): No data - must fetch.\n" )
        
        if ( self.forecastDate is not None) and ( targetDate == self.forecastDate):
            self.log.log ( 10, "weatherForecast.fetchUrl(): Forecast for %s is already fetch.\n" % self.forecastDate)
            return
        
        # Try fetching forecast at most once every 5 minues
        if (self.lastFetch is not None) and ( (now() - self.lastFetch) < dt.timedelta ( minutes = 5)):
            self.log.log ( 99, "weatherForecast.fetchUrl(): Tried fetching URL again too soon.. (< 5 minutes)\n")
            return None

        r = requests.get('http://opendata.fmi.fi/wfs/fin?service=WFS&version=2.0.0&request=GetFeature&storedquery_id=fmi::forecast::harmonie::surface::point::simple&place=Haukipudas&')

        self.lastFetch = now()

        self.forecastDate = targetDate
        
        return r.content


    def isDataUpToDate ( self, targetDate):
        return ( targetDate == self.forecastDate)
    
    def parseText ( self, pageText):
        self.prices = [None] * 24

        root = etree.fromstring(pageText) #create an ElementTree object 
        namespaces = {'wfs': 'http://www.opengis.net/wfs/2.0'
                    } # add more as needed

        # http://wiki.tei-c.org/index.php/Remove-Namespaces.xsl
        xslt=b'''<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">
        <xsl:output method="xml" indent="no"/>

        <xsl:template match="/|comment()|processing-instruction()">
            <xsl:copy>
            <xsl:apply-templates/>
            </xsl:copy>
        </xsl:template>

        <xsl:template match="*">
            <xsl:element name="{local-name()}">
            <xsl:apply-templates select="@*|node()"/>
            </xsl:element>
        </xsl:template>

        <xsl:template match="@*">
            <xsl:attribute name="{local-name()}">
            <xsl:value-of select="."/>
            </xsl:attribute>
        </xsl:template>
        </xsl:stylesheet>
        '''

        xslt_doc=etree.parse(io.BytesIO(xslt))
        transform=etree.XSLT(xslt_doc)
        root=transform(root)

        # A dictionary with time as key and as a value a second dict with
        # measurement name as key and meas result as value 
        meas = {}

        for member in root.findall('member', namespaces):
            for element in member:
                time_str = element.find('Time').text
                dt_utc = dateutil.parser.isoparse(time_str)
                dt_eet = dt_utc.replace(tzinfo=dt.timezone.utc).astimezone(tz=local_tz)

                if dt_eet not in meas:
                    meas[dt_eet] = {}

                name = element.find("ParameterName").text
                value = element.find("ParameterValue").text

                meas[dt_eet][name] = value
            # end for
        # end for

        df = pd.DataFrame()
        df = df.from_dict ( meas, orient='index')

        fc_date = self.getForecastDate()
        fc_date = dt.datetime ( fc_date.year, fc_date.month, fc_date.day).astimezone(tz=local_tz)
        fc_plus1_date = fc_date + dt.timedelta ( days=1)
        
        df_forecast_date = df.loc [ (df.index >= fc_date) & (df.index < fc_plus1_date)]

        sunrise = None
        sunset = None
        for index, series in df_forecast_date.iterrows():
            h = int(index.hour)
            temp = float(series['Temperature'])
            wind = float(series['WindSpeedMS'])
            humidity = float(series['Humidity'])
            self.weatherSeq[h] = weather ( hour=h, temp=temp, wind=wind, moist=humidity)

            if sunrise is None and float(series['RadiationGlobal']) > 10.0:
                sunrise = dt.datetime.combine ( self.forecastDate, dt.time(hour=h))
            # end if

            if sunrise is not None and sunset is None and float(series['RadiationGlobal']) < 10.0:
                sunset = dt.datetime.combine ( self.forecastDate, dt.time(hour=h))
            # end if
        # end for

        self.sunrise = sunrise
        self.sunset = sunset

        self.log.log ( 1, "Weather sequence parsed: \n")
        for k in self.weatherSeq.keys():
            self.log.log ( 1, "  %s\n" % self.weatherSeq[k])
        # end for
    # end def
            
    def fetchAndParseUrl ( self, date):
        text = self.fetchUrl ( date)

        if text is not None:
            self.parseText ( text)

    def getWeatherSeq ( self):
        return self.weatherSeq

    def getForecastDate ( self):
        return self.forecastDate

    def getSunrise ( self):
        return self.sunrise

    def getSunset ( self):
        return self.sunset

    def getTempSeq ( self):
        seq = [None]*24
        for hour in range(24):
            if hour not in self.weatherSeq.keys():
                seq[hour] = None
            else:
                seq[hour] = self.weatherSeq[hour].temp

        return seq

    # This method provides some kind of temperature sequence even if
    # we got some Nones from parsing the web page data. Average of
    # useful numbers are used for the Nones. If all the values parsed
    # were Nones, assume that it was -5 degrees centigrade.
    def getNonNoneTempSeq ( self):
        numValidTemps = 0
        validTempSum = 0.0
        seq = [None]*24
        for hour in range(24):
            if hour not in self.weatherSeq.keys():
                seq[hour] = None
            else:
                seq[hour] = self.weatherSeq[hour].temp
                validTempSum += seq[hour]
                numValidTemps = numValidTemps + 1

        if numValidTemps == 0:
            aveTemp = -5 # Assume -5 C if we did not get any temperatures
        else:        
            aveTemp = validTempSum / numValidTemps

        for ind in range(24):
            if seq[ind] is None:
                seq[ind] = aveTemp
                
        return seq
    
if __name__ == "__main__":

    import argparse

    parser = argparse.ArgumentParser(description='Electricity Nordpool Spot Price.')
    parser.add_argument('-R', action='store_true', dest='really', help='Give this option if you really want to fetch the Web page.')
    parser.add_argument('-D', action='store', type=str, dest='targetDate', help='The date of the forecast YYYYMMDD')
    parser.add_argument('-d', action='store_true', dest='dump', help='Fetch and dump web page source code, requires also option -R')
    parser.add_argument('-v', action='store', type=int, dest='verboseLevel', default=0)
    args = parser.parse_args()

    log = log.logger ( args.verboseLevel)

    if args.targetDate == None:
        targetDate = ( now() + dt.timedelta(days=+1) ).date()
    else:
        targetDate = dt.datetime.strptime ( args.targetDate, "%Y%m%d").date()
    
    if args.dump:
        log.log ( 0, "Fetching URL and dumping the source code..")
        wf = weatherForecast ( log, not args.really)
        text = wf.fetchUrl ( targetDate )
        # Dump the contents
        print ( text)
        if not args.really:
            log.log ( 0, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            log.log ( 0, "The above was read from foreca.txt. Use option -R if you really want to fetch the web page..")
            log.log ( 0, "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        exit()
        
    wf = weatherForecast ( log, not args.really)
    
    wf.fetchAndParseUrl ( targetDate )

    print ( "Date: %s" % wf.getForecastDate())

    wSeq = wf.getWeatherSeq()
    for k in wSeq.keys():
        print ( "%s" % wSeq[k])
    
    print ( "Sunrise: %s" % wf.getSunrise())
    print ( "Sunset: %s" % wf.getSunset())
    
    print ( "tempSeq: %s" % wf.getTempSeq())
    
