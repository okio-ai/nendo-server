# -*- encoding: utf-8 -*-
"""Action Data Transfer Objects."""
from __future__ import annotations

from enum import Enum
from typing import Dict, Optional

from pydantic import BaseModel

# if TYPE_CHECKING:
#     import datetime

"""
Trigger Action Models
"""

# class ActionMethodParam(BaseModel):
#     key: str
#     value: str
#     param_type: str = "str"


# class ActionMethod(BaseModel):
#     name: str
#     params: List[ActionMethodParam]


# class TriggerActionMethod(BaseModel):
#     module_name: str
#     method_name: ActionMethod


"""
Actions Queued Models
"""


# class ActionTriggerResponse(BaseModel):
#     run_id: str
#     module_name: str
#     method_name: str


class ActionState(Enum):
    """Action status types."""

    queued = "queued"
    started = "started"
    finished = "finished"
    failed = "failed"
    deferred = "deferred"
    scheduled = "scheduled"
    canceled = "canceled"
    stopped = "stopped"


class ActionStatus(BaseModel):
    """Action status class."""

    id: str
    enqueued_at: Optional[str]
    started_at: Optional[str]
    ended_at: Optional[str]
    status: ActionState
    meta: Optional[Dict]
    result: Optional[str]
    exc_info: Optional[str]
