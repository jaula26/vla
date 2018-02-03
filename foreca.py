import datetime as dt
import requests
import time
import re
import log
import os

def now():
    return ( dt.datetime.today())


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

        if not self.useDummyData:
            os.system ( "curl -s http://www.foreca.fi/Finland/Haukipudas/details/%s > foreca.txt" % targetDate.strftime("%Y%m%d"))

        self.lastFetch = now()

        # Always read data from a file
        text = ""
        with open('foreca.txt', 'r') as myfile:
            text = myfile.read().replace('\n', '')

        self.forecastDate = targetDate;
        
        return ( text);

    def isDataUpToDate ( self, targetDate):
        return ( targetDate == self.forecastDate)
    
    def parseText ( self, pageText):
        self.prices = [None] * 24
        
#        patForDate = r"\d\d?\.\d\d?\.\d\d\d\d";
#        try:
#            m = re.search ( r"Fortum Tarkan tuntihinnat\s+.*\s+(%s)" % patForDate, text);
#        except:
#            self.log.log ( 1, "No date string found")
#            self.pricesDate = None
#            return
#
#        try:
#            self.log.log ( 5, "Found date string: '%s'" % m.groups(1)[0])
#            d = dt.datetime.strptime(m.groups(1)[0],"%d.%m.%Y")
#            self.pricesDate = d.date()
#            self.log.log ( 1, "Parsed date string into %s" % self.pricesDate)
#        except:
#            self.log.log ( 0, "spotprice.parsePriceData: Could not parse date string")
#            self.pricesDate = None
#            return
        # Use ? to make .*?'s non-greedy
        m = re.findall ( r"<div class=\"c0\">\s+<strong>(\d\d.\d\d)</strong>.*?<strong>([+-]?\d+)&deg;</strong>.*?<strong>(\d+) m/s</strong>.*?<strong>(\d{1,2})%</strong>", pageText);
        for entry in m:
            t = dt.datetime.strptime(entry[0],"%H.%M")
            h = t.hour
            if (h < 0) or (h > 23):
                self.log.log ( 0, "Parsed entry '%s': hour %d out of range 0,..., 23?\n" % (entry, h))
                continue
            self.weatherSeq[h] = weather ( hour=h, temp=float(entry[1]), wind=float(entry[2]), moist=float(entry[3]))
            # For some reason there are some extra stuff in the page source.. its fine to break at hour 23.
            if h == 23:
                break

        msun = re.findall (r"<div class=\"csuntime\"><strong>(\d\d.\d\d)</strong></div>.*<div class=\"csunup\">.*?<div class=\"csuntime\"><strong>(\d\d.\d\d)</strong></div>.*<div class=\"csundown\">", pageText); 
        for entry in msun:
            self.sunrise = dt.datetime.combine ( self.forecastDate, dt.datetime.strptime(entry[0],"%H.%M").time())
            self.sunset = dt.datetime.combine ( self.forecastDate, dt.datetime.strptime(entry[1],"%H.%M").time())
                    
        self.log.log ( 1, "Weather sequence parsed: \n")
        for k in self.weatherSeq.keys():
            self.log.log ( 1, "  %s\n" % self.weatherSeq[k])
            
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
    
