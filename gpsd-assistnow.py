#!/usr/bin/env python3

import sys, os, contextlib, struct
import requests
import gps, gps.ubx

def assistnow(token, **kwargs):
    DATATYPES = ["eph", "alm", "aux", "pos"]
    FORMATS = ["mga", "aid"]
    GNSS = ["gps", "glo", "gal", "bds", "qzss"]

    def validate_value(value, available_choices):
        if value is not None and value not in available_choices:
            raise ValueError(f"Unknown value '{value}'; valid choices are: {', '.join(available_choices)}")
        return value

    def validate_list(values, available_choices):
        if values:
            if type(values) == str:
                values = [v.strip() for v in values.split(",")]
            for v in values:
                if not v in available_choices:
                    raise ValueError(f"Unknown value '{v}'; valid choices are: {', '.join(available_choices)}")
            return ",".join(values)

    def validate_number(value, min_value, max_value):
        if value is not None:
            try:
                value = float(value)
            except ValueError:
                raise ValueError(f"Invalid value '{v}'; not a number")
            if not min_value <= value <= max_value:
                raise ValueError(f"Invalid value '{v}'; not in [{min_value}, {max_value}]")
        return value

    url = "https://online-live1.services.u-blox.com/GetOnlineData.ashx"
    params = {
        "token": token,
        "datatype": validate_list(kwargs.get("datatype", None), DATATYPES),
        "format": validate_value(kwargs.get("format", None), FORMATS),
        "gnss": validate_list(kwargs.get("gnss", None), GNSS),
        "lat": validate_number(kwargs.get("lat", None), -90, 90),
        "lon": validate_number(kwargs.get("lon", None), -180, 180),
        "alt": validate_number(kwargs.get("alt", None), -1000, 50000),
        "pacc": validate_number(kwargs.get("pacc", None), 0, 6000000),
        "tacc": validate_number(kwargs.get("tacc", None), 0, 3600),
        "latency": validate_number(kwargs.get("latency", None), 0, 3600),
    }
    # u-blox uses semicolon as querystring separator
    data = ";".join([f"{k}={v}" for k,v in params.items() if v is not None])
    if params["lat"] is not None and params["lon"] is not None:
        data += ";filteronpos"
    r = requests.get(url, params=data)
    if r.status_code != requests.codes.ok:
        r.raise_for_status()
    data = r.content
    if params["lat"] is not None and params["lon"] is not None:
        # UBX-MGA-INI-POS_LLH
        lat = int(params["lat"] * 10**7)
        lon = int(params["lon"] * 10**7)
        alt = int((params["alt"] or 0) * 10**2)
        acc = int((params["pacc"] or 300) * 10 **6)
        m_data = bytearray(20)
        m_data[0] = 0x01
        m_data[1] = 0x00
        struct.pack_into("<3iI", m_data, 4, lat, lon, alt, acc)
        gps_model = gps.ubx.ubx()
        initial_position = gps_model.make_pkt(0x13, 0x40, m_data)
        data = initial_position + data
    return data

def send2gps(data):
    gps_model = gps.ubx.ubx()
    gps_model.verbosity = 2
    gps_model.timestamp = 0
    gps_model.io_handle = gps.gps_io(write_requested=True)
    while True:
        with contextlib.redirect_stdout(None):
            consumed = gps_model.decode_msg(data)
        if 0 >= consumed:
            break
        packet, data = data[:consumed], data[consumed:]
        gps_model.gps_send_raw(packet)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {os.path.basename(sys.argv[0])} token [key=value, ...]")
        sys.exit(1)
    token = sys.argv[1]
    kwargs = {}
    for item in sys.argv[2:]:
        k, v = item.split("=", 1)
        kwargs[k] = v
    try:
        data = assistnow(token, **kwargs)
    except ValueError as e:
        print(e)
        sys.exit(1)
    if data:
        send2gps(data)
