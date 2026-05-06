import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Login from './Login';

const authMock = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signUp: vi.fn(),
  signInWithOtp: vi.fn(),
  verifyOtp: vi.fn(),
  signInWithOAuth: vi.fn(),
}));

vi.mock('./lib/supabase', () => ({
  getAuthRedirectUrl: (path = '/agents') => `http://localhost${path}`,
  isSupabaseConfigured: true,
  supabase: {
    auth: authMock,
  },
}));

vi.mock('./lib/api', () => ({
  apiConnectionMessage: 'Backend not connected. Add NEXT_PUBLIC_API_URL in Vercel production env.',
  isApiConfigured: true,
}));

vi.mock('./lib/env', () => ({
  appMisconfiguredUserMessage: 'App is not configured. Please contact admin.',
  envIssueMessages: [],
  isApiConfigured: true,
  isPublicEnvValid: true,
  isSupabaseConfigured: true,
}));

function PathProbe() {
  const location = useLocation();
  return <span data-testid="path">{location.pathname}</span>;
}

function renderLogin() {
  return render(
    <MemoryRouter initialEntries={['/login']}>
      <Login />
      <PathProbe />
    </MemoryRouter>,
  );
}

describe('Login page', () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    authMock.getSession.mockResolvedValue({ data: { session: null } });
  });

  it('logs in with Supabase on success', async () => {
    authMock.getSession
      .mockResolvedValueOnce({ data: { session: null } })
      .mockResolvedValueOnce({ data: { session: { access_token: 'test-token' } } });
    authMock.signInWithPassword.mockResolvedValue({ error: null });

    renderLogin();

    fireEvent.change(screen.getByPlaceholderText('Email'), {
      target: { value: 'user@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Password'), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit login' }));

    await waitFor(() => {
      expect(authMock.signInWithPassword).toHaveBeenCalledWith({
        email: 'user@example.com',
        password: 'password123',
      });
    });
    expect(await screen.findByTestId('path')).toHaveTextContent('/agents');
  });

  it('shows API error message on failed login', async () => {
    authMock.signInWithPassword.mockResolvedValue({ error: { message: 'Invalid credentials' } });

    renderLogin();

    fireEvent.change(screen.getByPlaceholderText('Email'), {
      target: { value: 'bad@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Password'), {
      target: { value: 'wrong' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit login' }));

    expect(await screen.findByText('Invalid credentials')).toBeInTheDocument();
  });

  it('signs up and asks the user to verify email', async () => {
    authMock.signUp.mockResolvedValue({ data: { session: null }, error: null });

    renderLogin();

    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }));
    fireEvent.change(screen.getByPlaceholderText('Email'), {
      target: { value: 'new@example.com' },
    });
    fireEvent.change(screen.getByPlaceholderText('Password'), {
      target: { value: 'password123' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Submit signup' }));

    await waitFor(() => {
      expect(authMock.signUp).toHaveBeenCalledWith({
        email: 'new@example.com',
        password: 'password123',
        options: { emailRedirectTo: 'http://localhost/agents' },
      });
    });
    expect(await screen.findByText('Signup successful. Check your email/Gmail to verify your account.')).toBeInTheDocument();
  });

  it('starts Google OAuth login', async () => {
    authMock.signInWithOAuth.mockResolvedValue({ error: null });

    renderLogin();

    fireEvent.click(screen.getAllByRole('button', { name: 'Continue with Google' })[0]);

    await waitFor(() => {
      expect(authMock.signInWithOAuth).toHaveBeenCalledWith({
        provider: 'google',
        options: { redirectTo: 'http://localhost/agents' },
      });
    });
  });

  it('keeps first production auth testing on email and password only', async () => {
    renderLogin();

    expect(screen.queryByRole('button', { name: 'Email OTP' })).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText('Email OTP')).not.toBeInTheDocument();
  });
});
