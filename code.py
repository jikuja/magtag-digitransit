# SPDX-License-Identifier: MIT

import ssl
import wifi
import socketpool
import adafruit_requests
from adafruit_datetime import datetime
import alarm
import board
import supervisor
import displayio
import terminalio
import time
from adafruit_display_text import label
from analogio import AnalogIn

# https://github.com/micropython/micropython-lib/blob/master/python-stdlib/functools/functools.py#L20
def reduce(function, iterable, initializer=None):
    it = iter(iterable)
    if initializer is None:
        value = next(it)
    else:
        value = initializer
    for element in it:
        value = function(value, element)
    return value

def setupDisplay():
    # Setup 1
    global display
    display = board.DISPLAY
    g = displayio.Group()

    # Background
    background_bitmap = displayio.Bitmap(display.width // 8, display.height // 8, 1)
    palette = displayio.Palette(1)
    palette[0] = 0xFFFFFF
    t = displayio.TileGrid(background_bitmap, pixel_shader=palette, x=0, y=0)
    background_group = displayio.Group(scale=8)
    background_group.append(t)
    g.append(background_group)

    # Text
    global text_group
    text_group = displayio.Group(scale=1, x=1, y=1)
    #text_area = label.Label(terminalio.FONT, text=' '*20, color=0x000000)
    # TODO: text_area.text = loading... # TODO: calculate value for 20
    global text_area
    text_area = label.Label(terminalio.FONT, text='loading...', color=0x000000, anchor_point=(0, 0), anchored_position=(0,0))
    text_group.append(text_area)  # Add this text to the text group
    g.append(text_group)

    # Setup 2
    display.root_group = g
    display.refresh()

# First voltage print asap after setting up magtag
_batt_monitor = AnalogIn(board.BATTERY)
def battery() -> float:
    return (_batt_monitor.value / 65535.0) * 3.3 * 2
print("Voltage: %s" % str(battery()))

# Get configs from a config.py file
try:
    from config import config
except ImportError:
    print("Configs are kept in config.py, please add them there!")
    raise

#####
# setup from config.py
#####
debug = config.get("debug", False)
wifi_ssid = config["wifi_ssid"]
wifi_psk = config["wifi_psk"]
aio_username = config["aio_username"]
aio_key = config["aio_key"]
digitraffic_key = config.get("digitraffic_key")
digitraffic_url = config.get("digitraffic_url")
TIME_URL = "https://io.adafruit.com/api/v2/%s/integrations/time/strftime?x-aio-key=%s" % (aio_username, aio_key)
TIME_URL += "&fmt=%25Y-%25m-%25d+%25H%3A%25M+%25z+%25Z"

linesstopsdata = config["linesstopsdata"]
voltage_limit = config.get("voltage_limit", 3.0)

#####
# Create digitransit payload
#####
stops_str = '"' + '", "'.join(linesstopsdata.keys()) + '"'
if debug:
    print("stops_str: %s" % stops_str)
query = """query
{
  stops(ids: [%s]) {
    name
    gtfsId
    stoptimesWithoutPatterns(numberOfDepartures: 8, omitCanceled: false) {
      realtime
      realtimeArrival
      realtimeState
      arrivalDelay
      serviceDay
      trip {
        routeShortName
      }
    }
  }
}
""" % stops_str

if debug:
    print("Digitransit playload %s" % query)

#####
# Connect wifi
#####
def setupWifi():
    print("My MAC addr:", [hex(i) for i in wifi.radio.mac_address])
    print("Connecting to %s" % wifi_ssid)
    wifi.radio.connect(wifi_ssid, wifi_psk)
    print("Connected to %s!" % wifi_ssid)
    print("My IP address is", wifi.radio.ipv4_address)

    # Print voltage again
    print("Voltage later: %s" % str(battery()))

    ######
    # setup TCP pooling and requests object with TLS
    ######
    global requests
    pool = socketpool.SocketPool(wifi.radio)
    requests = adafruit_requests.Session(pool, ssl.create_default_context())

def requestTimeAndCalculateOffset():
    ######
    # request current time
    ######
    print("Fetching time from %s" % TIME_URL.replace(aio_key, "*****"))
    response = requests.get(TIME_URL)
    timeNow = response.text
    print("-" * 40)
    print("time now: %s" % response.text)
    print("-" * 40)
    # Calculcate offset with UTC
    timeOffset = 3*60*60 if "EEST" in timeNow else 2*60*60
    return timeNow, timeOffset

def sortHelper(elem):
    return elem["serviceDay"] + elem["realtimeArrival"]

def filterHelper(elem, lines):
    return elem["trip"]["routeShortName"] in lines

def extractAndFilterStopTimes(elem):
    id = elem["gtfsId"]
    lines = linesstopsdata[id]
    stopTimes = elem["stoptimesWithoutPatterns"]
    filtered = list(filter(lambda e: filterHelper(e, lines), stopTimes))
    return filtered

def createLine(elem, timeOffset):
    arrTime = datetime.fromtimestamp(elem["serviceDay"] + elem["realtimeArrival"] + timeOffset).time()
    busNumber = elem["trip"]["routeShortName"]
    realtimeState = elem["realtimeState"]
    delta = elem["arrivalDelay"]
    realtime = elem["realtime"]
    if elem["realtime"]:
        tilde = ""
    else:
        tilde = "~"
    if realtimeState == "CANCELED":
        tilde = "C"

    ret = """{:>4} {:1}{:02d}:{:02d} d: {:5d}s state: {:}""".format(busNumber, tilde, arrTime.hour, arrTime.minute, delta, realtimeState)
    return ret

def main(timeNow, timeOffset):
    #####
    # Get digitransit API data
    #####
    headers = {"digitransit-subscription-key": digitraffic_key}
    response = requests.post(digitraffic_url, json={"query": query}, headers=headers)
    print("Digitransit API: %s" % response.status_code)

    if response.status_code == 200:
        voltage = battery()
        payload = response.json()["data"]["stops"]
        if debug:
            print("payload: %s" % payload)

        filtered = [extractAndFilterStopTimes(elem) for elem in payload]
        print("filtered: %s" % len(filtered))
        merged = reduce(lambda a,b: a+b, filtered)
        merged.sort(key=sortHelper)

        # create stop time information to display on magtag
        result = [createLine(x, timeOffset) for x in merged]

        # merge time, voltage information and line data
        result = timeNow + ' ' + str(voltage) + ' volts\n' + '\n'.join(result[:7])
        print(result)
        return result
    else:
        raise Exception("Digitransit API: returned status code: %s" % response.status_code)

try:
    setupDisplay()
    setupWifi()
    timeNow, timeOffset = requestTimeAndCalculateOffset()
    result = main(timeNow, timeOffset)

except Exception as e:
    print('completed with Exception')
    import traceback
    import io
    import storage
    print('traceback.print_exception')
    traceback.print_exception(e, e, e.__traceback__)
    result = ''.join(traceback.format_exception(e, e, e.__traceback__))
    print('result from excepion no wrapping')
    print(result)
    #result = magtag.wrap_nicely(result, 48)
    print('result from excepion')
    print(result)
    #result = '\n'.join(result)
    print('Final result')
    print(result)

    # save stack on file
    if not supervisor.runtime.usb_connected:
        storage.remount("/", False, disable_concurrent_write_protection=True)
        file = io.open("stack.txt", "w")
        traceback.print_exception(e, e, e.__traceback__, file=file)

# Display result
text_area.text = result

# display warning on low woltage
# TODO: rewrite with display io
# TODO: blink LEDs
if battery() < voltage_limit:
    print("LOW Voltage")
    battery_label = label.Label(terminalio.FONT, text="\nLOW BAT\nLOW BAT\nLOW BAT\nLOW BAT\nLOW BAT\nLOW BAT",
        color=0x000000, background_color=0xAAAAAA,
        anchor_point=(0, 0), anchored_position=(180,24),
        padding_top=10, padding_bottom=10, padding_left=10, padding_right=20)
    text_group.append(battery_label)

# Make sure we can refresh display. Sleep if needed. Display support updates once per 5 seconds
print("display.time_to_refresh: " + str(display.time_to_refresh))
time.sleep(display.time_to_refresh + 0.10)
display.refresh()




if supervisor.runtime.usb_connected:
    #deinit some i/o
    _batt_monitor.deinit()
    #displayio.release_displays() # this will also wait until display is not busy
    # set up pin alarms
    pin_alarm = alarm.pin.PinAlarm(pin=board.D11, value=False, pull=True)  # button D
    # setup sleep
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 15*60)

    # sleep and restart
    print("Sleeping...")
    #time.sleep(15*60) # sleep will block REPL
    alarm.light_sleep_until_alarms(time_alarm, pin_alarm)
    print("Resetting...")
    supervisor.reload()
else:
    #deinit some i/o
    _batt_monitor.deinit()
    displayio.release_displays() # this will also wait until display is not busy
    # set up pin alarms
    pin_alarm = alarm.pin.PinAlarm(pin=board.D11, value=False, pull=True)  # button D
    # setup sleep
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 15*60)

    # restart
    print("deep sleep")
    print("exit_and_deep_sleep_until_alarms...")
    alarm.exit_and_deep_sleep_until_alarms(time_alarm, pin_alarm)
