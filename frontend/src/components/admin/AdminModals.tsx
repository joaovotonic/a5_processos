import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, Megaphone, X } from 'lucide-react';
import type { KanbanCard } from '../../types';
import { apiJson } from '../../lib/api';
import { MOTION_EASE } from '../motion/motionTokens';
import { MorphButton, type MorphButtonState } from '../fluid/morph-button/MorphButton';

/* ---------- CALL TECH MODAL ---------- */
export const CallTechModal: React.FC<{
  open: boolean;
  onClose: () => void;
  onSent: (msg: string) => void;
}> = ({ open, onClose, onSent }) => {
  const [techName, setTechName] = useState('Enzo');
  const [reason, setReason] = useState('Comparecer na recepção para atendimento');
  const [btnState, setBtnState] = useState<MorphButtonState>('idle');

  useEffect(() => {
    if (open) setBtnState('idle');
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBtnState('loading');
    const res = await apiJson<{ success: boolean }>('/api/admin/call-tech', {
      method: 'POST',
      body: JSON.stringify({ tech_name: techName, reason }),
    });
    if (res.ok && res.data.success) {
      setBtnState('done');
      setTimeout(() => {
        onSent(`📢 Chamado para ${techName} enviado na TV!`);
        onClose();
      }, 650);
    } else {
      setBtnState('idle');
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.2, ease: MOTION_EASE }}
            className="w-full max-w-md modernize-card p-6 space-y-4"
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-amber-500/15 text-amber-500 flex items-center justify-center">
                  <Megaphone className="w-5 h-5" />
                </div>
                <h3 className="text-sm font-extrabold text-zinc-900 dark:text-white">
                  Chamar Técnico na Recepção (Voz na TV)
                </h3>
              </div>
              <button type="button" onClick={onClose} className="p-1 text-slate-400 cursor-pointer">
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-3">
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Selecione o Destinatário
                </label>
                <select
                  value={techName}
                  onChange={(e) => setTechName(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold"
                >
                  <option value="Enzo">TEC. Enzo Gabriel</option>
                  <option value="Guilherme">TEC. Guilherme</option>
                  <option value="Wisley">TEC. Wisley</option>
                  <option value="João Otoni">TEC. João Otoni</option>
                  <option value="Iago">TEC. Iago</option>
                  <option value="Antonio">TEC. ANTONIO</option>
                  <option value="Arthur (ADM)">ADM. Arthur</option>
                  <option value="Roosevelt (ADM)">ADM. Roosevelt</option>
                  <option value="Priscila (ADM)">ADM. Priscila</option>
                  <option value="Senhor Jacson">SR. JACSON</option>
                  <option value="Todos os Técnicos">TODOS OS TÉCNICOS</option>
                </select>
              </div>
              <div>
                <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-zinc-400 mb-1">
                  Motivo do Chamado
                </label>
                <input
                  type="text"
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-medium"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2.5 rounded-full text-xs font-bold bg-slate-100 dark:bg-zinc-800 cursor-pointer"
                >
                  Cancelar
                </button>
                <MorphButton
                  type="submit"
                  state={btnState}
                  labels={{ idle: 'Disparar na TV', loading: 'Enviando...', done: 'Chamado Enviado!' }}
                />
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

/* ---------- DELETE AUTH MODAL ---------- */
export const DeleteAuthModal: React.FC<{
  card: KanbanCard | null;
  onClose: () => void;
  onDeleted: (osNumber: string) => void;
}> = ({ card, onClose, onDeleted }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (card) {
      setUsername('');
      setPassword('');
      setError('');
      setLoading(false);
    }
  }, [card]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!card) return;
    setError('');
    setLoading(true);
    const res = await apiJson<{ success: boolean; error?: string }>(`/api/cards/${card.id}`, {
      method: 'DELETE',
      body: JSON.stringify({ username: username.trim(), password: password.trim() }),
    });
    setLoading(false);
    if (!res.ok || !res.data.success) {
      setError(res.data.error || 'Credenciais de exclusão inválidas.');
      return;
    }
    onDeleted(card.os_number);
    onClose();
  };

  return (
    <AnimatePresence>
      {card && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          className="fixed inset-0 z-[60] bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => e.target === e.currentTarget && onClose()}
        >
          <motion.div
            role="dialog"
            aria-modal="true"
            initial={{ opacity: 0, scale: 0.94, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            className="w-full max-w-sm modernize-card p-6 border-rose-500/30 space-y-4"
          >
            <div className="flex items-center gap-2.5 text-rose-500">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <div className="min-w-0">
                <h3 className="font-extrabold text-sm text-zinc-900 dark:text-white">Excluir O.S. Permanentemente</h3>
                <p className="text-xs text-slate-500 truncate">
                  OS {card.os_number} • {card.client_name}
                </p>
              </div>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Ação irreversível. Informe login e senha master para excluir esta O.S.:
            </p>
            <form onSubmit={handleSubmit} className="space-y-3">
              <input
                type="text"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="Login Administrador (admin)"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold"
              />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Senha Administrador"
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold"
              />
              {error && (
                <div className="p-2.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-500 text-xs font-bold">
                  {error}
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-full text-xs font-bold bg-slate-100 dark:bg-zinc-800 cursor-pointer"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="px-4 py-2 rounded-full text-xs font-bold bg-rose-600 hover:bg-rose-500 text-white shadow cursor-pointer disabled:opacity-60"
                >
                  {loading ? 'Excluindo...' : 'Confirmar Exclusão'}
                </button>
              </div>
            </form>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};
