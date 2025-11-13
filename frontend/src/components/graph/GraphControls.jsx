import FileUploadButton from "../FileUploadButton";

/**
 * グラフ制御コンポーネント
 * 
 * グラフ操作用UIを提供
 * - ファイルアップロードボタン
 * - エラー表示
 * 
 * @param {Function} onFileUpload - ファイルアップロードハンドラー
 * @param {string} error - 表示するエラーメッセージ
 * @param {boolean} isLoading - ローディング状態
 * @returns {JSX.Element} グラフ制御UI
 */
const GraphControls = ({ onFileUpload, error, isLoading }) => {
  return (
    <div className="p-4 border-b border-gray-200 flex justify-end items-center">
      <div className="text-sm text-gray-600 mr-4">ネットワークファイルをここにドラッグ&ドロップ</div>
      <FileUploadButton
        className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded shadow-lg flex items-center justify-center"
        buttonText="ネットワークファイルをアップロード"
        onFileUpload={onFileUpload}
        disabled={isLoading}
      />
      
      {/* エラー表示 */}
      {error && (
        <div className="ml-4 text-red-500 text-sm max-w-md overflow-hidden text-ellipsis">
          {error}
        </div>
      )}
    </div>
  );
};

export default GraphControls;