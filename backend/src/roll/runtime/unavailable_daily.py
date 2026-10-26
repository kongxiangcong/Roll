"""Explicit fail-closed boundary for a module absent from the published source tree.

This does not implement, qualify, or reconstruct the historical SSE daily adapter.
"""
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict


class DailyPacketCommand(BaseModel):
    model_config = ConfigDict(extra='allow')


class DatedDaily:
    def __init__(self, prospective):
        pass

    def receipts(self, plan_id):
        return []

    def saved_packet(self, packet_id):
        return False

    def unavailable(self, *args, **kwargs):
        raise HTTPException(503, {'code': 'SSE_DAILY_MODULE_NOT_SHIPPED',
                                 'reason': 'Published source tree does not contain roll.market.sse_daily; no result generated.'})

    capture_once = build = packet = replay = unavailable
