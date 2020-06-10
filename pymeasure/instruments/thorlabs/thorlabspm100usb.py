#
# This file is part of the PyMeasure package.
#
# Copyright (c) 2013-2020 PyMeasure Developers
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import time
import logging

from pymeasure.instruments import Instrument, RangeException

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class ThorlabsPM100USB(Instrument):
    """Represents Thorlabs PM100USB powermeter"""

    wavelength_min = Instrument.measurement(
        "SENS:CORR:WAV? MIN", "Get minimum wavelength, in nm")

    wavelength_max = Instrument.measurement(
        "SENS:CORR:WAV? MAX", "Get maximum wavelength, in nm")

    average = Instrument.control("SENS:AVERage?", "SENS:AVERage %d",
                                 "Averaging rate")

    def set_zero(self, timeout=60):
        """Perform zero adjustment"""
        self.write("SENS:CORR:COLLect:ZERO:INITiate")
        start = time.time()
        while self.values("SENS:CORR:COLLect:ZERO:STATe?")[0] is 1:
            if time.time() > start + timeout:
                self.write("SENS:CORR:COLLect:ZERO:ABORt")
                log.info(
                    "Aborted zero adjustment for %s due to timeout."
                    % self.sensor_name)
            else:
                time.sleep(0.1)

    zero_offset = Instrument.measurement(
        "SENS:CORR:COLLect:ZERO:MAGnitude?", "Zero adjustment value")

    beamdiameter = Instrument.control(
        "SENS:CORR:BEAMdiameter?", "SENS:CORR:BEAMdiameter %g",
        "Assumed beam diameter, in mm")
    beamdiameter_min = Instrument.measurement(
        "SENS:CORR:BEAMdiameter? MIN", "Minimum beam diameter, in mm")
    beamdiameter_max = Instrument.measurement(
        "SENS:CORR:BEAMdiameter? MAX", "Maximum beam diameter, in mm")

    def __init__(self, adapter, **kwargs):
        super(ThorlabsPM100USB, self).__init__(
            adapter, "ThorlabsPM100USB powermeter", write_termination='\n', read_termination='\n', **kwargs)
        self.timeout = 3000  # where is this used??
        self.sensor()

    def measure_power(self, wavelength):
        """Set wavelength in nm and get power in W
        If wavelength is out of range it will be set to range limit"""
        if wavelength < self.wavelength_min:
            raise RangeException(
                "Wavelength %.2f nm out of range: using minimum wavelength: %.2f nm"
                % (wavelength, self.wavelength_min))
            # explicitly setting wavelenghth, although it would be autoset
            wavelength = self.wavelength_min
        if wavelength > self.wavelength_max:
            raise RangeException(
                "Wavelength %.2f nm out of range: using maximum wavelength: %.2f nm"
                % (wavelength, self.wavelength_max))
            wavelength = self.wavelength_max
        self.wavelength = wavelength
        return self.power

    def sensor(self):
        "Get sensor info"
        response = self.ask("SYST:SENSOR:IDN?").split(',')
        self.sensor_name = response[0]
        self.sensor_sn = response[1]
        self.sensor_cal_msg = response[2]
        self.sensor_type = response[3]
        self.sensor_subtype = response[4]
        self._flags_str = response[-1]
        # interpretation of the flags
        # rough trick using bin repr, maybe something more elegant exixts
        # (bitshift, bitarray?)
        # force representation as 9bits, max. value is 371 (sum of all codes)
        self._flags = '{0:09b}'.format(int(self._flags_str))
        # convert to boolean
        self._flags = tuple(map(lambda x: x == '1', self._flags))
        self._flags = reversed(self._flags)  # account for bit order
        # setting the flags; _dn are empty
        self.is_power, self.is_energy, _d4, _d8, \
            self.resp_settable, self.wavelength_settable, \
            self.tau_settable, _d128, self.temperature_sens = self._flags

    @property
    def wavelength(self):
        self.values("SENSE:CORR:WAV?")

    @wavelength.setter
    def wavelength(self, val):
        """Wavelength in nm; not set outside of range"""
        if self.wavelength_settable:
            self.values("SENSE:CORR:WAV %g" % val)
        else:
            raise Exception(
                "Wavelength is not settable for %s" % self.sensor_name)

    @property
    def energy(self):
        if self.is_energy:
            return self.values("MEAS:ENER?")
        else:
            raise Exception("%s is not an energy sensor" % self.sensor_name)

    @property
    def power(self):
        """Power, in Watts"""
        if self.is_power:
            return self.values("MEAS:POW?")
        else:
            raise Exception("%s is not a power sensor" % self.sensor_name)

    @property
    def power_density(self):
        """Power Density, in Watt/cm2"""
        if self.is_power:
            return self.values("MEAS:PDENsity?")
        else:
            raise Exception("%s is not a power sensor" % self.sensor_name)

    @property
    def temperature(self):
        """Temperature, in °C"""
        if self.temperature_sens:
            return self.values("MEAS:TEMPerature?")
