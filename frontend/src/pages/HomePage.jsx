import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import ChatList from '../components/ChatList';
import { Plus, Sparkles, ArrowRight } from 'lucide-react';

const HomePage = () => {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <div
      className="container fade-in"
      style={{
        padding: '2.5rem 1.5rem',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        minHeight: '100%',
        maxWidth: '1080px',
      }}
    >
      {/* M3 Expressive Hero Section */}
      <div
        style={{
          textAlign: 'center',
          marginBottom: '3.5rem',
          marginTop: '2.5rem',
        }}
      >
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.375rem 0.875rem',
            borderRadius: 'var(--md-sys-shape-full)',
            backgroundColor: 'var(--md-sys-color-primary-container)',
            color: 'var(--md-sys-color-on-primary-container)',
            fontSize: '0.8125rem',
            fontWeight: 600,
            marginBottom: '1.25rem',
          }}
        >
          <Sparkles size={14} aria-hidden />
          <span>AI-Driven Network Analytics</span>
        </div>

        <h1
          style={{
            fontSize: '3.25rem',
            fontWeight: 800,
            marginBottom: '1.25rem',
            color: 'var(--md-sys-color-on-surface)',
            letterSpacing: '-0.03em',
            lineHeight: 1.15,
          }}
        >
          Visualize Your Network Helper
        </h1>
        <p
          style={{
            fontSize: '1.1875rem',
            color: 'var(--md-sys-color-on-surface-variant)',
            maxWidth: '640px',
            margin: '0 auto',
            lineHeight: 1.65,
          }}
        >
          Uncover hidden insights in your graph data with conversational AI,
          automated NetworkX analysis, and interactive D3 visualization.
        </p>
      </div>

      {/* Main Action Area */}
      <div style={{ width: '100%', maxWidth: '860px', flex: 1 }}>
        {isAuthenticated ? (
          <div
            className="card fade-in"
            style={{
              borderRadius: 'var(--md-sys-shape-xxl)',
              boxShadow: 'var(--md-sys-elevation-2)',
              backgroundColor: 'var(--md-sys-color-surface-container-lowest)',
              border: '1px solid var(--md-sys-color-outline-subtle)',
              padding: '2rem 2.25rem',
            }}
          >
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: '1.75rem',
                borderBottom: '1px solid var(--md-sys-color-outline-subtle)',
                paddingBottom: '1.25rem',
              }}
            >
              <div>
                <h2
                  style={{
                    fontSize: '1.5rem',
                    fontWeight: 700,
                    marginBottom: '0.25rem',
                    color: 'var(--md-sys-color-on-surface)',
                  }}
                >
                  Your Workspaces
                </h2>
                <p
                  style={{
                    margin: 0,
                    color: 'var(--md-sys-color-on-surface-variant)',
                    fontSize: '0.875rem',
                  }}
                >
                  Welcome back, <strong style={{ color: 'var(--md-sys-color-primary)' }}>{user?.username}</strong>
                </p>
              </div>

              {/* Extended FAB style button */}
              <Link
                to="/chat/new"
                className="btn btn-primary"
                style={{
                  padding: '0.6875rem 1.5rem',
                  fontSize: '0.9375rem',
                  boxShadow: 'var(--md-sys-elevation-2)',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '0.5rem',
                }}
              >
                <Plus size={18} strokeWidth={2.5} />
                <span>New Analysis</span>
              </Link>
            </div>

            <div
              style={{
                backgroundColor: 'var(--md-sys-color-surface-container-low)',
                borderRadius: 'var(--md-sys-shape-xl)',
                border: '1px solid var(--md-sys-color-outline-subtle)',
                overflow: 'hidden',
              }}
            >
              <ChatList />
            </div>
          </div>
        ) : (
          <div
            style={{
              display: 'flex',
              gap: '1rem',
              justifyContent: 'center',
              marginTop: '1.5rem',
              flexWrap: 'wrap',
            }}
          >
            <Link
              to="/register"
              className="btn btn-primary"
              style={{
                padding: '0.875rem 2.25rem',
                fontSize: '1rem',
                boxShadow: 'var(--md-sys-elevation-2)',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.5rem',
              }}
            >
              <span>Get Started for Free</span>
              <ArrowRight size={18} />
            </Link>
            <Link
              to="/login"
              className="btn btn-outline"
              style={{
                padding: '0.875rem 2.25rem',
                fontSize: '1rem',
                backgroundColor: 'var(--md-sys-color-surface-container-lowest)',
              }}
            >
              Login to Account
            </Link>
          </div>
        )}
      </div>

      <footer
        style={{
          marginTop: 'auto',
          paddingTop: '3.5rem',
          color: 'var(--md-sys-color-outline)',
          fontSize: '0.8125rem',
        }}
      >
        GraphVisAgent — Master&apos;s Thesis Network Analytics
      </footer>
    </div>
  );
};

export default HomePage;
