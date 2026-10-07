"""Bounded decisive-fact command shared by actual producers and consumer."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field


class FactReference(BaseModel):
    model_config=ConfigDict(extra='forbid')
    snapshot_id:str
    fact_index:int=Field(ge=0)


class DecisiveFact(BaseModel):
    model_config=ConfigDict(extra='forbid')
    fact_id:str=Field(min_length=1,max_length=100)
    field:str=Field(min_length=1,max_length=80)
    references:list[FactReference]=Field(min_length=1,max_length=6)


class VerificationCommand(BaseModel):
    model_config=ConfigDict(extra='forbid')
    trigger:Literal['USER_SELECTED','MATERIAL_DOUBT','CRITICAL_CONFLICT']
    reason:str=Field(min_length=1,max_length=2000)
    facts:list[DecisiveFact]=Field(min_length=1,max_length=10)
    knowledge_cutoff:datetime|None=None
