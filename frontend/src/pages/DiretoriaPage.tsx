import React, { useEffect, useMemo, useRef, useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import {
  BarChart2,
  ChevronDown,
  Download,
  KeyRound,
  Layout,
  LayoutDashboard,
  LogOut,
  Moon,
  Sun,
  Truck,
  Volume2,
} from 'lucide-react';
import type { AuthUser, BoardData, DirectorReport } from '../types';
import { apiJson, getBootConfig, getSocket, playDoorbellSound } from '../lib/api';
import { A5Logo } from '../components/A5Logo';
import { useTheme } from '../components/ThemeProvider';
import { PillTabs } from '../components/fluid/pill-tabs/PillTabs';
import { IslandToast } from '../components/fluid/island-toast/IslandToast';
import { ChatWidget } from '../components/ChatWidget';
import { PasswordModal } from '../components/PasswordModal';
import { ChamadosTvSection } from '../components/diretoria/ChamadosTvSection';
import { DiretoriaRotasSection } from '../components/diretoria/DiretoriaRotasSection';
import { RelatoriosSection } from '../components/diretoria/RelatoriosSection';
import { MOTION_EASE } from '../components/motion/motionTokens';

interface DiretoriaPageProps {
  user: AuthUser;
  onNavigate?: (path: string) => void;
  onLogout: () => void;
  onReady?: () => void;
}

const DEFAULT_WORKSHOP_TECHS = [
  'João Otoni',
  'Wisley',
  'Guilherme',
  'Iago',
  'Enzo',
  'Edson',
  'Antonio',
];

export const DiretoriaPage: React.FC<DiretoriaPageProps> = ({ user, onNavigate, onLogout, onReady }) => {
  const boot = getBootConfig();
  const { theme, toggleTheme } = useTheme();

  const [tab, setTab] = useState<'chamados' | 'rotas' | 'relatorios' | 'todos'>('chamados');
  const [connected, setConnected] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);
  const toastTimerRef = useRef<number | null>(null);
  const [passwordModalOpen, setPasswordModalOpen] = useState(false);
  const [csvOpen, setCsvOpen] = useState(false);

  // Dados ao vivo
  const [board, setBoard] = useState<BoardData | null>(null);
  const [period, setPeriod] = useState<'today' | 'week' | 'month' | 'all'>('today');
  const [techFilter, setTechFilter] = useState('');
  const [report, setReport] = useState<DirectorReport | null>(null);
  const [reportLoading, setReportLoading] = useState(false);
  const [pendingRotasBadge, setPendingRotasBadge] = useState<number | undefined>(undefined);
  const [rotasRefreshSignal, setRotasRefreshSignal] = useState(0);

  const showToast = (msg: string) => {
    setToastMsg(msg);
    if (toastTimerRef.current) window.clearTimeout(toastTimerRef.current);
    toastTimerRef.current = window.setTimeout(() => setToastMsg(null), 3200);
  };

  const fetchBoard = async () => {
    const res = await apiJson<BoardData>('/api/board');
    if (res.ok && res.data?.lists) setBoard(res.data);
  };

  const fetchReport = async (p = period, t = techFilter) => {
    setReportLoading(true);
    try {
      const res = await apiJson<DirectorReport>(
        `/api/diretoria/report?period=${encodeURIComponent(p)}&tech=${encodeURIComponent(t)}`,
      );
      if (res.ok && res.data?.kpis) setReport(res.data);
    } finally {
      setReportLoading(false);
    }
  };

  useEffect(() => {
    Promise.allSettled([fetchBoard(), fetchReport(period, techFilter)]).finally(() => onReady?.());
  }, []);

  useEffect(() => {
    fetchReport(period, techFilter);
  }, [period, techFilter]);

  useEffect(() => {
    const socket = getSocket();
    setConnected(socket.connected);

    const onConnect = () => setConnected(true);
    const onDisconnect = () => setConnected(false);
    const onBoardUpdated = () => {
      fetchBoard();
      fetchReport(period, techFilter);
    };
    const onRoutesSent = (data: { total_calls?: number; message?: string }) => {
      setPendingRotasBadge(data?.total_calls || 1);
      playDoorbellSound();
      showToast(data?.message || '🔔 Novos chamados externos enviados pela Recepção!');
      setRotasRefreshSignal((s) => s + 1);
    };
    const onExternalEvent = () => {
      setRotasRefreshSignal((s) => s + 1);
    };

    socket.on('connect', onConnect);
    socket.on('disconnect', onDisconnect);
    socket.on('board_updated', onBoardUpdated);
    socket.on('external_routes_sent_to_director', onRoutesSent);
    socket.on('external_order_created', onExternalEvent);
    socket.on('external_order_updated', onExternalEvent);
    socket.on('external_order_deleted', onExternalEvent);
    socket.on('external_orders_rescheduled', onExternalEvent);

    return () => {
      socket.off('connect', onConnect);
      socket.off('disconnect', onDisconnect);
      socket.off('board_updated', onBoardUpdated);
      socket.off('external_routes_sent_to_director', onRoutesSent);
      socket.off('external_order_created', onExternalEvent);
      socket.off('external_order_updated', onExternalEvent);
      socket.off('external_order_deleted', onExternalEvent);
      socket.off('external_orders_rescheduled', onExternalEvent);
    };
  }, [period, techFilter]);

  // Limpa badge de chamados quando o Sr. Jacson entra na aba de Rotas
  useEffect(() => {
    if (tab === 'rotas' || tab === 'todos') {
      setPendingRotasBadge(undefined);
    }
  }, [tab]);

  const technicianOptions = useMemo(() => {
    const fromBoard = (board?.lists || [])
      .filter((l) => l.is_tech === 1 || (l.title || '').toUpperCase().startsWith('TEC.'))
      .map((l) => (l.title || '').replace(/^TEC\.\s*/i, '').trim())
      .filter(Boolean);
    const fromReport = (report?.technicians_performance || []).map((t) => t.name).filter(Boolean);
    return Array.from(new Set([...DEFAULT_WORKSHOP_TECHS, ...fromBoard, ...fromReport]));
  }, [board, report]);

  return (
    <div className="min-h-screen flex flex-col">
      {/* IslandToast flutuante abaixo do header para nunca cobrir as abas */}
      <div className="fixed top-[72px] inset-x-0 z-[80] pointer-events-none">
        <IslandToast message={toastMsg} />
      </div>

      {/* Top Glass Header */}
      <header className="px-4 sm:px-6 py-3 bg-white/95 dark:bg-zinc-950/95 border-b border-slate-200/80 dark:border-zinc-800/80 flex flex-wrap items-center justify-between gap-3 sticky top-0 z-30">
        <div className="flex items-center gap-3 min-w-0">
          <A5Logo variant="full" size="sm" />
          <span className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-500/12 text-blue-600 dark:text-sky-400 border border-blue-500/20 text-[10.5px] font-extrabold uppercase tracking-wider">
            <span
              className={`w-2 h-2 rounded-full ${
                connected ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'
              }`}
            />
            Diretoria • {user.display_name.split('(')[0].trim()}
          </span>
        </div>

        {/* Navegação com Fluid PillTabs */}
        <div className="flex items-center justify-center overflow-x-auto max-w-full">
          <PillTabs
            label="Módulos da Diretoria"
            value={tab}
            onChange={(val) => setTab(val as 'chamados' | 'rotas' | 'relatorios' | 'todos')}
            tabs={[
              {
                value: 'chamados',
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <Volume2 className="w-3.5 h-3.5" /> Chamados TV
                  </span>
                ),
              },
              {
                value: 'rotas',
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <Truck className="w-3.5 h-3.5" /> Rotas Externas
                  </span>
                ),
                count: pendingRotasBadge,
              },
              {
                value: 'relatorios',
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <BarChart2 className="w-3.5 h-3.5" /> Produtividade
                  </span>
                ),
              },
              {
                value: 'todos',
                label: (
                  <span className="inline-flex items-center gap-1.5">
                    <Layout className="w-3.5 h-3.5" /> Visão Geral
                  </span>
                ),
              },
            ]}
          />
        </div>

        {/* Ações do Cabeçalho */}
        <div className="flex items-center gap-1.5 flex-wrap">
          {/* Dropdown Exportar CSV */}
          <div className="relative">
            <button
              type="button"
              onClick={() => setCsvOpen((o) => !o)}
              className="px-3 py-2 rounded-full bento-inner-tile text-xs font-bold inline-flex items-center gap-1.5 hover:border-blue-500 cursor-pointer"
            >
              <Download className="w-3.5 h-3.5 text-blue-500" />
              <span className="hidden md:inline">Exportar CSV</span>
              <ChevronDown className="w-3 h-3 text-slate-400" />
            </button>
            {csvOpen && (
              <div
                onMouseLeave={() => setCsvOpen(false)}
                className="absolute right-0 mt-1.5 w-52 modernize-card p-1.5 z-50 text-xs font-bold shadow-2xl"
              >
                <a
                  href="/api/export/csv?period=day"
                  onClick={() => setCsvOpen(false)}
                  className="block px-3 py-2 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 transition"
                >
                  Finalizadas Hoje
                </a>
                <a
                  href="/api/export/csv?period=month"
                  onClick={() => setCsvOpen(false)}
                  className="block px-3 py-2 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 transition"
                >
                  Relatório Mensal
                </a>
                <a
                  href="/api/export/csv?period=year"
                  onClick={() => setCsvOpen(false)}
                  className="block px-3 py-2 rounded-xl hover:bg-slate-100 dark:hover:bg-zinc-800 transition"
                >
                  Relatório Anual
                </a>
                <a
                  href="/api/export/csv?period=all"
                  onClick={() => setCsvOpen(false)}
                  className="block px-3 py-2 rounded-xl text-blue-600 dark:text-sky-400 hover:bg-blue-50 dark:hover:bg-zinc-800 border-t border-slate-200/70 dark:border-zinc-800 mt-1 pt-2 transition"
                >
                  Base Completa (CSV)
                </a>
              </div>
            )}
          </div>

          {user.role === 'master' && (
            <button
              type="button"
              onClick={() => (onNavigate ? onNavigate('/admin') : (window.location.href = '/admin'))}
              className="px-3 py-2 rounded-full bg-blue-500/12 border border-blue-500/25 text-blue-600 dark:text-sky-400 text-xs font-extrabold inline-flex items-center gap-1 cursor-pointer"
              title="Trocar para Esteira Kanban (Master)"
            >
              <LayoutDashboard className="w-3.5 h-3.5" />
              <span className="hidden xl:inline">Recepção</span>
            </button>
          )}

          <button
            type="button"
            onClick={toggleTheme}
            className="p-2 rounded-full bento-inner-tile cursor-pointer"
            title="Alternar tema Claro/Escuro"
          >
            {theme === 'dark' ? (
              <Sun className="w-4 h-4 text-amber-400" />
            ) : (
              <Moon className="w-4 h-4 text-blue-600" />
            )}
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

      {/* Conteúdo Principal */}
      <main className="max-w-7xl w-full mx-auto p-4 sm:p-6 flex-1 pb-24">
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.22, ease: MOTION_EASE }}
            className="space-y-6"
          >
            {(tab === 'chamados' || tab === 'todos') && (
              <ChamadosTvSection
                callTargets={boot.callTargets}
                board={board}
                onRefreshBoard={fetchBoard}
                onToast={showToast}
              />
            )}

            {(tab === 'rotas' || tab === 'todos') && (
              <DiretoriaRotasSection onToast={showToast} refreshSignal={rotasRefreshSignal} />
            )}

            {(tab === 'relatorios' || tab === 'todos') && (
              <RelatoriosSection
                period={period}
                onPeriodChange={setPeriod}
                techFilter={techFilter}
                onTechFilterChange={setTechFilter}
                technicianOptions={technicianOptions}
                report={report}
                loading={reportLoading}
                onRefresh={() => fetchReport(period, techFilter)}
              />
            )}
          </motion.div>
        </AnimatePresence>
      </main>

      {/* Chat em tempo real Sr. Jacson <-> Priscila */}
      <ChatWidget viewer="jacson" onToast={showToast} />

      {/* Modal Alterar Senha */}
      <PasswordModal
        open={passwordModalOpen}
        user={user}
        onClose={() => setPasswordModalOpen(false)}
        onSuccess={(msg) => showToast(msg)}
      />
    </div>
  );
};
