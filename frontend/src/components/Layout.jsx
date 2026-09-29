import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Settings } from 'lucide-react';
import { useAuthStore } from '../stores/authStore';
import { useSettingsStore } from '../stores/settingsStore';

const Layout = ({ children, fullScreen = false }) => {
  const { isAuthenticated, user, logout } = useAuthStore();
  const location = useLocation();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    useSettingsStore.getState().reset();
    navigate('/login');
  };

  return (
    <div
      className="layout-root"
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        backgroundColor: 'var(--md-sys-color-surface-container-low)',
      }}
    >
      {/* M3 Expressive Top App Bar */}
      <header
        style={{
          height: '64px',
          backgroundColor: 'rgba(255, 255, 255, 0.92)',
          backdropFilter: 'blur(16px)',
          borderBottom: '1px solid var(--md-sys-color-outline-subtle)',
          display: 'flex',
          alignItems: 'center',
          padding: '0 1.75rem',
          justifyContent: 'space-between',
          zIndex: 50,
          position: 'sticky',
          top: 0,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '2rem' }}>
          <Link
            to="/"
            style={{
              fontSize: '1.25rem',
              fontFamily: 'var(--font-family-brand)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: 'var(--md-sys-color-primary)',
              textDecoration: 'none',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}
          >
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '50%',
                backgroundColor: 'var(--md-sys-color-primary)',
                boxShadow: '0 0 10px rgba(52, 84, 209, 0.6)',
              }}
            />
            GraphVisAgent
          </Link>

          {isAuthenticated && (
            <nav style={{ display: 'flex', gap: '0.5rem' }}>
              <Link
                to="/"
                style={{
                  padding: '0.375rem 1rem',
                  borderRadius: 'var(--md-sys-shape-full)',
                  backgroundColor:
                    location.pathname === '/'
                      ? 'var(--md-sys-color-secondary-container)'
                      : 'transparent',
                  color:
                    location.pathname === '/'
                      ? 'var(--md-sys-color-on-secondary-container)'
                      : 'var(--md-sys-color-on-surface-variant)',
                  fontWeight: 600,
                  fontSize: '0.875rem',
                  textDecoration: 'none',
                  transition: 'all 0.15s ease',
                }}
              >
                Home
              </Link>
            </nav>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          {isAuthenticated ? (
            <>
              <Link
                to="/settings"
                title="Settings"
                aria-current={location.pathname === '/settings' ? 'page' : undefined}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '0.625rem',
                  padding: '0.25rem 0.875rem 0.25rem 0.375rem',
                  backgroundColor:
                    location.pathname === '/settings'
                      ? 'var(--md-sys-color-secondary-container)'
                      : 'var(--md-sys-color-surface-container)',
                  borderRadius: 'var(--md-sys-shape-full)',
                  border: '1px solid var(--md-sys-color-outline-subtle)',
                  fontSize: '0.8125rem',
                  fontWeight: 600,
                  color: 'var(--md-sys-color-on-surface)',
                  textDecoration: 'none',
                }}
              >
                <div
                  style={{
                    width: '26px',
                    height: '26px',
                    borderRadius: '50%',
                    backgroundColor: 'var(--md-sys-color-primary)',
                    color: 'var(--md-sys-color-on-primary)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '0.75rem',
                    fontWeight: 700,
                  }}
                >
                  {user?.username?.[0]?.toUpperCase() || 'U'}
                </div>
                <span>{user?.username}</span>
                <Settings size={14} aria-hidden style={{ color: 'var(--md-sys-color-on-surface-variant)' }} />
              </Link>

              <button
                onClick={handleLogout}
                className="btn btn-ghost"
                style={{
                  padding: '0.4rem 0.875rem',
                  fontSize: '0.8125rem',
                  color: 'var(--md-sys-color-on-surface-variant)',
                }}
              >
                Logout
              </button>
            </>
          ) : (
            <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
              <Link
                to="/login"
                className="btn btn-ghost"
                style={{ fontSize: '0.875rem', padding: '0.5rem 1rem' }}
              >
                Login
              </Link>
              <Link
                to="/register"
                className="btn btn-primary"
                style={{
                  padding: '0.5rem 1.25rem',
                  fontSize: '0.875rem',
                }}
              >
                Get Started
              </Link>
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main
        style={{
          flex: 1,
          overflow: fullScreen ? 'hidden' : 'auto',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        {children}
      </main>
    </div>
  );
};

export default Layout;
