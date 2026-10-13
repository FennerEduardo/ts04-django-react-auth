import { configureStore } from '@reduxjs/toolkit';
import type { AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient } from '../api/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-client';
import { defaultClient as defaultAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient, autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkReducer } from './autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkSlice';

/** One API client per feature of the service (each slice uses its own). */
export interface AppClients {
  autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework: AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient;
}

export function createAppStore(clients: Partial<AppClients> = {}) {
  const extraArgument: { clients: AppClients } = {
    clients: {
      autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework: clients.autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework ?? defaultAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient(),
    }
  };
  return configureStore({
    reducer: { autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework: autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkReducer },
    middleware: getDefault => getDefault({ thunk: { extraArgument } })
  });
}

export type AppStore = ReturnType<typeof createAppStore>;
export type RootState = ReturnType<AppStore['getState']>;
export type AppDispatch = AppStore['dispatch'];
