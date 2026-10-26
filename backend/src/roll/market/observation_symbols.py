"""Strict symbols for the supported SSE/SZSE cash-equity daily adapters."""
import re


def symbols(instrument):
    if not re.fullmatch(r'(SSE:(60|68)\d{4}|SZSE:(00|30)\d{4})', instrument):
        raise ValueError('OBSERVATION_SOURCE_SCOPE_UNSUPPORTED')
    exchange, code = instrument.split(':')
    suffix = 'SH' if exchange == 'SSE' else 'SZ'
    return code, suffix+code, code+'.'+suffix
