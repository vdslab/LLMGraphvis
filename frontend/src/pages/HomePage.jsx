import React from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

const HomePage = () => {
  const { isAuthenticated, user } = useAuthStore();

  return (
    <div className="card" style={{ maxWidth: '600px', margin: '4rem auto', textAlign: 'center' }}>
      <h1 style={{ fontSize: '2.5rem', marginBottom: '1rem', color: 'var(--primary-color)' }}>
        GraphVisAgent
      </h1>
      <p style={{ fontSize: '1.25rem', color: 'var(--text-secondary)', marginBottom: '2rem' }}>
        Interactive Network Visualization with LLM
      </p>
      
      <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center' }}>
        {isAuthenticated ? (
          <>
            <p>Welcome back, {user?.username}!</p>
            {/* In a real app, list chats or button to create new */}
            <Link to="/chat/new" className="btn btn-primary" style={{ textDecoration: 'none' }}>
              Go to Dashboard
            </Link>
            <button 
              onClick={() => useAuthStore.getState().logout()} 
              className="btn" 
              style={{ border: '1px solid var(--border-color)', cursor: 'pointer' }}
            >
              Logout
            </button>
          </>
        ) : (
          <>
            <Link to="/login" className="btn btn-primary" style={{ textDecoration: 'none' }}>
              Login
            </Link>
            <Link to="/register" className="btn" style={{ textDecoration: 'none', border: '1px solid var(--border-color)' }}>
              Register
            </Link>
          </>
        )}
      </div>
    </div>
  );
};

export default HomePage;
