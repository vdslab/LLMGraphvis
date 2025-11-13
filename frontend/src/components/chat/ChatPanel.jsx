import { useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import MessageInput from "./MessageInput";
import MessageList from "./MessageList";
import useChatStore from "../../services/chatStore";

/**
 * チャットパネルコンポーネント
 * 
 * メッセージ表示、入力フォーム、送信機能を統合
 */
const ChatPanel = () => {
  const { 
    messages, 
    sendMessage, 
    isProcessing,
    addMessage
  } = useChatStore();
  
  const messagesEndRef = useRef();

  // メッセージリスト末尾へスクロール
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // メッセージ送信ハンドラー
  const handleSendMessage = async (messageText) => {
    if (!messageText.trim() || isProcessing) return;
    await sendMessage(messageText);
  };

  return (
    <div className="flex-1 flex flex-col bg-white border-r border-gray-200">
      {/* メッセージ表示エリア */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <MessageList messages={messages} />
        
        {/* タイピングインジケーター */}
        {isProcessing && (
          <div className="flex justify-start mb-4">
            <div className="flex-shrink-0 h-8 w-8 rounded-full bg-blue-500 flex items-center justify-center mr-2">
              <svg
                className="h-5 w-5 text-white"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714a2.25 2.25 0 001.5 2.25m0 0v2.8a2.25 2.25 0 01-1.5 2.25m0 0a2.25 2.25 0 01-1.5 0M5 14.5v2.8a2.25 2.25 0 002.25 2.25h9A2.25 2.25 0 0018.5 17.3v-2.8a2.25 2.25 0 00-2.25-2.25h-.75m-6 0h6"
                />
              </svg>
            </div>
            <div className="bg-gray-100 p-3 rounded-lg">
              <div className="flex space-x-1">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-100"></div>
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce delay-200"></div>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 入力フォームエリア */}
      <div className="p-4 border-t border-gray-200">
        <MessageInput onSendMessage={handleSendMessage} isProcessing={isProcessing} />
      </div>
    </div>
  );
};

export default ChatPanel;