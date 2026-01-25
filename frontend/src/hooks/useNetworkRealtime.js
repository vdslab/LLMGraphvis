import { useState, useEffect, useCallback, useRef } from 'react';

/**
 * Custom hook to manage Server-Sent Events (SSE) connection.
 * 
 * @param {string} url - The URL to subscribe to.
 * @param {Object} options - Configuration options.
 * @param {number} [options.delay=0] - Delay before connecting (useful if waiting for ID).
 * @param {Function} [options.onMessage] - Callback for 'message' events.
 * @param {Function} [options.onError] - Callback for 'error' events.
 * @param {Object} [options.eventHandlers] - Map of event type -> callback.
 * @returns {Object} Connection state ({ isConnected, error, lastMessage }).
 */
export const useNetworkRealtime = (url, { delay = 0, onMessage, onError, eventHandlers } = {}) => {
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState(null);
  const [lastMessage, setLastMessage] = useState(null);
  const eventSourceRef = useRef(null);

  // Use refs for callbacks to avoid re-connecting when they change
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const eventHandlersRef = useRef(eventHandlers);

  useEffect(() => {
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    eventHandlersRef.current = eventHandlers;
  }, [onMessage, onError, eventHandlers]);

  const connect = useCallback(() => {
    if (!url) return;

    // Cleanup existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    console.log(`Connecting to SSE: ${url}`);
    const es = new EventSource(url);
    eventSourceRef.current = es;

    es.onopen = () => {
      console.log('SSE Connection Opened');
      setIsConnected(true);
      setError(null);
    };

    es.onerror = (e) => {
      console.error('SSE Connection Error', e);
      setIsConnected(false);
      setError('Connection lost. Retrying...');
      if (onErrorRef.current) onErrorRef.current(e);
    };

    es.onmessage = (event) => {
      try {
        const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
        setLastMessage(data);
        if (onMessageRef.current) onMessageRef.current(data);
      } catch (err) {
        console.warn('Failed to parse SSE message JSON', event.data);
      }
    };

    // Custom Event Handlers
    // We bind these once. If handler logic changes, the Ref inside the wrapper will catch it.
    // However, we need to iterate over the *initial* keys which shouldn't change often.
    // Ideally eventHandlers keys are static.
    if (eventHandlersRef.current) {
      Object.keys(eventHandlersRef.current).forEach((type) => {
        es.addEventListener(type, (event) => {
          try {
            const data = typeof event.data === 'string' ? JSON.parse(event.data) : event.data;
            // Always call the latest handler
            if (eventHandlersRef.current && eventHandlersRef.current[type]) {
                eventHandlersRef.current[type](data);
            }
          } catch (err) {
            console.error(`Error handling event '${type}'`, err);
          }
        });
      });
    }

  }, [url]); // ONLY re-connect if URL changes.

  useEffect(() => {
    let timeoutId;
    if (url) {
      if (delay > 0) {
        timeoutId = setTimeout(connect, delay);
      } else {
        connect();
      }
    }

    return () => {
      if (timeoutId) clearTimeout(timeoutId);
      if (eventSourceRef.current) {
        console.log('Closing SSE Connection');
        eventSourceRef.current.close();
        setIsConnected(false);
      }
    };
  }, [connect, url, delay]);

  return { isConnected, error, lastMessage };
};
