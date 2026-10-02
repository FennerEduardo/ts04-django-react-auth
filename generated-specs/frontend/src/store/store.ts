import { configureStore } from '@reduxjs/toolkit';
import { AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient } from '../api/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-client';
import { defaultClient, autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkReducer } from './autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkSlice';

export function createAppStore(client: AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient = defaultClient()) {
  return configureStore({
    reducer: { autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework: autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkReducer },
    middleware: getDefault => getDefault({ thunk: { extraArgument: { client } } })
  });
}

export type AppStore = ReturnType<typeof createAppStore>;
export type RootState = ReturnType<AppStore['getState']>;
export type AppDispatch = AppStore['dispatch'];
