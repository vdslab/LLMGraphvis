
import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import ChatList from '../components/ChatList';

const HomePage = () => {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <div className="container fade-in" style={{ padding: '2rem 1rem', display: 'flex', flexDirection: 'column', alignItems: 'center', minHeight: '100%' }}>
      
      {/* Hero Section */}
      <div style={{ textAlign: 'center', marginBottom: '4rem', marginTop: '4rem' }}>
        <h1 style={{ 
          fontSize: '3.5rem', 
          marginBottom: '1.5rem',
          background: 'linear-gradient(135deg, var(--primary-color), #4f46e5)',
          WebkitBackgroundClip: 'text',
          WebkitTextFillColor: 'transparent',
          backgroundClip: 'text',
          lineHeight: 1.1
        }}>
          Visualize Your Network Helper
        </h1>
        <p style={{ fontSize: '1.25rem', color: 'var(--text-secondary)', maxWidth: '600px', margin: '0 auto', lineHeight: 1.8 }}>
          Uncover hidden insights in your graph data with AI-powered interactive visualization and analysis.
        </p>
      </div>
      
      {/* Main Action Area */}
      <div style={{ width: '100%', maxWidth: '900px', flex: 1 }}>
        {isAuthenticated ? (
          <div className="card fade-in" style={{ animationDelay: '0.1s', border: '1px solid var(--border-color)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
              <div>
                <h2 style={{ fontSize: '1.5rem', marginBottom: '0.25rem' }}>Your Workspaces</h2>
                <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '0.9rem' }}>Welcome back, {user?.username}</p>
              </div>
              <Link to="/chat/new" className="btn btn-primary" style={{ padding: '0.75rem 1.5rem', fontSize: '1rem' }}>
                <span style={{ fontSize: '1.2rem' }}>+</span> New Analysis
              </Link>
            </div>

            <div style={{ backgroundColor: 'var(--background-color)', borderRadius: 'var(--radius-lg)', padding: '1rem' }}>
               <ChatList />
            </div>
          </div>
        ) : (
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginTop: '2rem' }}>
            <Link to="/register" className="btn btn-primary" style={{ padding: '1rem 2.5rem', fontSize: '1.1rem' }}>
              Get Started for Free
            </Link>
            <Link to="/login" className="btn btn-outline" style={{ padding: '1rem 2.5rem', fontSize: '1.1rem', backgroundColor: 'white' }}>
              Login to Account
            </Link>
          </div>
        )}
      </div>

      <footer style={{ marginTop: 'auto', paddingTop: '4rem', color: 'var(--text-muted)', fontSize: '0.875rem' }}>
        © {new Date().getFullYear()} Takuma SHIRASHOJI. All rights reserved.
      </footer>
    </div>
  );
};

export default HomePage;
