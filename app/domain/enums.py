""" Domain enumerations for the application """
from enum import Enum


class TicketStatus(str, Enum):
    OPEN = "open"
    QUARANTINED = "quarantined"
    DISCARDED = "discarded"

