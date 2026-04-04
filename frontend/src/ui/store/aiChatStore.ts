import { create } from "zustand"
import { persist } from "zustand/middleware"

import type { AiChatContextKind } from "@/views/ai/chatRouting"

export type AiChatCourseEvidence = {
  kind: "transcript" | "slide_text" | "video_frame"
  instanceId: string
  startMs: number
  endMs: number
  title: string
  preview?: string
}

export type AiChatMessage = {
  id: string
  role: "user" | "assistant" | "system"
  content: string
  createdAt: number
  modelReliabilityIssue?: boolean
  courseEvidence?: AiChatCourseEvidence[]
}

export type AiChatConversation = {
  id: string
  projectId: string
  contextKind: AiChatContextKind
  nodeId: string
  title: string
  createdAt: number
  updatedAt: number
  messages: AiChatMessage[]
}

type AiChatState = {
  conversations: AiChatConversation[]
  createConversation: (payload: {
    projectId: string
    contextKind: AiChatContextKind
    nodeId: string
    messages: AiChatMessage[]
  }) => string
  appendMessages: (conversationId: string, messages: AiChatMessage[]) => void
  replaceMessages: (conversationId: string, messages: AiChatMessage[]) => void
  renameConversation: (conversationId: string, title: string) => void
  removeConversation: (conversationId: string) => void
  reset: () => void
}

const MAX_CONVERSATIONS = 80

function createLocalId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function summarizeConversationTitle(messages: AiChatMessage[]) {
  const firstUserMessage = messages.find((message) => message.role === "user")?.content.trim() ?? ""
  if (!firstUserMessage) return "新会话"
  if (firstUserMessage.length <= 28) return firstUserMessage
  return `${firstUserMessage.slice(0, 27).trimEnd()}…`
}

const initialState = {
  conversations: [] as AiChatConversation[],
}

export const useAiChatStore = create<AiChatState>()(
  persist(
    (set) => ({
      ...initialState,
      createConversation: (payload) => {
        let createdConversationId = ""
        set((state) => {
          createdConversationId = createLocalId()
          const now = Date.now()
          const createdConversation: AiChatConversation = {
            id: createdConversationId,
            projectId: payload.projectId,
            contextKind: payload.contextKind,
            nodeId: payload.nodeId,
            title: summarizeConversationTitle(payload.messages),
            createdAt: now,
            updatedAt: now,
            messages: payload.messages,
          }
          return {
            conversations: [createdConversation, ...state.conversations].slice(0, MAX_CONVERSATIONS),
          }
        })
        return createdConversationId
      },
      appendMessages: (conversationId, messages) =>
        set((state) => {
          const nextConversations = state.conversations.map((conversation) => {
            if (conversation.id !== conversationId) return conversation
            const nextMessages = [...conversation.messages, ...messages]
            return {
              ...conversation,
              title: summarizeConversationTitle(nextMessages),
              updatedAt: Date.now(),
              messages: nextMessages,
            }
          })
          nextConversations.sort((left, right) => right.updatedAt - left.updatedAt)
          return {
            conversations: nextConversations.slice(0, MAX_CONVERSATIONS),
          }
        }),
      replaceMessages: (conversationId, messages) =>
        set((state) => {
          const nextConversations = state.conversations.map((conversation) => {
            if (conversation.id !== conversationId) return conversation
            return {
              ...conversation,
              title: summarizeConversationTitle(messages),
              updatedAt: Date.now(),
              messages,
            }
          })
          nextConversations.sort((left, right) => right.updatedAt - left.updatedAt)
          return {
            conversations: nextConversations.slice(0, MAX_CONVERSATIONS),
          }
        }),
      renameConversation: (conversationId, title) =>
        set((state) => ({
          conversations: state.conversations.map((conversation) =>
            conversation.id === conversationId
              ? {
                  ...conversation,
                  title: title.trim() || conversation.title,
                }
              : conversation,
          ),
        })),
      removeConversation: (conversationId) =>
        set((state) => ({
          conversations: state.conversations.filter((conversation) => conversation.id !== conversationId),
        })),
      reset: () => set(initialState),
    }),
    { name: "plm-ai-chat" },
  ),
)
