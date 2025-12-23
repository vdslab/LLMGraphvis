import React from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import ChatList from '../components/ChatList';

const HomePage = () => {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <div className="card" style={{ maxWidth: '800px', margin: '4rem auto', textAlign: 'center', minHeight: '60vh', display: 'flex', flexDirection: 'column' }}>
      <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', color: 'var(--primary-color)' }}>
        GraphVisAgent
      </h1>
      <p style={{ fontSize: '1.25rem', color: 'var(--text-secondary)', marginBottom: '2rem' }}>
        Interactive Network Visualization with LLM
      </p>
      
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {isAuthenticated ? (
          <>
            <p>Welcome back, {user?.username}!</p>
            <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', marginBottom: '2rem' }}>
                <Link to="/chat/new" className="btn btn-primary" style={{ textDecoration: 'none' }}>
                + Start New Analysis
                </Link>
                <button 
                onClick={() => useAuthStore.getState().logout()} 
                className="btn" 
                style={{ border: '1px solid var(--border-color)', cursor: 'pointer' }}
                >
                Logout
                </button>
            </div>

            <div style={{ textAlign: 'left', border: '1px solid #eee', borderRadius: '8px', overflow: 'hidden' }}>
                <ChatList />
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
            <Link to="/login" className="btn btn-primary" style={{ textDecoration: 'none' }}>
              Login
            </Link>
            <Link to="/register" className="btn" style={{ textDecoration: 'none', border: '1px solid var(--border-color)' }}>
              Register
            </Link>
          </div>
        )}
      </div>
    </div>
  );
};

export default HomePage;
