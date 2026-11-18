
import math
import re
from collections import Counter

from chatbot.knowledge_base import KNOWLEDGE_BASE


STOP_WORDS = {
    "the", "is", "are", "am", "was", "were", "what",
    "which", "who", "whom", "when", "where", "why",
    "how", "can", "could", "would", "should", "do",
    "does", "did", "have", "has", "had", "will",
    "shall", "may", "might", "must", "a", "an", "and",
    "or", "but", "if", "then", "than", "to", "of",
    "in", "on", "at", "for", "from", "with", "by",
    "about", "as", "it", "its", "this", "that", "these",
    "those", "i", "me", "my", "we", "our", "you",
    "your", "he", "she", "they", "them", "their",
    "please", "tell", "explain", "give", "show"
}


NORMALIZATION_MAP = {
    "hidden": "hide",
    "hides": "hide",
    "hiding": "hide",
    "profiles": "profile",
    "photos": "photo",
    "messages": "message",
    "requests": "request",
    "matches": "match",
    "matched": "match",
    "matching": "match",
    "blocked": "block",
    "blocking": "block",
    "removed": "remove",
    "removing": "remove",
    "connections": "connection",
    "preferences": "preference",
    "users": "user"
}


def tokenize(text):
    """
    Convert text into normalized searchable words.
    """

    words = re.findall(r"[a-zA-Z0-9]+", str(text).lower())

    tokens = []

    for word in words:
        word = NORMALIZATION_MAP.get(word, word)

        if len(word) > 1 and word not in STOP_WORDS:
            tokens.append(word)

    return tokens


def calculate_idf(documents):
    """
    Calculate Inverse Document Frequency for all terms.
    """

    document_frequency = Counter()

    for document in documents:
        document_frequency.update(set(document))

    total_documents = len(documents)

    idf_scores = {}

    for word, frequency in document_frequency.items():
        idf_scores[word] = (
            math.log((total_documents + 1) / (frequency + 1)) + 1
        )

    return idf_scores


def calculate_cosine_similarity(query_vector, document_vector):
    """
    Calculate cosine similarity between two vectors.
    """

    common_words = set(query_vector) & set(document_vector)

    dot_product = sum(
        query_vector[word] * document_vector[word]
        for word in common_words
    )

    query_magnitude = math.sqrt(
        sum(value ** 2 for value in query_vector.values())
    )

    document_magnitude = math.sqrt(
        sum(value ** 2 for value in document_vector.values())
    )

    if query_magnitude == 0 or document_magnitude == 0:
        return 0.0

    return dot_product / (
        query_magnitude * document_magnitude
    )


def retrieve_knowledge(query, top_k=3, min_score=0.06):
    """
    Retrieve the most relevant knowledge chunks for a query.
    """

    if not query or not str(query).strip():
        return []

    # Prepare knowledge documents
    knowledge_documents = []
    valid_chunks = []

    for chunk in KNOWLEDGE_BASE:
        text = (
            chunk.get("title", "")
            + " "
            + chunk.get("content", "")
        )

        tokens = tokenize(text)

        if tokens:
            knowledge_documents.append(tokens)
            valid_chunks.append(chunk)

    if not knowledge_documents:
        return []

    # Calculate IDF
    idf_scores = calculate_idf(knowledge_documents)

    # Prepare query vector
    query_tokens = tokenize(query)
    query_counts = Counter(query_tokens)

    query_vector = {
        word: (1 + math.log(count)) * idf_scores[word]
        for word, count in query_counts.items()
        if word in idf_scores
    }

    if not query_vector:
        return []

    # Calculate document scores
    results = []

    for chunk, document_tokens in zip(
        valid_chunks,
        knowledge_documents
    ):
        document_counts = Counter(document_tokens)

        document_vector = {
            word: (1 + math.log(count)) * idf_scores[word]
            for word, count in document_counts.items()
        }

        score = calculate_cosine_similarity(
            query_vector,
            document_vector
        )

        if score >= min_score:
            results.append({
                "id": chunk["id"],
                "title": chunk["title"],
                "content": chunk["content"].strip(),
                "score": round(score, 4)
            })

    # Highest similarity first
    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:top_k]
