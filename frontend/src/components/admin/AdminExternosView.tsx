import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  BellRing,
  Calendar,
  Copy,
  Download,
  Edit3,
  FileSpreadsheet,
  Image as ImageIcon,
  Maximize2,
  Plus,
  RefreshCw,
  Save,
  Trash2,
  Truck,
  X,
  XCircle,
} from 'lucide-react';
import type { ExternalOrder, RouteSummary } from '../../types';
import { apiJson, localTodayISO, playDoorbellSound } from '../../lib/api';
import { exportCompactRoutePng } from '../../lib/routePngExporter';
import { RouteCompactCard } from '../RouteCompactCard';
import { CopyMorph } from '../fluid/copy-morph/CopyMorph';
import { MOTION_EASE } from '../motion/motionTokens';

interface AdminExternosViewProps {
  onToast: (msg: string) => void;
  onPendingCountChange?: (count: number) => void;
}

export const AdminExternosView: React.FC<AdminExternosViewProps> = ({ onToast, onPendingCountChange }) => {
  const [date, setDate] = useState(localTodayISO());
  const [summary, setSummary] = useState<RouteSummary | null>(null);
  const [loading, setLoading] = useState(false);

  // Modals
  const [orderModalOpen, setOrderModalOpen] = useState(false);
  const [editingOrder, setEditingOrder] = useState<Partial<ExternalOrder> | null>(null);
  const [naoAtendidoOrder, setNaoAtendidoOrder] = useState<ExternalOrder | null>(null);
  const [naoAtendidoReason, setNaoAtendidoReason] = useState('');
  const [rescheduleDate, setRescheduleDate] = useState(localTodayISO());
  const [savedImagesOpen, setSavedImagesOpen] = useState(false);
  const [savedImages, setSavedImages] = useState<string[]>([]);
  const [previewInfo, setPreviewInfo] = useState<{
    techName: string;
    title: string;
    groups: Array<[string, ExternalOrder[]]>;
  } | null>(null);
  const [whatsappTexts, setWhatsappTexts] = useState<Record<string, string>>({});

  const loadData = async () => {
    setLoading(true);
    try {
      const res = await apiJson<{ success: boolean; summary: RouteSummary }>(
        `/api/externos/routes/summary?date=${encodeURIComponent(date)}&shift=geral`,
      );
      if (res.ok && res.data.success) {
        setSummary(res.data.summary);
        onPendingCountChange?.(res.data.summary.unassigned?.length || 0);
      }
      const txtRes = await apiJson<{ success: boolean; messages?: Record<string, string> }>(
        `/api/externos/whatsapp-text?date=${encodeURIComponent(date)}&shift=geral`,
      );
      if (txtRes.ok && txtRes.data.messages) {
        setWhatsappTexts(txtRes.data.messages);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [date]);

  const openNewOrder = (order?: ExternalOrder) => {
    if (order) {
      setEditingOrder({ ...order });
    } else {
      const now = new Date();
      setEditingOrder({
        client_name: '',
        os_number: '',
        open_date: now.toLocaleDateString('pt-BR'),
        open_time: `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`,
        sector: '',
        equipment_model: '',
        reported_defect: '',
        tasks_notes: '',
        technician: '',
        route_date: date,
        route_shift: 'geral',
      });
    }
    setOrderModalOpen(true);
  };

  const handleSaveOrder = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingOrder) return;
    const isEdit = Boolean(editingOrder.id);
    const url = isEdit ? `/api/externos/orders/${editingOrder.id}` : '/api/externos/orders';
    const method = isEdit ? 'PUT' : 'POST';
    const res = await apiJson<{ success: boolean; error?: string }>(url, {
      method,
      body: JSON.stringify({
        ...editingOrder,
        route_date: editingOrder.route_date || date,
        route_shift: editingOrder.route_shift || 'geral',
      }),
    });
    if (res.ok && res.data.success) {
      setOrderModalOpen(false);
      onToast(isEdit ? 'Chamado atualizado!' : 'Novo chamado cadastrado!');
      loadData();
    } else {
      onToast(res.data.error || 'Erro ao salvar chamado.');
    }
  };

  const handleDeleteOrder = async (orderId: number) => {
    if (!confirm('Deseja realmente excluir este chamado externo?')) return;
    const res = await apiJson<{ success: boolean }>(`/api/externos/orders/${orderId}`, { method: 'DELETE' });
    if (res.ok && res.data.success) {
      onToast('Chamado excluído.');
      loadData();
    }
  };

  const handleNotifyDirector = async () => {
    const res = await apiJson<{ success: boolean; error?: string }>('/api/externos/routes/notify-director', {
      method: 'POST',
      body: JSON.stringify({ date, shift: 'geral' }),
    });
    if (res.ok && res.data.success) {
      playDoorbellSound();
      onToast('🔔 Chamados enviados ao Sr. Jacson!');
      loadData();
    } else {
      onToast(res.data.error || 'Erro ao notificar Diretoria.');
    }
  };

  const handleAttendance = async (order: ExternalOrder, attended: boolean) => {
    if (attended) {
      const res = await apiJson<{ success: boolean }>(`/api/externos/orders/${order.id}`, {
        method: 'PUT',
        body: JSON.stringify({ attendance_status: 'attended', unattended_reason: '' }),
      });
      if (res.ok && res.data.success) {
        onToast(`✅ ${order.client_name} marcado como Atendido!`);
        loadData();
      }
    } else {
      setNaoAtendidoOrder(order);
      setNaoAtendidoReason('');
      setRescheduleDate(date);
    }
  };

  const submitNaoAtendido = async (reschedule: boolean) => {
    if (!naoAtendidoOrder) return;
    if (!naoAtendidoReason.trim()) {
      onToast('Informe o motivo do não atendimento.');
      return;
    }
    await apiJson(`/api/externos/orders/${naoAtendidoOrder.id}`, {
      method: 'PUT',
      body: JSON.stringify({
        attendance_status: 'not_attended',
        unattended_reason: naoAtendidoReason.trim(),
        technician: '',
        route_order: 0,
        status: 'pending_route',
      }),
    });
    if (reschedule) {
      await apiJson('/api/externos/orders/reschedule', {
        method: 'POST',
        body: JSON.stringify({
          order_ids: [naoAtendidoOrder.id],
          date: rescheduleDate,
          shift: 'geral',
        }),
      });
    }
    setNaoAtendidoOrder(null);
    onToast('Chamado atualizado e retornado para pendentes!');
    loadData();
  };

  const getRouteFilename = (techName: string) => {
    const cleanDate = date.split('-').reverse().join('-');
    const techClean = (techName || 'CONJUNTA').replace(/[^A-Z0-9]/gi, '_').toUpperCase();
    return `ROTA_${techClean}_${cleanDate}.png`;
  };

  const unassigned = summary?.unassigned || [];
  const technicians = summary?.technicians || {};
  const techKeys = Object.keys(technicians);
  const dateFormatted = date.split('-').reverse().join('/');
  const allTechGroups: Array<[string, ExternalOrder[]]> = techKeys.map((t) => [t, technicians[t]]);

  const captureRoute = async (
    techName: string,
    title: string,
    groups: Array<[string, ExternalOrder[]]>,
    action: 'copy' | 'download' | 'save',
  ) => {
    return exportCompactRoutePng({
      title,
      shiftLabel: '',
      dateFormatted,
      techGroups: groups,
      filename: getRouteFilename(techName),
      action,
      onToast,
    });
  };

  const saveAllImages = async () => {
    if (!summary) return;
    onToast('💾 Salvando imagens compactas em rotas_imagens/...');
    let count = 0;
    for (const tName of Object.keys(summary.technicians || {})) {
      const ok = await captureRoute(
        tName,
        `ROTA ${tName}`,
        [[tName, summary.technicians[tName]]],
        'save',
      );
      if (ok) count++;
    }
    if (await captureRoute('CONJUNTA', 'ROTA CONJUNTA GERAL', allTechGroups, 'save')) count++;
    onToast(`💾 ${count} imagem(ns) compacta(s) salva(s) em rotas_imagens/!`);
  };

  const openSavedModal = async () => {
    setSavedImagesOpen(true);
    const res = await apiJson<{ success: boolean; images: string[] }>('/api/externos/saved-images');
    if (res.ok && res.data.images) setSavedImages(res.data.images);
  };

  return (
    <div className="flex-1 overflow-y-auto p-3 sm:p-4 space-y-3">
      {/* Top Action Bar */}
      <div className="modernize-card p-3 sm:p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2.5">
          <div className="w-9 h-9 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-500 shrink-0">
            <Truck className="w-4.5 h-4.5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-xs sm:text-sm font-black uppercase tracking-wider text-zinc-900 dark:text-white">
                Chamados Externos &amp; Rotas
              </h2>
              <span
                className={`text-[10px] font-bold px-2 py-0.5 rounded-full border ${
                  summary?.status === 'finalized'
                    ? 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30'
                    : summary?.status === 'pending_director'
                    ? 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30'
                    : 'bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300 border-slate-200 dark:border-zinc-700'
                }`}
              >
                {summary?.status === 'finalized'
                  ? '✅ Liberadas pelo Sr. Jacson'
                  : summary?.status === 'pending_director'
                  ? '🔔 Aguardando Diretoria'
                  : '⏳ Pendentes'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bento-inner-tile">
            <Calendar className="w-3.5 h-3.5 text-blue-500" />
            <input
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent font-mono text-xs font-bold focus:outline-none cursor-pointer"
            />
          </div>

          <button
            type="button"
            onClick={() => openNewOrder()}
            className="px-3.5 py-1.5 rounded-full btn-modernize-light text-xs inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Novo Chamado</span>
          </button>

          <button
            type="button"
            onClick={handleNotifyDirector}
            className="px-3.5 py-1.5 rounded-full btn-modernize-primary text-xs inline-flex items-center gap-1.5 cursor-pointer"
          >
            <BellRing className="w-3.5 h-3.5" />
            <span>Enviar p/ Sr. Jacson</span>
          </button>

          <a
            href={`/api/externos/export/csv?date=${encodeURIComponent(date)}&shift=geral`}
            className="px-3 py-1.5 rounded-full bento-inner-tile text-xs font-bold inline-flex items-center gap-1.5 hover:border-emerald-500"
          >
            <FileSpreadsheet className="w-3.5 h-3.5 text-emerald-500" />
            <span>CSV</span>
          </a>

          <button
            type="button"
            onClick={loadData}
            className="p-1.5 rounded-full bento-inner-tile hover:border-blue-500 cursor-pointer"
            title="Atualizar"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-500' : ''}`} />
          </button>
        </div>
      </div>

      {/* Section 1: Pending Calls (Compact) */}
      <div className="modernize-card p-3.5 space-y-2">
        <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-2">
          <h3 className="text-xs font-black uppercase tracking-wider text-zinc-900 dark:text-white">
            📋 Chamados Pendentes de Rota ({unassigned.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[11.5px]">
            <thead>
              <tr className="text-[10px] font-black uppercase text-slate-500 dark:text-zinc-400 border-b border-slate-200 dark:border-zinc-800">
                <th className="py-1.5 px-2.5">Cliente</th>
                <th className="py-1.5 px-2 text-center">O.S.</th>
                <th className="py-1.5 px-2.5">Setor / Modelo</th>
                <th className="py-1.5 px-2.5">Defeito</th>
                <th className="py-1.5 px-2.5">Obs.</th>
                <th className="py-1.5 px-2 text-center">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-zinc-800">
              {unassigned.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-4 text-center text-xs text-slate-400">
                    Nenhum chamado pendente de rota.
                  </td>
                </tr>
              ) : (
                unassigned.map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50/70 dark:hover:bg-zinc-900/50">
                    <td className="py-1.5 px-2.5 font-extrabold text-zinc-900 dark:text-white">
                      {o.client_name}
                      {o.attendance_status === 'not_attended' && (
                        <span className="ml-1.5 px-1.5 py-0.5 rounded-full text-[9px] bg-rose-500/15 text-rose-600 dark:text-rose-400">
                          Não At.: {o.unattended_reason}
                        </span>
                      )}
                    </td>
                    <td className="py-1.5 px-2 text-center font-mono font-bold text-blue-600 dark:text-sky-400 whitespace-nowrap">
                      {o.os_number || 'S/N'}
                    </td>
                    <td className="py-1.5 px-2.5 text-slate-600 dark:text-zinc-300">
                      {[o.sector, o.equipment_model].filter(Boolean).join(' • ') || '-'}
                    </td>
                    <td className="py-1.5 px-2.5">{o.reported_defect || '-'}</td>
                    <td className="py-1.5 px-2.5 text-rose-500 font-semibold">{o.tasks_notes || '-'}</td>
                    <td className="py-1.5 px-2 text-center">
                      <div className="inline-flex gap-1">
                        <button
                          type="button"
                          onClick={() => openNewOrder(o)}
                          className="p-1 rounded-lg text-blue-500 hover:bg-blue-500/10 cursor-pointer"
                          title="Editar"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDeleteOrder(o.id)}
                          className="p-1 rounded-lg text-rose-500 hover:bg-rose-500/10 cursor-pointer"
                          title="Excluir"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Section 2: Finalized Routes & WhatsApp Export (Compact View) */}
      {techKeys.length > 0 && (
        <div className="space-y-3">
          <div className="modernize-card p-3 sm:p-3.5 flex flex-wrap items-center justify-between gap-2.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs font-black uppercase tracking-wider text-zinc-900 dark:text-white">
                🗺️ Rotas Montadas ({techKeys.length} Equipe(s))
              </span>
              <span className="text-[11px] font-mono font-bold px-2 py-0.5 rounded-full bg-slate-100 dark:bg-zinc-800 text-slate-600 dark:text-zinc-300">
                {dateFormatted}
              </span>
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              {whatsappTexts.CONJUNTA && (
                <CopyMorph text={whatsappTexts.CONJUNTA} label="Texto Geral" doneLabel="Copiado!" compact />
              )}
              <button
                type="button"
                onClick={() => captureRoute('CONJUNTA', 'ROTA CONJUNTA GERAL', allTechGroups, 'copy')}
                className="px-3 py-1.5 rounded-full bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-[11px] inline-flex items-center gap-1 cursor-pointer"
                title="Copiar imagem da Rota Conjunta Geral para colar no WhatsApp"
              >
                <Copy className="w-3 h-3" /> Conjunta Img
              </button>
              <button
                type="button"
                onClick={() => captureRoute('CONJUNTA', 'ROTA CONJUNTA GERAL', allTechGroups, 'download')}
                className="px-3 py-1.5 rounded-full btn-modernize-light text-[11px] inline-flex items-center gap-1 cursor-pointer"
              >
                <Download className="w-3 h-3" /> Conjunta PNG
              </button>
              <button
                type="button"
                onClick={() =>
                  setPreviewInfo({
                    techName: 'CONJUNTA',
                    title: 'ROTA CONJUNTA GERAL',
                    groups: allTechGroups,
                  })
                }
                className="px-2.5 py-1.5 rounded-full bento-inner-tile text-[11px] font-bold inline-flex items-center gap-1 cursor-pointer"
              >
                <Maximize2 className="w-3 h-3" /> Visualizar
              </button>
              <button
                type="button"
                onClick={saveAllImages}
                className="px-3 py-1.5 rounded-full btn-modernize-primary text-[11px] inline-flex items-center gap-1 cursor-pointer"
              >
                <Save className="w-3 h-3" />
                <span>Salvar Todas</span>
              </button>
              <button
                type="button"
                onClick={openSavedModal}
                className="px-2.5 py-1.5 rounded-full bento-inner-tile text-[11px] font-bold inline-flex items-center gap-1 cursor-pointer"
              >
                <ImageIcon className="w-3 h-3 text-purple-500" />
                <span>Salvas</span>
              </button>
            </div>
          </div>

          {/* Compact Individual Tech Route Cards */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-3">
            {techKeys.map((tName) => {
              const stops = technicians[tName] || [];
              const singleGroup: Array<[string, ExternalOrder[]]> = [[tName, stops]];
              return (
                <div key={tName} className="modernize-card p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2 pb-1.5 border-b border-slate-200/80 dark:border-zinc-800">
                    <div className="flex items-center gap-2 min-w-0">
                      <h4 className="text-xs font-black uppercase text-zinc-900 dark:text-white truncate">
                        🔧 {tName}
                      </h4>
                      <span className="font-mono text-[10px] font-black px-2 py-0.5 rounded-full bg-blue-500/12 text-blue-700 dark:text-sky-400 border border-blue-500/20">
                        {stops.length} parada{stops.length > 1 ? 's' : ''}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-1">
                      {whatsappTexts[tName] && (
                        <CopyMorph text={whatsappTexts[tName]} label="Texto" doneLabel="Copiado!" compact />
                      )}
                      <button
                        type="button"
                        onClick={() => captureRoute(tName, `ROTA ${tName}`, singleGroup, 'copy')}
                        className="px-2.5 py-1 rounded-full btn-modernize-primary text-[11px] inline-flex items-center gap-1 cursor-pointer"
                      >
                        <Copy className="w-3 h-3" /> Imagem
                      </button>
                      <button
                        type="button"
                        onClick={() => captureRoute(tName, `ROTA ${tName}`, singleGroup, 'download')}
                        className="px-2.5 py-1 rounded-full bento-inner-tile text-[11px] font-bold inline-flex items-center gap-1 cursor-pointer"
                      >
                        <Download className="w-3 h-3" /> PNG
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setPreviewInfo({
                            techName: tName,
                            title: `ROTA ${tName}`,
                            groups: singleGroup,
                          })
                        }
                        className="p-1.5 rounded-full bento-inner-tile text-[11px] cursor-pointer"
                        title="Visualizar card mobile"
                      >
                        <Maximize2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>

                  {/* Lista compacta de paradas */}
                  <div className="space-y-1.5">
                    {stops.map((s, idx) => (
                      <div
                        key={s.id}
                        className="px-2.5 py-1.5 rounded-xl bg-slate-50/80 dark:bg-zinc-900/75 border border-slate-200/80 dark:border-zinc-800 flex items-center justify-between gap-2"
                      >
                        <div className="flex items-start gap-2 min-w-0 flex-1">
                          <span className="w-5 h-5 mt-0.5 rounded-md bg-blue-600 text-white font-mono font-black text-[10px] flex items-center justify-center shrink-0">
                            {idx + 1}º
                          </span>
                          <div className="min-w-0 flex-1 space-y-0.5 text-[11px] leading-snug">
                            <div className="flex items-center gap-1.5 flex-wrap">
                              <strong className="font-black uppercase text-zinc-900 dark:text-white">
                                {s.client_name}
                              </strong>
                              <span className="font-mono text-[9.5px] font-bold px-1.5 py-0.2 rounded bg-blue-50 dark:bg-blue-950/60 text-blue-700 dark:text-sky-300 border border-blue-200 dark:border-blue-800 shrink-0">
                                {s.os_number ? `OS ${s.os_number}` : 'S/N'}
                              </span>
                              {s.sector && (
                                <span className="text-slate-500 dark:text-zinc-400">• {s.sector}</span>
                              )}
                              {s.equipment_model && (
                                <span className="text-slate-500 dark:text-zinc-400">• {s.equipment_model}</span>
                              )}
                            </div>
                            {s.reported_defect && (
                              <div className="text-slate-700 dark:text-zinc-300">
                                {s.reported_defect}
                              </div>
                            )}
                            {s.tasks_notes && (
                              <div className="inline-block px-2 py-0.5 rounded-md bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-rose-600 dark:text-rose-400 font-extrabold text-[10.5px] uppercase">
                                ⚠️ {s.tasks_notes}
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="flex flex-col sm:flex-row items-end sm:items-center gap-1 shrink-0">
                          <button
                            type="button"
                            onClick={() => handleAttendance(s, true)}
                            className={`px-2 py-1 rounded-lg text-[10px] font-bold cursor-pointer transition ${
                              s.attendance_status === 'attended'
                                ? 'bg-emerald-600 text-white shadow-xs'
                                : 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 hover:bg-emerald-500/25'
                            }`}
                          >
                            ✓ At.
                          </button>
                          <button
                            type="button"
                            onClick={() => handleAttendance(s, false)}
                            className="px-2 py-1 rounded-lg text-[10px] font-bold bg-rose-500/15 text-rose-700 dark:text-rose-400 hover:bg-rose-500/25 cursor-pointer transition"
                            title="Não Atendido"
                          >
                            ✕ Não
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Modal: New/Edit Order */}
      <AnimatePresence>
        {orderModalOpen && editingOrder && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={(e) => e.target === e.currentTarget && setOrderModalOpen(false)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              transition={{ duration: 0.2, ease: MOTION_EASE }}
              className="w-full max-w-lg modernize-card p-6 space-y-4"
            >
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
                <h3 className="text-sm font-extrabold text-zinc-900 dark:text-white">
                  {editingOrder.id ? `Editar Chamado O.S. ${editingOrder.os_number || ''}` : 'Cadastrar Chamado Externo'}
                </h3>
                <button type="button" onClick={() => setOrderModalOpen(false)} className="p-1 text-slate-400 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <form onSubmit={handleSaveOrder} className="space-y-3 text-xs">
                <div className="grid grid-cols-2 gap-3">
                  <input
                    type="text"
                    required
                    placeholder="Cliente *"
                    value={editingOrder.client_name || ''}
                    onChange={(e) => setEditingOrder({ ...editingOrder, client_name: e.target.value })}
                    className="col-span-2 px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-bold"
                  />
                  <input
                    type="text"
                    placeholder="Nº O.S."
                    value={editingOrder.os_number || ''}
                    onChange={(e) => setEditingOrder({ ...editingOrder, os_number: e.target.value })}
                    className="px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 font-mono"
                  />
                  <input
                    type="text"
                    placeholder="Setor / Bairro"
                    value={editingOrder.sector || ''}
                    onChange={(e) => setEditingOrder({ ...editingOrder, sector: e.target.value })}
                    className="px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800"
                  />
                  <input
                    type="text"
                    placeholder="Modelo do Equipamento"
                    value={editingOrder.equipment_model || ''}
                    onChange={(e) => setEditingOrder({ ...editingOrder, equipment_model: e.target.value })}
                    className="col-span-2 px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800"
                  />
                  <input
                    type="text"
                    placeholder="Defeito Relatado"
                    value={editingOrder.reported_defect || ''}
                    onChange={(e) => setEditingOrder({ ...editingOrder, reported_defect: e.target.value })}
                    className="col-span-2 px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800"
                  />
                  <input
                    type="text"
                    placeholder="Observações / Tarefas"
                    value={editingOrder.tasks_notes || ''}
                    onChange={(e) => setEditingOrder({ ...editingOrder, tasks_notes: e.target.value })}
                    className="col-span-2 px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800"
                  />
                </div>
                <div className="flex justify-end gap-2 pt-2">
                  <button
                    type="button"
                    onClick={() => setOrderModalOpen(false)}
                    className="px-4 py-2 rounded-full bg-slate-100 dark:bg-zinc-800 font-bold cursor-pointer"
                  >
                    Cancelar
                  </button>
                  <button type="submit" className="px-5 py-2 rounded-full btn-modernize-primary cursor-pointer">
                    Salvar Chamado
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal: Não Atendido */}
      <AnimatePresence>
        {naoAtendidoOrder && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={(e) => e.target === e.currentTarget && setNaoAtendidoOrder(null)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              initial={{ opacity: 0, scale: 0.94, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 10 }}
              className="w-full max-w-md modernize-card p-6 space-y-4"
            >
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
                <div className="flex items-center gap-2 text-rose-500">
                  <XCircle className="w-5 h-5" />
                  <h3 className="text-sm font-extrabold">Motivo do Não Atendimento</h3>
                </div>
                <button type="button" onClick={() => setNaoAtendidoOrder(null)} className="p-1 text-slate-400 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <p className="text-xs font-bold text-zinc-900 dark:text-white">
                {naoAtendidoOrder.client_name} (O.S. {naoAtendidoOrder.os_number || 'S/N'})
              </p>
              <div className="flex flex-wrap gap-1.5">
                {['Falta de tempo / Rota cheia', 'Estabelecimento fechado', 'Faltou peça', 'Cliente remarcou'].map((r) => (
                  <button
                    key={r}
                    type="button"
                    onClick={() => setNaoAtendidoReason(r)}
                    className="px-2.5 py-1 rounded-full text-[11px] font-bold bento-inner-tile hover:border-rose-400 cursor-pointer"
                  >
                    {r}
                  </button>
                ))}
              </div>
              <textarea
                rows={2}
                value={naoAtendidoReason}
                onChange={(e) => setNaoAtendidoReason(e.target.value)}
                placeholder="Descreva o motivo..."
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 text-xs"
              />
              <div className="text-xs">
                <label className="block font-bold text-slate-500 dark:text-zinc-400 mb-1">
                  Remarcar para a data:
                </label>
                <input
                  type="date"
                  value={rescheduleDate}
                  onChange={(e) => setRescheduleDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl bento-inner-tile font-mono font-bold"
                />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => submitNaoAtendido(false)}
                  className="px-4 py-2 rounded-full bg-slate-200 dark:bg-zinc-800 text-xs font-bold cursor-pointer"
                >
                  Deixar Pendente
                </button>
                <button
                  type="button"
                  onClick={() => submitNaoAtendido(true)}
                  className="px-4 py-2 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold cursor-pointer"
                >
                  Remarcar Chamado
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal: Saved Images */}
      <AnimatePresence>
        {savedImagesOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={(e) => e.target === e.currentTarget && setSavedImagesOpen(false)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              initial={{ opacity: 0, scale: 0.94 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="w-full max-w-2xl modernize-card p-6 max-h-[85vh] overflow-y-auto space-y-4"
            >
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
                <h3 className="text-sm font-extrabold">Histórico em rotas_imagens/ ({savedImages.length})</h3>
                <button type="button" onClick={() => setSavedImagesOpen(false)} className="p-1 text-slate-400 cursor-pointer">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {savedImages.map((fname) => (
                  <div key={fname} className="p-3 bento-inner-tile space-y-2">
                    <div className="font-mono text-[11px] font-bold truncate">{fname}</div>
                    <img src={`/api/externos/images/${encodeURIComponent(fname)}`} alt={fname} className="w-full h-36 object-contain bg-white rounded-xl" />
                  </div>
                ))}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modal: Preview Card */}
      <AnimatePresence>
        {previewInfo && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={(e) => e.target === e.currentTarget && setPreviewInfo(null)}
          >
            <motion.div
              role="dialog"
              aria-modal="true"
              className="w-full max-w-xl modernize-card p-5 space-y-4 max-h-[90vh] overflow-y-auto"
            >
              <div className="flex items-center justify-between gap-2">
                <h3 className="text-sm font-extrabold">Visualização Compacta ({previewInfo.techName})</h3>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => captureRoute(previewInfo.techName, previewInfo.title, previewInfo.groups, 'copy')}
                    className="px-4 py-1.5 rounded-full btn-modernize-primary text-xs cursor-pointer"
                  >
                    Copiar Imagem
                  </button>
                  <button
                    type="button"
                    onClick={() => captureRoute(previewInfo.techName, previewInfo.title, previewInfo.groups, 'download')}
                    className="px-4 py-1.5 rounded-full bento-inner-tile text-xs font-bold cursor-pointer"
                  >
                    Baixar PNG
                  </button>
                  <button type="button" onClick={() => setPreviewInfo(null)} className="p-1.5 text-slate-400 cursor-pointer">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="flex justify-center">
                <RouteCompactCard
                  title={previewInfo.title}
                  dateFormatted={dateFormatted}
                  techGroups={previewInfo.groups}
                />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};
