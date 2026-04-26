import { ref, onUnmounted } from 'vue'

export interface SSEStreamCallback {
  onEvent: (data: any) => void | Promise<void>
  onError?: (error: Error) => void
  onComplete?: () => void
}

export interface SSEStream {
  id: string
  controller: AbortController
  reader: ReadableStreamDefaultReader<Uint8Array>
  startTime: number
}

const activeStreams = ref<Map<string, SSEStream>>(new Map())

export function useSSEStreamManager() {
  function createStreamId(): string {
    return `stream_${Date.now()}_${Math.random().toString(36).slice(2, 11)}`
  }

  async function startStream(
    url: string,
    options: RequestInit,
    callbacks: SSEStreamCallback
  ): Promise<string> {
    const streamId = createStreamId()
    const controller = new AbortController()

    try {
      const response = await fetch(url, {
        ...options,
        signal: controller.signal,
      })

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      const streamInfo: SSEStream = {
        id: streamId,
        controller,
        reader,
        startTime: Date.now(),
      }
      activeStreams.value.set(streamId, streamInfo)

      processStream(streamId, reader, decoder, buffer, callbacks)

      return streamId
    } catch (error: any) {
      if (error.name === 'AbortError') {
        console.log(`Stream ${streamId} was aborted`)
      } else {
        console.error(`Stream ${streamId} error:`, error)
        callbacks.onError?.(error)
      }
      throw error
    }
  }

  async function processStream(
    streamId: string,
    reader: ReadableStreamDefaultReader<Uint8Array>,
    decoder: TextDecoder,
    initialBuffer: string,
    callbacks: SSEStreamCallback
  ) {
    let buffer = initialBuffer

    try {
      while (true) {
        const { done, value } = await reader.read()

        if (done) {
          break
        }

        buffer += decoder.decode(value, { stream: true })
        const events = buffer.split('\n\n')
        buffer = events.pop() || ''

        for (const event of events) {
          if (event.trim() && event.startsWith('data: ')) {
            try {
              const data = JSON.parse(event.slice(6))
              await callbacks.onEvent(data)

              if (data.type === 'done') {
                callbacks.onComplete?.()
                return
              }
            } catch (parseError) {
              console.error(`Failed to parse SSE event:`, parseError)
            }
          }
        }
      }

      if (buffer.trim()) {
        console.warn(`Incomplete SSE data at end of stream: ${buffer}`)
      }

      callbacks.onComplete?.()
    } catch (error: any) {
      if (error.name !== 'AbortError') {
        console.error(`Stream ${streamId} processing error:`, error)
        callbacks.onError?.(error)
      }
    } finally {
      activeStreams.value.delete(streamId)
    }
  }

  function abortStream(streamId: string) {
    const stream = activeStreams.value.get(streamId)
    if (stream) {
      stream.controller.abort()
      activeStreams.value.delete(streamId)
      console.log(`Stream ${streamId} aborted`)
    }
  }

  function abortAllStreams() {
    for (const [streamId, stream] of activeStreams.value) {
      stream.controller.abort()
      console.log(`Stream ${streamId} aborted`)
    }
    activeStreams.value.clear()
  }

  function getActiveStreams(): string[] {
    return Array.from(activeStreams.value.keys())
  }

  function isStreamActive(streamId: string): boolean {
    return activeStreams.value.has(streamId)
  }

  return {
    startStream,
    abortStream,
    abortAllStreams,
    getActiveStreams,
    isStreamActive,
    activeStreams,
  }
}

export function useSSEStream(callbacks: SSEStreamCallback) {
  const { startStream, abortStream, isStreamActive } = useSSEStreamManager()
  const currentStreamId = ref<string | null>(null)

  async function start(url: string, options: RequestInit): Promise<string> {
    if (currentStreamId.value) {
      abortStream(currentStreamId.value)
    }
    currentStreamId.value = await startStream(url, options, callbacks)
    return currentStreamId.value
  }

  function stop() {
    if (currentStreamId.value) {
      abortStream(currentStreamId.value)
      currentStreamId.value = null
    }
  }

  onUnmounted(() => {
    stop()
  })

  return {
    start,
    stop,
    streamId: currentStreamId,
    isActive: () => currentStreamId.value ? isStreamActive(currentStreamId.value) : false,
  }
}