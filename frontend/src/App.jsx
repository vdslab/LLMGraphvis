import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import ProtectedRoute from './components/ProtectedRoute';
import HomePage from './pages/HomePage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
// Removed NetworkVisualizationPage and LayoutRecommendationPage as part of migration to MCP-based design
import NetworkChatPage from './pages/NetworkChatPage';
import useAuthStore from './services/authStore';
import websocketService from './services/websocketService';

/**
 * The main application component.
 *
 * This component sets up the router and handles authentication state.
 *
 * @returns {JSX.Element} The rendered application.
 */
function App() {
  const { checkAuth, isLoading, isAuthenticated } = useAuthStore();
  const [authInitialized, setAuthInitialized] = useState(false);
  
  // Check authentication status on app load
  useEffect(() => {
    const initAuth = async () => {
      try {
        console.log("App: Initializing authentication check");
        await checkAuth();
        console.log("App: Authentication check completed");
      } catch (err) {
        console.error("App: Authentication check failed:", err);
      } finally {
        setAuthInitialized(true);
      }
    };
    
    initAuth();
  }, [checkAuth]);
  
  // Connect to WebSocket when authenticated
  useEffect(() => {
    if (isAuthenticated && authInitialized) {
      console.log("App: User is authenticated, connecting to WebSocket");
      websocketService.connect();
      
      // Cleanup function to disconnect WebSocket when component unmounts
      return () => {
        console.log("App: Disconnecting WebSocket");
        websocketService.disconnect();
      };
    }
  }, [isAuthenticated, authInitialized]);
  
  // Show loading spinner while checking authentication
  if (isLoading && !authInitialized) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }
  
  return (
    <Router>
      <div className="h-screen bg-gray-100 flex flex-col">
        <Navbar />
        <main className="flex-grow">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            {/* Routes for /network and /recommend have been removed as part of migration to MCP-based design */}
            <Route 
              path="/chat" 
              element={
                <ProtectedRoute>
                  <NetworkChatPage />
                </ProtectedRoute>
              } 
            />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
