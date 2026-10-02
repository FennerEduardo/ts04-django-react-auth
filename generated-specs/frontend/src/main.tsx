import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { Provider } from 'react-redux';
import { AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel } from './components/AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel';
import { createAppStore } from './store/store';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Provider store={createAppStore()}>
      <AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel />
    </Provider>
  </StrictMode>
);
