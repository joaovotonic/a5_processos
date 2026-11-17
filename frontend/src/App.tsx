import React, { useEffect, useState } from 'react';
import { MotionConfig } from 'motion/react';
import type { AuthUser } from './types';
import { apiJson, getBootConfig } from './lib/api';
import { ThemeProvider } from './components/ThemeProvider';
import { EmberRevealShell } from './components/motion/MotionPrimitives';
import { LoginPage } from './pages/LoginPage';
import { AdminPage } from './pages/AdminPage';
import { DiretoriaPage } from './pages/DiretoriaPage';

function resolvePathForUser(user: AuthUser | null, rawPath: string): 'login' | 'admin' | 'diretoria' {
  if (!user) return 'login';
  if (user.role === 'diretoria') return 'diretoria';
  if (user.role === 'admin_recepcao') return 'admin';
  if (rawPath.startsWith('/diretoria') || rawPath.startsWith('/chamado')) return 'diretoria';
  return 'admin';
}

export const App: React.FC = () => {
  const boot = getBootConfig();
  const [user, setUser] = useState<AuthUser | null>(boot.user);
  const [pathname, setPathname] = useState<string>(() => window.location.pathname || '/');
  const [revealKey, setRevealKey] = useState(1);
  const [panelReady, setPanelReady] = useState(false);

  useEffect(() => {
    // Revalida sessão no servidor ao abrir para evitar cache obsoleto do navegador
    apiJson<{ authenticated: boolean; user?: AuthUser }>('/api/auth/me').then((res) => {
      if (res.ok && res.data.authenticated && res.data.user) {
        setUser(res.data.user);
      } else if (res.ok && res.data.authenticated === false) {
        setUser(null);
      }
    });

    const onPopState = () => {
      setPathname(window.location.pathname || '/');
    };
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const navigate = (targetPath: string) => {
    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, '', targetPath);
    }
    setPanelReady(false);
    setPathname(targetPath);
    setRevealKey((k) => k + 1);
  };

  const handleLoginSuccess = (loggedUser: AuthUser, redirectTo: string) => {
    setUser(loggedUser);
    const dest =
      loggedUser.role === 'diretoria'
        ? '/diretoria'
        : loggedUser.role === 'admin_recepcao'
          ? '/admin'
          : redirectTo || loggedUser.home_route || '/admin';
    navigate(dest);
  };

  const handleLogout = async () => {
    await apiJson('/api/auth/logout', { method: 'POST' });
    setUser(null);
    navigate('/login');
  };

  const view = resolvePathForUser(user, pathname);

  // Mantém a URL sincronizada caso um perfil tente acessar a rota errada
  useEffect(() => {
    if (view === 'login' && pathname !== '/login') {
      window.history.replaceState({}, '', '/login');
    } else if (view === 'diretoria' && !pathname.startsWith('/diretoria') && !pathname.startsWith('/chamado')) {
      window.history.replaceState({}, '', '/diretoria');
    } else if (view === 'admin' && pathname !== '/admin') {
      window.history.replaceState({}, '', '/admin');
    }
  }, [view, pathname]);

  if (view === 'login' || !user) {
    return (
      <MotionConfig reducedMotion="user">
        <ThemeProvider>
          <LoginPage onLoginSuccess={handleLoginSuccess} />
        </ThemeProvider>
      </MotionConfig>
    );
  }

  return (
    <MotionConfig reducedMotion="user">
      <ThemeProvider>
        <EmberRevealShell
          revealKey={revealKey}
          ready={panelReady}
          minDurationMs={revealKey === 1 ? 1600 : 950}
          subtitle={
            view === 'diretoria'
              ? 'Sincronizando painel da Diretoria...'
              : 'Sincronizando Esteira Kanban...'
          }
        >
          {view === 'diretoria' ? (
            <DiretoriaPage
              user={user}
              onNavigate={navigate}
              onLogout={handleLogout}
              onReady={() => setPanelReady(true)}
            />
          ) : (
            <AdminPage
              user={user}
              onNavigate={navigate}
              onLogout={handleLogout}
              onReady={() => setPanelReady(true)}
            />
          )}
        </EmberRevealShell>
      </ThemeProvider>
    </MotionConfig>
  );
};

export default App;
