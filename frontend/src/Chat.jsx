import { useCallback, useEffect, useRef, useState } from "react";
import api from "./api";
import "./Chat.css";

function getMessages(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.messages)) return data.messages;
  return [];
}

function formatMessageTime(value) {
  if (!value) return "";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";

  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

// Format last seen date and time
function formatLastSeen(value) {
  if (!value) return "Last seen unavailable";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Last seen unavailable";
  }

  const now = new Date();

  const time = date.toLocaleTimeString("en-IN", {
    hour: "2-digit",
    minute: "2-digit",
  });

  if (date.toDateString() === now.toDateString()) {
    return `Last seen today at ${time}`;
  }

  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);

  if (date.toDateString() === yesterday.toDateString()) {
    return `Last seen yesterday at ${time}`;
  }

  const dateLabel = date.toLocaleDateString("en-IN", {
    day: "numeric",
    month: "short",
    ...(date.getFullYear() !== now.getFullYear()
      ? { year: "numeric" }
      : {}),
  });

  return `Last seen ${dateLabel} at ${time}`;
}

function Chat({
  profileId,
  profileName,
  currentProfileId,
  presenceStatus = null,
  onClose,
}) {
  const [messages, setMessages] = useState([]);
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [isOtherTyping, setIsOtherTyping] = useState(false);

  const [wsReady, setWsReady] = useState(false);
  const [callStatus, setCallStatus] = useState("idle");
  const [activeCallType, setActiveCallType] = useState(null);
  const [incomingCall, setIncomingCall] = useState(null);
  const [localStream, setLocalStream] = useState(null);
  const [remoteStream, setRemoteStream] = useState(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isCameraOff, setIsCameraOff] = useState(false);
  const [callError, setCallError] = useState("");

  const isFetchingRef = useRef(false);
  const wsRef = useRef(null);
  const chatWsRef = useRef(null);
  const typingTimeoutRef = useRef(null);
  const incomingTypingTimeoutRef = useRef(null);

  const pcRef = useRef(null);
  const localStreamRef = useRef(null);
  const incomingOfferRef = useRef(null);
  const pendingCandidatesRef = useRef([]);
  const callStatusRef = useRef("idle");

  const localVideoRef = useRef(null);
  const remoteVideoRef = useRef(null);
  const remoteAudioRef = useRef(null);

  const changeCallStatus = useCallback((status) => {
    callStatusRef.current = status;
    setCallStatus(status);
  }, []);

  const sendSignal = useCallback((type, data = {}) => {
    const socket = wsRef.current;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      setCallError("Calling server is not connected.");
      return false;
    }

    socket.send(JSON.stringify({ type, data }));
    return true;
  }, []);

  const cleanupCall = useCallback(({ notify = false } = {}) => {
    if (notify) {
      sendSignal("call_end", {});
    }

    if (pcRef.current) {
      pcRef.current.onicecandidate = null;
      pcRef.current.ontrack = null;
      pcRef.current.onconnectionstatechange = null;
      pcRef.current.close();
      pcRef.current = null;
    }

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        track.stop();
      });
      localStreamRef.current = null;
    }

    setLocalStream(null);
    setRemoteStream(null);
    setIncomingCall(null);
    setActiveCallType(null);
    setIsMuted(false);
    setIsCameraOff(false);

    incomingOfferRef.current = null;
    pendingCandidatesRef.current = [];

    changeCallStatus("idle");
  }, [sendSignal, changeCallStatus]);

  const flushPendingCandidates = useCallback(async (peerConnection) => {
    const candidates = [...pendingCandidatesRef.current];
    pendingCandidatesRef.current = [];

    for (const candidate of candidates) {
      try {
        await peerConnection.addIceCandidate(
          new RTCIceCandidate(candidate)
        );
      } catch (err) {
        console.error("ICE candidate error:", err);
      }
    }
  }, []);

  const createPeerConnection = useCallback((stream) => {
    const peerConnection = new RTCPeerConnection({
      iceServers: [
        {
          urls: "stun:stun.l.google.com:19302",
        },
      ],
    });

    stream.getTracks().forEach((track) => {
      peerConnection.addTrack(track, stream);
    });

    peerConnection.onicecandidate = (event) => {
      if (event.candidate) {
        sendSignal("ice_candidate", {
          candidate: event.candidate.toJSON(),
        });
      }
    };

    peerConnection.ontrack = (event) => {
      if (event.streams?.[0]) {
        setRemoteStream(event.streams[0]);
      }
    };

    peerConnection.onconnectionstatechange = () => {
      if (peerConnection.connectionState === "connected") {
        changeCallStatus("connected");
        setCallError("");
      }

      if (peerConnection.connectionState === "failed") {
        setCallError(
          "Connection failed. A TURN server may be required."
        );
      }

      if (peerConnection.connectionState === "disconnected") {
        setCallError("Call connection interrupted.");
      }
    };

    pcRef.current = peerConnection;
    return peerConnection;
  }, [sendSignal, changeCallStatus]);

  // WebSocket connection for audio/video calling
  useEffect(() => {
    if (!profileId) return;

    const token = localStorage.getItem("access_token");

    if (!token) {
      setCallError("Please log in again to use calling.");
      return;
    }

    const baseURL = api.defaults.baseURL
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:")
      .replace(/\/$/, "");

    const socketURL =
      `${baseURL}/ws/call/${encodeURIComponent(profileId)}/` +
      `?token=${encodeURIComponent(token)}`;

    const socket = new WebSocket(socketURL);
    wsRef.current = socket;

    socket.onopen = () => {
      setWsReady(true);
      setCallError("");
    };

    socket.onmessage = async (event) => {
      let message;

      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }

      const data = message.data || {};

      try {
        switch (message.type) {
          case "call_offer": {
            if (callStatusRef.current !== "idle") {
              sendSignal("call_reject", {});
              return;
            }

            incomingOfferRef.current = data.sdp;

            setIncomingCall({
              fromName: message.from_name || "Member",
              fromProfileId: message.from_profile_id,
              callType: data.call_type,
            });

            setActiveCallType(data.call_type);
            changeCallStatus("incoming");
            setCallError("");
            break;
          }

          case "call_answer": {
            const peerConnection = pcRef.current;
            if (!peerConnection || !data.sdp) return;

            await peerConnection.setRemoteDescription(
              new RTCSessionDescription({
                type: "answer",
                sdp: data.sdp,
              })
            );

            await flushPendingCandidates(peerConnection);
            break;
          }

          case "ice_candidate": {
            if (!data.candidate) return;

            const peerConnection = pcRef.current;

            if (peerConnection?.remoteDescription) {
              await peerConnection.addIceCandidate(
                new RTCIceCandidate(data.candidate)
              );
            } else {
              pendingCandidatesRef.current.push(data.candidate);
            }
            break;
          }

          case "call_reject":
            cleanupCall();
            setCallError("The other user declined the call.");
            break;

          case "call_end":
            cleanupCall();
            setCallError("The other user ended the call.");
            break;

          case "error":
            setCallError(message.message || "Calling error occurred.");
            break;

          default:
            break;
        }
      } catch (err) {
        console.error("Calling signal error:", err);
        setCallError("Unable to process the call signal.");
      }
    };

    // socket.onerror = () => {
    //   setCallError("Unable to connect to calling server.");
    // };

    socket.onclose = (event) => {
      setWsReady(false);

      if (callStatusRef.current !== "idle") {
        cleanupCall();
        setCallError(`Call connection closed (${event.code}).`);
      }
    };

    return () => {
      socket.onopen = null;
      socket.onmessage = null;
      socket.onerror = null;
      socket.onclose = null;

      cleanupCall();

      if (wsRef.current === socket) {
        wsRef.current = null;
      }

      socket.close();
      setWsReady(false);
    };
  }, [
    profileId,
    changeCallStatus,
    cleanupCall,
    flushPendingCandidates,
    sendSignal,
  ]);

  // Separate WebSocket connection for chat typing indicator
  useEffect(() => {
    if (!profileId) return;

    const token = localStorage.getItem("access_token");

    if (!token) return;

    const baseURL = api.defaults.baseURL
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:")
      .replace(/\/$/, "");

    const socketURL =
      `${baseURL}/ws/chat/${encodeURIComponent(profileId)}/` +
      `?token=${encodeURIComponent(token)}`;

    const socket = new WebSocket(socketURL);

    chatWsRef.current = socket;

    socket.onmessage = (event) => {
      let message;

      try {
        message = JSON.parse(event.data);
      } catch {
        return;
      }

      if (message.type === "typing") {
        setIsOtherTyping(true);

        clearTimeout(incomingTypingTimeoutRef.current);

        incomingTypingTimeoutRef.current = setTimeout(() => {
          setIsOtherTyping(false);
        }, 3000);
      }

      if (message.type === "stop_typing") {
        setIsOtherTyping(false);

        clearTimeout(incomingTypingTimeoutRef.current);
      }

      if (message.type === "chat_access_revoked") {
        setIsOtherTyping(false);
        setError(
          message.message || "Chat access is no longer available."
        );
      }
    };

    socket.onclose = () => {
      setIsOtherTyping(false);
    };

    return () => {
      socket.onmessage = null;
      socket.onclose = null;

      clearTimeout(typingTimeoutRef.current);
      clearTimeout(incomingTypingTimeoutRef.current);

      if (chatWsRef.current === socket) {
        chatWsRef.current = null;
      }

      socket.close();
      setIsOtherTyping(false);
    };
  }, [profileId]);

  // Attach streams to media elements
  useEffect(() => {
    if (localVideoRef.current) {
      localVideoRef.current.srcObject = localStream || null;
    }

    if (remoteVideoRef.current) {
      remoteVideoRef.current.srcObject = remoteStream || null;
    }

    if (remoteAudioRef.current) {
      remoteAudioRef.current.srcObject = remoteStream || null;
    }
  }, [localStream, remoteStream, activeCallType]);

  // Start audio/video call
  const startCall = async (type) => {
    if (!wsReady || callStatusRef.current !== "idle") {
      setCallError("Calling server is not ready.");
      return;
    }

    setCallError("");
    setActiveCallType(type);
    changeCallStatus("calling");

    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error("Camera/microphone requires HTTPS or localhost.");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: type === "video",
      });

      localStreamRef.current = stream;
      setLocalStream(stream);

      const peerConnection = createPeerConnection(stream);

      const offer = await peerConnection.createOffer();
      await peerConnection.setLocalDescription(offer);

      const sent = sendSignal("call_offer", {
        call_type: type,
        sdp: offer.sdp,
      });

      if (!sent) cleanupCall();
    } catch (err) {
      console.error("Start call error:", err);
      cleanupCall();

      setCallError(
        err.name === "NotAllowedError"
          ? "Microphone/camera permission denied."
          : err.message || "Unable to start call."
      );
    }
  };

  // Accept incoming call
  const acceptCall = async () => {
    const offerSDP = incomingOfferRef.current;
    const type = activeCallType;

    if (!offerSDP || !type) {
      setCallError("Incoming call information is missing.");
      return;
    }

    changeCallStatus("connecting");
    setCallError("");

    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: true,
        video: type === "video",
      });

      localStreamRef.current = stream;
      setLocalStream(stream);

      const peerConnection = createPeerConnection(stream);

      await peerConnection.setRemoteDescription(
        new RTCSessionDescription({
          type: "offer",
          sdp: offerSDP,
        })
      );

      await flushPendingCandidates(peerConnection);

      const answer = await peerConnection.createAnswer();
      await peerConnection.setLocalDescription(answer);

      sendSignal("call_answer", {
        sdp: answer.sdp,
      });
    } catch (err) {
      console.error("Accept call error:", err);
      cleanupCall();
      sendSignal("call_reject", {});

      setCallError(
        err.name === "NotAllowedError"
          ? "Microphone/camera permission denied."
          : err.message || "Unable to accept call."
      );
    }
  };

  const rejectCall = () => {
    sendSignal("call_reject", {});
    cleanupCall();
  };

  const endCall = () => {
    cleanupCall({ notify: true });
  };

  const toggleMute = () => {
    const stream = localStreamRef.current;
    if (!stream) return;

    const nextMuted = !isMuted;

    stream.getAudioTracks().forEach((track) => {
      track.enabled = !nextMuted;
    });

    setIsMuted(nextMuted);
  };

  const toggleCamera = () => {
    const stream = localStreamRef.current;
    if (!stream) return;

    const nextCameraOff = !isCameraOff;

    stream.getVideoTracks().forEach((track) => {
      track.enabled = !nextCameraOff;
    });

    setIsCameraOff(nextCameraOff);
  };

  // Send typing events to the other user
  const handleTypingChange = (event) => {
    const value = event.target.value;

    setContent(value);

    const socket = chatWsRef.current;

    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return;
    }

    clearTimeout(typingTimeoutRef.current);

    if (!value.trim()) {
      socket.send(JSON.stringify({
        type: "stop_typing",
      }));
      return;
    }

    socket.send(JSON.stringify({
      type: "typing",
    }));

    typingTimeoutRef.current = setTimeout(() => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify({
          type: "stop_typing",
        }));
      }
    }, 1200);
  };

  // Load chat messages
  const loadMessages = useCallback(async ({ silent = false } = {}) => {
    if (!profileId || isFetchingRef.current) return;

    isFetchingRef.current = true;

    if (!silent) {
      setLoading(true);
      setError("");
    }

    try {
      const response = await api.get(
        `/api/profiles/chat/${profileId}/`
      );

      setMessages(getMessages(response.data));

      if (!silent) setError("");
    } catch (err) {
      if (!silent) {
        setError(
          err.response?.data?.error ||
          err.response?.data?.detail ||
          "Unable to load messages. Please try again."
        );
      }
    } finally {
      isFetchingRef.current = false;
      if (!silent) setLoading(false);
    }
  }, [profileId]);

  useEffect(() => {
    if (!profileId) return;

    loadMessages();

    const intervalId = setInterval(() => {
      loadMessages({ silent: true });
    }, 5000);

    return () => clearInterval(intervalId);
  }, [profileId, loadMessages]);

  // Send message
  const handleSendMessage = async (event) => {
    event.preventDefault();

    const messageText = content.trim();

    if (!messageText || sending || !profileId) return;

    setSending(true);
    setError("");
    setSuccess("");

    try {
      await api.post(
        `/api/profiles/chat/${profileId}/`,
        { content: messageText }
      );

      setContent("");

      // Stop typing indicator immediately after sending
      const typingSocket = chatWsRef.current;

      if (
        typingSocket &&
        typingSocket.readyState === WebSocket.OPEN
      ) {
        typingSocket.send(JSON.stringify({
          type: "stop_typing",
        }));
      }

      clearTimeout(typingTimeoutRef.current);

      setSuccess("Message sent.");
      await loadMessages();
    } catch (err) {
      setError(
        err.response?.data?.error ||
        err.response?.data?.detail ||
        "Unable to send message. Please try again."
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="chat-overlay">
      <section className="chat-container">

        {/* CHAT HEADER + ONLINE/OFFLINE STATUS */}
        <header className="chat-header">
          <div>
            <h2 className="chat-title">
              {profileName || "Member"}
            </h2>

            <span className="chat-subtitle">Chat</span>

            <div
              className="chat-presence-status"
              role="status"
              aria-live="polite"
              style={{
                display: "flex",
                alignItems: "center",
                gap: "7px",
                marginTop: "5px",
                fontSize: "12px",
                color: presenceStatus?.is_online
                  ? "#16803c"
                  : "#6b7280",
              }}
            >
              <span
                aria-hidden="true"
                style={{
                  width: "8px",
                  height: "8px",
                  borderRadius: "50%",
                  display: "inline-block",
                  flexShrink: 0,
                  backgroundColor: presenceStatus
                    ? presenceStatus.is_online
                      ? "#22c55e"
                      : "#9ca3af"
                    : "#f59e0b",
                }}
              />

              <span>
                {!presenceStatus
                  ? "Checking status..."
                  : presenceStatus.is_online
                    ? "Online"
                    : formatLastSeen(presenceStatus.last_seen)}
              </span>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="chat-close-button"
            aria-label="Close chat"
          >
            ×
          </button>
        </header>

        <div className="call-toolbar">
          {/* <button
            type="button"
            onClick={() => startCall("audio")}
            disabled={!wsReady || callStatus !== "idle"}
            className="call-button audio-call-button"
          >
            📞 Audio Call
          </button> */}

          {/* <button
            type="button"
            onClick={() => startCall("video")}
            disabled={!wsReady || callStatus !== "idle"}
            className="call-button video-call-button"
          >
            📹 Video Call
          </button> */}

          {/* <span className={`call-connection-status ${wsReady ? "connected" : ""}`}>
            {wsReady ? "Calling ready" : "Connecting..."}
          </span> */}
        </div>

        {incomingCall && callStatus === "incoming" && (
          <div className="incoming-call-panel">
            <h3>Incoming {incomingCall.callType} call</h3>
            <p>{incomingCall.fromName} is calling you.</p>

            <div className="call-actions">
              <button
                type="button"
                onClick={acceptCall}
                className="call-button accept-call-button"
              >
                Accept
              </button>

              <button
                type="button"
                onClick={rejectCall}
                className="call-button reject-call-button"
              >
                Reject
              </button>
            </div>
          </div>
        )}

        {callStatus !== "idle" && callStatus !== "incoming" && (
          <div className="active-call-panel">
            <h3>
              {callStatus === "calling"
                ? "Calling..."
                : callStatus === "connecting"
                  ? "Connecting..."
                  : "Call connected"}
            </h3>

            <p>
              {profileName || "Member"} · {activeCallType} call
            </p>

            {activeCallType === "video" && (
              <div className="call-video-grid">
                <video
                  ref={remoteVideoRef}
                  autoPlay
                  playsInline
                  className="remote-video"
                />

                <video
                  ref={localVideoRef}
                  autoPlay
                  playsInline
                  muted
                  className="local-video"
                />
              </div>
            )}

            {activeCallType === "audio" && (
              <>
                <audio ref={remoteAudioRef} autoPlay />
                <p>🎙️ Audio call in progress</p>
              </>
            )}

            <div className="call-actions">
              <button
                type="button"
                onClick={toggleMute}
                disabled={!localStream}
                className="call-button control-call-button"
              >
                {isMuted ? "Unmute" : "Mute"}
              </button>

              {activeCallType === "video" && (
                <button
                  type="button"
                  onClick={toggleCamera}
                  disabled={!localStream}
                  className="call-button control-call-button"
                >
                  {isCameraOff ? "Camera On" : "Camera Off"}
                </button>
              )}

              <button
                type="button"
                onClick={endCall}
                className="call-button reject-call-button"
              >
                End Call
              </button>
            </div>
          </div>
        )}

        {callError && (
          <p className="call-error" role="alert">
            {callError}
          </p>
        )}

        <div className="chat-toolbar">
          <span>Conversation</span>

          <div className="chat-toolbar-right">
            <small className="chat-auto-refresh" />

            <button
              type="button"
              onClick={() => loadMessages()}
              disabled={loading}
              className="chat-refresh-button"
            >
              {loading ? "Refreshing..." : "🔄️"}
            </button>
          </div>
        </div>

        <div className="chat-message-area">
          {loading && messages.length === 0 && (
            <p className="chat-info-text">
              Loading messages...
            </p>
          )}

          {!loading && messages.length === 0 && !error && (
            <div className="chat-empty-state">
              <span className="chat-empty-icon">♡</span>
              <p>No messages yet.</p>
              <small>Start the conversation!</small>
            </div>
          )}

          {/* Typing Indicator */}
          {isOtherTyping && (
            <div
              className="chat-typing-indicator"
              role="status"
              aria-live="polite"
            >
              <span className="chat-typing-dots">•••</span>
              <span>{profileName || "Member"} is typing...</span>
            </div>
          )}

          {/* Chat Messages */}
          {messages.map((message) => {
            const isMine =
              String(message.sender) === String(currentProfileId);

            return (
              <div
                key={message.id}
                className={`chat-message-row ${
                  isMine
                    ? "chat-message-mine"
                    : "chat-message-theirs"
                }`}
              >
                <div
                  className={`chat-message-bubble ${
                    isMine
                      ? "chat-my-message"
                      : "chat-their-message"
                  }`}
                >
                  <p className="chat-message-content">
                    {message.content}
                  </p>

                  {/* Message Time */}
                  <small
                    className={`chat-message-time ${
                      isMine
                        ? "chat-time-mine"
                        : "chat-time-theirs"
                    }`}
                  >
                    {formatMessageTime(message.created_at)}
                  </small>

                  {/* Sent / Seen Status */}
                  {isMine && (
                    <small className="chat-message-seen">
                      {message.is_read
                        ? `Seen${
                            message.read_at
                              ? ` · ${formatMessageTime(message.read_at)}`
                              : ""
                          }`
                        : "Sent"}
                    </small>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {error && (
          <p className="chat-error" role="alert">
            {error}
          </p>
        )}

        {success && (
          <p className="chat-success" role="status">
            {success}
          </p>
        )}

        <form onSubmit={handleSendMessage} className="chat-form">
          <input
            type="text"
            value={content}
            onChange={handleTypingChange}
            placeholder="Write a message..."
            maxLength={2000}
            className="chat-input"
            disabled={sending}
          />

          <button
            type="submit"
            disabled={!content.trim() || sending}
            className="chat-send-button"
          >
            {sending ? "Sending..." : "Send"}
          </button>
        </form>

      </section>
    </div>
  );
}

export default Chat;