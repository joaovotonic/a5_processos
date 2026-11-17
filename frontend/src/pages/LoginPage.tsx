import React, { useState } from 'react';
import { motion } from 'motion/react';
import { Lock, Moon, Sun, Tv, UserCheck, Shield, Sparkles } from 'lucide-react';
import { A5Logo } from '../components/A5Logo';
import { useTheme } from '../components/ThemeProvider';
import { EmberRevealShell } from '../components/motion/MotionPrimitives';
import { MOTION_EASE } from '../components/motion/motionTokens';
import { MorphButton, type MorphButtonState } from '../components/fluid/morph-button/MorphButton';
import { SegmentedPicker } from '../components/fluid/segmented-picker/SegmentedPicker';
import { apiJson, getBootConfig } from '../lib/api';
import type { AuthUser } from '../types';

interface LoginPageProps {
  onLoginSuccess: (user: AuthUser, redirectTo: string) => void;
}

export const LoginPage: React.FC<LoginPageProps> = ({ onLoginSuccess }) => {
  const boot = getBootConfig();
  const { theme, toggleTheme } = useTheme();

  const [mode, setMode] = useState<'login' | 'setup'>('login');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [btnState, setBtnState] = useState<MorphButtonState>('idle');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setBtnState('loading');

    if (mode === 'setup') {
      const res = await apiJson<{ success: boolean; user?: AuthUser; redirect_to?: string; error?: string }>(
        '/api/auth/setup-director',
        {
          method: 'POST',
          body: JSON.stringify({ username, password, confirm_password: confirmPassword }),
        },
      );
      if (!res.ok || !res.data.success || !res.data.user) {
        setBtnState('idle');
        setError(res.data.error || 'Não foi possível concluir o primeiro acesso.');
        return;
      }
      setBtnState('done');
      setTimeout(() => onLoginSuccess(res.data.user!, res.data.redirect_to || '/diretoria'), 650);
      return;
    }

    const res = await apiJson<{ success: boolean; user?: AuthUser; redirect_to?: string; error?: string }>(
      '/api/auth/login',
      {
        method: 'POST',
        body: JSON.stringify({ username, password }),
      },
    );
    if (!res.ok || !res.data.success || !res.data.user) {
      setBtnState('idle');
      setError(res.data.error || 'Usuário ou senha incorretos.');
      return;
    }
    setBtnState('done');
    setTimeout(() => onLoginSuccess(res.data.user!, res.data.redirect_to || res.data.user!.home_route), 600);
  };

  const quickFillUser = (u: string) => {
    setMode('login');
    setUsername(u);
    setError('');
  };

  return (
    <EmberRevealShell revealKey={1} minDurationMs={1400} subtitle="Inicializando acesso seguro...">
      <div className="min-h-screen flex flex-col items-center justify-center p-4 sm:p-6 relative overflow-hidden">
        {/* Ambient radial highlights */}
        <div
          aria-hidden
          className="pointer-events-none fixed -top-32 left-1/2 -translate-x-1/2 w-[780px] h-[420px] rounded-full opacity-35 blur-3xl"
          style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.32) 0%, transparent 70%)' }}
        />

        {/* Top floating theme & TV link */}
        <div className="fixed top-4 right-4 z-20 flex items-center gap-2">
          <a
            href="/tv"
            className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-full modernize-card text-xs font-bold text-slate-700 dark:text-zinc-200 hover:border-blue-500/40 transition"
          >
            <Tv className="w-3.5 h-3.5 text-blue-600 dark:text-sky-400" />
            <span>TV Oficina (Sem Login)</span>
          </a>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label="Alternar tema claro/escuro"
            className="w-9 h-9 rounded-full modernize-card flex items-center justify-center text-slate-700 dark:text-zinc-200 cursor-pointer"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-blue-600" />}
          </button>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 18, scale: 0.97 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.42, ease: MOTION_EASE }}
          className="w-full max-w-md modernize-card p-7 sm:p-8 space-y-6 relative overflow-hidden"
        >
          <div className="absolute top-0 inset-x-0 h-1 bg-gradient-to-r from-[#5D87FF] via-[#38BDF8] to-[#2563EB]" />

          <div className="flex flex-col items-center text-center space-y-2.5 pt-1">
            <A5Logo variant="full" size="lg" />
            <div className="pt-1">
              <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-[11px] font-bold uppercase tracking-wider bg-blue-500/10 text-blue-600 dark:text-sky-400 border border-blue-500/20">
                <Shield className="w-3 h-3" />
                <span>Acesso ao Painel A5</span>
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-xs leading-relaxed">
              Entre com seu perfil para ir diretamente à sua área de trabalho (Recepção ou Diretoria Executiva).
            </p>
          </div>

          {/* Atalhos rápidos de perfil */}
          <div className="grid grid-cols-3 gap-2">
            <button
              type="button"
              onClick={() => quickFillUser('priscila')}
              className={`bento-inner-tile px-2.5 py-2 text-center transition cursor-pointer ${
                username.toLowerCase() === 'priscila' ? 'ring-2 ring-blue-500 border-blue-500/50' : 'hover:border-blue-400/50'
              }`}
            >
              <span className="block text-[10px] font-extrabold uppercase text-blue-600 dark:text-sky-400">Recepção</span>
              <span className="block text-xs font-bold text-zinc-900 dark:text-white mt-0.5">Priscila</span>
            </button>
            <button
              type="button"
              onClick={() => quickFillUser(boot.directorSavedUser || 'jacson')}
              className={`bento-inner-tile px-2.5 py-2 text-center transition cursor-pointer ${
                username.toLowerCase() === (boot.directorSavedUser || 'jacson').toLowerCase()
                  ? 'ring-2 ring-amber-500 border-amber-500/50'
                  : 'hover:border-amber-400/50'
              }`}
            >
              <span className="block text-[10px] font-extrabold uppercase text-amber-600 dark:text-amber-400">Diretoria</span>
              <span className="block text-xs font-bold text-zinc-900 dark:text-white mt-0.5">Sr. Jacson</span>
            </button>
            <button
              type="button"
              onClick={() => quickFillUser('admin')}
              className={`bento-inner-tile px-2.5 py-2 text-center transition cursor-pointer ${
                username.toLowerCase() === 'admin' ? 'ring-2 ring-emerald-500 border-emerald-500/50' : 'hover:border-emerald-400/50'
              }`}
            >
              <span className="block text-[10px] font-extrabold uppercase text-emerald-600 dark:text-emerald-400">Master</span>
              <span className="block text-xs font-bold text-zinc-900 dark:text-white mt-0.5">Geral</span>
            </button>
          </div>

          {!boot.directorFirstAccessDone && (
            <div className="flex justify-center">
              <SegmentedPicker
                label="Modo de acesso"
                value={mode}
                onChange={(val) => {
                  setMode(val);
                  setError('');
                }}
                options={[
                  { value: 'login', label: 'Entrar' },
                  {
                    value: 'setup',
                    label: (
                      <span className="inline-flex items-center gap-1">
                        <Sparkles className="w-3.5 h-3.5" /> 1º Acesso Diretoria
                      </span>
                    ),
                  },
                ]}
              />
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-3.5">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                Usuário
              </label>
              <div className="relative">
                <UserCheck className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                  autoComplete="username"
                  placeholder="priscila, jacson ou admin"
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-sm font-semibold text-zinc-900 dark:text-white focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                Senha
              </label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoComplete={mode === 'setup' ? 'new-password' : 'current-password'}
                  placeholder="Digite sua senha"
                  className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-sm font-semibold text-zinc-900 dark:text-white focus:border-blue-500 focus:outline-none"
                />
              </div>
            </div>

            {mode === 'setup' && (
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Confirmar Senha
                </label>
                <div className="relative">
                  <Lock className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    autoComplete="new-password"
                    placeholder="Repita a nova senha da Diretoria"
                    className="w-full pl-10 pr-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-sm font-semibold text-zinc-900 dark:text-white focus:border-blue-500 focus:outline-none"
                  />
                </div>
              </div>
            )}

            {error && (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-bold"
              >
                {error}
              </motion.div>
            )}

            <div className="pt-1 flex justify-center">
              <MorphButton
                type="submit"
                state={btnState}
                className="w-full justify-center"
                labels={{
                  idle: mode === 'setup' ? 'Criar Acesso Diretoria' : 'Entrar no Sistema',
                  loading: 'Verificando...',
                  done: 'Acesso Liberado!',
                }}
              />
            </div>
          </form>

          <div className="pt-3 border-t border-slate-200 dark:border-zinc-800 flex items-center justify-center text-[11px] text-slate-400 dark:text-zinc-500">
            <span>Esteira A5 Tecnologia • Manaus/AM</span>
          </div>
        </motion.div>
      </div>
    </EmberRevealShell>
  );
};
