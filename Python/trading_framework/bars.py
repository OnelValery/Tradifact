import datetime

# the table below maximizes the amount of bars per request for a given barSize based on the table at
# https://interactivebrokers.github.io/tws-api/historical_limitations.html#gsc.tab=0
barSize2durationStr = {"1 secs": "1800 S",
                       "5 secs": "3600 S",
                       "10 secs": "14400 S",
                       "15 secs": "14400 S",
                       "30 secs": "28800 S",

                       "1 min": "1 D",
                       "2 mins": "2 D",
                       "3 mins": "1 W",
                       "5 mins": "1 W",
                       "10 mins": "1 W",
                       "15 mins": "1 W",
                       "20 mins": "1 W",
                       "30 mins": "1 M",

                       "1 hour": "1 M",
                       "2 hours": "1 M",
                       "3 hours": "1 M",
                       "4 hours": "1 M",
                       "8 hours": "1 M",

                       "1 day": "1 Y",
                       "1 week": "1 Y",
                       "1 month": "1 Y"}

barSize2indextype = {}
for barSize, durationStr in barSize2durationStr.items():
    if "sec" in barSize or "min" in barSize or "hour" in barSize:
        barSize2indextype[barSize] = datetime.datetime
    else:
        barSize2indextype[barSize] = datetime.date


def barsize2barsize_string(barsize):
    # transform the bar size into a string, timescale expressed in days or larger are not supported at this time
    barsize_string = ""
    if barsize < 60:
        barsize_string = str(barsize) + " sec" + ("s" if barsize > 1 else "")
    elif barsize <= 1800:
        if (barsize % 60) != 0:
            print("The bar size should be a multiple of 60 when between 60 (i min) and 1800 (30 mins)")
        minutes = barsize // 60
        barsize_string = str(minutes) + " min" + ("s" if minutes > 1 else "")
    elif barsize <= 28800:
        if (barsize % 3600) != 0:
            print("The bar size should be a multiple of 3600 when between 3600 (1 hour) and 28800 (8 hours)")
        hours = barsize // 3600
        barsize_string = str(hours) + " hour" + ("s" if hours > 1 else "")

    if barsize_string not in barSize2durationStr:
        print("The transformed bar size of " + barsize_string + " is not one of the bar sizes supported by IB")
        print("The valid set is", ", ".join(list(barSize2durationStr.keys())))
        return None
    return barsize_string
