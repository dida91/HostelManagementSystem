"""Model registry. Importing this module registers every table on Base.metadata,
which is what Alembic autogenerate and the test harness rely on."""

from app.models.ai import (
    AIOperation,
    AssistantConversation,
    AssistantMessage,
    RagQuery,
)
from app.models.complaint import Complaint, ComplaintAIAnalysis, ComplaintEvent
from app.models.document import ChunkEmbedding, Document, DocumentChunk
from app.models.finance import (
    FeeInvoice,
    FeeStructure,
    InvoiceLineItem,
    Payment,
    StudentLedgerEntry,
)
from app.models.hostel import Bed, BedAssignment, Block, Room
from app.models.leave import LeaveDocument, LeaveRequest
from app.models.mess import Announcement, MessFeedback, MessFeedbackAI, MessMenu
from app.models.user import AuditLog, RefreshToken, Student, User

__all__ = [
    "AIOperation",
    "AssistantConversation",
    "AssistantMessage",
    "RagQuery",
    "Complaint",
    "ComplaintAIAnalysis",
    "ComplaintEvent",
    "ChunkEmbedding",
    "Document",
    "DocumentChunk",
    "FeeInvoice",
    "FeeStructure",
    "InvoiceLineItem",
    "Payment",
    "StudentLedgerEntry",
    "Bed",
    "BedAssignment",
    "Block",
    "Room",
    "LeaveDocument",
    "LeaveRequest",
    "Announcement",
    "MessFeedback",
    "MessFeedbackAI",
    "MessMenu",
    "AuditLog",
    "RefreshToken",
    "Student",
    "User",
]
