#!/usr/bin/env python3

import sys, os, contextlib, struct, json, time, traceback
import requests
import gps, gps.ubx
from gps.misc import monotonic

ME = os.path.basename(sys.argv[0])
USAGE = f"""
Usage: {ME} [key=value ...]

Valid keys:
- device: GPSd device
- token: only used for an unregistered device
- data, gnss, lat, lon, alt, pacc: used for requesting data from u-blox service
- cache_duration: validity of already downloaded data, in hours (default: 3)

Examples:
- registration:
  {ME} [device=DEVICE] token=TOKEN
- update:
  {ME} [device=DEVICE] data=eph gnss=gps,glo lat=LAT lon=LON

Documentation:
    https://support.thingstream.io/hc/en-gb/articles/19691380675356-AssistNow-device-registration
    https://assistnowapi.services.u-blox.com/

"""

class Helpers:
    def here(fname):
        return os.path.join(os.path.abspath(os.path.dirname(__file__)), os.path.basename(fname))

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


class UBlox(gps.ubx.ubx):
    def __init__(self, device=None):
        self.timestamp = 0
        self.verbosity = 0
        self.io_handle = gps.gps_io(write_requested=True, gpsd_device=device)

    def decode_msg(self, data):
        with contextlib.redirect_stdout(None): # suppress output
            consumed = super().decode_msg(data)
        return consumed, data[:consumed], data[consumed:]

    def wait_for(self, m_cls, m_id, timeout=2):
        expected = bytes([0xb5, 0x62, m_cls, m_id])
        data = b''
        start = monotonic()
        while timeout > (monotonic() - start):
            if 0 < self.io_handle.ser.waiting():
                data += self.io_handle.ser.sock.recv(8192)
            consumed, packet, data = self.decode_msg(data)
            if packet[0:4] == expected:
                return packet
        return b''

    def fetch_answer(self, msg):
        cmd = self.commands[msg]
        m_data = cmd["opt"]
        m_cls, m_id, m_data = m_data[0], m_data[1], m_data[2:]
        self.gps_send(m_cls, m_id, m_data)
        return self.wait_for(m_cls, m_id)

    def send_data(self, data):
        while len(data):
            consumed, packet, data = self.decode_msg(data)
            if 0 >= consumed:
                break
            self.gps_send_raw(packet)

    def get_ubx_sec_uniqid(self):
        return self.fetch_answer("SEC-UNIQID")

    def get_ubx_mon_ver(self):
        return self.fetch_answer("MON-VER")

    def ubx_mga_ini_pos_llh(self, lat_deg, lon_deg, alt_m=0, pacc_km=300):
        # UBX-MGA-INI-POS_LLH
        lat = int(lat_deg * 10**7)
        lon = int(lon_deg * 10**7)
        alt = int(alt_m * 10**2)
        acc = int(pacc_km * 10 **6)
        m_data = bytearray(20)
        m_data[0] = 0x01
        m_data[1] = 0x00
        struct.pack_into("<3iI", m_data, 4, lat, lon, alt, acc)
        return self.make_pkt(0x13, 0x40, m_data)


class AssistNow:
    def __init__(self, device=None, cache_duration=3):
        self.ublox = UBlox(device)
        self.cache_duration=Helpers.validate_number(cache_duration, 0, 24)
        self.config_file = Helpers.here("assistnow.json")
        self.cache_file = Helpers.here("assistnow.cache")
        self.config = self.load_config()
        self.cache = self.load_cache()

    def load_config(self):
        config = {}
        try:
            config = json.load(open(self.config_file, "r"))
        except:
            pass
        return config

    def save_config(self):
        if self.config:
            open(self.config_file, "w").write(json.dumps(self.config, indent=2))

    def load_cache(self):
        cache = None
        try:
            s = os.stat(self.cache_file)
            if time.time() - s.st_mtime <= self.cache_duration*3600:
                cache = open(self.cache_file, "rb").read()
        except:
            pass
        return cache

    def save_cache(self):
        if self.cache:
            open(self.cache_file, "wb").write(self.cache)

    def is_registered(self):
        return "chipcode" in self.config

    def register(self, token):
        if self.is_registered():
            raise Exception("Device already registered.")

        sec_uniqid = self.ublox.fetch_answer("SEC-UNIQID").hex().upper()
        mon_ver = self.ublox.fetch_answer("MON-VER").hex().upper()
        if not sec_uniqid or not mon_ver:
            raise Exception("Device did not answer")
        url = "https://api.thingstream.io/ztp/assistnow/credentials"
        data = {"token": token, "messages": {"UBX-SEC-UNIQID": sec_uniqid, "UBX-MON-VER": mon_ver}}
        r = requests.post(url, json=data)
        if r.status_code != requests.codes.ok:
            r.raise_for_status()
        self.config = r.json()
        self.save_config()

    def update(self, **kwargs):
        if not self.is_registered():
            raise Exception("Device not registered.")

        if not kwargs:
            kwargs = self.config
        allowed_data = [d.strip() for d in self.config["allowedData"].split(",")]
        params = {
            "data": Helpers.validate_list(kwargs.get("data", None), allowed_data),
            "gnss": Helpers.validate_list(kwargs.get("gnss", None), ["gps", "glo", "gal", "bds", "qzss"]),
            "lat": Helpers.validate_number(kwargs.get("lat", None), -90, 90),
            "lon": Helpers.validate_number(kwargs.get("lon", None), -180, 180),
            "alt": Helpers.validate_number(kwargs.get("alt", None), -1000, 50000),
            "pacc": Helpers.validate_number(kwargs.get("pacc", None), 0, 6000000),
        }
        if params["lat"] is not None and params["lon"] is not None:
            params["filteronpos"] = 1

        changed = False
        for k, v in params.items():
            if self.config.get(k, None) != v:
                self.config[k] = v
                changed = True
        if changed:
            print("Update parameters have changed: invalidate cache")
            self.save_config()
            self.cache = None

        if not self.cache:
            url = self.config["serviceUrl"]
            params["chipcode"] = self.config["chipcode"]
            print(f"Fetching data from {url}")
            r = requests.get(url, params=params)
            if r.status_code != requests.codes.ok:
                r.raise_for_status()
            data = r.content
            if params["lat"] is not None and params["lon"] is not None:
                args = [params[k] for k in ["lat", "lon"]]
                kwargs = {k: params[k] for k in ["alt", "pacc"] if params[k] is not None}
                initial_position = self.ublox.ubx_mga_ini_pos_llh(*args, **kwargs)
                data = initial_position + data
            self.cache = data
            self.save_cache()
        else:
            print("Valid cache found")

        self.ublox.send_data(self.cache)
        print("Sent data to device")

if __name__ == "__main__":

    kwargs = {}
    try:
        for item in sys.argv[1:]:
            k, v = item.split("=", 1)
            kwargs[k] = v
    except:
        print(USAGE)
        quit(1)

    assistnow = AssistNow(
        device=kwargs.get("device", None),
        cache_duration=kwargs.get("cache_duration", 3),
    )

    if not assistnow.is_registered():
        if not "token" in kwargs:
            print("Device is unregistered")
            print(f"Usage: {os.path.basename(sys.argv[0])} token=TOKEN")
            quit(1)
        try:
            assistnow.register(kwargs["token"])
            print(f"Device now registered with chipcode {assistnow.config['chipcode']}")
            quit(0)
        except:
            print("Error during registration")
            traceback.print_exc()
            quit(1)

    try:
        assistnow.update(**kwargs)
    except:
        print("Error during update")
        traceback.print_exc()
        quit(1)
