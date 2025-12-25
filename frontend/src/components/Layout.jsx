
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

const Layout = ({ children, fullScreen = false }) => {
  const { isAuthenticated, user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <div className="layout-root" style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100vh', 
      backgroundColor: 'var(--background-color)' 
    }}>
      {/* Navbar */}
      <header style={{
        height: '64px',
        backgroundColor: 'rgba(255, 255, 255, 0.8)',
        backdropFilter: 'blur(12px)',
        borderBottom: '1px solid var(--border-color)',
        display: 'flex',
        alignItems: 'center',
        padding: '0 2rem',
        justifyContent: 'space-between',
        zIndex: 50,
        position: 'sticky',
        top: 0
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          <Link to="/" style={{ 
            fontSize: '1.25rem', 
            fontWeight: 800, 
            background: 'linear-gradient(135deg, var(--primary-color), #4f46e5)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            textDecoration: 'none'
          }}>
            GraphVisAgent
          </Link>
          
          {isAuthenticated && (
            <nav style={{ display: 'flex', gap: '1rem' }}>
              <Link to="/" style={{ 
                color: location.pathname === '/' ? 'var(--primary-color)' : 'var(--text-secondary)',
                fontWeight: 500,
                fontSize: '0.9rem'
              }}>Home</Link>
              {/* Add more links here if needed */}
            </nav>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {isAuthenticated ? (
            <>
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '0.5rem',
                padding: '0.25rem 0.75rem',
                backgroundColor: 'var(--background-color)',
                borderRadius: '999px',
                border: '1px solid var(--border-color)',
                fontSize: '0.875rem',
                color: 'var(--text-secondary)'
              }}>
                <div style={{ 
                  width: '24px', 
                  height: '24px', 
                  borderRadius: '50%', 
                  backgroundColor: 'var(--primary-color)',
                  color: 'white',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.75rem',
                  fontWeight: 700
                }}>
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <span>{user?.username}</span>
              </div>
              
              <button 
                onClick={handleLogout}
                className="btn btn-ghost"
                style={{ padding: '0.5rem', fontSize: '0.875rem' }}
              >
                Logout
              </button>
            </>
          ) : (
            <div style={{ display: 'flex', gap: '0.75rem' }}>
              <Link to="/login" className="btn btn-ghost" style={{ fontSize: '0.9rem' }}>
                Login
              </Link>
              <Link to="/register" className="btn btn-primary" style={{ padding: '0.5rem 1rem', fontSize: '0.9rem' }}>
                Get Started
              </Link>
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main style={{ 
        flex: 1, 
        overflow: fullScreen ? 'hidden' : 'auto',
        position: 'relative',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {children}
      </main>
    </div>
  );
};

export default Layout;
