import React from 'react';
import ReactDOM from 'react-dom/client';
import { App } from './App';
import { AuthProvider } from './context/AuthContext';
import { PlayerProvider } from './context/PlayerContext';
import { FlightProvider } from './context/FlightContext';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <AuthProvider>
      <PlayerProvider>
        <FlightProvider>
          <App />
        </FlightProvider>
      </PlayerProvider>
    </AuthProvider>
  </React.StrictMode>
);
