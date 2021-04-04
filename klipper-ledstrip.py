#!/usr/bin/env python3
# pylint: disable=C0326
'''
Script to take info from Klipper and light up WS281x LED strip based on current status
'''

import json
import math
import time
import requests
from rpi_ws281x import Adafruit_NeoPixel

LED_COUNT      = 10      # Number of LED pixels.
LED_PIN        = 10      # GPIO pin connected to the pixels (18 uses PWM, 10 uses SPI).
LED_FREQ_HZ    = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA        = 10      # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 100     # Set to 0 for darkest and 255 for brightest
LED_INVERT     = False   # True to invert the signal (when using NPN transistor level shift)
LED_CHANNEL    = 0       # set to '1' for GPIOs 13, 19, 41, 45 or 53

## Colors to use          R    G    B
HEATING_BASE_COLOR     = (0  , 0  , 255)
HEATING_PROGRESS_COLOR = (255, 0  , 0  )
PRINT_BASE_COLOR       = (0  , 0  , 0  )
PRINT_PROGRESS_COLOR   = (0  , 255, 0  )
STANDBY_COLOR          = (255, 0  , 255)
PAUSED_COLOR           = (0  , 255, 0  )
ERROR_COLOR            = (255, 0  , 0  )

## Reverses the direction of progress and chase
REVERSE = True


def printer_state():
    ''' Get printer status '''
    url = 'http://localhost:7125/printer/objects/query?print_stats'
    ret = requests.get(url)
    return json.loads(ret.text)['result']['status']['print_stats']['state']


def heating_percent(component):
    ''' Get heating percent for given component '''
    url = f'http://localhost:7125/printer/objects/query?{component}'
    temp = json.loads(requests.get(url).text)['result']['status'][component]
    if temp['target'] == 0.0:
        return 0
    return math.floor(temp['temperature'] / temp['target'] * 100)


def printing_percent():
    ''' Get printing progress percent '''
    url = 'http://localhost:7125/printer/objects/query?display_status'
    req = json.loads(requests.get(url).text)
    return math.floor(req['result']['status']['display_status']['progress']*100)


def average(num_a, num_b):
    ''' Average two given numbers '''
    return round((num_a + num_b) / 2)


def mix_color(colour1, colour2, percent_of_c1=None):
    ''' Mix two colors to a given percentage '''
    if percent_of_c1:
        colour1 = [x * percent_of_c1 for x in colour1]
        percent_of_c2 = 1 - percent_of_c1
        colour2 = [x * percent_of_c2 for x in colour2]

    col_r = average(colour1[0], colour2[0])
    col_g = average(colour1[1], colour2[1])
    col_b = average(colour1[2], colour2[2])
    return tuple([int(col_r), int(col_g), int(col_b)])


def color_brightness_correction(color):
    ''' Adjust given color to set brightness '''
    brightness_correction = LED_BRIGHTNESS / 255
    return (
        int(color[0] * brightness_correction),
        int(color[1] * brightness_correction),
        int(color[2] * brightness_correction)
    )


def progress(strip, percent, base_color, progress_color):
    ''' Set LED strip to given progress with base and progress colors '''
    strip.setBrightness(LED_BRIGHTNESS)
    num_pixels = strip.numPixels()
    upper_bar = (percent / 100) * num_pixels
    upper_remainder, upper_whole = math.modf(upper_bar)
    pixels_remaining = num_pixels

    for i in range(int(upper_whole)):
        pixel = ((num_pixels - 1) - i) if REVERSE else i
        strip.setPixelColorRGB(pixel, *color_brightness_correction(progress_color))
        pixels_remaining -= 1

    if upper_remainder > 0.0:
        tween_color = mix_color(progress_color, base_color, upper_remainder)
        pixel = ((num_pixels - int(upper_whole)) - 1) if REVERSE else int(upper_whole)
        strip.setPixelColorRGB(pixel, *color_brightness_correction(tween_color))
        pixels_remaining -= 1

    for i in range(pixels_remaining):
        pixel = (
            ((pixels_remaining - 1) - i)
            if REVERSE
            else ((num_pixels - pixels_remaining) + i)
        )
        strip.setPixelColorRGB(pixel, *color_brightness_correction(base_color))

    strip.show()


def fade(strip, color, speed='slow'):
    ''' Fade entire strip with given color and speed '''
    speed = 0.05 if speed == 'slow' else 0.005
    for pixel in range(strip.numPixels()):
        strip.setPixelColorRGB(pixel, *color)
    strip.show()

    for i in range(LED_BRIGHTNESS):
        strip.setBrightness(i)
        strip.show()
        time.sleep(speed)

    time.sleep(speed * 5)

    for i in range(LED_BRIGHTNESS, -1, -1):
        strip.setBrightness(i)
        strip.show()
        time.sleep(speed)


def chase(strip, color, reverse):
    ''' Light one LED from one ond of the strip to the other, optionally reversed '''
    strip.setBrightness(LED_BRIGHTNESS)
    for i in reversed(range(strip.numPixels()+1)) if reverse else range(strip.numPixels()+1):
        for pixel in range(strip.numPixels()):
            print(i, pixel)
            if i == pixel:
                strip.setPixelColorRGB(pixel, *color)
            else:
                strip.setPixelColorRGB(pixel, 0, 0, 0)
            strip.show()
            time.sleep(0.01)


def bounce(strip, color):
    ''' Bounce one LED back and forth '''
    chase(strip, color, False)
    chase(strip, color, True)


def run():
    ''' Do work son '''
    strip = Adafruit_NeoPixel(LED_COUNT,
                              LED_PIN,
                              LED_FREQ_HZ,
                              LED_DMA,
                              LED_INVERT,
                              LED_BRIGHTNESS,
                              LED_CHANNEL)
    strip.begin()

    try:
        while True:
            print(printer_state())
            while printer_state() == 'printing':

                bed_heating_percent = heating_percent('heater_bed')
                while bed_heating_percent < 99:
                    # print(f'Bed heating percent: {bed_heating_percent}')
                    progress(strip,
                             bed_heating_percent,
                             HEATING_BASE_COLOR,
                             HEATING_PROGRESS_COLOR)
                    time.sleep(2)
                    bed_heating_percent = heating_percent('heater_bed')

                extruder_heating_percent = heating_percent('extruder')
                while extruder_heating_percent < 99:
                    # print(f'Extruder heating percent: {extruder_heating_percent}')
                    progress(strip,
                             extruder_heating_percent,
                             HEATING_BASE_COLOR,
                             HEATING_PROGRESS_COLOR)
                    time.sleep(2)
                    extruder_heating_percent = heating_percent('extruder')

                printing_percent_ = printing_percent()
                while printing_percent_ < 100:
                    # print(f'Print progress percent: {printing_percent_}')
                    progress(strip,
                             printing_percent_,
                             PRINT_BASE_COLOR,
                             PRINT_PROGRESS_COLOR)
                    time.sleep(2)
                    printing_percent_ = printing_percent()

            while printer_state() == 'standby':
                fade(strip, STANDBY_COLOR, 'slow')

            while printer_state() == 'paused':
                bounce(strip, PAUSED_COLOR)

            while printer_state() == 'error':
                fade(strip, ERROR_COLOR, 'fast')

            time.sleep(2)

    except KeyboardInterrupt:
        for i in range(strip.numPixels()):
            strip.setPixelColorRGB(i, 0, 0, 0)
        strip.show()


if __name__ == '__main__':
    run()