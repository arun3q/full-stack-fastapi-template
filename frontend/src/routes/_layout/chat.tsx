import { useQuery } from "@tanstack/react-query"
import { createFileRoute } from "@tanstack/react-router"
import { Bot, Send, Square, User } from "lucide-react"
import { useRef, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import useCustomToast from "@/hooks/useCustomToast"
import { featureApi, streamChat } from "@/lib/featureApi"

type ChatMessage = {
  role: "user" | "assistant"
  content: string
}

export const Route = createFileRoute("/_layout/chat")({
  component: ChatPage,
  head: () => ({
    meta: [
      {
        title: "AI Chat - FastAPI Template",
      },
    ],
  }),
})

function ChatPage() {
  const { showErrorToast } = useCustomToast()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState("")
  const [isStreaming, setIsStreaming] = useState(false)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  const aiHealthQuery = useQuery({
    queryKey: ["aiHealth"],
    queryFn: featureApi.aiHealth,
  })

  const scrollToBottom = () => {
    requestAnimationFrame(() => {
      scrollRef.current?.scrollIntoView({ behavior: "smooth" })
    })
  }

  const sendMessage = async () => {
    const content = input.trim()
    if (!content || isStreaming) return

    setInput("")
    const userMessage: ChatMessage = { role: "user", content }
    const assistantMessage: ChatMessage = { role: "assistant", content: "" }
    setMessages((prev) => [...prev, userMessage, assistantMessage])
    setIsStreaming(true)
    scrollToBottom()

    const abortController = new AbortController()
    abortRef.current = abortController

    try {
      await streamChat({
        messages: messages
          .concat(userMessage)
          .map((m): { role: string; content: string } => ({
            role: m.role,
            content: m.content,
          })),
        signal: abortController.signal,
        onToken: (token) => {
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.role === "assistant") {
              next[next.length - 1] = {
                ...last,
                content: last.content + token,
              }
            }
            return next
          })
          scrollToBottom()
        },
      })
    } catch (error) {
      if (!abortController.signal.aborted) {
        showErrorToast((error as Error).message)
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }

  const stopStreaming = () => {
    abortRef.current?.abort()
  }

  const provider = aiHealthQuery.data?.provider

  return (
    <div className="flex h-[calc(100svh-7rem)] flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">AI Chat</h1>
          <p className="text-muted-foreground">
            Stream responses from your configured LLM provider
          </p>
        </div>
        {aiHealthQuery.isLoading ? (
          <Skeleton className="h-6 w-32" />
        ) : provider ? (
          <Badge variant="secondary">{provider}</Badge>
        ) : (
          <Badge variant="outline">Not configured</Badge>
        )}
      </div>

      <div className="flex flex-1 flex-col overflow-y-auto rounded-lg border bg-background">
        <div className="flex flex-1 flex-col gap-4 p-4">
          {messages.length === 0 ? (
            <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
              <Bot className="size-10 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                {provider
                  ? `Ask anything, streaming replies from ${provider}.`
                  : "AI is not configured. Set AI_PROVIDER and an API key in your environment."}
              </p>
            </div>
          ) : (
            messages.map((message, index) => (
              <div
                key={index}
                className={`flex gap-3 ${
                  message.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`flex max-w-[80%] items-start gap-2 rounded-lg px-3 py-2 text-sm ${
                    message.role === "user"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted"
                  }`}
                >
                  {message.role === "assistant" ? (
                    <Bot className="mt-0.5 size-4 shrink-0" />
                  ) : (
                    <User className="mt-0.5 size-4 shrink-0" />
                  )}
                  <span className="whitespace-pre-wrap">
                    {message.content}
                    {message.role === "assistant" &&
                    isStreaming &&
                    index === messages.length - 1 ? (
                      <span className="ml-0.5 inline-block animate-pulse">
                        ▋
                      </span>
                    ) : null}
                  </span>
                </div>
              </div>
            ))
          )}
          <div ref={scrollRef} />
        </div>
      </div>

      <div className="flex gap-2">
        <Input
          data-testid="chat-input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              sendMessage()
            }
          }}
          placeholder="Type your message…"
          disabled={isStreaming}
        />
        {isStreaming ? (
          <Button
            variant="outline"
            onClick={stopStreaming}
            data-testid="chat-stop"
          >
            <Square className="size-4" />
          </Button>
        ) : (
          <Button onClick={sendMessage} data-testid="chat-send">
            <Send className="size-4" />
          </Button>
        )}
      </div>
    </div>
  )
}
