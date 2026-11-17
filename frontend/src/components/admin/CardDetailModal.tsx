import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Activity,
  AlertTriangle,
  ArrowRightCircle,
  CheckCircle,
  Inbox,
  Layers,
  PackageCheck,
  Plus,
  Printer,
  Send,
  ShieldCheck,
  Trash2,
  Unlock,
  Wrench,
  X,
  XCircle,
} from 'lucide-react';
import type { KanbanCard, KanbanList } from '../../types';
import { analyzeWeightDiff, apiJson } from '../../lib/api';
import { MOTION_EASE } from '../motion/motionTokens';
import { CopyMorph } from '../fluid/copy-morph/CopyMorph';
import { MorphButton, type MorphButtonState } from '../fluid/morph-button/MorphButton';

interface CardDetailModalProps {
  card: KanbanCard | null;
  lists: KanbanList[];
  onClose: () => void;
  onRefresh: (reopenOs?: string) => Promise<void>;
  onAdvanceAdmin: (osNumber: string, action: string) => Promise<void>;
  onDeleteRequest: (card: KanbanCard) => void;
  onToast: (msg: string) => void;
}

const STEPS = [
  { num: 1, name: 'Orçamentos a Fazer' },
  { num: 2, name: 'Em Diagnóstico' },
  { num: 3, name: 'Orçamento Concluído' },
  { num: 4, name: 'Enviado ao Cliente' },
  { num: 5, name: 'Aprovado pelo Cliente' },
  { num: 6, name: 'Em Manutenção' },
  { num: 7, name: 'Finalizada / Pronta' },
];

export const CardDetailModal: React.FC<CardDetailModalProps> = ({
  card,
  lists,
  onClose,
  onRefresh,
  onAdvanceAdmin,
  onDeleteRequest,
  onToast,
}) => {
  const [targetListId, setTargetListId] = useState<string>('');
  const [adminNotes, setAdminNotes] = useState('');
  const [shelfLocation, setShelfLocation] = useState('');
  const [clientName, setClientName] = useState('');
  const [reportedDefect, setReportedDefect] = useState('');
  const [saveBtnState, setSaveBtnState] = useState<MorphButtonState>('idle');

  useEffect(() => {
    if (!card) return;
    setTargetListId(String(card.list_id));
    setAdminNotes(card.admin_notes || '');
    setShelfLocation(card.shelf_location || '');
    setClientName(card.client_name || '');
    setReportedDefect(card.reported_defect || '');
    setSaveBtnState('idle');
  }, [card]);

  useEffect(() => {
    if (!card) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [card, onClose]);

  if (!card) return null;

  const phase = card.pipeline_phase || 'ORCAMENTOS_A_FAZER';
  const lTitle = (card.list_title || '').toUpperCase();
  const lRole = (card.list_role || '').toLowerCase();

  let activeStepIndex = 0;
  let phaseName = '1. Orçamentos a Fazer';
  if (phase === 'EM_ORCAMENTO' || (card.list_is_tech && !card.finished_at && phase !== 'EM_MANUTENCAO')) {
    activeStepIndex = 1;
    phaseName = '2. Em Diagnóstico / Orçamento';
  } else if (phase === 'ORCAMENTOS_FEITOS' || lTitle.includes('FEITO')) {
    activeStepIndex = 2;
    phaseName = '3. Orçamento Concluído';
  } else if (phase === 'ORCAMENTOS_ENVIADOS' || lTitle.includes('ENVIAD')) {
    activeStepIndex = 3;
    phaseName = '4. Enviado ao Cliente';
  } else if (phase === 'NAO_AUTORIZADO' || lTitle.includes('NÃO AUTORIZAD') || lTitle.includes('NAO AUTORIZAD')) {
    activeStepIndex = 3;
    phaseName = 'Orçamento NÃO Autorizado';
  } else if (phase === 'BALANCAS_PENDENTES' || lTitle.includes('PENDENTE')) {
    activeStepIndex = 4;
    phaseName = '5. Aprovado • Falta Peça (Pendente)';
  } else if (phase === 'APROVADOS' || lTitle.includes('APROVAD')) {
    activeStepIndex = 4;
    phaseName = '5. Aprovado (Liberado)';
  } else if (phase === 'EM_MANUTENCAO') {
    activeStepIndex = 5;
    phaseName = '6. Em Manutenção na Bancada';
  } else if (phase === 'PRONTAS' || phase === 'FINALIZADAS' || card.finished_at || lTitle.includes('FINALIZADA')) {
    activeStepIndex = 6;
    phaseName = '7. Finalizada / Pronta';
  }

  const isOrcamentosCol = lRole === 'orcamento' || lTitle === 'ORÇAMENTOS' || lTitle === 'ORCAMENTOS';
  const isAprovadosCol = lRole.includes('aprovad') || lTitle.includes('APROVAD');
  const isPendentesCol = lRole.includes('pendente') || lTitle.includes('PENDENTE');
  const canSendQuote = phase === 'ORCAMENTOS_FEITOS' || lTitle.includes('FEITO');
  const canApproveQuote = phase === 'ORCAMENTOS_ENVIADOS' || lTitle.includes('ENVIAD');
  const isNaoAutorizado = phase === 'NAO_AUTORIZADO' || lTitle.includes('NÃO AUTORIZAD') || lTitle.includes('NAO AUTORIZAD');

  const activeLabels = card.labels || [];
  const isLabelActive = (name: string) => activeLabels.some((l) => l.name?.trim().toUpperCase() === name.trim().toUpperCase());
  const hasFaltaPeca = isLabelActive('FALTA PEÇA');
  const isUrgent = isLabelActive('URGENTE') || isLabelActive('URGÊNCIA');
  const isWarranty = isLabelActive('EM GARANTIA');

  const handleToggleLabel = async (name: string, color: string) => {
    const res = await apiJson<{ success?: boolean; error?: string }>(`/api/cards/${card.id}/toggle-label`, {
      method: 'POST',
      body: JSON.stringify({ name, color, actor: 'Priscila (Recepção)' }),
    });
    if (!res.ok) {
      onToast(res.data.error || 'Não foi possível atualizar a etiqueta.');
      return;
    }
    await onRefresh(card.os_number);
  };

  const handleCustomLabel = async () => {
    const name = prompt('Digite o nome da nova etiqueta:');
    if (name && name.trim()) await handleToggleLabel(name.trim(), '#3B82F6');
  };

  const handleMoveColumn = async () => {
    const lid = Number(targetListId);
    if (!lid || lid === card.list_id) return;
    const res = await apiJson(`/api/cards/${card.id}/move`, {
      method: 'POST',
      body: JSON.stringify({ target_list_id: lid, new_position: 0, actor: 'Priscila (Recepção)' }),
    });
    if (res.ok) {
      onToast(`O.S. ${card.os_number} transferida!`);
      await onRefresh(card.os_number);
    }
  };

  const handleMoveToPendentes = async () => {
    const pendList = lists.find((l) => l.role === 'balancas_pendentes' || l.title.toUpperCase().includes('PENDENTE'));
    if (!pendList) return;
    const res = await apiJson(`/api/cards/${card.id}/move`, {
      method: 'POST',
      body: JSON.stringify({ target_list_id: pendList.id, new_position: 0, actor: 'Priscila (Recepção)' }),
    });
    if (res.ok) {
      onToast(`O.S. ${card.os_number} movida para BALANÇAS PENDENTES.`);
      await onRefresh(card.os_number);
    }
  };

  const handleSaveDetails = async () => {
    setSaveBtnState('loading');
    const res = await apiJson(`/api/cards/${card.id}/update`, {
      method: 'POST',
      body: JSON.stringify({
        client_name: clientName.trim().toUpperCase(),
        reported_defect: reportedDefect.trim(),
        shelf_location: shelfLocation.trim(),
        admin_notes: adminNotes,
      }),
    });
    if (res.ok) {
      setSaveBtnState('done');
      onToast('Anotações e dados da O.S. salvos!');
      await onRefresh(card.os_number);
      setTimeout(() => setSaveBtnState('idle'), 1200);
    } else {
      setSaveBtnState('idle');
    }
  };

  const handleReopenAction = async (approve: boolean) => {
    const url = approve ? `/api/cards/${card.id}/reopen-quote` : `/api/cards/${card.id}/deny-reopen`;
    const res = await apiJson(url, {
      method: 'POST',
      body: JSON.stringify({ actor: 'Priscila (Recepção)' }),
    });
    if (res.ok) {
      onToast(approve ? 'Reabertura autorizada!' : 'Pedido de reabertura recusado.');
      await onRefresh(card.os_number);
    }
  };

  const allPhotos = [
    ...(card.entry_photos || []).map((src) => ({ group: 'Entrada', src })),
    ...(card.label_before_photos || []).map((src) => ({ group: 'Etiqueta Antes', src })),
    ...(card.quote_photos || []).map((src) => ({ group: 'Orçamento', src })),
    ...(card.label_after_photos || []).map((src) => ({ group: 'Etiqueta Depois', src })),
    ...(card.exit_photos || []).map((src) => ({ group: 'Saída', src })),
  ];

  const standardTags = [
    { name: 'URGENTE', label: '🔥 Urgência', color: '#EF4444' },
    { name: 'EM GARANTIA', label: '🛡️ Garantia', color: '#8B5CF6' },
    { name: 'FALTA PEÇA', label: '📦 Falta Peça', color: '#F97316' },
    { name: 'AGUARDANDO', label: '⏳ Aguardando', color: '#F59E0B' },
    { name: 'FEITO ORÇ.', label: '🔬 Feito Orç.', color: '#0EA5E9' },
    { name: 'AGUARDANDO PAGAMENTO', label: '💳 Pagamento', color: '#EC4899' },
  ];

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={(e) => e.target === e.currentTarget && onClose()}
      >
        <motion.div
          role="dialog"
          aria-modal="true"
          initial={{ opacity: 0, scale: 0.94, y: 14 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 10 }}
          transition={{ duration: 0.22, ease: MOTION_EASE }}
          className="w-full max-w-3xl modernize-card p-6 max-h-[93vh] overflow-y-auto space-y-5"
        >
          {/* 1. Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 dark:border-zinc-800 pb-3.5">
            <div className="flex items-center gap-2.5">
              <span className="font-mono tabular-nums text-base font-black px-3 py-1 rounded-xl bg-blue-500/12 text-blue-600 dark:text-sky-400 border border-blue-500/30">
                O.S. {card.os_number}
              </span>
              <span className="text-xs font-bold px-3 py-1 rounded-xl bento-inner-tile">
                Coluna: {card.list_title || 'N/A'}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {canSendQuote && (
                <button
                  type="button"
                  onClick={() => onAdvanceAdmin(card.os_number, 'enviar_cliente')}
                  className="px-3.5 py-1.5 rounded-full btn-modernize-primary text-xs inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Send className="w-3.5 h-3.5" />
                  <span>Enviar ao Cliente</span>
                </button>
              )}
              {canApproveQuote && (
                <>
                  <button
                    type="button"
                    onClick={() => onAdvanceAdmin(card.os_number, 'aprovar')}
                    className="px-3.5 py-1.5 rounded-full bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
                  >
                    <CheckCircle className="w-3.5 h-3.5" />
                    <span>APROVADO</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => onAdvanceAdmin(card.os_number, 'nao_autorizado')}
                    className="px-3.5 py-1.5 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
                  >
                    <XCircle className="w-3.5 h-3.5" />
                    <span>NÃO AUTORIZADO</span>
                  </button>
                </>
              )}
              {isNaoAutorizado && (
                <button
                  type="button"
                  onClick={() => onAdvanceAdmin(card.os_number, 'fechar_balanca')}
                  className="px-3.5 py-1.5 rounded-full bg-rose-700 hover:bg-rose-600 text-white text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <PackageCheck className="w-3.5 h-3.5" />
                  <span>FECHAR BALANÇA</span>
                </button>
              )}

              <button
                type="button"
                onClick={() => window.open(`/etiqueta/${encodeURIComponent(card.os_number)}`, '_blank', 'width=450,height=380')}
                className="px-3 py-1.5 rounded-full bento-inner-tile text-xs font-bold inline-flex items-center gap-1.5 hover:border-blue-500 cursor-pointer"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>Etiqueta</span>
              </button>
              <button
                type="button"
                onClick={() => onDeleteRequest(card)}
                className="p-2 rounded-full text-slate-400 hover:text-rose-500 hover:bg-rose-500/10 cursor-pointer"
                title="Excluir O.S."
              >
                <Trash2 className="w-4 h-4" />
              </button>
              <button
                type="button"
                onClick={onClose}
                className="p-2 rounded-full text-slate-400 hover:bg-slate-100 dark:hover:bg-zinc-800 cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 2. Reopen Banner */}
          {card.reopen_requested === 1 && (
            <div className="p-3.5 rounded-2xl bg-amber-500/15 border border-amber-500/40 flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-2.5 text-xs font-bold text-amber-700 dark:text-amber-300">
                <Unlock className="w-5 h-5 shrink-0" />
                <span>
                  {card.reopen_requested_by || 'Técnico'} solicitou reabertura do orçamento para edição.
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => handleReopenAction(true)}
                  className="px-3 py-1.5 rounded-full bg-emerald-600 text-white text-xs font-bold cursor-pointer"
                >
                  Autorizar
                </button>
                <button
                  type="button"
                  onClick={() => handleReopenAction(false)}
                  className="px-3 py-1.5 rounded-full bg-rose-600 text-white text-xs font-bold cursor-pointer"
                >
                  Recusar
                </button>
              </div>
            </div>
          )}

          {/* 3. Client Hero */}
          <div className="p-4 bento-inner-tile text-center space-y-1">
            <h2 className="text-xl font-black uppercase tracking-tight text-zinc-900 dark:text-white">
              {card.client_name}
            </h2>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              {card.equipment_type} • Modelo: <strong className="text-zinc-900 dark:text-zinc-100">{card.equipment_model || 'TOLEDO PRIX'}</strong> • Série:{' '}
              <strong className="font-mono text-zinc-900 dark:text-zinc-100">{card.serial_number || 'N/I'}</strong>
            </p>
            {card.inmetro_seal && (
              <div className="pt-2 flex justify-center">
                <CopyMorph text={card.inmetro_seal} label={`Lacre IPEM: ${card.inmetro_seal}`} doneLabel="Lacre Copiado!" compact />
              </div>
            )}
          </div>

          {/* 4. Phase-Aware Labels */}
          <div className="p-4 rounded-2xl bento-inner-tile space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-extrabold uppercase tracking-wider text-zinc-900 dark:text-zinc-200">
                🏷️ Etiquetas da Balança {isOrcamentosCol ? '(Orçamentos)' : isAprovadosCol || isPendentesCol ? '(Aprovada)' : ''}
              </span>
              {isOrcamentosCol && (
                <span className="text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400">
                  Notifica na TV
                </span>
              )}
            </div>

            {isOrcamentosCol ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
                <button
                  type="button"
                  onClick={() => handleToggleLabel('URGENTE', '#EF4444')}
                  className={`px-4 py-2.5 rounded-xl border text-xs font-black flex items-center justify-between cursor-pointer transition ${
                    isUrgent ? 'bg-rose-600 text-white border-rose-600' : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800'
                  }`}
                >
                  <span>🔥 URGÊNCIA</span>
                  <span>{isUrgent ? '✓ Marcado' : '+ Marcar'}</span>
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleLabel('EM GARANTIA', '#8B5CF6')}
                  className={`px-4 py-2.5 rounded-xl border text-xs font-black flex items-center justify-between cursor-pointer transition ${
                    isWarranty ? 'bg-purple-600 text-white border-purple-600' : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800'
                  }`}
                >
                  <span>🛡️ EM GARANTIA</span>
                  <span>{isWarranty ? '✓ Marcado' : '+ Marcar'}</span>
                </button>
              </div>
            ) : (
              <div className="flex flex-wrap gap-2">
                {standardTags.map((st) => {
                  const active = isLabelActive(st.name);
                  return (
                    <button
                      key={st.name}
                      type="button"
                      onClick={() => handleToggleLabel(st.name, st.color)}
                      className={`px-3 py-1.5 rounded-full border text-xs font-bold transition cursor-pointer ${
                        active
                          ? 'text-white shadow-sm'
                          : 'bg-white dark:bg-zinc-900 border-slate-200 dark:border-zinc-800 text-slate-700 dark:text-zinc-300'
                      }`}
                      style={active ? { backgroundColor: st.color, borderColor: st.color } : undefined}
                    >
                      {st.label} {active ? '✓' : '+'}
                    </button>
                  );
                })}
                <button
                  type="button"
                  onClick={handleCustomLabel}
                  className="px-3 py-1.5 rounded-full border border-dashed border-slate-300 dark:border-zinc-700 text-xs font-bold text-slate-500 hover:border-blue-500 hover:text-blue-500 inline-flex items-center gap-1 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" /> Nova
                </button>
              </div>
            )}

            {(isAprovadosCol || isPendentesCol) && hasFaltaPeca && !isPendentesCol && (
              <div className="p-3 rounded-xl bg-orange-500/15 border border-orange-500/30 flex flex-wrap items-center justify-between gap-2">
                <span className="text-xs font-bold text-orange-600 dark:text-orange-300">
                  ⚠️ Falta Peça marcado: mova para não poluir a TV da oficina.
                </span>
                <button
                  type="button"
                  onClick={handleMoveToPendentes}
                  className="px-3.5 py-1.5 rounded-full bg-orange-500 text-slate-950 font-black text-xs inline-flex items-center gap-1.5 cursor-pointer"
                >
                  <Inbox className="w-3.5 h-3.5" />
                  Mover p/ BALANÇAS PENDENTES
                </button>
              </div>
            )}
          </div>

          {/* 5. Estágio e Transferência */}
          <div className="p-4 rounded-2xl border border-blue-500/20 bg-blue-500/[0.04] space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2 text-xs font-extrabold uppercase text-blue-600 dark:text-sky-400">
                <Activity className="w-4 h-4" />
                <span>Fase Atual: {phaseName}</span>
              </div>
              <span className="font-mono text-xs font-bold text-blue-600 dark:text-sky-400">
                Etapa {activeStepIndex + 1} de 7
              </span>
            </div>

            <div className="grid grid-cols-7 gap-1.5 h-2">
              {STEPS.map((st, i) => (
                <div
                  key={st.num}
                  className={`rounded-full transition-all ${
                    i === activeStepIndex
                      ? 'bg-blue-600 ring-2 ring-blue-400/40'
                      : i < activeStepIndex
                      ? 'bg-emerald-500'
                      : 'bg-slate-200 dark:bg-zinc-800'
                  }`}
                />
              ))}
            </div>

            <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-700 dark:text-zinc-200">
                <Layers className="w-4 h-4 text-blue-500" />
                <span>Transferir para outra coluna:</span>
              </div>
              <div className="flex items-center gap-2 w-full sm:w-auto">
                <select
                  value={targetListId}
                  onChange={(e) => setTargetListId(e.target.value)}
                  className="flex-1 sm:w-56 px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold"
                >
                  {lists.map((l) => (
                    <option key={l.id} value={l.id}>
                      {l.title} {l.id === card.list_id ? '(Atual)' : ''}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={handleMoveColumn}
                  disabled={Number(targetListId) === card.list_id}
                  className="px-4 py-2 rounded-full btn-modernize-primary text-xs inline-flex items-center gap-1.5 disabled:opacity-40 cursor-pointer"
                >
                  <ArrowRightCircle className="w-4 h-4" />
                  <span>Mover</span>
                </button>
              </div>
            </div>
          </div>

          {/* 6. Dados Editáveis & Defeito */}
          <div className="p-4 rounded-2xl bento-inner-tile space-y-3">
            <div className="flex items-center gap-2 text-xs font-extrabold uppercase text-amber-600 dark:text-amber-400">
              <AlertTriangle className="w-4 h-4" />
              <span>Defeito &amp; Anotações Internas da Recepção</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Cliente</label>
                <input
                  type="text"
                  value={clientName}
                  onChange={(e) => setClientName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-bold"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Prateleira / Local</label>
                <input
                  type="text"
                  value={shelfLocation}
                  onChange={(e) => setShelfLocation(e.target.value)}
                  placeholder="Ex: Bancada 01"
                  className="w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs"
                />
              </div>
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Defeito Relatado</label>
              <textarea
                rows={2}
                value={reportedDefect}
                onChange={(e) => setReportedDefect(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs font-mono"
              />
            </div>
            <div>
              <label className="block text-[10px] font-bold uppercase text-slate-500 mb-1">Anotações Internas (Priscila)</label>
              <textarea
                rows={2}
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                placeholder="Observações de contato, urgência ou peças..."
                className="w-full px-3 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs"
              />
            </div>
            <div className="flex justify-end">
              <MorphButton
                type="button"
                onClick={handleSaveDetails}
                state={saveBtnState}
                labels={{ idle: 'Salvar Alterações', loading: 'Salvando...', done: 'Salvo!' }}
              />
            </div>
          </div>

          {/* 8. Laudo Técnico / Metrologia / Peças */}
          {(card.quote_data?.technical_report || card.solution || card.quote_data?.solution || (card.quote_data?.parts_items?.length || 0) > 0) && (
            <div className="p-4 rounded-2xl bento-inner-tile space-y-2.5 text-xs">
              <div className="flex items-center gap-2 font-extrabold uppercase text-emerald-600 dark:text-emerald-400">
                <Wrench className="w-4 h-4" />
                <span>Folha Técnica &amp; Laudo ({card.evaluator_tech || card.tech_name || 'Oficina'})</span>
              </div>
              {card.quote_data?.technical_report && (
                <p className="p-2.5 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800">
                  <strong>Laudo:</strong> {card.quote_data.technical_report}
                </p>
              )}
              {(card.solution || card.quote_data?.solution) && (
                <p className="p-2.5 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800">
                  <strong>Solução:</strong> {card.solution || card.quote_data?.solution}
                </p>
              )}
              {card.quote_data?.parts_items?.length > 0 && (
                <div className="space-y-1">
                  <strong>Peças Selecionadas:</strong>
                  <div className="flex flex-wrap gap-1.5">
                    {card.quote_data.parts_items.map((pt, i) => (
                      <span key={i} className="px-2.5 py-1 rounded-lg bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-mono text-[11px]">
                        {pt.qty}x [{pt.code}] {pt.description}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(card.quote_data?.weights_initial || {}).map(([wk, wv]) => {
                  const d = analyzeWeightDiff(wk, wv);
                  if (!d) return null;
                  return (
                    <span
                      key={wk}
                      className={`px-2 py-0.5 rounded-lg font-mono text-[10.5px] font-bold border ${
                        d.isDiff
                          ? 'bg-amber-500/15 text-amber-600 border-amber-500/30'
                          : 'bg-emerald-500/10 text-emerald-600 border-emerald-500/30'
                      }`}
                    >
                      {wk}: {wv}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* 9. Fotos */}
          {allPhotos.length > 0 && (
            <div className="p-4 rounded-2xl bento-inner-tile space-y-2.5">
              <span className="text-xs font-extrabold uppercase text-zinc-900 dark:text-white flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-blue-500" />
                Fotos Anexadas ({allPhotos.length})
              </span>
              <div className="grid grid-cols-3 sm:grid-cols-5 gap-2">
                {allPhotos.map((ph, idx) => (
                  <a key={idx} href={ph.src} target="_blank" rel="noreferrer" className="group relative rounded-xl overflow-hidden border border-slate-200 dark:border-zinc-800 aspect-square block">
                    <img src={ph.src} alt={ph.group} className="w-full h-full object-cover group-hover:scale-105 transition-transform" />
                    <span className="absolute inset-x-0 bottom-0 bg-black/65 text-white text-[9px] font-bold px-1.5 py-0.5 text-center truncate">
                      {ph.group}
                    </span>
                  </a>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};
