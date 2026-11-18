
import logging

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from chatbot.retriever import retrieve_knowledge
from chatbot.gemini_service import (
    generate_gemini_response,
    GeminiAPIError,
)


logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def ask_chatbot(request):
    """
    Authenticated API endpoint for the Smart Matrimonial
    Platform RAG-based Gemini chatbot.
    """

    question = request.data.get("question")

    # Validate question
    if not isinstance(question, str) or not question.strip():
        return Response(
            {
                "error": "Please provide a valid question."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    question = question.strip()

    # Limit question length
    if len(question) > 1000:
        return Response(
            {
                "error": "Question cannot exceed 1000 characters."
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        # Retrieve relevant platform knowledge
        retrieved_chunks = retrieve_knowledge(
            question,
            top_k=3
        )

        # Generate answer using Gemini and RAG context
        answer = generate_gemini_response(
            question,
            retrieved_chunks
        )

        return Response(
            {
                "success": True,
                "question": question,
                "answer": answer,
                "sources": [
                    {
                        "id": chunk["id"],
                        "title": chunk["title"]
                    }
                    for chunk in retrieved_chunks
                ]
            },
            status=status.HTTP_200_OK
        )

    except GeminiAPIError:
        logger.exception("Gemini API request failed.")

        return Response(
            {
                "success": False,
                "error": (
                    "AI service is temporarily unavailable. "
                    "Please try again later."
                )
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    except Exception:
        logger.exception("Unexpected chatbot error.")

        return Response(
            {
                "success": False,
                "error": "Something went wrong. Please try again."
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
