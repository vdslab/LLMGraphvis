import React from 'react';
import ReactMarkdown from 'react-markdown';

/**
 * メッセージリストコンポーネント
 * 
 * チャットメッセージの一覧を表示
 * 
 * @param {Object[]} messages - 表示するメッセージの配列
 * @returns {JSX.Element} メッセージリスト
 */
const MessageList = ({ messages }) => {
  if (!messages || messages.length === 0) {
    return (
      <div className="text-center text-gray-400 py-8">
        メッセージはまだありません。会話を始めましょう。
      </div>
    );
  }

  return (
    <>
      {messages.map((message, index) => (
        <div
          key={index}
          className={`flex ${message.role === "user" ? "justify-end" : "justify-start"} mb-4`}
        >
          {/* アシスタントメッセージのアバター */}
          {message.role === "assistant" && (
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
          )}

          <div
            className={`max-w-3/4 p-3 rounded-lg ${
              message.role === "user"
                ? "bg-blue-100 text-blue-900"
                : "bg-gray-100 text-gray-900"
            }`}
          >
            <div className="prose prose-sm max-w-none">
              <ReactMarkdown>{message.content}</ReactMarkdown>
            </div>

            {/* タイムスタンプ表示 */}
            {message.timestamp && (
              <div className="text-xs text-gray-500 mt-1">
                {new Date(message.timestamp).toLocaleTimeString()}
              </div>
            )}
          </div>
        </div>
      ))}
    </>
  );
};

export default MessageList;