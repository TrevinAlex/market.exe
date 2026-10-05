import { useId, useState, type FormEvent } from 'react';
import { ApiError, PASSWORD_MAX, PASSWORD_MIN, USERNAME_RE, errorMessage } from '../api/client';
import { useAuth } from '../hooks/useAuth';

type Mode = 'login' | 'register';

/** Login / register form for user accounts. Calls onDone after success. */
export function AuthForm({ initialMode = 'login', onDone }: { initialMode?: Mode; onDone?: () => void }) {
  const { login, register } = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  const isRegister = mode === 'register';
  const userErr = username && !USERNAME_RE.test(username) ? '3–32 characters: letters, digits, underscore.' : null;
  const passErr =
    isRegister && password && (password.length < PASSWORD_MIN || password.length > PASSWORD_MAX)
      ? `Password must be ${PASSWORD_MIN}–${PASSWORD_MAX} characters.`
      : null;
  const confirmErr = isRegister && confirm && confirm !== password ? 'Passwords do not match.' : null;
  const canSubmit =
    !busy && USERNAME_RE.test(username) && password.length > 0 && !passErr && (!isRegister || confirm === password);

  const switchMode = (m: Mode) => {
    setMode(m);
    setError(null);
    setConfirm('');
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setError(null);
    try {
      await (isRegister ? register(username, password) : login(username, password));
      onDone?.();
    } catch (err) {
      setError(
        err instanceof ApiError && err.status === 422 ? 'Invalid username or password format.' : errorMessage(err),
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel auth-panel" aria-labelledby={`${id}-title`}>
      <h2 className="panel-title" id={`${id}-title`}>
        {isRegister ? '> Create account' : '> User login'}
      </h2>

      <form className="stack" onSubmit={onSubmit} noValidate>
        <label className="auth-field">
          <span>Username</span>
          <input
            className="input"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value.trim())}
            aria-invalid={!!userErr}
            aria-describedby={userErr ? `${id}-uerr` : undefined}
            maxLength={32}
            required
            autoFocus
          />
          {userErr && (
            <small id={`${id}-uerr`} className="auth-err">
              {userErr}
            </small>
          )}
        </label>

        <label className="auth-field">
          <span>Password</span>
          <input
            className="input"
            type="password"
            name="password"
            autoComplete={isRegister ? 'new-password' : 'current-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!passErr}
            aria-describedby={passErr ? `${id}-perr` : undefined}
            maxLength={PASSWORD_MAX}
            required
          />
          {passErr && (
            <small id={`${id}-perr`} className="auth-err">
              {passErr}
            </small>
          )}
        </label>

        {isRegister && (
          <label className="auth-field">
            <span>Confirm password</span>
            <input
              className="input"
              type="password"
              name="confirm"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              aria-invalid={!!confirmErr}
              aria-describedby={confirmErr ? `${id}-cerr` : undefined}
              maxLength={PASSWORD_MAX}
              required
            />
            {confirmErr && (
              <small id={`${id}-cerr`} className="auth-err">
                {confirmErr}
              </small>
            )}
          </label>
        )}

        {error && (
          <div className="alert" role="alert">
            <span>! ERR // {error}</span>
          </div>
        )}

        <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
          {busy ? 'Please wait…' : isRegister ? 'Register' : 'Login'}
        </button>
      </form>

      <p className="mono dim auth-switch">
        {isRegister ? 'Already have an account? ' : 'No account yet? '}
        <button type="button" className="link-btn" onClick={() => switchMode(isRegister ? 'login' : 'register')}>
          {isRegister ? 'Login' : 'Register'}
        </button>
      </p>
    </section>
  );
}
