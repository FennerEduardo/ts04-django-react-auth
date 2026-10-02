import { createAsyncThunk, createSlice } from '@reduxjs/toolkit';
import { CommandName, CommandResult, createAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient, AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient } from '../api/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-client';

export interface AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkState {
  events: CommandResult[];
  status: 'idle' | 'loading' | 'failed';
  error: string | null;
}

const initialState: AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkState = { events: [], status: 'idle', error: null };

export interface ExecuteArgs {
  id: string;
  command: CommandName;
  payload?: Record<string, unknown>;
}

export const executeCommand = createAsyncThunk<CommandResult, ExecuteArgs, { extra: { client: AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient } }>(
  'autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework/execute',
  ({ id, command, payload }, { extra }) => extra.client.execute(id, command, payload, { idempotencyKey: crypto.randomUUID() })
);

const autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkSlice = createSlice({
  name: 'autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework',
  initialState,
  reducers: {},
  extraReducers: builder => {
    builder
      .addCase(executeCommand.pending, state => {
        state.status = 'loading';
        state.error = null;
      })
      .addCase(executeCommand.fulfilled, (state, action) => {
        state.status = 'idle';
        state.events.push(action.payload);
      })
      .addCase(executeCommand.rejected, (state, action) => {
        state.status = 'failed';
        state.error = action.error.message ?? 'Request failed';
      });
  }
});

export const autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkReducer = autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkSlice.reducer;
export const defaultClient = () => createAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient({ baseUrl: import.meta.env.VITE_API_URL ?? '' });
