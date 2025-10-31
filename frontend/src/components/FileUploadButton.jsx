import React, { useRef } from 'react';
import useNetworkStore from '../services/networkStore';

/**
 * A prominent file upload button component for network files.
 * This component provides a button that opens a file dialog when clicked,
 * and handles the file upload process.
 *
 * @param {object} props - The component props.
 * @param {string} [props.className=''] - Additional CSS classes for the button.
 * @param {string} [props.buttonText='Upload Network File'] - The text to display on the button.
 * @param {Function} [props.onFileUpload=null] - A custom file upload handler.
 * @param {boolean} [props.iconOnly=false] - Whether to display only the icon on small screens.
 * @returns {JSX.Element} The rendered file upload button.
 */
const FileUploadButton = ({ 
  className = '', 
  buttonText = 'Upload Network File',
  onFileUpload = null, // Add onFileUpload prop with default value of null
  iconOnly = false // Add iconOnly prop to show only icon on small screens
}) => {
  const { uploadNetworkFile } = useNetworkStore();
  const fileInputRef = useRef(null);

  /**
   * Handles the file selection event.
   *
   * @param {React.ChangeEvent<HTMLInputElement>} e - The file input change event.
   */
  const handleFileChange = async (e) => {
    if (e.target.files && e.target.files[0]) {
      try {
        const file = e.target.files[0];
        console.log("File selected:", file.name);
        
        // If onFileUpload prop is provided, use it
        if (onFileUpload) {
          console.log("Using provided onFileUpload handler");
          await onFileUpload(file);
        } 
        // Otherwise use the default network store upload
        else {
          console.log("Using default uploadNetworkFile handler");
          // Upload the file using the network store
          const result = await uploadNetworkFile(file);
          
          if (result) {
            console.log("File uploaded successfully");
          } else {
            console.error("Failed to upload file");
          }
        }
      } catch (error) {
        console.error("Error uploading file:", error);
      } finally {
        // Reset the file input
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    }
  };

  /**
   * Handles the button click event, triggering the file input.
   */
  const handleButtonClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div className={`file-upload-button ${className}`}>
      {/* Hidden file input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept=".graphml,.gexf,.gml,.json,.net,.edgelist,.adjlist"
        className="hidden"
      />
      
      {/* Visible button - Using the className prop for styling */}
      <button
        onClick={handleButtonClick}
        className={className || "px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 flex items-center"}
        aria-label="Upload network file"
        title="Upload network file"
      >
        <svg 
          className={`w-5 h-5 ${iconOnly ? '' : 'mr-2'}`}
          fill="none" 
          stroke="currentColor" 
          viewBox="0 0 24 24" 
          xmlns="http://www.w3.org/2000/svg"
        >
          <path 
            strokeLinecap="round" 
            strokeLinejoin="round" 
            strokeWidth={2} 
            d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
          />
        </svg>
        {iconOnly ? null : buttonText}
      </button>
    </div>
  );
};

export default FileUploadButton;
