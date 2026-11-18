
import { useState } from "react";
import api from "./api";
import "./AIChatbot.css";

function AIChatbot() {
  const [isOpen, setIsOpen] = useState(false);
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);

  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hello! 👋 Welcome to Smart Matrimonial AI Assistant. You can ask me questions about our platform's features, profiles, matches, compatibility scores, photos, and chat.",
      sources: [],
    },
  ]);

  const handleSubmit = async (event) => {
    event.preventDefault();

    const trimmedQuestion = question.trim();

    if (!trimmedQuestion || loading) {
      return;
    }

    if (trimmedQuestion.length > 1000) {
      return;
    }

    const userMessage = {
      id: `${Date.now()}-user`,
      role: "user",
      content: trimmedQuestion,
      sources: [],
    };

    setMessages((previous) => [...previous, userMessage]);
    setQuestion("");
    setLoading(true);

    try {
      const response = await api.post("/api/chatbot/ask/", {
        question: trimmedQuestion,
      });

      const assistantMessage = {
        id: `${Date.now()}-assistant`,
        role: "assistant",
        content:
          response.data?.answer ||
          "Sorry, I could not generate a response.",
        sources: Array.isArray(response.data?.sources)
          ? response.data.sources
          : [],
      };

      setMessages((previous) => [
        ...previous,
        assistantMessage,
      ]);
    } catch (error) {
      const errorMessage =
        error.response?.data?.error ||
        "Unable to connect to the AI assistant. Please try again.";

      setMessages((previous) => [
        ...previous,
        {
          id: `${Date.now()}-error`,
          role: "assistant",
          content: errorMessage,
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ai-chatbot-container">
      {/* Floating chatbot button */}
      {!isOpen && (
        <button
          type="button"
          className="ai-chatbot-launcher"
          onClick={() => setIsOpen(true)}
          aria-label="Open AI Assistant"
          aria-expanded={false}
        >
          <span className="ai-launcher-icon">✦</span>
          <span>AI Assistant</span>
        </button>
      )}

      {/* Chatbot window */}
      {isOpen && (
        <section
          className="ai-chatbot-window"
          role="dialog"
          aria-label="Smart Matrimonial AI Assistant"
        >
          <header className="ai-chatbot-header">
            <div className="ai-chatbot-heading">
              <div className="ai-chatbot-avatar">✦</div>

              <div>
                <h3>Smart Matrimonial AI</h3>
                <p>
                  <span className="ai-status-dot"></span>
                  Platform Assistant
                </p>
              </div>
            </div>

            <button
              type="button"
              className="ai-chatbot-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close chatbot"
            >
              ×
            </button>
          </header>

          <div
            className="ai-chatbot-messages"
            role="log"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.map((message) => (
              <div
                key={message.id}
                className={`ai-message-row ${
                  message.role === "user"
                    ? "ai-user-row"
                    : "ai-assistant-row"
                }`}
              >
                <div
                  className={`ai-message-bubble ${
                    message.role === "user"
                      ? "ai-user-message"
                      : "ai-assistant-message"
                  }`}
                >
                  <p>{message.content}</p>

                  {message.sources?.length > 0 && (
                    <div className="ai-message-sources">
                      <span>Sources:</span>

                      {message.sources.map((source) => (
                        <span
                          className="ai-source-tag"
                          key={source.id}
                        >
                          {source.title}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {loading && (
              <div className="ai-message-row ai-assistant-row">
                <div className="ai-message-bubble ai-assistant-message ai-typing">
                  <span></span>
                  <span></span>
                  <span></span>
                  <small>AI is thinking...</small>
                </div>
              </div>
            )}
          </div>

          <form
            className="ai-chatbot-input-area"
            onSubmit={handleSubmit}
          >
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about Smart Matrimonial..."
              rows={2}
              maxLength={1000}
              disabled={loading}
              aria-label="Type your question"
            />

            <div className="ai-chatbot-input-footer">
              <span>{question.length}/1000</span>

              <button
                type="submit"
                disabled={!question.trim() || loading}
                aria-label="Send message"
              >
                {loading ? "..." : "➤"}
              </button>
            </div>
          </form>

          <footer className="ai-chatbot-footer">
            AI answers are based on available platform information.
          </footer>
        </section>
      )}
    </div>
  );
}

export default AIChatbot;
