# SPDX-FileCopyrightText: 2018 Tony DiCola for Adafruit Industries
# SPDX-FileCopyrightText: 2018 ladyada for Adafruit Industries
# SPDX-FileCopyrightText: 2021 Mark Olsson <mark@markolsson.se>
#
# SPDX-License-Identifier: MIT

"""
`adafruit_st7565`
====================================================

A display control library for ST7565 graphic displays

* Author(s): ladyada, Mark Olsson

Implementation Notes
--------------------

**Hardware:**

* `ST7565 graphic display <https://www.adafruit.com/product/250>`_

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

* Adafruit's Bus Device library: https://github.com/adafruit/Adafruit_CircuitPython_BusDevice

"""

import time
from micropython import const
from adafruit_bus_device import spi_device

try:
    import framebuf
except ImportError:
    import adafruit_framebuf as framebuf

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_ST7565.git"


class ST7565(framebuf.FrameBuffer):
    """ST7565-based LCD display."""

    # pylint: disable=too-many-instance-attributes

    LCDWIDTH = const(128)
    LCDHEIGHT = const(64)

    # LCD Page Order
    pagemap = (0, 1, 2, 3, 4, 5, 6, 7)

    CMD_DISPLAY_OFF = const(0xAE)
    CMD_DISPLAY_ON = const(0xAF)
    CMD_SET_DISP_START_LINE = const(0x40)
    CMD_SET_PAGE = const(0xB0)
    CMD_SET_COLUMN_UPPER = const(0x10)
    CMD_SET_COLUMN_LOWER = const(0x00)
    CMD_SET_ADC_NORMAL = const(0xA0)
    CMD_SET_ADC_REVERSE = const(0xA1)
    CMD_SET_DISP_NORMAL = const(0xA6)
    CMD_SET_DISP_REVERSE = const(0xA7)
    CMD_SET_ALLPTS_NORMAL = const(0xA4)
    CMD_SET_ALLPTS_ON = const(0xA5)
    CMD_SET_BIAS_9 = const(0xA2)
    CMD_SET_BIAS_7 = const(0xA3)
    CMD_INTERNAL_RESET = const(0xE2)
    CMD_SET_COM_NORMAL = const(0xC0)
    CMD_SET_COM_REVERSE = const(0xC8)
    CMD_SET_POWER_CONTROL = const(0x28)
    CMD_SET_RESISTOR_RATIO = const(0x20)
    CMD_SET_VOLUME_FIRST = const(0x81)
    CMD_SET_VOLUME_SECOND = const(0x00)
    CMD_SET_STATIC_OFF = const(0xAC)
    CMD_SET_STATIC_ON = const(0xAD)
    CMD_SET_STATIC_REG = const(0x00)

    def __init__(
        self, spi, dc_pin, cs_pin, reset_pin=None, *, contrast=0, baudrate=1000000
    ):
        self._dc_pin = dc_pin
        dc_pin.switch_to_output(value=False)

        self.spi_device = spi_device.SPIDevice(spi, cs_pin, baudrate=baudrate)

        self._reset_pin = reset_pin
        if reset_pin:
            reset_pin.switch_to_output(value=True)

        self.buffer = bytearray(self.LCDHEIGHT * self.LCDWIDTH)
        super().__init__(self.buffer, self.LCDWIDTH, self.LCDHEIGHT)

        self._contrast = None
        self._invert = False

        self.reset()

        # LCD bias select
        self.write_cmd(self.CMD_SET_BIAS_7)
        # ADC select
        self.write_cmd(self.CMD_SET_ADC_REVERSE)
        # SHL select
        self.write_cmd(self.CMD_SET_COM_NORMAL)
        # Initial display line
        self.write_cmd(self.CMD_SET_DISP_START_LINE)
        # Turn on voltage converter (VC=1, VR=0, VF=0)
        self.write_cmd(self.CMD_SET_POWER_CONTROL | 0x4)
        time.sleep(0.05)
        # Turn on voltage regulator (VC=1, VR=1, VF=0)
        self.write_cmd(self.CMD_SET_POWER_CONTROL | 0x6)
        time.sleep(0.05)
        # Turn on voltage follower (VC=1, VR=1, VF=1)
        self.write_cmd(self.CMD_SET_POWER_CONTROL | 0x7)
        time.sleep(0.01)
        # Set lcd operating voltage (regulator resistor, ref voltage resistor)
        self.write_cmd(self.CMD_SET_RESISTOR_RATIO | 0x7)
        # Turn on display
        self.write_cmd(self.CMD_DISPLAY_ON)
        # Display all points
        self.write_cmd(self.CMD_SET_ALLPTS_NORMAL)

        # Contrast
        self.contrast = contrast

    def reset(self):
        """Reset the display"""
        if self._reset_pin:
            # Toggle RST low to reset.
            self._reset_pin.value = False
            time.sleep(0.5)
            self._reset_pin.value = True
            time.sleep(0.5)

    def write_cmd(self, cmd):
        """Send a command to the SPI device"""
        self._dc_pin.value = False
        with self.spi_device as spi:
            spi.write(bytearray([cmd]))  # pylint: disable=no-member

    def show(self):
        """write out the frame buffer via SPI"""
        for page in self.pagemap:
            # Home cursor on the page
            # Set page
            self.write_cmd(self.CMD_SET_PAGE | self.pagemap[page])
            # Set lower bits of column
            self.write_cmd(self.CMD_SET_COLUMN_LOWER | (0 & 0xF))
            # Set upper bits of column
            self.write_cmd(self.CMD_SET_COLUMN_UPPER | ((0 >> 4) & 0xF))

            # Page start row
            row_start = page << 7
            # Page stop row
            row_stop = (page + 1) << 7
            # slice page from buffer and pack bits to bytes then send to display
            self._dc_pin.value = True
            with self.spi_device as spi:
                spi.write(self.buffer[row_start:row_stop])  # pylint: disable=no-member

    @property
    def invert(self):
        """Whether the display is inverted, cached value"""
        return self._invert

    @invert.setter
    def invert(self, val):
        """Set invert on or normal display on"""
        self._invert = val
        if val:
            self.write_cmd(self.CMD_SET_DISP_REVERSE)
        else:
            self.write_cmd(self.CMD_SET_DISP_NORMAL)

    @property
    def contrast(self):
        """The cached contrast value"""
        return self._contrast

    @contrast.setter
    def contrast(self, val):
        """Set contrast to specified value (should be 0-127)."""
        self._contrast = max(0, min(val, 0x7F))  # Clamp to values 0-0x7f
        self.write_cmd(self.CMD_SET_VOLUME_FIRST)
        self.write_cmd(self.CMD_SET_VOLUME_SECOND | (self._contrast & 0x3F))
