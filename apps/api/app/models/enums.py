"""Domain enumerations.

Stored as native PostgreSQL enums so invalid values are rejected by the database,
not merely by application code.
"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    WARDEN = "WARDEN"
    STAFF = "STAFF"
    STUDENT = "STUDENT"


class StudentStatus(str, enum.Enum):
    PROSPECTIVE = "PROSPECTIVE"
    ACTIVE = "ACTIVE"
    ON_LEAVE = "ON_LEAVE"
    ALUMNI = "ALUMNI"
    SUSPENDED = "SUSPENDED"


class RoomStatus(str, enum.Enum):
    AVAILABLE = "AVAILABLE"
    FULL = "FULL"
    MAINTENANCE = "MAINTENANCE"
    CLOSED = "CLOSED"


class RoomType(str, enum.Enum):
    SINGLE = "SINGLE"
    DOUBLE = "DOUBLE"
    TRIPLE = "TRIPLE"
    DORMITORY = "DORMITORY"


class BedStatus(str, enum.Enum):
    VACANT = "VACANT"
    OCCUPIED = "OCCUPIED"
    RESERVED = "RESERVED"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"


class AssignmentStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    ENDED = "ENDED"
    CANCELLED = "CANCELLED"


class InvoiceStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    ISSUED = "ISSUED"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"


class PaymentMethod(str, enum.Enum):
    CASH = "CASH"
    BANK_TRANSFER = "BANK_TRANSFER"
    ESEWA = "ESEWA"
    KHALTI = "KHALTI"
    CHEQUE = "CHEQUE"


class PaymentStatus(str, enum.Enum):
    RECORDED = "RECORDED"
    REVERSED = "REVERSED"


class LedgerEntryType(str, enum.Enum):
    DEBIT = "DEBIT"  # student owes (invoice issued)
    CREDIT = "CREDIT"  # student paid / adjustment in their favour


class ComplaintCategory(str, enum.Enum):
    WATER = "WATER"
    ELECTRICITY = "ELECTRICITY"
    INTERNET = "INTERNET"
    CLEANLINESS = "CLEANLINESS"
    FOOD = "FOOD"
    MAINTENANCE = "MAINTENANCE"
    SECURITY = "SECURITY"
    NOISE = "NOISE"
    HARASSMENT = "HARASSMENT"
    STAFF_BEHAVIOUR = "STAFF_BEHAVIOUR"
    OTHER = "OTHER"


class ComplaintPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    TRIAGED = "TRIAGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REJECTED = "REJECTED"


class Department(str, enum.Enum):
    MAINTENANCE = "MAINTENANCE"
    HOUSEKEEPING = "HOUSEKEEPING"
    MESS = "MESS"
    SECURITY = "SECURITY"
    IT = "IT"
    ADMINISTRATION = "ADMINISTRATION"
    WARDEN_OFFICE = "WARDEN_OFFICE"


class Sentiment(str, enum.Enum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"


class LeaveType(str, enum.Enum):
    HOME_VISIT = "HOME_VISIT"
    MEDICAL = "MEDICAL"
    ACADEMIC = "ACADEMIC"
    EMERGENCY = "EMERGENCY"
    OTHER = "OTHER"


class LeaveStatus(str, enum.Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class MealType(str, enum.Enum):
    BREAKFAST = "BREAKFAST"
    LUNCH = "LUNCH"
    SNACKS = "SNACKS"
    DINNER = "DINNER"


class DocumentType(str, enum.Enum):
    HOSTEL_RULES = "HOSTEL_RULES"
    FEE_POLICY = "FEE_POLICY"
    LEAVE_POLICY = "LEAVE_POLICY"
    MESS_POLICY = "MESS_POLICY"
    NOTICE = "NOTICE"
    FAQ = "FAQ"
    OTHER = "OTHER"


class DocumentStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PROCESSING = "PROCESSING"
    INDEXED = "INDEXED"
    FAILED = "FAILED"
    ARCHIVED = "ARCHIVED"


class AIOperationStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class AIErrorCategory(str, enum.Enum):
    TIMEOUT = "TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    SCHEMA_INVALID = "SCHEMA_INVALID"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    AUTH = "AUTH"
    BAD_REQUEST = "BAD_REQUEST"
    UNKNOWN = "UNKNOWN"


class MessageRole(str, enum.Enum):
    USER = "USER"
    ASSISTANT = "ASSISTANT"
    TOOL = "TOOL"
    SYSTEM = "SYSTEM"


class NotificationCategory(str, enum.Enum):
    ANNOUNCEMENT = "ANNOUNCEMENT"
    LEAVE_REQUESTED = "LEAVE_REQUESTED"
    LEAVE_DECIDED = "LEAVE_DECIDED"
    COMPLAINT_UPDATED = "COMPLAINT_UPDATED"
    INVOICE_ISSUED = "INVOICE_ISSUED"
    FEE_REMINDER = "FEE_REMINDER"
    FEE_OVERDUE = "FEE_OVERDUE"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    ROOM_ALLOCATED = "ROOM_ALLOCATED"
    ACCOUNT_SECURITY = "ACCOUNT_SECURITY"


class NotificationChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"


class DeliveryStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
