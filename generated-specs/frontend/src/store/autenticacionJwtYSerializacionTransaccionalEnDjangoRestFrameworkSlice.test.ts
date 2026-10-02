import { describe, expect, it, vi } from 'vitest';
import { createAppStore } from './store';
import { executeCommand } from './autenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkSlice';
import type { AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient } from '../api/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-client';

describe('autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework slice', () => {
  it('records the event returned by the backend', async () => {
    const result = { type: 'ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted', aggregateId: 'agg-1', version: 1 };
    const client = { execute: vi.fn().mockResolvedValue(result) } as unknown as AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient;
    const store = createAppStore(client);

    await store.dispatch(executeCommand({ id: 'agg-1', command: 'process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework' }));

    expect(store.getState().autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework).toEqual({ events: [result], status: 'idle', error: null });
  });

  it('keeps the error message when the command fails', async () => {
    const client = { execute: vi.fn().mockRejectedValue(new Error('Command id is required')) } as unknown as AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient;
    const store = createAppStore(client);

    await store.dispatch(executeCommand({ id: 'agg-1', command: 'process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework' }));

    expect(store.getState().autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework.status).toBe('failed');
    expect(store.getState().autenticacionJwtYSerializacionTransaccionalEnDjangoRestFramework.error).toBe('Command id is required');
  });
});
