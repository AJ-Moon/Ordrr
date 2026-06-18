import { useEffect, useRef, useState, useCallback } from "react";
import { useLocation } from "react-router-dom";
import { useRestaurant } from "@/contexts/RestaurantContext";
import { track } from "@/lib/analytics";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  isOrder?: boolean;
  orderId?: string;
  orderTotal?: number;
}

interface ApiMessage {
  role: "user" | "assistant";
  content: string;
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function genId() {
  return Math.random().toString(36).slice(2, 9);
}

function formatTime(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

// ─── Typing indicator ─────────────────────────────────────────────────────────

function TypingDots() {
  return (
    <div className="chat-bubble chat-bubble--bot" style={{ padding: "12px 16px" }}>
      <span className="typing-dots">
        <span />
        <span />
        <span />
      </span>
    </div>
  );
}

// ─── Order success bubble ─────────────────────────────────────────────────────

function OrderSuccessBubble({
  orderId,
  total,
}: {
  orderId: string;
  total: number;
}) {
  return (
    <div className="order-success-bubble">
      <div className="order-success-bubble__icon">✅</div>
      <div>
        <div className="order-success-bubble__title">Order #{orderId} confirmed!</div>
        <div className="order-success-bubble__total">Total: ${total.toFixed(2)}</div>
        <a href="/orders" className="order-success-bubble__link">
          Track your order →
        </a>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function ChatWidget() {
  const location = useLocation();
  const { restaurantName, primaryColor } = useRestaurant();

  // Hide on all admin routes
  const isAdmin =
    location.pathname.startsWith("/admin") ||
    location.pathname.startsWith("/platform-admin");
  if (isAdmin) return null;

  return <ChatWidgetInner primaryColor={primaryColor} restaurantName={restaurantName} />;
}

function ChatWidgetInner({
  primaryColor,
  restaurantName,
}: {
  primaryColor: string;
  restaurantName: string;
}) {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [unread, setUnread] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [history, setHistory] = useState<ApiMessage[]>([]);
  const [showWelcomeBubble, setShowWelcomeBubble] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const initialized = useRef(false);

  // Load session from sessionStorage
  useEffect(() => {
    const saved = sessionStorage.getItem("chat_session_id");
    if (saved) setSessionId(saved);
    else {
      // Show the welcome bubble after 2 seconds if no prior session exists
      const timer = setTimeout(() => {
        setShowWelcomeBubble(true);
      }, 2000);
      return () => clearTimeout(timer);
    }
  }, []);

  // Welcome message on first open
  useEffect(() => {
    if (open && !initialized.current) {
      initialized.current = true;
      track("chat_opened");
      setMessages([
        {
          id: genId(),
          role: "assistant",
          content: `Hi! 👋 I'm your order assistant for ${restaurantName}. I can help you browse the menu, answer questions, and place your order right here in chat. What can I get you today?`,
          timestamp: new Date(),
        },
      ]);
    }
    if (open) {
      setUnread(false);
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [open, restaurantName]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (open) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, loading, open]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || loading) return;

      const userMsg: ChatMessage = {
        id: genId(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setLoading(true);
      track("chat_message_sent", { properties: { intent: "general", length: text.length } });

      const newHistory: ApiMessage[] = [
        ...history,
        { role: "user", content: text },
      ];

      try {
        const token = localStorage.getItem("user_token");
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
          },
          body: JSON.stringify({
            message: text,
            session_id: sessionId,
            conversation_history: history,
          }),
        });

        if (!res.ok) throw new Error("API error");
        const data = await res.json();

        // Save session
        if (data.session_id) {
          setSessionId(data.session_id);
          sessionStorage.setItem("chat_session_id", data.session_id);
        }

        // Build assistant message
        const isOrder = data.action?.type === "order_placed";
        const assistantMsg: ChatMessage = {
          id: genId(),
          role: "assistant",
          content: data.reply,
          timestamp: new Date(),
          isOrder,
          orderId: isOrder ? data.action.order_id : undefined,
          orderTotal: isOrder ? data.action.total : undefined,
        };

        setMessages((prev) => [...prev, assistantMsg]);
        setHistory([
          ...newHistory,
          { role: "assistant", content: data.reply },
        ]);

        // Badge if closed
        if (!open) setUnread(true);
      } catch {
        setMessages((prev) => [
          ...prev,
          {
            id: genId(),
            role: "assistant",
            content:
              "Sorry, I'm having trouble right now. Please try again or call us directly! 📞",
            timestamp: new Date(),
          },
        ]);
      } finally {
        setLoading(false);
      }
    },
    [loading, history, sessionId, open],
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <>
      {/* Inline styles — no Tailwind dependency for this widget */}
      <style>{`
        .chat-trigger {
          position: fixed;
          bottom: 24px;
          right: 24px;
          z-index: 9999;
          width: 56px;
          height: 56px;
          border-radius: 50%;
          background: ${primaryColor};
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          box-shadow: 0 4px 24px rgba(0,0,0,0.18);
          transition: transform 0.18s, box-shadow 0.18s;
        }
        .chat-trigger:hover { transform: scale(1.08); box-shadow: 0 6px 28px rgba(0,0,0,0.22); }
        .chat-trigger svg { width: 26px; height: 26px; fill: white; }

        .chat-unread-dot {
          position: absolute;
          top: 4px;
          right: 4px;
          width: 12px;
          height: 12px;
          border-radius: 50%;
          background: #ef4444;
          border: 2px solid white;
        }

        .chat-panel {
          position: fixed;
          bottom: 92px;
          right: 24px;
          width: 380px;
          height: 520px;
          z-index: 9998;
          background: white;
          border-radius: 16px;
          box-shadow: 0 8px 48px rgba(0,0,0,0.18);
          display: flex;
          flex-direction: column;
          overflow: hidden;
          animation: chatSlideIn 0.22s ease;
        }
        @media (max-width: 640px) {
          .chat-panel {
            inset: 0;
            width: 100%;
            height: 100%;
            bottom: 0;
            right: 0;
            border-radius: 0;
          }
        }
        @keyframes chatSlideIn {
          from { opacity: 0; transform: translateY(16px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)   scale(1); }
        }

        .chat-header {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 14px 16px;
          border-bottom: 1px solid #f1f5f9;
          background: white;
          flex-shrink: 0;
        }
        .chat-header__avatar {
          width: 36px;
          height: 36px;
          border-radius: 50%;
          background: ${primaryColor};
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
        }
        .chat-header__avatar svg { width: 18px; height: 18px; fill: white; }
        .chat-header__info { flex: 1; min-width: 0; }
        .chat-header__title { font-weight: 600; font-size: 14px; color: #0f172a; line-height: 1.2; }
        .chat-header__subtitle { font-size: 12px; color: #64748b; display: flex; align-items: center; gap: 4px; }
        .chat-header__online-dot { width: 7px; height: 7px; border-radius: 50%; background: #22c55e; }
        .chat-close {
          background: none; border: none; cursor: pointer;
          color: #94a3b8; padding: 4px; border-radius: 6px;
          display: flex; align-items: center; justify-content: center;
          transition: color 0.15s, background 0.15s;
          flex-shrink: 0;
        }
        .chat-close:hover { color: #0f172a; background: #f1f5f9; }
        .chat-close svg { width: 18px; height: 18px; }

        .chat-messages {
          flex: 1;
          overflow-y: auto;
          padding: 16px;
          display: flex;
          flex-direction: column;
          gap: 10px;
          scroll-behavior: smooth;
        }
        .chat-messages::-webkit-scrollbar { width: 4px; }
        .chat-messages::-webkit-scrollbar-track { background: transparent; }
        .chat-messages::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 2px; }

        .chat-msg-row {
          display: flex;
          flex-direction: column;
        }
        .chat-msg-row--user { align-items: flex-end; }
        .chat-msg-row--bot  { align-items: flex-start; }

        .chat-bubble {
          max-width: 78%;
          padding: 10px 14px;
          font-size: 14px;
          line-height: 1.5;
          word-break: break-word;
          white-space: pre-wrap;
        }
        .chat-bubble--user {
          background: ${primaryColor};
          color: white;
          border-radius: 18px 18px 4px 18px;
        }
        .chat-bubble--bot {
          background: #f1f5f9;
          color: #0f172a;
          border-radius: 18px 18px 18px 4px;
        }
        .chat-ts {
          font-size: 11px;
          color: #94a3b8;
          margin-top: 3px;
          padding: 0 2px;
        }

        .typing-dots {
          display: inline-flex;
          gap: 4px;
          align-items: center;
        }
        .typing-dots span {
          width: 7px; height: 7px;
          border-radius: 50%;
          background: #94a3b8;
          animation: typingBounce 1.2s infinite;
        }
        .typing-dots span:nth-child(2) { animation-delay: 0.2s; }
        .typing-dots span:nth-child(3) { animation-delay: 0.4s; }
        @keyframes typingBounce {
          0%, 80%, 100% { transform: translateY(0); }
          40%            { transform: translateY(-6px); }
        }

        .order-success-bubble {
          max-width: 78%;
          border: 1.5px solid #22c55e;
          border-radius: 18px 18px 18px 4px;
          padding: 12px 16px;
          background: #f0fdf4;
          display: flex;
          gap: 10px;
          align-items: flex-start;
        }
        .order-success-bubble__icon { font-size: 20px; flex-shrink: 0; margin-top: 1px; }
        .order-success-bubble__title { font-weight: 600; font-size: 14px; color: #15803d; }
        .order-success-bubble__total { font-size: 13px; color: #166534; margin: 2px 0; }
        .order-success-bubble__link {
          font-size: 13px;
          color: #16a34a;
          text-decoration: underline;
          cursor: pointer;
          font-weight: 500;
        }
        .order-success-bubble__link:hover { color: #15803d; }

        .chat-input-area {
          border-top: 1px solid #f1f5f9;
          padding: 12px;
          display: flex;
          gap: 8px;
          align-items: flex-end;
          flex-shrink: 0;
          background: white;
        }
        .chat-input {
          flex: 1;
          border: 1.5px solid #e2e8f0;
          border-radius: 10px;
          padding: 9px 12px;
          font-size: 14px;
          color: #0f172a;
          outline: none;
          resize: none;
          background: #f8fafc;
          transition: border-color 0.15s;
          font-family: inherit;
        }
        .chat-input:focus { border-color: ${primaryColor}; background: white; }
        .chat-input::placeholder { color: #94a3b8; }
        .chat-input:disabled { opacity: 0.6; }

        .chat-send {
          width: 38px;
          height: 38px;
          border-radius: 10px;
          background: ${primaryColor};
          border: none;
          cursor: pointer;
          display: flex;
          align-items: center;
          justify-content: center;
          flex-shrink: 0;
          transition: opacity 0.15s, transform 0.12s;
        }
        .chat-send:disabled { opacity: 0.5; cursor: not-allowed; }
        .chat-send:not(:disabled):hover { opacity: 0.88; transform: scale(1.05); }
        .chat-send svg { width: 17px; height: 17px; fill: white; }

        .chat-welcome-bubble {
          position: fixed;
          bottom: 96px;
          right: 24px;
          z-index: 9998;
          background: white;
          color: #0f172a;
          padding: 18px 24px;
          border-radius: 16px 16px 0 16px;
          box-shadow: 0 6px 28px rgba(0,0,0,0.18);
          font-size: 16px;
          font-weight: 500;
          cursor: pointer;
          animation: welcomeSlideIn 0.3s cubic-bezier(0.16, 1, 0.3, 1);
          border: 1px solid #f1f5f9;
          padding-right: 42px;
        }
        .chat-welcome-close {
          position: absolute;
          top: 10px;
          right: 10px;
          width: 24px;
          height: 24px;
          background: none;
          border: none;
          cursor: pointer;
          color: #94a3b8;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          padding: 0;
          transition: color 0.15s;
        }
        .chat-welcome-close:hover { color: #0f172a; }
        @keyframes welcomeSlideIn {
          from { opacity: 0; transform: translateY(10px) scale(0.95); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .chat-welcome-bubble::after {
          content: "";
          position: absolute;
          bottom: -6px;
          right: 16px;
          width: 12px;
          height: 12px;
          background: white;
          border-right: 1px solid #f1f5f9;
          border-bottom: 1px solid #f1f5f9;
          transform: rotate(45deg);
        }
      `}</style>

      {/* Trigger button */}
      <button
        id="chat-widget-trigger"
        className="chat-trigger"
        onClick={() => {
          setOpen((o) => !o);
          setShowWelcomeBubble(false);
        }}
        aria-label="Open chat assistant"
      >
        {open ? (
          <svg viewBox="0 0 24 24"><path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/></svg>
        ) : (
          <svg viewBox="0 0 24 24"><path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm-2 12H6v-2h12v2zm0-3H6V9h12v2zm0-3H6V6h12v2z"/></svg>
        )}
        {unread && !open && <span className="chat-unread-dot" />}
      </button>

      {/* Welcome Bubble */}
      {showWelcomeBubble && !open && (
        <div 
          className="chat-welcome-bubble" 
          onClick={() => { 
            setOpen(true); 
            setShowWelcomeBubble(false); 
          }}
        >
          Hi there! 👋 Need help ordering?
          <button
            className="chat-welcome-close"
            onClick={(e) => {
              e.stopPropagation();
              setShowWelcomeBubble(false);
            }}
            aria-label="Close welcome message"
          >
            ✕
          </button>
        </div>
      )}

      {/* Chat panel */}
      {open && (
        <div className="chat-panel" role="dialog" aria-label="Chat with order assistant">
          {/* Header */}
          <div className="chat-header">
            <div className="chat-header__avatar">
              <svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg>
            </div>
            <div className="chat-header__info">
              <div className="chat-header__title">{restaurantName}</div>
              <div className="chat-header__subtitle">
                <span className="chat-header__online-dot" />
                Order Assistant • Online
              </div>
            </div>
            <button
              className="chat-close"
              onClick={() => setOpen(false)}
              aria-label="Close chat"
            >
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
                <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>

          {/* Messages */}
          <div className="chat-messages" id="chat-messages-area">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`chat-msg-row chat-msg-row--${msg.role === "user" ? "user" : "bot"}`}
              >
                {msg.isOrder && msg.orderId != null ? (
                  <OrderSuccessBubble orderId={msg.orderId} total={msg.orderTotal ?? 0} />
                ) : (
                  <div className={`chat-bubble chat-bubble--${msg.role === "user" ? "user" : "bot"}`}>
                    {msg.content}
                  </div>
                )}
                <span className="chat-ts">{formatTime(msg.timestamp)}</span>
              </div>
            ))}

            {loading && (
              <div className="chat-msg-row chat-msg-row--bot">
                <TypingDots />
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Input area */}
          <div className="chat-input-area">
            <input
              ref={inputRef}
              id="chat-input"
              className="chat-input"
              placeholder="Type a message..."
              value={input}
              maxLength={500}
              disabled={loading}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              autoComplete="off"
            />
            <button
              id="chat-send-btn"
              className="chat-send"
              disabled={loading || !input.trim()}
              onClick={() => sendMessage(input)}
              aria-label="Send message"
            >
              <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
            </button>
          </div>
        </div>
      )}
    </>
  );
}
