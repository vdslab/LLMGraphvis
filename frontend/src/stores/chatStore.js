import { create } from 'zustand';
import { useNetworkStore } from './networkStore';
import {
  getChats,
  getChat,
  getChatMessages,
  exportNetwork,
  createChat as createChatAPI,
  updateChat as updateChatAPI,
  processMessage as processMessageAPI,
  uploadGraphML,
  getLlmProviders,
  getSampleNetworks,
  loadSampleNetwork as loadSampleNetworkAPI,
  getApiErrorMessage,
} from '../services/api';

export const useChatStore = create((set, get) => ({
  chatId: null,
  chatName: null,
  messages: [],
  isLoading: false,
  thinkingMessage: null,
  streamingMessageId: null,
  runningTool: null,
  // Backend pipeline steps for the turn in progress. Kept apart from
  // thinkingMessage on purpose: these are our labels, not model reasoning.
  progressSteps: [],
  // Tool results that finished before the assistant message they belong to
  // existed; adopted by appendMessageChunk when it creates that message.
  pendingToolExecutions: [],

  // Per-chat LLM provider/model pin (null means "use server default")
  chatProvider: null,
  chatModel: null,
  llmProviders: [],

  // Bundled starter data, loaded from the backend so the UI never hardcodes
  // which samples are installed.
  sampleNetworks: [],
  sampleNetworksStatus: 'idle',
  sampleNetworksError: null,

  // Token/cost usage tracking (Stage 7)
  chatUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },   // lifetime total for this chat session (client-side accumulation across turns)
  currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null },  // running total for the turn currently in progress

  // Get all chats for current user
  fetchChats: async () => {
    const res = await getChats();
    return res.data;
  },
  
  // Get chat details
  fetchChat: async (chatId) => {
    const res = await getChat(chatId);
    
    // Race condition guard: ensure we are still on the requested chat
    if (get().chatId !== chatId) return;

    if (res.data.network) {
      useNetworkStore.getState().setNetworkData(res.data.network);
    } else {
      useNetworkStore.getState().reset();
    }
    
    // Sync network ID if present
    if (res.data.network_id) {
       useNetworkStore.getState().setNetworkId(res.data.network_id);
    }

    set({
      chatName: res.data.name ?? null,
      chatProvider: res.data.provider ?? null,
      chatModel: res.data.model ?? null,
    });

    return res.data;
  },

  // Load the catalog of provider/model options a chat can be pinned to
  fetchLlmProviders: async () => {
    if (get().llmProviders.length > 0) return get().llmProviders;
    const res = await getLlmProviders();
    set({ llmProviders: res.data });
    return res.data;
  },

  fetchSampleNetworks: async () => {
    if (get().sampleNetworksStatus === 'success') return get().sampleNetworks;

    set({ sampleNetworksStatus: 'loading', sampleNetworksError: null });
    try {
      const res = await getSampleNetworks();
      set({ sampleNetworks: res.data, sampleNetworksStatus: 'success' });
      return res.data;
    } catch (error) {
      set({
        sampleNetworksStatus: 'error',
        sampleNetworksError: getApiErrorMessage(error),
      });
      throw error;
    }
  },

  // Pin (or clear, with null) this chat's provider/model
  updateChatSettings: async (chatId, { provider, model }) => {
    const res = await updateChatAPI(chatId, { provider, model });
    set({ chatProvider: res.data.provider ?? null, chatModel: res.data.model ?? null });
    return res.data;
  },
  
  // Get message history
  fetchMessages: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return;
    
    const res = await getChatMessages(id);
    
    // Race condition guard
    if (get().chatId !== id) return;

    let inputTokens = 0;
    let outputTokens = 0;
    let estimatedCostUsd = 0;

    res.data.forEach(msg => {
      if (msg.usage) {
        inputTokens += msg.usage.input_tokens || 0;
        outputTokens += msg.usage.output_tokens || 0;
        estimatedCostUsd += msg.usage.estimated_cost_usd || 0;
      }
    });

    set({ 
      messages: res.data,
      chatUsage: { inputTokens, outputTokens, estimatedCostUsd },
      currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null }
    });
    return res.data;
  },

  // Create a new chat
  createChat: async (name) => {
    const res = await createChatAPI(name);
    set({ chatId: res.data.id, chatName: res.data.name ?? null, messages: [] });
    useNetworkStore.getState().setNetworkId(res.data.network_id);
    return res.data;
  },

  // Rename a chat. The backend marks any name sent from here as user-chosen, so
  // auto-naming (upload filename / generated title) stops touching this chat.
  renameChat: async (chatId, name) => {
    const res = await updateChatAPI(chatId, { name });
    if (get().chatId === chatId) {
      set({ chatName: res.data.name ?? null });
    }
    return res.data;
  },

  // Name assigned by the backend (chat_renamed SSE event)
  setChatName: (name) => set({ chatName: name }),

  // Upload network file to chat
  uploadNetwork: async (chatId, file) => {
    get().beginTurn();
    try {
      await uploadGraphML(chatId, file);
      // Response is 202 Accepted.
      // SSE will handle the rest.
    } catch (error) {
      console.error("Failed to upload network:", error);
      get().endTurn();
      throw error;
    }
  },

  loadSampleNetwork: async (chatId, sampleId) => {
    get().beginTurn();
    try {
      await loadSampleNetworkAPI(chatId, sampleId);
      // Response is 202 Accepted; SSE completes the shared import pipeline.
    } catch (error) {
      console.error("Failed to load sample network:", error);
      get().endTurn();
      throw error;
    }
  },

  // --- Turn lifecycle -------------------------------------------------------
  // A turn is one POST that the backend answers 202 to, followed by SSE events
  // until a terminal one (message / message_complete / error). Everything that
  // is only true *during* a turn is set and cleared here, in one place, so a
  // mid-turn event like render_update can no longer half-end the turn.

  beginTurn: () => set({
    isLoading: true,
    thinkingMessage: null,
    progressSteps: [],
    runningTool: null,
    pendingToolExecutions: [],
  }),

  endTurn: () => {
    set({
      isLoading: false,
      thinkingMessage: null,
      progressSteps: [],
      runningTool: null,
      streamingMessageId: null,
      pendingToolExecutions: [],
    });
    // A message the user wrote while this turn was running goes out now.
    get().dispatchQueued();
  },

  // A new running step implicitly finishes the previous one, so the backend
  // only has to name what it is starting.
  setProgress: ({ label, status }) => set((state) => {
    const steps = state.progressSteps.map((step) => ({ ...step, status: 'done' }));
    const existing = steps.findIndex((step) => step.label === label);
    if (existing !== -1) {
      steps[existing].status = status;
      return { progressSteps: steps, isLoading: true };
    }
    return { progressSteps: [...steps, { label, status }], isLoading: true };
  }),

  // --- Sending --------------------------------------------------------------

  setMessageStatus: (localId, status) => set((state) => ({
    messages: state.messages.map((message) =>
      message.localId === localId ? { ...message, status } : message
    ),
  })),

  /**
   * Post a queued message and open a turn for it.
   *
   * The user message is already on screen at this point — it is added the
   * instant the user hits send, and only its status changes here.
   */
  dispatchMessage: async (localId) => {
    const message = get().messages.find((m) => m.localId === localId);
    if (!message) return;

    get().beginTurn();
    get().setMessageStatus(localId, 'sending');

    try {
      await processMessageAPI(get().chatId, message.content);
      // 202 Accepted; SSE carries the rest of the turn.
      get().setMessageStatus(localId, 'sent');
    } catch (error) {
      console.error("Failed to send message:", error);
      get().setMessageStatus(localId, 'failed');
      set({ isLoading: false, thinkingMessage: null, progressSteps: [] });
    }
  },

  /**
   * Show the user's message immediately, then send it.
   *
   * Sending during a turn is allowed: the message is parked with status
   * 'queued' and dispatched by endTurn(). One turn at a time is a backend
   * constraint (a turn reads the chat history it is about to extend), not a
   * reason to take the keyboard away from the user.
   */
  sendMessage: async (content) => {
    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const busy = get().isLoading;

    set((state) => ({
      messages: [...state.messages, {
        id: localId,
        localId,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
        status: busy ? 'queued' : 'sending',
      }],
    }));

    if (busy) return;
    await get().dispatchMessage(localId);
  },

  dispatchQueued: () => {
    if (get().isLoading) return;
    const next = get().messages.find((message) => message.status === 'queued');
    if (next) get().dispatchMessage(next.localId);
  },

  retryMessage: async (message) => {
    if (get().isLoading) {
      get().setMessageStatus(message.localId, 'queued');
      return;
    }
    await get().dispatchMessage(message.localId);
  },

  // Export network as GraphML
  exportNetworkAsGraphML: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return;
    
    const response = await exportNetwork(id);
    
    // Create a download link
    const url = window.URL.createObjectURL(new Blob([response.data]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `network_${id}.graphml`);
    document.body.appendChild(link);
    link.click();
    link.remove();
  },

  addMessage: (message) => {
    set((state) => {
      // Deduplicate: Check if message with same ID already exists
      if (state.messages.some(m => m.id === message.id)) {
        return {};
      }

      // Also check if we have a streaming message that needs to be replaced/merged
      // This handles the race condition where `message` event arrives but we have a `isStreaming` placeholder
      
      // Use ID check if available, otherwise strict role/streaming check
      const streamingMsg = state.streamingMessageId 
        ? state.messages.find(m => m.id === state.streamingMessageId)
        : state.messages.find(m => m.isStreaming && m.role === 'assistant');

      if (streamingMsg && message.role === 'assistant') {
         // Assuming this is the finalized version of the streaming message
         const updatedMessages = state.messages.map(m => {
            if (m.id === streamingMsg.id) {
                return { ...message, isStreaming: false };
            }
            return m;
         });
         return { messages: updatedMessages };
      }

      return { messages: [...state.messages, message] };
    });
    // `message` is terminal for the turn that produced it (the upload
    // pipeline's only output, or an assistant reply delivered whole).
    get().endTurn();
  },

  appendMessageChunk: (content) => {
    set((state) => {
      const messages = [...state.messages];
      let msgIndex = -1;
      
      // 1. Try to find by streamingMessageId
      if (state.streamingMessageId) {
          msgIndex = messages.findIndex(m => m.id === state.streamingMessageId);
      }
      
      // 2. Fallback: Find last streaming assistant message
      if (msgIndex === -1) {
          msgIndex = messages.findLastIndex(m => m.isStreaming && m.role === 'assistant');
      }

      if (msgIndex !== -1) {
        // Update existing
        const msg = { ...messages[msgIndex] };
        msg.content += content;
        messages[msgIndex] = msg;
        return { 
          messages,
          thinkingMessage: null 
        };
      } else {
        // Create new, adopting any tool results that finished before there was
        // a message to hold them.
        const newId = Date.now();
        const newMessage = {
          role: 'assistant',
          content,
          id: newId,
          created_at: new Date().toISOString(),
          isStreaming: true,
          tool_executions: state.pendingToolExecutions
        };
        return {
          messages: [...messages, newMessage],
          thinkingMessage: null,
          streamingMessageId: newId,
          pendingToolExecutions: []
        };
      }
    });
  },

  addToolExecutionToStreamingMessage: (toolData) => {
      set((state) => {
          // A tool can finish before the assistant has emitted any text, so
          // there is no message to attach it to yet. Hold it: the transcript
          // marker that refers to it by index arrives moments later, and
          // dropping it here left that marker rendering as a tool stuck on
          // "running" for the rest of the turn.
          if (!state.streamingMessageId) {
              return { pendingToolExecutions: [...state.pendingToolExecutions, toolData] };
          }

          const messages = [...state.messages];
          const idx = messages.findIndex(m => m.id === state.streamingMessageId);
          if (idx === -1) return {};

          const msg = { ...messages[idx] };
          if (!msg.tool_executions) msg.tool_executions = [];
          
          msg.tool_executions = [...msg.tool_executions, toolData];
          messages[idx] = msg;
          
          return { messages };
      });
  },

  finalizeStreamingMessage: (realId, content = null, tool_executions = null) => {
    set((state) => {
      const messages = [...state.messages];
      // Use findLast or specific ID
      const idx = state.streamingMessageId 
        ? messages.findIndex(m => m.id === state.streamingMessageId)
        : messages.findLastIndex(m => m.isStreaming);
        
      if (idx !== -1) {
        messages[idx].isStreaming = false;
        if (realId) {
            messages[idx].id = realId;
        }
        if (content) {
            messages[idx].content = content;
        }
        if (tool_executions) {
            messages[idx].tool_executions = tool_executions;
        }
      }
      return { messages };
    });
    get().endTurn();
  },

  setThinkingMessage: (msg) => set({ thinkingMessage: msg }),
  setRunningTool: (tool) => set({ runningTool: tool }),

  appendThinkingMessage: (chunk) => set((state) => ({
    thinkingMessage: (state.thinkingMessage || "") + chunk
  })),

  setIsLoading: (loading) => set({ isLoading: loading }),

  setChatId: (id) => set({ chatId: id }),

  // Usage tracking (Stage 7): usage_update SSE events carry a RUNNING TOTAL for the
  // in-progress turn (not deltas), so this replaces currentTurnUsage wholesale each time.
  setCurrentTurnUsage: (data) => set({
    currentTurnUsage: {
      inputTokens: data.input_tokens ?? 0,
      outputTokens: data.output_tokens ?? 0,
      estimatedCostUsd: data.estimated_cost_usd ?? 0,
      provider: data.provider ?? null,
      model: data.model ?? null,
    }
  }),

  // Folds the now-final currentTurnUsage into the lifetime chatUsage total, then
  // resets currentTurnUsage for the next turn. Call this once, when a turn fully completes.
  commitTurnUsage: () => set((state) => ({
    chatUsage: {
      inputTokens: state.chatUsage.inputTokens + state.currentTurnUsage.inputTokens,
      outputTokens: state.chatUsage.outputTokens + state.currentTurnUsage.outputTokens,
      estimatedCostUsd: state.chatUsage.estimatedCostUsd + state.currentTurnUsage.estimatedCostUsd,
    },
    currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null },
  })),

  // Note: no existing reset()/clearChat()-style action was found in this store to hook into
  // (chat switches go through setChatId + fetchChat + fetchMessages, none of which "reset" state).
  // This action is provided for future wiring but is not currently called anywhere.
  resetUsage: () => set({
    chatUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0 },
    currentTurnUsage: { inputTokens: 0, outputTokens: 0, estimatedCostUsd: 0, provider: null, model: null }
  })
}));
