import { useState } from 'react';

/**
 * メッセージ入力コンポーネント
 * 
 * テキストの入力と送信を処理
 * 
 * @param {Function} onSendMessage - メッセージ送信時のコールバック関数
 * @param {boolean} isProcessing - 処理中フラグ（送信ボタン無効化用）
 * @returns {JSX.Element} メッセージ入力フォーム
 */
const MessageInput = ({ onSendMessage, isProcessing }) => {
  const [inputMessage, setInputMessage] = useState('');

  /**
   * フォーム送信ハンドラ
   * 
   * @param {React.FormEvent} e - イベントオブジェクト
   */
  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!inputMessage.trim() || isProcessing) {
      return;
    }
    
    onSendMessage(inputMessage);
    setInputMessage('');
  };

  return (
    <form onSubmit={handleSubmit} className="flex">
      <input
        type="text"
        value={inputMessage}
        onChange={(e) => setInputMessage(e.target.value)}
        placeholder="メッセージを入力..."
        className="flex-1 px-4 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        disabled={isProcessing}
      />
      <button
        type="submit"
        className="px-4 py-2 bg-blue-600 text-white rounded-r-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50"
        disabled={!inputMessage.trim() || isProcessing}
      >
        <svg
          className="h-5 w-5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
          />
        </svg>
      </button>
    </form>
  );
};

export default MessageInput;