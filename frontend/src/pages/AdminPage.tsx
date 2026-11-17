import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Bell,
  Camera,
  CloudUpload,
  KeyRound,
  LayoutDashboard,
  LogOut,
  Megaphone,
  Moon,
  Plus,
  Search,
  Shield,
  Sun,
  Truck,
  Unlock,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import type { AuthUser, BoardData, KanbanCard, KanbanList, PendingEntry } from '../types';
import { apiJson, getBootConfig, getSocket, playDoorbellSound, playNotificationBeep } from '../lib/api';
import { A5Logo } from '../components/A5Logo';
import { useTheme } from '../components/ThemeProvider';
import { PillTabs } from '../components/fluid/pill-tabs/PillTabs';
import { IslandToast } from '../components/fluid/island-toast/IslandToast';
import { ChatWidget } from '../components/ChatWidget';
import { PasswordModal } from '../components/PasswordModal';
import { KanbanBoard } from '../components/admin/KanbanBoard';
import { NewOsModal } from '../components/admin/NewOsModal';
import { CardDetailModal } from '../components/admin/CardDetailModal';
import { CallTechModal, DeleteAuthModal, PendingPhotosModal } from '../components/admin/AdminModals';
import { AdminExternosView } from '../components/admin/AdminExternosView';
import { MOTION_EASE } from '../components/motion/motionTokens';

interface AdminPageProps {
  user: AuthUser;
  onNavigate?: (path: string) => void;
  onLogout: () => void;
  onReady?: () => void;
}

export const AdminPage: React.FC<AdminPageProps> = ({ user, onNavigate, onLogout, onReady }) => {
  const { theme, toggleTheme } = useTheme();
  const boot = getBootConfig();

  const [view, setView] = useState<'kanban' | 'externos'>('kanban');
  const [board, setBoard] = useState<BoardData | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFilter, setActiveFilter] = useState('todos');
  const [connected, setConnected] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const [extPendingBadge, setExtPendingBadge] = useState(0);

  // Cloud Backup 16h40 reminder
  const [showCloudBanner, setShowCloudBanner] = useState(false);
  const [cloudBackingUp, setCloudBackingUp] = useState(false);

  // Modals
  const [newOsOpen, setNewOsOpen] = useState(false);
  const [selectedPendingEntry, setSelectedPendingEntry] = useState<PendingEntry | null>(null);
  const [pendingPhotosOpen, setPendingPhotosOpen] = useState(false);
  const [callTechOpen, setCallTechOpen] = useState(false);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [detailCard, setDetailCard] = useState<KanbanCard | null>(null);
  const [deleteCardTarget, setDeleteCardTarget] = useState<KanbanCard | null>(null);
  const ignoreSocketBoardUntilRef = useRef(0);

  const showToast = useCallback((msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg((cur) => (cur === msg ? null : cur)), 3200);
  }, []);

  const fetchBoard = useCallback(async () => {
    const res = await apiJson<BoardData>('/api/board');
    if (res.ok && res.data?.lists) {
      setBoard(res.data);
    }
  }, []);

  const checkCloudBackup = async () => {
    const now = new Date();
    const day = now.getDay();
    const mins = now.getHours() * 60 + now.getMinutes();
    if (day >= 1 && day <= 5 && mins >= 16 * 60 + 40) {
      const res = await apiJson<{ synced_today?: boolean }>('/api/backup/github-status');
      if (res.ok && !res.data.synced_today) setShowCloudBanner(true);
    }
  };

  useEffect(() => {
    fetchBoard().finally(() => onReady?.());
    checkCloudBackup();
    const backupTimer = setInterval(checkCloudBackup, 60000);

    const socket = getSocket();
    setConnected(socket.connected);
    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);
    const onBoard = (data: BoardData) => {
      if (Date.now() < ignoreSocketBoardUntilRef.current) return;
      setBoard(data);
    };
    const onAdminNotif = (payload: { message?: string }) => {
      playNotificationBeep();
      if (payload?.message) showToast(payload.message);
      fetchBoard();
    };
    const onRouteFinalized = () => {
      playDoorbellSound();
      showToast('🚚 Sr. Jacson liberou as rotas externas!');
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('board_updated', onBoard);
    socket.on('admin_notification', onAdminNotif);
    socket.on('external_routes_finalized', onRouteFinalized);

    return () => {
      clearInterval(backupTimer);
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('board_updated', onBoard);
      socket.off('admin_notification', onAdminNotif);
      socket.off('external_routes_finalized', onRouteFinalized);
    };
  }, []);

  const openCardDetail = useCallback(async (osNumber: string) => {
    const res = await apiJson<KanbanCard & { error?: string }>(`/api/cards/${encodeURIComponent(osNumber)}`);
    if (res.ok && res.data?.id) {
      setDetailCard(res.data);
    } else {
      showToast(res.data?.error || 'O.S. não encontrada.');
    }
  }, [showToast]);

  const handleRefreshDetail = async (reopenOs?: string) => {
    await fetchBoard();
    if (reopenOs) {
      await openCardDetail(reopenOs);
    }
  };

  const handleMoveCard = useCallback(async (cardId: number, targetListId: number, newPosition: number, orderedCardIds: number[]) => {
    let sourceListId: number | null = null;
    // Atualização otimista instantânea no cliente preservando referência das colunas intocadas
    setBoard((prev) => {
      if (!prev?.lists) return prev;
      let movedCard: KanbanCard | undefined;
      for (const l of prev.lists) {
        const found = l.cards.find((c) => c.id === cardId);
        if (found) {
          movedCard = found;
          sourceListId = l.id;
          break;
        }
      }
      if (!movedCard) return prev;
      const targetListTitle = prev.lists.find((l) => l.id === targetListId)?.title || movedCard.list_title;
      const orderIndex = new Map<number, number>(orderedCardIds.map((id, i) => [id, i]));
      const nextLists = prev.lists.map((l) => {
        if (l.id !== targetListId && l.id !== sourceListId) {
          return l;
        }
        if (l.id !== targetListId) {
          return { ...l, cards: l.cards.filter((c) => c.id !== cardId) };
        }
        const cleaned = l.cards.filter((c) => c.id !== cardId);
        const updatedCard: KanbanCard = { ...movedCard!, list_id: targetListId, list_title: targetListTitle };
        const merged = [...cleaned, updatedCard];
        merged.sort((a, b) => {
          const ia = orderIndex.get(a.id);
          const ib = orderIndex.get(b.id);
          if (ia !== undefined && ib !== undefined) return ia - ib;
          if (ia !== undefined) return -1;
          if (ib !== undefined) return 1;
          return 0;
        });
        return { ...l, cards: merged };
      });
      return { ...prev, lists: nextLists };
    });

    ignoreSocketBoardUntilRef.current = Date.now() + 1400;
    const res = await apiJson<{ success?: boolean; board?: BoardData; error?: string }>(`/api/cards/${cardId}/move`, {
      method: 'POST',
      body: JSON.stringify({
        target_list_id: targetListId,
        new_position: newPosition,
        ordered_card_ids: orderedCardIds,
        actor: user.display_name || 'Priscila (Recepção)',
      }),
    });
    if (res.ok && res.data.board) {
      const serverBoard = res.data.board;
      setBoard((prev) => {
        if (!prev?.lists) return serverBoard;
        const prevById = new Map(prev.lists.map((l) => [l.id, l]));
        return {
          ...serverBoard,
          lists: serverBoard.lists.map((srvList) => {
            if (srvList.id !== targetListId && srvList.id !== sourceListId) {
              const oldList = prevById.get(srvList.id);
              if (oldList && oldList.cards.length === srvList.cards.length && oldList.title === srvList.title) {
                return oldList;
              }
            }
            return srvList;
          }),
        };
      });
    } else if (!res.ok) {
      ignoreSocketBoardUntilRef.current = 0;
      showToast(res.data.error || 'Erro ao mover cartão.');
      fetchBoard();
    }
  }, [fetchBoard, showToast, user.display_name]);

  const handleAdvanceAdmin = useCallback(async (osNumber: string, action: string) => {
    let url = '/api/esteira/adm-enviar-cliente';
    if (action === 'aprovar') url = '/api/esteira/adm-aprovar';
    else if (action === 'nao_autorizado') url = '/api/esteira/adm-nao-autorizar';
    else if (action === 'fechar_balanca') url = '/api/esteira/fechar-balanca';

    const res = await apiJson<{ success?: boolean; error?: string }>(url, {
      method: 'POST',
      body: JSON.stringify({ os_number: osNumber, action }),
    });
    if (res.ok && res.data.success) {
      const msgMap: Record<string, string> = {
        aprovar: `✅ O.S. ${osNumber} aprovada! TV avisada.`,
        nao_autorizado: `🚫 O.S. ${osNumber} marcada como NÃO AUTORIZADA.`,
        fechar_balanca: `🏁 O.S. ${osNumber} fechada e finalizada!`,
        enviar_cliente: `📤 O.S. ${osNumber} enviada ao cliente!`,
      };
      showToast(msgMap[action] || `O.S. ${osNumber} atualizada!`);
      setDetailCard((cur) => (cur?.os_number === osNumber ? null : cur));
      fetchBoard();
    } else {
      showToast(res.data.error || 'Erro ao avançar O.S.');
    }
  }, [fetchBoard, showToast]);

  const handleCloudBackup = async () => {
    setCloudBackingUp(true);
    showToast('☁️ Enviando banco de dados para o GitHub...');
    const res = await apiJson<{ success: boolean; message?: string; error?: string }>('/api/backup/github-cloud', {
      method: 'POST',
      body: JSON.stringify({ dry_run: false }),
    });
    setCloudBackingUp(false);
    if (res.ok && res.data.success) {
      setShowCloudBanner(false);
      showToast('☁️ Backup na nuvem concluído com sucesso!');
    } else {
      showToast(res.data.error || 'Falha ao subir backup para o GitHub.');
    }
  };

  const handleCreateList = useCallback(async () => {
    const title = prompt('Nome da nova coluna:');
    if (!title?.trim()) return;
    await apiJson('/api/lists', { method: 'POST', body: JSON.stringify({ title: title.trim(), is_tech: false }) });
    fetchBoard();
  }, [fetchBoard]);

  const handleRenameList = useCallback(async (list: KanbanList) => {
    const title = prompt('Novo nome da coluna:', list.title);
    if (!title?.trim()) return;
    await apiJson(`/api/lists/${list.id}`, { method: 'PUT', body: JSON.stringify({ title: title.trim() }) });
    fetchBoard();
  }, [fetchBoard]);

  const handleDeleteList = useCallback(async (list: KanbanList) => {
    if (!confirm(`Remover coluna vazia "${list.title}"?`)) return;
    await apiJson(`/api/lists/${list.id}`, { method: 'DELETE' });
    fetchBoard();
  }, [fetchBoard]);

  const lists = board?.lists || [];
  const labels = board?.labels || [];
  const pendingEntries = board?.pending_entries || [];
  const tvMuted = board?.settings?.tv_muted === '1';
  const reopenCards = lists.flatMap((l) => l.cards).filter((c) => c.reopen_requested === 1);

  const handleToggleTvSilence = async () => {
    const nextMuted = !tvMuted;
    const res = await apiJson<{ success: boolean }>('/api/admin/panic-silence', {
      method: 'POST',
      body: JSON.stringify({ muted: nextMuted }),
    });
    if (res.ok && res.data.success) {
      showToast(nextMuted ? '🔇 TV da oficina silenciada.' : '🔊 Som da TV reativado.');
      fetchBoard();
    }
  };

  const handleDeletePendingEntry = async (entryId: number) => {
    if (!confirm('Excluir esta pré-entrada de fotos?')) return;
    const res = await apiJson<{ success: boolean }>(`/api/pending-entries/${entryId}`, { method: 'DELETE' });
    if (res.ok && res.data.success) {
      showToast('Pré-entrada removida.');
      fetchBoard();
    }
  };

  return (
    <div className="min-h-screen h-screen flex flex-col overflow-hidden">
      {/* Floating IslandToast abaixo do header para não sobrepor as abas */}
      <div className="fixed top-[72px] inset-x-0 z-[80] pointer-events-none">
        <IslandToast message={toastMsg} />
      </div>

      {/* Top Bento Header */}
      <header className="px-4 sm:px-6 py-3 bg-white/95 dark:bg-zinc-950/95 border-b border-slate-200/80 dark:border-zinc-800/80 flex flex-wrap items-center justify-between gap-3 z-30 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <A5Logo variant="full" size="sm" />
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/12 text-blue-600 dark:text-sky-400 border border-blue-500/20 text-[10.5px] font-extrabold uppercase tracking-wider">
            <span className={`w-2 h-2 rounded-full ${connected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
            Recepção • {user.display_name.split(' ')[0]}
          </span>
        </div>

        <div className="flex items-center justify-center">
          <PillTabs
            label="Módulos da Recepção"
            value={view}
            onChange={(val) => setView(val as 'kanban' | 'externos')}
            tabs={[
              {
                value: 'kanban',
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <LayoutDashboard className="w-3.5 h-3.5" /> Esteira Kanban
                  </span>
                ),
                count: board?.stats?.total_active,
              },
              {
                value: 'externos',
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <Truck className="w-3.5 h-3.5" /> Externos &amp; Rotas
                  </span>
                ),
                count: extPendingBadge || undefined,
              },
            ]}
          />
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button
            type="button"
            onClick={() => {
              setSelectedPendingEntry(null);
              setNewOsOpen(true);
            }}
            className="px-3.5 py-2 rounded-full btn-modernize-primary text-xs inline-flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Nova O.S.</span>
          </button>

          <button
            type="button"
            onClick={() => setPendingPhotosOpen(true)}
            className="relative px-3 py-2 rounded-full bento-inner-tile hover:border-blue-500 text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
            title="Fotos da Recepção (Pré-Entrada)"
          >
            <Camera className="w-3.5 h-3.5 text-sky-500" />
            <span className="hidden lg:inline">Pré-Entrada</span>
            {pendingEntries.length > 0 && (
              <span className="px-1.5 py-0.5 rounded-full bg-sky-500 text-white text-[10px] font-black tabular-nums leading-none">
                {pendingEntries.length}
              </span>
            )}
          </button>

          <button
            type="button"
            onClick={() => setCallTechOpen(true)}
            className="px-3 py-2 rounded-full bento-inner-tile hover:border-amber-500 text-xs font-bold inline-flex items-center gap-1.5 cursor-pointer"
            title="Chamar Técnico / ADM na TV"
          >
            <Megaphone className="w-3.5 h-3.5 text-amber-500" />
            <span className="hidden xl:inline">Chamar TV</span>
          </button>

          <button
            type="button"
            onClick={handleToggleTvSilence}
            className={`p-2 rounded-full border cursor-pointer transition ${
              tvMuted
                ? 'bg-rose-500/15 border-rose-500/40 text-rose-500'
                : 'bento-inner-tile text-slate-500 hover:border-blue-500'
            }`}
            title={tvMuted ? 'TV Silenciada (clique para ativar som)' : 'Silenciar avisos na TV'}
          >
            {tvMuted ? <VolumeX className="w-4 h-4" /> : <Volume2 className="w-4 h-4 text-sky-500" />}
          </button>

          {user.role === 'master' && (
            <button
              type="button"
              onClick={() => (onNavigate ? onNavigate('/diretoria') : (window.location.href = '/diretoria'))}
              className="px-3 py-2 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-600 dark:text-amber-400 text-xs font-extrabold inline-flex items-center gap-1 cursor-pointer"
              title="Trocar para Diretoria (Master)"
            >
              <Shield className="w-3.5 h-3.5" />
              <span className="hidden xl:inline">Diretoria</span>
            </button>
          )}

          <button
            type="button"
            onClick={handleCloudBackup}
            disabled={cloudBackingUp}
            className="p-2 rounded-full bento-inner-tile hover:border-emerald-500 cursor-pointer"
            title="Subir Backup p/ GitHub"
          >
            <CloudUpload className={`w-4 h-4 text-emerald-500 ${cloudBackingUp ? 'animate-pulse' : ''}`} />
          </button>

          <button
            type="button"
            onClick={toggleTheme}
            className="p-2 rounded-full bento-inner-tile cursor-pointer"
            title="Alternar tema Claro/Escuro"
          >
            {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-blue-600" />}
          </button>

          <button
            type="button"
            onClick={() => setPasswordModalOpen(true)}
            className="p-2 rounded-full bento-inner-tile cursor-pointer"
            title="Alterar Senha"
          >
            <KeyRound className="w-4 h-4 text-slate-500" />
          </button>

          <button
            type="button"
            onClick={onLogout}
            className="px-3 py-2 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 text-xs font-bold inline-flex items-center gap-1 cursor-pointer"
          >
            <LogOut className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Sair</span>
          </button>
        </div>
      </header>

      {/* Cloud Backup 16h40 Banner */}
      <AnimatePresence>
        {showCloudBanner && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="px-5 py-2.5 bg-gradient-to-r from-[#1E3A8A] via-[#1D4ED8] to-[#0F172A] text-white flex flex-wrap items-center justify-between gap-3 z-20 shrink-0"
          >
            <div className="flex items-center gap-2.5 text-xs">
              <Bell className="w-4 h-4 text-amber-300 animate-bounce" />
              <span className="font-extrabold">Lembrete 16h40:</span>
              <span>Salve as O.S. de hoje na nuvem (GitHub joaovotonic/a5_processos).</span>
            </div>
            <button
              type="button"
              onClick={handleCloudBackup}
              className="px-3.5 py-1.5 rounded-full bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-black text-xs cursor-pointer"
            >
              ☁️ Subir Banco Agora
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Reopen Requests Alert Banner */}
      {reopenCards.length > 0 && view === 'kanban' && (
        <div className="px-5 py-2 bg-amber-500/12 border-b border-amber-500/30 flex flex-wrap items-center justify-between gap-2 text-xs shrink-0">
          <div className="flex items-center gap-2 font-bold text-amber-700 dark:text-amber-300">
            <Unlock className="w-4 h-4" />
            <span>Pedidos de Reabertura de Orçamento ({reopenCards.length}):</span>
            {reopenCards.map((rc) => (
              <button
                key={rc.id}
                type="button"
                onClick={() => openCardDetail(rc.os_number)}
                className="px-2.5 py-0.5 rounded-full bg-amber-500 text-slate-950 font-black text-[11px] cursor-pointer"
              >
                OS {rc.os_number} ({rc.reopen_requested_by || 'Técnico'})
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Subbar Filters (Kanban view) */}
      {view === 'kanban' && (
        <div className="px-4 sm:px-6 py-2.5 bg-white/60 dark:bg-zinc-950/60 border-b border-slate-200/70 dark:border-zinc-800/70 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="relative w-full sm:w-80">
            <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Buscar O.S., cliente, modelo, lacre..."
              className="w-full pl-9 pr-8 py-1.5 rounded-full bento-inner-tile text-xs font-semibold focus:border-blue-500 focus:outline-none"
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-zinc-900 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-1.5">
            {[
              { id: 'todos', label: 'Todos' },
              { id: 'urgente', label: '🔥 Urgentes' },
              { id: 'sla', label: '⏱️ +24h SLA' },
              { id: 'estufa', label: '🌡️ Estufa Ativa' },
              { id: 'reabrir', label: '🔓 Reaberturas' },
            ].map((f) => (
              <button
                key={f.id}
                type="button"
                onClick={() => setActiveFilter(f.id)}
                className={`px-3 py-1.5 rounded-full text-[11px] font-bold transition cursor-pointer ${
                  activeFilter === f.id
                    ? 'btn-modernize-primary'
                    : 'bento-inner-tile text-slate-600 dark:text-zinc-300 hover:border-blue-400'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Main Content */}
      <AnimatePresence mode="wait">
        {view === 'kanban' ? (
          <motion.div
            key="kanban-view"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: MOTION_EASE }}
            className="flex-1 flex flex-col overflow-hidden"
          >
            <KanbanBoard
              lists={lists}
              searchQuery={searchQuery}
              activeFilter={activeFilter}
              onMoveCard={handleMoveCard}
              onOpenDetail={openCardDetail}
              onAdvanceAdmin={handleAdvanceAdmin}
              onDeleteRequest={setDeleteCardTarget}
              onCreateList={handleCreateList}
              onRenameList={handleRenameList}
              onDeleteList={handleDeleteList}
            />
          </motion.div>
        ) : (
          <motion.div
            key="externos-view"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: MOTION_EASE }}
            className="flex-1 flex flex-col overflow-hidden"
          >
            <AdminExternosView onToast={showToast} onPendingCountChange={setExtPendingBadge} />
          </motion.div>
        )}
      </AnimatePresence>

      {/* Modals */}
      <NewOsModal
        open={newOsOpen}
        lists={lists}
        labels={labels}
        initialEntry={selectedPendingEntry}
        onClose={() => {
          setNewOsOpen(false);
          setSelectedPendingEntry(null);
        }}
        onCreated={(osNum) => {
          showToast(`✅ O.S. ${osNum} cadastrada na esteira!`);
          setSelectedPendingEntry(null);
          fetchBoard();
        }}
      />

      <PendingPhotosModal
        open={pendingPhotosOpen}
        intakeUrl={boot.intakeUrl}
        pendingEntries={pendingEntries}
        onClose={() => setPendingPhotosOpen(false)}
        onUseEntry={(entry) => {
          setPendingPhotosOpen(false);
          setSelectedPendingEntry(entry);
          setNewOsOpen(true);
        }}
        onDeleteEntry={handleDeletePendingEntry}
      />

      <CallTechModal
        open={callTechOpen}
        onClose={() => setCallTechOpen(false)}
        onSent={(msg) => showToast(msg)}
      />

      <CardDetailModal
        card={detailCard}
        lists={lists}
        onClose={() => setDetailCard(null)}
        onRefresh={handleRefreshDetail}
        onAdvanceAdmin={handleAdvanceAdmin}
        onDeleteRequest={(c) => setDeleteCardTarget(c)}
        onToast={showToast}
      />

      <DeleteAuthModal
        card={deleteCardTarget}
        onClose={() => setDeleteCardTarget(null)}
        onDeleted={(osNum) => {
          showToast(`🗑️ O.S. ${osNum} excluída permanentemente.`);
          if (detailCard?.os_number === osNum) setDetailCard(null);
          fetchBoard();
        }}
      />

      <PasswordModal
        open={passwordModalOpen}
        user={user}
        onClose={() => setPasswordModalOpen(false)}
        onSuccess={showToast}
      />

      <ChatWidget viewer="priscila" onToast={showToast} />
    </div>
  );
};
