// React 18 + Redux Toolkit State & Client
import { createSlice, createAsyncThunk, PayloadAction } from '@reduxjs/toolkit';
import axios from 'axios';

export interface AutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkState {
  items: any[];
  selectedItem: any | null;
  loading: boolean;
  error: string | null;
  tenantId: string | null;
}

const initialState: AutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkState = {
  items: [],
  selectedItem: null,
  loading: false,
  error: null,
  tenantId: null
};

// Async Thunk to consume Backend API
export const fetchAutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkList = createAsyncThunk(
  'autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFramework/fetchList',
  async (tenantId: string | undefined, { rejectWithValue }) => {
    try {
      const response = await axios.get(`/api/v1/autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFramework`, {
        headers: tenantId ? { 'X-Tenant-ID': tenantId } : {}
      });
      return response.data;
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.message || 'Error fetching data');
    }
  }
);

export const executeAutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkCommand = createAsyncThunk(
  'autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFramework/executeCommand',
  async (payload: { commandName: string; data: any; idempotencyKey?: string }, { rejectWithValue }) => {
    try {
      const headers: Record<string, string> = {};
      if (payload.idempotencyKey) {
        headers['X-Idempotency-Key'] = payload.idempotencyKey;
      }
      const response = await axios.post(`/api/v1/autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFramework/commands`, payload.data, { headers });
      return response.data;
    } catch (err: any) {
      return rejectWithValue(err.response?.data?.message || 'Error executing command');
    }
  }
);

export const autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkSlice = createSlice({
  name: 'autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFramework',
  initialState,
  reducers: {
    setTenantId: (state, action: PayloadAction<string>) => {
      state.tenantId = action.payload;
    },
    onRealtimeEventReceived: (state, action: PayloadAction<{ eventType: string; payload: any }>) => {
      state.items.unshift(action.payload);
    },
    resetState: (state) => {
      Object.assign(state, initialState);
    }
  },
  extraReducers: (builder) => {
    builder
      .addCase(fetchAutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkList.pending, (state) => {
        state.loading = true;
        state.error = null;
      })
      .addCase(fetchAutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkList.fulfilled, (state, action) => {
        state.loading = false;
        state.items = action.payload;
      })
      .addCase(fetchAutenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkList.rejected, (state, action) => {
        state.loading = false;
        state.error = action.payload as string;
      });
  }
});

export const { setTenantId, onRealtimeEventReceived, resetState } = autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkSlice.actions;
export default autenticaciónJWTYSerializaciónTransaccionalEnDjangoRESTFrameworkSlice.reducer;
