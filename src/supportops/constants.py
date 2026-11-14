from enum import Enum, IntEnum

class RoleEnum(str, Enum):
    USER = "user"
    AGENT = "agent"
    MANAGER = "manager"
    ADMIN = "admin"
class TicketStatusEnum(IntEnum):
    NEW = 1
    ASSIGNED = 2
    IN_PROGRESS = 3
    ON_HOLD = 4
    RESOLVED = 5
    CLOSED = 6
    REOPENED = 7
class TicketPriorityEnum(IntEnum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4