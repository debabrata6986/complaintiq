import { useState, useEffect, useRef, useCallback } from "react";

export function useWebSocket(sessionId) {
  const [status, setStatus] = useState("connecting");
  const [lastMessage, setLastMessage] = useState(null);
  const ws = useRef(null);
  const reconnectAttempts = useRef(0);
  const maxRetries = 3;

  const connect = useCallback(() => {
    if (!sessionId) return;
    
    // Construct WS URL
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = process.env.REACT_APP_API_URL 
      ? new URL(process.env.REACT_APP_API_URL).host 
      : window.location.hostname + ":8001"; // Fallback to hardcoded 8001 for dev
    const wsUrl = `${protocol}//${host}/api/realtime/ws/${sessionId}`;

    setStatus("connecting");
    ws.current = new WebSocket(wsUrl);

    ws.current.onopen = () => {
      setStatus("connected");
      reconnectAttempts.current = 0;
    };

    ws.current.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        setLastMessage(data);
      } catch (err) {
        console.error("Failed to parse WS message", err);
      }
    };

    ws.current.onclose = () => {
      if (reconnectAttempts.current < maxRetries) {
        setStatus("connecting"); // Reconnecting state could be handled as 'connecting' or 'reconnecting'
        const timeout = Math.pow(2, reconnectAttempts.current) * 1000;
        reconnectAttempts.current += 1;
        setTimeout(connect, timeout);
      } else {
        setStatus("disconnected");
      }
    };

    ws.current.onerror = (error) => {
      console.error("WebSocket error", error);
      setStatus("error");
    };
  }, [sessionId]);

  useEffect(() => {
    connect();
    return () => {
      if (ws.current) {
        ws.current.close();
      }
    };
  }, [connect]);

  const send = useCallback((type, payload) => {
    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify({ type, ...payload }));
    }
  }, []);

  return { send, lastMessage, status };
}
