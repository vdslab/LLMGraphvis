import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import useAuthStore from '../services/authStore';

/**
 * A component that protects a route from unauthenticated access.
 *
 * @param {object} props - The component props.
 * @param {JSX.Element} props.children - The child components to render if the user is authenticated.
 * @returns {JSX.Element} The rendered component.
 */
const ProtectedRoute = ({ children }) => {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();
  const location = useLocation();
  const [authChecked, setAuthChecked] = useState(false);

  useEffect(() => {
    const verifyAuth = async () => {
      if (!isAuthenticated && !isLoading) {
        console.log("ProtectedRoute: Not authenticated, checking auth status");
        try {
          const result = await checkAuth();
          console.log("ProtectedRoute: Auth check result:", result);
        } catch (error) {
          console.error("ProtectedRoute: Auth check failed:", error);
        } finally {
          setAuthChecked(true);
        }
      } else {
        setAuthChecked(true);
      }
    };

    verifyAuth();
  }, [isAuthenticated, isLoading, checkAuth]);

  if (isLoading || !authChecked) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    console.log("ProtectedRoute: Not authenticated, redirecting to login");
    // Redirect to login page with return url
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  console.log("ProtectedRoute: Authenticated, rendering children");
  return children;
};

export default ProtectedRoute;
