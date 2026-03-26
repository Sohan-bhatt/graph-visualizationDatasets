import { create } from "zustand";
import type { ChatMessage } from "../types/graph";
import { sendChatMessage } from "../api/client";

interface ChatState {
  messages: ChatMessage[];
  isStreaming: boolean;
  currentThought: string;
  currentSql: string;
  sessionId: string;

  sendMessage: (text: string, highlightCallback: (ids: string[], focalNodeId?: string) => void) => Promise<void>;
  clearMessages: () => void;
}

export const useChatStore = create<ChatState>((set, get) => ({
  messages: [],
  isStreaming: false,
  currentThought: "",
  currentSql: "",
  sessionId: `session_${Date.now()}`,

  sendMessage: async (text: string, highlightCallback: (ids: string[], focalNodeId?: string) => void) => {
    const { messages, sessionId } = get();

    const userMsg: ChatMessage = { role: "user", content: text };
    set({
      messages: [...messages, userMsg],
      isStreaming: true,
      currentThought: "",
      currentSql: "",
    });

    try {
      await sendChatMessage(
        text,
        sessionId,
        (thought: string) => set({ currentThought: thought }),
        (sql: string) => set({ currentSql: sql }),
        () => {},
        (answer: string, sources: string[], highlightedIds: string[], queryType: string, focalNodeId?: string) => {
          const assistantMsg: ChatMessage = {
            role: "assistant",
            content: answer,
            thought: get().currentThought,
            sql: get().currentSql,
            sources,
            highlighted_ids: highlightedIds,
            focal_node_id: focalNodeId,
            query_type: queryType,
          };
          set((state) => ({
            messages: [...state.messages, assistantMsg],
            isStreaming: false,
            currentThought: "",
            currentSql: "",
          }));
          if (highlightedIds.length > 0) {
            highlightCallback(highlightedIds, focalNodeId);
          }
        },
        (error: string) => {
          const errorMsg: ChatMessage = {
            role: "assistant",
            content: `Error: ${error}`,
            is_guardrailed: true,
          };
          set((state) => ({
            messages: [...state.messages, errorMsg],
            isStreaming: false,
          }));
        }
      );
    } catch (e) {
      const errorMsg: ChatMessage = {
        role: "assistant",
        content: `Connection error: ${String(e)}`,
        is_guardrailed: true,
      };
      set((state) => ({
        messages: [...state.messages, errorMsg],
        isStreaming: false,
      }));
    }
  },

  clearMessages: () => {
    set({
      messages: [],
      currentThought: "",
      currentSql: "",
      sessionId: `session_${Date.now()}`,
    });
  },
}));
