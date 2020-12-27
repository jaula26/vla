import temperature_csv as tc

def test_temperature_csv():
    c = tc.temperatureCsv('../20201218_temp.csv')

    print(c.df)
# end def