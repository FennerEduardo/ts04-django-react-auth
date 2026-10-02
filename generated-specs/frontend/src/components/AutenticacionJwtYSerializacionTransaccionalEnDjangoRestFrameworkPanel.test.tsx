import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { Provider } from 'react-redux';
import { createAppStore } from '../store/store';
import { AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel } from './AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel';
import type { AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient } from '../api/autenticacion-jwt-y-serializacion-transaccional-en-django-rest-framework-client';

describe('AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel', () => {
  it('executes a command and lists the resulting event', async () => {
    const client = { execute: vi.fn().mockResolvedValue({ type: 'ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted', aggregateId: 'agg-1', version: 1 }) } as unknown as AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient;
    render(
      <Provider store={createAppStore(client)}>
        <AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel />
      </Provider>
    );

    await userEvent.type(screen.getByLabelText('Aggregate id'), 'agg-1');
    await userEvent.click(screen.getByRole('button', { name: 'process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework' }));

    expect(await screen.findByText('ProcessAutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkCompleted v1')).toBeInTheDocument();
    expect(client.execute).toHaveBeenCalledWith('agg-1', 'process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework', undefined, expect.objectContaining({ idempotencyKey: expect.any(String) }));
  });

  it('disables commands until an aggregate id is entered', () => {
    render(
      <Provider store={createAppStore({ execute: vi.fn() } as unknown as AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkClient)}>
        <AutenticacionJwtYSerializacionTransaccionalEnDjangoRestFrameworkPanel />
      </Provider>
    );
    expect(screen.getByRole('button', { name: 'process_autenticacion_jwt_y_serializacion_transaccional_en_django_rest_framework' })).toBeDisabled();
  });
});
