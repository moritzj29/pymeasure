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
from pymeasure.instruments.validators import (strict_discrete_set,
                                              strict_range)

log = logging.getLogger(__name__)
log.addHandler(logging.NullHandler())


class ThorlabsPM100USB(Instrument):
    """Represents Thorlabs PM100USB powermeter"""

    def __init__(self, adapter, **kwargs):
        super(ThorlabsPM100USB, self).__init__(
            adapter, "ThorlabsPM100USB powermeter", write_termination='\n',
            read_termination='\n', **kwargs)
        self.check_errors()
        self.sensor()

    # -------------------------------
    # SYSTem subsystem commands
    # -------------------------------

    def check_errors(self):
        """Check if any Errors occured
        """
        (code, message) = self.ask("SYSTem:ERRor?").split(',')
        if code != 0:
            log.warning(
                "{}: {} (Error Code: {})".format(self.name, message, code)
                )

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

    # -------------------------------
    # SENSe subsystem commands
    # -------------------------------

    # AVERage

    average = Instrument.control("SENS:AVERage?", "SENS:AVERage %d",
                                 "Averaging rate")

    # CORRection

    def set_zero(self, timeout=60):
        """Perform zero adjustment.

        :param timeout: abort after timeout (in s), defaults to 60
        :type timeout: int, optional
        """
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

    wavelength_min = Instrument.measurement(
        "SENS:CORR:WAV? MIN", "Get minimum wavelength, in nm")

    wavelength_max = Instrument.measurement(
        "SENS:CORR:WAV? MAX", "Get maximum wavelength, in nm")

    @property
    def wavelength(self):
        """Wavelength, in nm"""
        self.values("SENSE:CORR:WAV?")[0]

    @wavelength.setter
    def wavelength(self, val):
        wavelength = strict_range(
            wavelength, (self.wavelength_min, self.wavelength_max))
        if self.wavelength_settable:
            self.write("SENSE:CORR:WAV %g" % val)
        else:
            raise Exception(
                "Wavelength is not settable for %s" % self.sensor_name)

    # -------------------------------
    # INPut subsystem commands
    # -------------------------------

    # -------------------------------
    # Measurement commands
    # -------------------------------

    @property
    def power(self):
        """Power, in Watts"""
        if self.is_power:
            return self.values("MEAS:POWer?")[0]
        else:
            raise Exception("%s is not a power sensor" % self.sensor_name)

    @property
    def current(self):
        """DC Current, in A"""
        if self.is_power:
            return self.values("MEAS:CURRent?")[0]
        else:
            raise Exception("%s is not a power sensor" % self.sensor_name)

    @property
    def voltage(self):
        """DC Voltage, in V"""
        if self.is_power:
            return self.values("MEAS:VOLTage?")[0]
        else:
            raise Exception("%s is not a power sensor" % self.sensor_name)

    @property
    def energy(self):
        """Energy, in J"""
        if self.is_energy:
            return self.values("MEAS:ENERgy?")[0]
        else:
            raise Exception("%s is not an energy sensor" % self.sensor_name)

    @property
    def frequency(self):
        """Frequency, in Hz"""
        if self.is_energy:
            return self.values("MEAS:FREQuency?")[0]
        else:
            raise Exception("%s is not an energy sensor" % self.sensor_name)

    @property
    def power_density(self):
        """Power Density, in Watt/cm2"""
        if self.is_power:
            return self.values("MEAS:PDENsity?")[0]
        else:
            raise Exception("%s is not a power sensor" % self.sensor_name)

    @property
    def energy_density(self):
        """Energy Density, in J/cm2"""
        if self.is_energy:
            return self.values("MEAS:EDENsity?")[0]
        else:
            raise Exception("%s is not a energy sensor" % self.sensor_name)

    @property
    def resistance(self):
        """Resistance, in Ohm"""
        if self.temperature_sens:
            return self.values("MEAS:RESistance?")[0]

    @property
    def temperature(self):
        """Temperature, in °C"""
        if self.temperature_sens:
            return self.values("MEAS:TEMPerature?")[0]

    def measure_power(self, wavelength):
        """Set wavelength in nm and get power in W"""
        self.wavelength = wavelength
        return self.power
