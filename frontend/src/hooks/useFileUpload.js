import { useState } from 'react';
import useNetworkStore from '../services/networkStore';
import useChatStore from '../services/chatStore';

/**
 * ファイルアップロード処理のためのカスタムフック
 * 
 * ネットワークファイルのアップロード処理とエラーハンドリングを提供
 * 
 * @returns {Object} ファイルアップロード関連の状態と関数
 *   - handleFileUpload: ファイルアップロード関数
 *   - error: エラーメッセージ
 *   - isUploading: アップロード中フラグ
 *   - clearError: エラーをクリアする関数
 */
export const useFileUpload = () => {
  const { uploadNetworkFile } = useNetworkStore();
  const { addMessage } = useChatStore();
  
  const [error, setError] = useState(null);
  const [isUploading, setIsUploading] = useState(false);
  
  /**
   * ファイルアップロードハンドラー
   * 
   * @param {File} file - アップロードするファイル
   * @returns {Promise<Object>} アップロード結果
   */
  const handleFileUpload = async (file) => {
    // エラー状態をリセット
    setError(null);
    
    // ファイル検証
    if (!file) {
      setError("ファイルが選択されていません");
      return { success: false, error: "ファイルが選択されていません" };
    }
    
    // ファイル拡張子チェック
    const fileExtension = file.name.split('.').pop().toLowerCase();
    const supportedFormats = ['graphml', 'gexf', 'gml', 'json', 'net', 'edgelist', 'adjlist'];
    
    if (!supportedFormats.includes(fileExtension)) {
      const errorMsg = `サポートされていないファイル形式: .${fileExtension}。サポート形式: ${supportedFormats.join(', ')}`;
      setError(errorMsg);
      return { success: false, error: errorMsg };
    }
    
    // 空ファイルチェック
    if (file.size === 0) {
      setError("ファイルが空です");
      return { success: false, error: "ファイルが空です" };
    }
    
    // アップロード処理
    try {
      setIsUploading(true);
      
      const result = await uploadNetworkFile(file);
      
      if (result && result.success === true) {
        // チャットにシステムメッセージを追加
        addMessage({
          role: "assistant",
          content: `ネットワークファイル "${file.name}" がアップロードされ、処理されました。`,
          timestamp: new Date().toISOString(),
        });
        return { success: true };
      } else {
        const errorMsg = result?.error || "ファイルの処理に失敗しました";
        setError(errorMsg);
        return { success: false, error: errorMsg };
      }
    } catch (error) {
      // エラーメッセージの抽出
      const errorMsg = error.response?.data?.detail || 
                       error.message || 
                       "ファイルのアップロード中にエラーが発生しました";
      
      setError(errorMsg);
      
      // チャットにエラーメッセージを追加
      addMessage({
        role: "assistant",
        content: `ファイルのアップロード中にエラーが発生しました: ${errorMsg}`,
        timestamp: new Date().toISOString(),
        error: true,
      });
      
      return { success: false, error: errorMsg };
    } finally {
      setIsUploading(false);
    }
  };
  
  /**
   * エラー状態をクリア
   */
  const clearError = () => {
    setError(null);
  };
  
  return {
    handleFileUpload,
    error,
    isUploading,
    clearError
  };
};

export default useFileUpload;