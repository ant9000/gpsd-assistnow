# GPSD-AssistNow

This Python script implements u-blox AssistNow support for GPSD.

## Requirements
You will need to have [gpsd](https://gpsd.io) and Python3 [requests](https://pypi.org/project/requests/) library installed.

# Usage

You can get basic usage with:
```
./assistnow.py help
```

To request data, you need to [register](https://portal.thingstream.io/register) an account at u-blox ThingStream service.
You can then obtain a token for registering devices, by creating an AssistNow profile at 
[Location Services > ZTP > Device Profile](https://portal.thingstream.io/app/location-services/device-profiles).

To register your device, launch

```
./assistnow.py [device=DEVICE] token=TOKEN
```

with the newly created token. If everything works correctly, you will find a file named `assistnow.json` containing authentication data for the update requests. You might need to specify an explicit device (for instance, `/dev/gpsd0`) if you have configured more than one in GPSd.

For update requests, pass all the optional parameters as `key=value` pairs on the command line. For instance:

```
./assistnow.py data=ualm,utime,ulorb_l1 gnss=gps,glo lat=YY.YY lon=XX.XX
```

Received A-GNSS data is cached in `assistnow.cache`, and will be used for further requests with the same parameters for up to `cache_duration` hours. Request parameters are saved to `assistnow.json`; if not explicitly provided on the command line, they will default to last used ones. If parameters change, cache will be invalidated.

See the [documentation for u-blox AssistNow A-GNSS](https://support.thingstream.io/hc/en-gb/articles/19690127778204-AssistNow-User-guide)
