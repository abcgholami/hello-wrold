import { useEffect, useRef, useCallback, useState } from 'react'

type WSStatus = 'connecting' | 'open' | 'closed' | 'error'

interface UseWebSocketOptions {
  onMessage?: (data: unknown) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (event: Event) => void
  reconnect?: boolean
  reconnectDelay?: number
  maxReconnectAttempts?: number
}

export function useWebSocket(url: string | null, options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnect = true,
    reconnectDelay = 2000,
    maxReconnectAttempts = 5,
  } = options

  const wsRef = useRef<WebSocket | null>(null)
  const reconnectCount = useRef(0)
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [status, setStatus] = useState<WSStatus>('closed')

  const connect = useCallback(() => {
    if (!url) return
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return

    setStatus('connecting')
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      setStatus('open')
      reconnectCount.current = 0
      onOpen?.()
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        onMessage?.(data)
      } catch {
        onMessage?.(event.data)
      }
    }

    ws.onclose = () => {
      setStatus('closed')
      onClose?.()
      if (reconnect && reconnectCount.current < maxReconnectAttempts) {
        reconnectCount.current += 1
        reconnectTimer.current = setTimeout(connect, reconnectDelay)
      }
    }

    ws.onerror = (event) => {
      setStatus('error')
      onError?.(event)
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnect, reconnectDelay, maxReconnectAttempts])

  const disconnect = useCallback(() => {
    if (reconnectTimer.current) clearTimeout(reconnectTimer.current)
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('closed')
  }, [])

  const sendMessage = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(typeof data === 'string' ? data : JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    if (url) connect()
    return disconnect
  }, [url]) // eslint-disable-line react-hooks/exhaustive-deps

  return { status, sendMessage, disconnect, reconnect: connect }
}
