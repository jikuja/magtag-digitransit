# magtag-digitransit

![Alt text](image.png)

## Hardware

[Adafruit](https://www.adafruit.com/product/4800) Magtag with [CircuitPython](https://circuitpython.org/board/adafruit_magtag_2.9_grayscale/)

Out of stock on January 2024

[Main documentation](https://learn.adafruit.com/adafruit-magtag) on Adafruit web page.

## Requirements

* [Install UF2 Bootloader](https://learn.adafruit.com/adafruit-magtag/install-uf2-bootloader)
* [Install CircuitPython](https://learn.adafruit.com/adafruit-magtag/circuitpython)
* [Install CircuitPython libraries](https://learn.adafruit.com/adafruit-magtag/circuitpython-libraries-2)
  * Copy required moduels and directories into device
* Copy code into device USB device
* Setup config
  * TBD

## Tested versions

* TinyUF2 Bootloader 0.18.1 (Nov 14 2023)
* Adafruit CircuitPython 8.2.9 on 2023-12-06
* CircuitPython libraries version: adafruit-circuitpython-bundle-8.x-mpy-20240130
  * Required modules
    * adafruit_datetime.mpy
    * Note: Modules listed in Adafruit documentation are not needed
      * Some are frozen into firmware since 7.2.0
      * This code does not use Magtag library
