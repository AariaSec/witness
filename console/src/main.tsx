import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
// Fonts are bundled locally — the console makes no third-party requests.
import '@fontsource-variable/inter';
import '@fontsource-variable/jetbrains-mono';
import './styles/index.css';
import App from './App';

const el = document.getElementById('root');
if (!el) throw new Error('#root missing from index.html');
createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
