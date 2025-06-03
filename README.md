# GPSD-AssistNow

This Python script implements u-blox AssistNow support for GPSD.

## Requirements
You will need to have [gpsd](https://gpsd.io) and the Python3 [requests](https://pypi.org/project/requests/) library installed.

# Usage

[Register](https://portal.thingstream.io/register) at u-blox ThingStream to get a token for the requests. The token is the only required parameter:

```
./gpsd-assistnow.py TOKEN
```

You can pass all the optional parameters as `key=value` pairs on the command line:

```
./gpsd-assistnow.py TOKEN lat=YY.YY lon=XX.XX gnss=gps,glo datatype=eph
```

See the [documentation for u-blox AssistNow A-GNSS](https://developer.thingstream.io/guides/location-services/assistnow-user-guide).
