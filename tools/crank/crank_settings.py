"""Disabled opt-in template. SPDX-License-Identifier: MIT.

Copy only one validated configuration into CRANK_CONFIG to enable hardware.
Replace placeholders after checking the selected board and encoder/pot wiring.
"""
CRANK_CONFIG = {'enabled': False}

SEESAW_TEMPLATE = {
    'enabled': False,
    'kind': 'seesaw',
    'bus_factory': 'REPLACE_WITH_BOARD_BUS_FACTORY',
    'address': None,
    'encoder': 0,
    'counts_per_revolution': None,
    'direction': 1,
    'zero_degrees': 0,
}

ANALOG_TEMPLATE = {
    'enabled': False,
    'kind': 'analog',
    'pin': 'REPLACE_WITH_VERIFIED_ADC_PIN',
    'adc_min': None,
    'adc_max': None,
    'deadband': 128,
    'travel_degrees': None,
    'direction': 1,
    'zero_degrees': 0,
}
