import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, Camera, Megaphone, Plus, QrCode, Trash2, X } from 'lucide-react';
import type { KanbanCard, PendingEntry } from '../../types';
import { apiJson } from '../../lib/api';
import { MOTION_EASE } from '../motion/motionTokens';
import { MorphButton, type MorphButtonState } from '../fluid/morph-button/MorphButton';
import { CopyMorph } from '../fluid/copy-morph/CopyMorph';

/* ---------- PENDING PHOTOS MODAL ---------- */
export const PendingPhotosModal: React.FC<{
  open: boolean;
  intakeUrl: string;
  pendingEntries: PendingEntry[];
  onClose: () => void;
  onUseEntry: (entry: PendingEntry) => void;
  onDeleteEntry: (id: number) => void;
}> = ({ open, intakeUrl, pendingEntries, onClose, onUseEntry, onDeleteEntry }) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  const qrImg = `https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=${encodeURIComponent(intakeUrl)}`;

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
            initial={{ opacity: 0, scale: 0.94, y: 14 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 10 }}
            transition={{ duration: 0.22, ease: MOTION_EASE }}
            className="w-full max-w-2xl modernize-card p-6 max-h-[90vh] overflow-y-auto space-y-4"
          >
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
              <div className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-blue-500/15 text-blue-600 dark:text-sky-400 flex items-center justify-center">
                  <QrCode className="w-5 h-5" />
                </div>
                <div>
                  <h2 className="text-base font-extrabold text-zinc-900 dark:text-white">
                    Fotos da Recepção (Pré-Entrada Teorema)
                  </h2>
                  <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                    Fotografe pelo celular antes de emitir a O.S. e vincule depois.
                  </p>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="p-1.5 rounded-full hover:bg-slate-100 dark:hover:bg-zinc-800 text-slate-400 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 p-4 bento-inner-tile items-center">
              <div className="md:col-span-2 space-y-2.5">
                <span className="text-[11px] font-extrabold uppercase tracking-wider text-blue-600 dark:text-sky-400 block">
                  Link Direto para Celular:
                </span>
                <div className="p-2.5 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-mono text-xs font-bold text-blue-600 dark:text-sky-400 break-all">
                  {intakeUrl}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <CopyMorph text={intakeUrl} label="Copiar Link" doneLabel="Copiado!" compact />
                  <a
                    href="/recepcao-fotos"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-full btn-modernize-light text-xs"
                  >
                    <Camera className="w-3.5 h-3.5" />
                    <span>Abrir Tela Mobile</span>
                  </a>
                </div>
              </div>
              <div className="flex flex-col items-center justify-center bg-white p-3 rounded-2xl border border-slate-200">
                <img src={qrImg} alt="QR Code Recepção" className="w-28 h-28 object-contain" />
                <span className="text-[10px] font-bold text-slate-500 mt-1">Escaneie no celular</span>
              </div>
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-extrabold uppercase tracking-wider text-slate-500 dark:text-zinc-400">
                Entradas Aguardando O.S. ({pendingEntries.length})
              </h3>
              {pendingEntries.length === 0 ? (
                <div className="p-6 text-center rounded-2xl border border-dashed border-slate-300 dark:border-zinc-800 text-xs text-slate-400">
                  Nenhuma pré-entrada aguardando O.S.
                </div>
              ) : (
                pendingEntries.map((pe) => (
                  <div
                    key={pe.id}
                    className="p-3.5 rounded-2xl bento-inner-tile flex flex-wrap items-center justify-between gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="font-extrabold text-xs uppercase text-zinc-900 dark:text-white truncate">
                        {pe.client_name}
                      </div>
                      <div className="text-[11px] text-slate-500 dark:text-zinc-400">
                        {pe.equipment_type} {pe.equipment_model ? `• ${pe.equipment_model}` : ''} •{' '}
                        {pe.photos?.length || 0} foto(s)
                      </div>
                      {pe.photos?.length > 0 && (
                        <div className="flex gap-1.5 mt-2 overflow-x-auto">
                          {pe.photos.map((p, i) => (
                            <img key={i} src={p} alt="" className="w-12 h-12 rounded-xl object-cover border border-slate-200 dark:border-zinc-700" />
                          ))}
                        </div>
                      )}
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => onUseEntry(pe)}
                        className="px-3.5 py-2 rounded-full btn-modernize-primary text-xs inline-flex items-center gap-1.5 cursor-pointer"
                      >
                        <Plus className="w-3.5 h-3.5" />
                        <span>Gerar O.S.</span>
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeleteEntry(pe.id)}
                        className="p-2 rounded-full text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 cursor-pointer"
                        title="Excluir pré-entrada"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

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
