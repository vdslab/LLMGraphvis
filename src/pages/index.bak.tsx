import React from 'react';
import Layout from '@theme/Layout';

function Home() {
  return (
    <Layout title="Hello">
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          height: '50vh',
          fontSize: '20px',
        }}>
        <p>Hello World</p>
      </div>
    </Layout>
  );
}

export default Home;