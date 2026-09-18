from __future__ import annotations

from fastapi import APIRouter, Depends

from app.ai.providers.registry import ai_is_available, get_embedding_provider, get_llm_provider
from app.ai.services.chat import AssistantService
from app.ai.services.embeddings import EmbeddingService
from app.ai.services.rag import RagService
from app.ai.services.retrieval import RetrievalService
from app.api.deps import PrincipalDep, SessionDep, rate_limit
from app.core.errors import AIUnavailableError
from app.schemas.complaint import AssistantAsk, AssistantReply, RagAsk, RagReply

router = APIRouter(
    prefix="/assistant",
    tags=["assistant"],
    # AI calls cost money and quota; limit them far more tightly than reads.
    dependencies=[Depends(rate_limit("ai"))],
)


def _require_ai() -> None:
    if not ai_is_available():
        raise AIUnavailableError("The AI assistant is not available. Please try again later.")


@router.post("/ask", response_model=AssistantReply)
async def ask(
    payload: AssistantAsk, principal: PrincipalDep, session: SessionDep
) -> AssistantReply:
    """Authenticated assistant turn.

    Tools are selected from the caller's role before the model runs, and the
    model cannot reference any identity but the authenticated one.
    """
    _require_ai()
    service = AssistantService(provider=get_llm_provider())
    turn = await service.respond(session=session, principal=principal, message=payload.message)
    return AssistantReply(
        text=turn.text,
        tool_calls=turn.tool_calls,
        citations=turn.citations,
        iterations=turn.iterations,
        conversation_id=payload.conversation_id,
    )


@router.post("/documents/ask", response_model=RagReply)
async def ask_documents(payload: RagAsk, principal: PrincipalDep, session: SessionDep) -> RagReply:
    """RAG over hostel documents, with citations."""
    _require_ai()
    embeddings = EmbeddingService(get_embedding_provider())
    rag = RagService(
        provider=get_llm_provider(),
        embeddings=embeddings,
        retrieval=RetrievalService(embedding_model=embeddings.model_name),
    )
    result = await rag.answer(
        session=session,
        question=payload.question,
        user_id=principal.user_id,
        top_k=payload.top_k,
    )
    return RagReply(answer=result.answer, grounded=result.grounded, citations=result.citations)
