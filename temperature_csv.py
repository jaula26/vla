import pandas as pd

class temperatureCsv:
    def __init__(self, filename):
        """
        """
        df = pd.read_csv ( filename)
        df['local_time'] = pd.to_datetime ( df['local_time'], format='%Y-%m-%d %H:%M:%S.%f')
        df.local_time = df.local_time.dt.tz_localize('EET').dt.tz_convert('UTC')
        df = df.set_index('local_time')

        self.df = df

    # end def __init__()
# end class

