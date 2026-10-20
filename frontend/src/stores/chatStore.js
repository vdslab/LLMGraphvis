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
  getChatUsage,
  getSampleNetworks,
  loadSampleNetwork as loadSampleNetworkAPI,
  getApiErrorMessage,
} from '../services/api';

export const EMPTY_USAGE_TOTALS = {
  input_tokens: 0,
  output_tokens: 0,
  cached_input_tokens: 0,
  cache_write_tokens: 0,
  reasoning_tokens: 0,
  estimated_cost_usd: 0,
  unpriced_count: 0,
  task_count: 0,
  request_count: 0,
};
const EMPTY_CHAT_USAGE = { chatId: null, totals: EMPTY_USAGE_TOTALS, entries: [] };
const EMPTY_TURN_USAGE = {
  input_tokens: 0,
  output_tokens: 0,
  cached_input_tokens: 0,
  cache_write_tokens: 0,
  reasoning_tokens: 0,
  estimated_cost_usd: 0,
  provider: null,
  model: null,
};

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

  // Token/cost usage (ADR 0025). chatUsage is what the backend stored for this
  // chat — the only source of truth; currentTurnUsage is the live running total
  // of the turn in progress, shown on top of it until the turn is stored.
  chatUsage: EMPTY_CHAT_USAGE,
  currentTurnUsage: EMPTY_TURN_USAGE,

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

    set({ messages: res.data });
    // Usage is loaded on its own so a failure there never hides the messages.
    get().fetchChatUsage(id).catch((error) => {
      console.warn('Failed to load chat usage:', error);
    });
    return res.data;
  },

  // Load what the backend stored for this chat: every turn and chat title,
  // including turns that ended in an error. Replaces the live turn total.
  fetchChatUsage: async (chatId = null) => {
    const id = chatId || get().chatId;
    if (!id) return null;
    const res = await getChatUsage(id);
    if (get().chatId !== id) return null;
    set({
      chatUsage: { chatId: id, totals: res.data.totals, entries: res.data.entries },
      currentTurnUsage: EMPTY_TURN_USAGE,
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
      const response = message.inputResponse
        ? await processMessageAPI(get().chatId, message.content, message.inputResponse)
        : await processMessageAPI(get().chatId, message.content);
      if (response?.data?.status === 'already_accepted') {
        await get().fetchMessages();
        get().endTurn();
        return true;
      }
      // 202 Accepted; SSE carries the rest of the turn.
      get().setMessageStatus(localId, 'sent');
      return true;
    } catch (error) {
      console.error("Failed to send message:", error);
      get().setMessageStatus(localId, 'failed');
      set({ isLoading: false, thinkingMessage: null, progressSteps: [] });
      return false;
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
  sendMessage: async (content, inputResponse = null) => {
    const localId = `local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const busy = get().isLoading;

    set((state) => ({
      messages: [...state.messages, {
        id: localId,
        localId,
        role: 'user',
        content,
        inputResponse,
        created_at: new Date().toISOString(),
        status: busy ? 'queued' : 'sending',
      }],
    }));

    if (busy) return;
    return await get().dispatchMessage(localId);
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
      } else if (realId && content && !messages.some(m => m.id === realId)) {
        // Nothing streamed (e.g. the model failed before its first chunk):
        // the stored reply arrives only here, so add it.
        messages.push({
          id: realId,
          role: 'assistant',
          content,
          created_at: new Date().toISOString(),
          tool_executions: tool_executions || [],
        });
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

  // usage_update SSE events carry a RUNNING TOTAL for the in-progress turn (not
  // deltas), so this replaces currentTurnUsage wholesale each time.
  setCurrentTurnUsage: (data) => set({
    currentTurnUsage: { ...EMPTY_TURN_USAGE, ...data },
  }),

  // The turn (or a chat title) has been stored: reload the stored totals, which
  // now include it, instead of adding the live numbers client-side.
  refreshUsage: () => {
    get().fetchChatUsage().catch((error) => {
      console.warn('Failed to refresh chat usage:', error);
    });
  },

  resetUsage: () => set({
    chatUsage: EMPTY_CHAT_USAGE,
    currentTurnUsage: EMPTY_TURN_USAGE,
  })
}));
