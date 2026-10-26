"""Strict symbols for the supported SSE/SZSE cash-equity daily adapters."""
import re


def symbols(instrument):
    if not re.fullmatch(r'(SSE:6\d{5}|SZSE:[03]\d{5})', instrument):
        raise ValueError('OBSERVATION_SOURCE_SCOPE_UNSUPPORTED')
    exchange, code = instrument.split(':')
    suffix = 'SH' if exchange == 'SSE' else 'SZ'
    return code, suffix+code, code+'.'+suffix
