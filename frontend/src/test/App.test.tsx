import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from '../App';
import { api } from '../api/client';
import { preview, session, task } from './fixtures';

vi.mock('../api/client', () => ({
  api: { health: vi.fn(), session: vi.fn(), tasks: vi.fn(), preview: vi.fn(), createTask: vi.fn() },
}));

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(api.health).mockResolvedValue({
    status: 'ok',
    mode: 'scaffold',
    storage: 'memory',
    workflows_implemented: false,
  });
  vi.mocked(api.session).mockResolvedValue(session);
  vi.mocked(api.tasks).mockResolvedValue([task]);
  vi.mocked(api.preview).mockResolvedValue(preview);
});

describe('merchant workspace', () => {
  it('separates static previews from task execution and disables sends', async () => {
    render(<App />);
    expect(await screen.findByText('Sharma General Store')).toBeInTheDocument();
    expect(screen.getByText(/No execution receipt/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Review & send/ })).toBeDisabled();
    expect(screen.getByText(/These values are separate/)).toBeInTheDocument();
  });

  it('uses an example request and saves a task without claiming completion', async () => {
    vi.mocked(api.createTask).mockResolvedValue({
      ...task,
      task_id: 'new-task',
      goal: 'A new request',
    });
    render(<App />);
    await screen.findByText('Sharma General Store');
    fireEvent.click(screen.getByRole('button', { name: 'Why is my settlement short?' }));
    fireEvent.click(screen.getByRole('button', { name: /Start a task/ }));
    await waitFor(() => expect(api.createTask).toHaveBeenCalledWith('Why is my settlement short?'));
    expect(await screen.findByRole('heading', { name: 'A new request' })).toBeInTheDocument();
    expect(screen.getByText('AWAITING INPUT')).toBeInTheDocument();
  });

  it('shows a recoverable error when the backend is offline', async () => {
    vi.mocked(api.health).mockRejectedValue(new Error('API offline'));
    render(<App />);
    expect(await screen.findByRole('alert')).toHaveTextContent('API offline');
    expect(screen.getByRole('button', { name: /Start a task/ })).toBeDisabled();
    vi.mocked(api.health).mockResolvedValue({
      status: 'ok',
      mode: 'scaffold',
      storage: 'memory',
      workflows_implemented: false,
    });
    fireEvent.click(screen.getByRole('button', { name: 'Retry connection' }));
    expect(await screen.findByText('Sharma General Store')).toBeInTheDocument();
  });

  it('preserves the draft when saving fails', async () => {
    vi.mocked(api.createTask).mockRejectedValue(new Error('Please retry'));
    render(<App />);
    await screen.findByText('Sharma General Store');
    fireEvent.change(screen.getByLabelText('Tell BizMate what you need'), {
      target: { value: 'Investigate' },
    });
    fireEvent.click(screen.getByRole('button', { name: /Start a task/ }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Please retry');
    expect(screen.getByLabelText('Tell BizMate what you need')).toHaveValue('Investigate');
  });
});
