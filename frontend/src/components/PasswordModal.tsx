import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { KeyRound, ShieldCheck, X } from 'lucide-react';
import type { AuthUser } from '../types';
import { apiJson } from '../lib/api';
import { MOTION_EASE } from './motion/motionTokens';
import { MorphButton, type MorphButtonState } from './fluid/morph-button/MorphButton';

interface PasswordModalProps {
  open: boolean;
  user: AuthUser;
  onClose: () => void;
  onSuccess: (msg: string) => void;
}

interface UserListItem {
  id: number;
  username: string;
  display_name: string;
  role: string;
}

export const PasswordModal: React.FC<PasswordModalProps> = ({ open, user, onClose, onSuccess }) => {
  const [targetUsername, setTargetUsername] = useState(user.username);
  const [newPassword, setNewPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [btnState, setBtnState] = useState<MorphButtonState>('idle');
  const [usersList, setUsersList] = useState<UserListItem[]>([]);

  useEffect(() => {
    if (!open) return;
    setTargetUsername(user.username);
    setNewPassword('');
    setConfirm('');
    setError('');
    setBtnState('idle');
    if (user.role === 'master') {
      apiJson<{ success: boolean; users: UserListItem[] }>('/api/auth/users').then((r) => {
        if (r.ok && r.data.users) setUsersList(r.data.users);
      });
    }
  }, [open, user]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (newPassword.length < 4) {
      setError('A senha deve ter pelo menos 4 caracteres.');
      return;
    }
    if (newPassword !== confirm) {
      setError('As senhas digitadas não conferem.');
      return;
    }
    setBtnState('loading');
    const res = await apiJson<{ success: boolean; error?: string; message?: string }>('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ username: targetUsername, new_password: newPassword }),
    });
    if (!res.ok || !res.data.success) {
      setBtnState('idle');
      setError(res.data.error || 'Erro ao atualizar senha.');
      return;
    }
    setBtnState('done');
    setTimeout(() => {
      onSuccess(`Senha de ${targetUsername} atualizada com sucesso!`);
      onClose();
    }, 850);
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) onClose();
          }}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.22, ease: MOTION_EASE }}
            className="w-full max-w-md modernize-card p-6 space-y-4"
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-500/15 text-blue-600 dark:text-sky-400 flex items-center justify-center">
                  <KeyRound className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-extrabold text-zinc-900 dark:text-white">
                    {user.role === 'master' ? 'Gerenciar Senhas de Acesso' : 'Alterar Minha Senha'}
                  </h3>
                  <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                    Perfil ativo: {user.display_name}
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fechar"
                className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-500 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3.5">
              {user.role === 'master' && usersList.length > 0 && (
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                    Usuário a Atualizar
                  </label>
                  <select
                    value={targetUsername}
                    onChange={(e) => setTargetUsername(e.target.value)}
                    className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold text-zinc-900 dark:text-white"
                  >
                    {usersList.map((u) => (
                      <option key={u.id} value={u.username}>
                        {u.display_name} ({u.username})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Nova Senha
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  placeholder="Mínimo 4 caracteres"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-semibold text-zinc-900 dark:text-white focus:border-blue-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Confirmar Nova Senha
                </label>
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  required
                  placeholder="Repita a senha"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-semibold text-zinc-900 dark:text-white focus:border-blue-500 focus:outline-none"
                />
              </div>

              {error && (
                <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-600 dark:text-rose-400 text-xs font-semibold flex items-center gap-2">
                  <ShieldCheck className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 hover:bg-slate-200 dark:hover:bg-zinc-700 cursor-pointer"
                >
                  Cancelar
                </button>
                <MorphButton
                  type="submit"
                  state={btnState}
                  labels={{ idle: 'Salvar Senha', loading: 'Salvando...', done: 'Salva!' }}
                />
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
