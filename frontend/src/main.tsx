import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import { AuthProvider } from './hooks/useAuth';
import { PinsProvider } from './hooks/usePins';
import './index.css';

createRoot(document.getElementById('root') as HTMLElement).render(
  <StrictMode>
    <AuthProvider>
      <PinsProvider>
        <App />
      </PinsProvider>
    </AuthProvider>
  </StrictMode>,
);
