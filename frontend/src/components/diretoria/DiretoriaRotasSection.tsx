import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  closestCorners,
  useDroppable,
  useSensor,
  useSensors,
  type DragEndEvent,
  type DragStartEvent,
  type DropAnimation,
} from '@dnd-kit/core';
import {
  SortableContext,
  arrayMove,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import {
  AlertCircle,
  Calendar,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ChevronsDown,
  ChevronsUp,
  Copy,
  Download,
  GripVertical,
  Hand,
  Plus,
  RefreshCw,
  Save,
  Send,
  Truck,
  UserCheck,
  UserPlus,
  X,
} from 'lucide-react';
import type { ExternalOrder, RouteSummary } from '../../types';
import { apiJson, localTodayISO } from '../../lib/api';
import { exportCompactRoutePng } from '../../lib/routePngExporter';
import { RouteCompactCard } from '../RouteCompactCard';
import { MOTION_EASE, SPRING_SNAPPY } from '../motion/motionTokens';

const DEFAULT_TECH_CATALOG = [
  'EDSON',
  'ANTONIO',
  'ENZO',
  'JOAO',
  'GUILHERME',
  'WISLEY',
  'IAGO',
  'ENZO / JOAO',
  'ENZO / EDSON',
  'EDSON / ANTONIO',
];

const SELECTED_TECHS_KEY = 'a5_diretoria_selected_techs_v2';

interface DiretoriaRotasSectionProps {
  onToast: (msg: string) => void;
  refreshSignal?: number;
}

/* ========================================================================= */
/* CARTÕES ARRASTÁVEIS (@dnd-kit/sortable)                                    */
/* ========================================================================= */

function useHoverReveal(delayMs = 280) {
  const [expanded, setExpanded] = useState(false);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    };
  }, []);

  const onMouseEnter = () => {
    if (timerRef.current !== null) window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => setExpanded(true), delayMs);
  };

  const onMouseLeave = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setExpanded(false);
  };

  const cancel = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
    }
    setExpanded(false);
  };

  return { expanded, onMouseEnter, onMouseLeave: cancel, cancel };
}

const DraggableUnassignedCard = memo<{
  order: ExternalOrder;
  techOptions: string[];
  onQuickAssign: (orderId: number, tech: string) => void;
}>(({ order, techOptions, onQuickAssign }) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `order-${order.id}`,
    data: { type: 'order', order, sourceZone: 'unassigned' },
  });
  const { expanded, onMouseEnter, onMouseLeave, cancel } = useHoverReveal(280);
  const showExpanded = expanded && !isDragging;

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition: transition ?? undefined,
    opacity: isDragging ? 0.35 : 1,
    willChange: isDragging ? 'transform' : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onPointerDownCapture={cancel}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      title="Arraste pressionando em qualquer parte do cartão"
      className={`kanban-card-surface px-2.5 py-2 rounded-xl bg-white dark:bg-zinc-900 border space-y-1 cursor-grab active:cursor-grabbing select-none transition-colors duration-150 ${
        showExpanded
          ? 'border-blue-400/75 dark:border-sky-500/50 shadow-sm'
          : 'border-slate-200/90 dark:border-zinc-800 hover:border-blue-500/60 hover:shadow-sm'
      }`}
    >
      <div className="flex items-center justify-between gap-1.5">
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <GripVertical className="w-3.5 h-3.5 text-slate-400 shrink-0" />
          <span
            className={`font-extrabold text-[11.5px] text-zinc-900 dark:text-white ${
              showExpanded ? 'whitespace-normal break-words' : 'truncate'
            }`}
          >
            {order.client_name}
          </span>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          {order.attendance_status === 'not_attended' && (
            <span className="font-mono text-[9px] px-1.5 py-0.5 rounded-full bg-rose-500/15 text-rose-600 dark:text-rose-400 font-bold border border-rose-500/30">
              Não At.
            </span>
          )}
          <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-blue-500/12 text-blue-600 dark:text-sky-400 font-bold">
            {order.os_number ? `OS ${order.os_number}` : 'S/N'}
          </span>
        </div>
      </div>

      <div className="text-[10.5px] text-slate-600 dark:text-zinc-300 pl-5 flex flex-wrap items-center gap-x-2 gap-y-0.5 leading-snug">
        {order.open_date && (
          <span className="font-mono font-bold text-amber-700 dark:text-amber-300">
            {order.open_date}
            {order.open_time ? ` ${order.open_time}` : ''}
          </span>
        )}
        {(order.sector || order.equipment_model) && (
          <span>
            • {order.sector || '-'}
            {order.equipment_model ? ` | ${order.equipment_model}` : ''}
          </span>
        )}
        {order.reported_defect && (
          <span className={`text-zinc-800 dark:text-zinc-200 font-semibold ${showExpanded ? 'whitespace-normal break-words' : 'truncate max-w-[260px]'}`}>
            • {order.reported_defect}
          </span>
        )}
      </div>

      {order.unattended_reason && (
        <div className="ml-5 text-[10.5px] text-rose-600 dark:text-rose-400 font-bold flex items-center gap-1">
          <AlertCircle className="w-3 h-3 shrink-0" />
          <span>{order.unattended_reason}</span>
        </div>
      )}

      {order.tasks_notes && (
        <div
          className={`ml-5 text-[10.5px] text-rose-600 dark:text-rose-400 font-bold bg-rose-50 dark:bg-rose-950/40 px-2 py-0.5 rounded-lg border border-rose-200 dark:border-rose-900/40 ${
            showExpanded ? 'whitespace-normal break-words' : 'truncate'
          }`}
        >
          ⚠️ {order.tasks_notes}
        </div>
      )}

      <div className="pl-5 pt-0.5">
        <select
          value=""
          onPointerDown={(e) => e.stopPropagation()}
          onChange={(e) => {
            if (e.target.value) onQuickAssign(order.id, e.target.value);
          }}
          className="w-full bg-slate-50 dark:bg-zinc-800 border border-slate-200 dark:border-zinc-700 text-zinc-900 dark:text-white rounded-lg px-2 py-1 text-[11px] font-bold focus:outline-none focus:border-blue-500 cursor-pointer"
        >
          <option value="">Atribuir p/ Técnico...</option>
          {techOptions.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
});

const DraggableStopCard = memo<{
  stop: ExternalOrder;
  techName: string;
  index: number;
  total: number;
  onMoveStep: (tech: string, index: number, dir: -1 | 1) => void;
  onUnassign: (orderId: number) => void;
  onSaveNotes: (orderId: number, notes: string) => void;
}>(({ stop, techName, index, total, onMoveStep, onUnassign, onSaveNotes }) => {
  const [noteDraft, setNoteDraft] = useState(stop.tasks_notes || '');
  const { expanded, onMouseEnter, onMouseLeave, cancel } = useHoverReveal(280);

  useEffect(() => {
    setNoteDraft(stop.tasks_notes || '');
  }, [stop.tasks_notes]);

  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `order-${stop.id}`,
    data: { type: 'order', order: stop, sourceZone: techName },
  });
  const showExpanded = expanded && !isDragging;

  const style: React.CSSProperties = {
    transform: CSS.Translate.toString(transform),
    transition: transition ?? undefined,
    opacity: isDragging ? 0.35 : 1,
    willChange: isDragging ? 'transform' : undefined,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      onPointerDownCapture={cancel}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      title="Arraste pressionando em qualquer lugar do cartão"
      className={`kanban-card-surface px-2.5 py-1.5 rounded-xl bg-white dark:bg-zinc-900 border flex flex-col gap-1 cursor-grab active:cursor-grabbing select-none transition-colors duration-150 ${
        showExpanded
          ? 'border-blue-400/75 dark:border-sky-500/50 shadow-sm'
          : 'border-slate-200/90 dark:border-zinc-800 hover:border-blue-500/60 hover:shadow-xs'
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 flex-1 min-w-0">
          <GripVertical className="w-3.5 h-3.5 text-slate-400 shrink-0" />

          <span className="w-6 h-6 rounded-lg bg-gradient-to-br from-blue-500 to-blue-700 text-white font-mono font-black text-[11px] flex items-center justify-center shrink-0">
            {index + 1}º
          </span>

          <div className="flex-1 min-w-0 space-y-0.5">
            <div className="flex items-center gap-1.5 flex-wrap text-[11px] leading-tight">
              <strong
                className={`font-black text-zinc-900 dark:text-white ${
                  showExpanded ? 'whitespace-normal break-words' : 'truncate max-w-[230px]'
                }`}
              >
                {stop.client_name}
              </strong>
              <span className="font-mono text-[9.5px] font-bold px-1.5 py-0.5 rounded bg-slate-100 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 shrink-0">
                {stop.os_number ? `OS ${stop.os_number}` : 'S/N'}
              </span>
              {stop.sector && (
                <span className="text-slate-500 dark:text-zinc-400">• {stop.sector}</span>
              )}
              {stop.equipment_model && (
                <span className="text-slate-500 dark:text-zinc-400">• {stop.equipment_model}</span>
              )}
              {stop.reported_defect && (
                <span
                  className={`text-slate-700 dark:text-zinc-300 ${
                    showExpanded ? 'whitespace-normal break-words' : 'truncate max-w-[240px]'
                  }`}
                >
                  • {stop.reported_defect}
                </span>
              )}
            </div>

            <input
              type="text"
              value={noteDraft}
              onPointerDown={(e) => e.stopPropagation()}
              onChange={(e) => setNoteDraft(e.target.value)}
              onBlur={() => {
                if (noteDraft !== (stop.tasks_notes || '')) {
                  onSaveNotes(stop.id, noteDraft);
                }
              }}
              placeholder="Obs. / Tarefa..."
              className="w-full h-6 bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 rounded-lg px-2 py-0 text-[11px] text-rose-600 dark:text-rose-400 font-bold focus:outline-none focus:border-rose-500 cursor-text"
            />
          </div>
        </div>

        {/* BOTÕES ▲ / ▼ / ✕ COMPACTOS */}
        <div
          className="flex items-center gap-1 shrink-0"
          onPointerDown={(e) => e.stopPropagation()}
        >
          <button
            type="button"
            onClick={() => onMoveStep(techName, index, -1)}
            disabled={index === 0}
            title="Subir parada"
            className="p-1 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
          >
            <ChevronUp className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => onMoveStep(techName, index, 1)}
            disabled={index === total - 1}
            title="Descer parada"
            className="p-1 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-700 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 disabled:opacity-30 disabled:pointer-events-none transition cursor-pointer"
          >
            <ChevronDown className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={() => onUnassign(stop.id)}
            title="Remover parada da rota"
            className="p-1 rounded-lg border border-rose-200 dark:border-rose-900/60 text-rose-600 dark:text-rose-400 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition cursor-pointer"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* EXPANSÃO SUAVE AO PASSAR O MOUSE PARA MOSTRAR TAREFA / DEFEITO COMPLETO */}
      <AnimatePresence>
        {showExpanded && (stop.reported_defect || stop.tasks_notes || stop.open_date) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.16, ease: MOTION_EASE }}
            className="overflow-hidden"
          >
            <div className="ml-12 pt-1 pb-0.5 px-2.5 rounded-lg bg-slate-50/90 dark:bg-zinc-950/80 border border-slate-200/80 dark:border-zinc-800 text-[10.5px] text-slate-700 dark:text-zinc-300 space-y-0.5">
              {(stop.open_date || stop.sector || stop.equipment_model) && (
                <div className="text-slate-500 dark:text-zinc-400 font-semibold">
                  {stop.open_date ? `Abertura: ${stop.open_date}${stop.open_time ? ` ${stop.open_time}` : ''}` : ''}
                  {stop.open_date && (stop.sector || stop.equipment_model) ? ' • ' : ''}
                  {[stop.sector, stop.equipment_model].filter(Boolean).join(' • ')}
                </div>
              )}
              {stop.reported_defect && (
                <div className="font-semibold text-zinc-900 dark:text-zinc-100 leading-snug">
                  Defeito: {stop.reported_defect}
                </div>
              )}
              {noteDraft && (
                <div className="font-extrabold text-rose-600 dark:text-rose-400 leading-snug">
                  ⚠️ Tarefa: {noteDraft}
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});

const UnassignedDropZone = memo<{
  orders: ExternalOrder[];
  techOptions: string[];
  onQuickAssign: (orderId: number, tech: string) => void;
}>(({ orders, techOptions, onQuickAssign }) => {
  const { setNodeRef, isOver } = useDroppable({
    id: 'zone-unassigned',
    data: { type: 'zone', zone: 'unassigned' },
  });
  const itemIds = useMemo(() => orders.map((o) => `order-${o.id}`), [orders]);

  return (
    <div
      ref={setNodeRef}
      className={`space-y-2.5 min-h-[200px] p-2 rounded-2xl transition-colors duration-150 ${
        isOver ? 'bg-blue-500/10 ring-2 ring-blue-500/40' : ''
      }`}
    >
      <SortableContext
        items={itemIds}
        strategy={verticalListSortingStrategy}
      >
        {orders.length === 0 ? (
          <div className="text-center py-10 text-slate-400 dark:text-zinc-500 text-xs">
            <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-500/60 mb-2" />
            <p className="font-bold">Todos os chamados foram distribuídos!</p>
            <p className="text-[11px] mt-1">Arraste um cartão para cá se quiser devolver.</p>
          </div>
        ) : (
          orders.map((order) => (
            <DraggableUnassignedCard
              key={order.id}
              order={order}
              techOptions={techOptions}
              onQuickAssign={onQuickAssign}
            />
          ))
        )}
      </SortableContext>
    </div>
  );
});

const TechDropZone = memo<{
  techName: string;
  stops: ExternalOrder[];
  collapsed: boolean;
  onToggleCollapse: (techName: string) => void;
  onRemoveTech: (techName: string) => void;
  onMoveStep: (tech: string, index: number, dir: -1 | 1) => void;
  onUnassign: (orderId: number) => void;
  onSaveNotes: (orderId: number, notes: string) => void;
}>(({
  techName,
  stops,
  collapsed,
  onToggleCollapse,
  onRemoveTech,
  onMoveStep,
  onUnassign,
  onSaveNotes,
}) => {
  const { setNodeRef, isOver } = useDroppable({
    id: `zone-tech-${techName}`,
    data: { type: 'zone', zone: techName },
  });
  const itemIds = useMemo(() => stops.map((s) => `order-${s.id}`), [stops]);

  return (
    <div className="modernize-card overflow-hidden">
      <div className="px-3 py-2 bg-slate-100/80 dark:bg-zinc-900/70 border-b border-slate-200/80 dark:border-zinc-800 flex items-center justify-between gap-2">
        <button
          type="button"
          onClick={() => onToggleCollapse(techName)}
          className="flex items-center gap-2 flex-1 min-w-0 text-left cursor-pointer"
        >
          <span className="w-6 h-6 rounded-lg bg-blue-500/15 text-blue-600 dark:text-sky-400 flex items-center justify-center shrink-0">
            {collapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
          </span>
          <h4 className="text-xs font-black text-zinc-900 dark:text-white tracking-wide truncate">
            ROTA: {techName}
          </h4>
        </button>

        <div className="flex items-center gap-1.5 shrink-0">
          <span className="font-mono text-[11px] font-black px-2 py-0.5 rounded-full bg-blue-500/12 text-blue-700 dark:text-sky-400 border border-blue-500/25">
            {stops.length} atend.
          </span>
          {stops.length === 0 && (
            <button
              type="button"
              onClick={() => onRemoveTech(techName)}
              title={`Tirar ${techName} da tela`}
              className="p-1 rounded-lg border border-slate-200 dark:border-zinc-700 text-slate-400 hover:text-rose-500 hover:border-rose-400 transition cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </div>

      {!collapsed && (
        <div ref={setNodeRef} className={`p-2 transition-colors duration-150 ${isOver ? 'bg-blue-500/10' : ''}`}>
          <SortableContext
            items={itemIds}
            strategy={verticalListSortingStrategy}
          >
            <div className="min-h-[48px] space-y-1.5">
              {stops.length === 0 ? (
                <div className="text-center py-6 border-2 border-dashed border-slate-300/80 dark:border-zinc-800 rounded-2xl text-slate-400 dark:text-zinc-500 text-xs flex flex-col items-center gap-1.5">
                  <Hand className="w-5 h-5 text-blue-500/70" />
                  <span className="font-bold">
                    Arraste chamados aqui para a rota de {techName}
                  </span>
                </div>
              ) : (
                stops.map((stop, idx) => (
                  <DraggableStopCard
                    key={stop.id}
                    stop={stop}
                    techName={techName}
                    index={idx}
                    total={stops.length}
                    onMoveStep={onMoveStep}
                    onUnassign={onUnassign}
                    onSaveNotes={onSaveNotes}
                  />
                ))
              )}
            </div>
          </SortableContext>
        </div>
      )}
    </div>
  );
});

const EMPTY_STOPS: ExternalOrder[] = [];
const ROUTE_DROP_ANIMATION: DropAnimation = {
  duration: 180,
  easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
};

/* ========================================================================= */
/* COMPONENTE PRINCIPAL DE ROTAS DA DIRETORIA                                */
/* ========================================================================= */

export const DiretoriaRotasSection: React.FC<DiretoriaRotasSectionProps> = ({
  onToast,
  refreshSignal = 0,
}) => {
  const [routeDate, setRouteDate] = useState(localTodayISO());
  const [summary, setSummary] = useState<RouteSummary | null>(null);
  const [availableTechs, setAvailableTechs] = useState<string[]>(DEFAULT_TECH_CATALOG);
  const [selectedTechs, setSelectedTechs] = useState<string[]>(() => {
    try {
      const raw = JSON.parse(localStorage.getItem(SELECTED_TECHS_KEY) || '[]');
      return Array.isArray(raw) ? raw : [];
    } catch {
      return [];
    }
  });
  const [collapsedTechs, setCollapsedTechs] = useState<Set<string>>(new Set());
  const [activeOrder, setActiveOrder] = useState<ExternalOrder | null>(null);
  const [previewModalOpen, setPreviewModalOpen] = useState(false);

  // Modal Tarefa Avulsa
  const [taskModalOpen, setTaskModalOpen] = useState(false);
  const [taskClient, setTaskClient] = useState('');
  const [taskOs, setTaskOs] = useState('');
  const [taskSector, setTaskSector] = useState('');
  const [taskNotes, setTaskNotes] = useState('');
  const [taskTech, setTaskTech] = useState('');

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 4 },
    }),
  );

  const persistSelected = (next: string[]) => {
    setSelectedTechs(next);
    try {
      localStorage.setItem(SELECTED_TECHS_KEY, JSON.stringify(next));
    } catch {
      // Ignore storage quota errors
    }
  };

  const loadRoutes = async () => {
    const res = await apiJson<{
      success: boolean;
      summary: RouteSummary;
      available_technicians?: string[];
    }>(`/api/externos/routes/summary?date=${encodeURIComponent(routeDate)}&shift=geral`);

    if (res.ok && res.data.success) {
      setSummary(res.data.summary);
      if (Array.isArray(res.data.available_technicians)) {
        const merged = Array.from(
          new Set([
            ...DEFAULT_TECH_CATALOG,
            ...res.data.available_technicians.map((t) => t.toUpperCase()),
          ]),
        );
        setAvailableTechs(merged);
      }
      // Garante que qualquer técnico já com paradas apareça visível na tela
      const withStops = Object.entries(res.data.summary.technicians || {})
        .filter(([, stops]) => stops && stops.length > 0)
        .map(([t]) => t);
      if (withStops.length > 0) {
        setSelectedTechs((prev) => Array.from(new Set([...prev, ...withStops])));
      }
    }
  };

  useEffect(() => {
    loadRoutes();
  }, [routeDate, refreshSignal]);

  // Mapa unificado dos técnicos exibidos na tela (preserva referência por técnico para memo)
  const techColumns = useMemo(() => {
    const map: Record<string, ExternalOrder[]> = {};
    const raw = summary?.technicians || {};
    for (const [t, stops] of Object.entries(raw)) {
      if (stops && stops.length > 0) map[t] = stops;
    }
    for (const t of selectedTechs) {
      if (!map[t]) map[t] = raw[t] && raw[t].length > 0 ? raw[t] : EMPTY_STOPS;
    }
    return map;
  }, [summary, selectedTechs]);

  const allChipTechs = useMemo(
    () => Array.from(new Set([...availableTechs, ...Object.keys(techColumns)])),
    [availableTechs, techColumns],
  );

  const toggleTechChip = useCallback((techName: string) => {
    const clean = techName.trim().toUpperCase();
    const currentStops = techColumns[clean] || [];
    if (techColumns[clean]) {
      if (currentStops.length > 0) {
        onToast(`O técnico ${clean} possui ${currentStops.length} chamado(s). Remova antes ou minimize.`);
        return;
      }
      persistSelected(selectedTechs.filter((t) => t !== clean));
    } else {
      persistSelected([...selectedTechs, clean]);
      setCollapsedTechs((prev) => {
        const copy = new Set(prev);
        copy.delete(clean);
        return copy;
      });
    }
  }, [techColumns, selectedTechs, onToast]);

  const handleToggleCollapseTech = useCallback((techName: string) => {
    setCollapsedTechs((prev) => {
      const next = new Set(prev);
      if (next.has(techName)) next.delete(techName);
      else next.add(techName);
      return next;
    });
  }, []);

  const addCustomTech = () => {
    const name = window.prompt('Digite o nome do Técnico ou Dupla para adicionar à rota:');
    if (!name || !name.trim()) return;
    const clean = name.trim().toUpperCase();
    if (!availableTechs.includes(clean)) setAvailableTechs((prev) => [...prev, clean]);
    if (!selectedTechs.includes(clean)) persistSelected([...selectedTechs, clean]);
  };

  const saveTechStopsOrder = async (techName: string, stops: ExternalOrder[]) => {
    const assignments = stops.map((s, idx) => ({
      id: s.id,
      technician: techName,
      route_order: idx + 1,
      tasks_notes: s.tasks_notes || '',
    }));
    await apiJson('/api/externos/routes/save', {
      method: 'POST',
      body: JSON.stringify({
        date: routeDate,
        shift: 'geral',
        assignments,
        finalize: false,
        director_name: 'Sr. Jacson',
      }),
    });
    await loadRoutes();
  };

  const handleQuickAssign = useCallback(async (orderId: number, techName: string) => {
    const clean = techName.trim().toUpperCase();
    if (!selectedTechs.includes(clean)) persistSelected([...selectedTechs, clean]);
    setSummary((prev) => {
      if (!prev) return prev;
      const moved = prev.unassigned.find((o) => o.id === orderId);
      if (!moved) return prev;
      const nextTechs = { ...prev.technicians };
      nextTechs[clean] = [...(nextTechs[clean] || []), { ...moved, technician: clean, status: 'draft' }];
      return { ...prev, unassigned: prev.unassigned.filter((o) => o.id !== orderId), technicians: nextTechs };
    });
    await apiJson(`/api/externos/orders/${orderId}`, {
      method: 'PUT',
      body: JSON.stringify({
        technician: clean,
        route_date: routeDate,
        route_shift: 'geral',
        status: 'draft',
        attendance_status: 'pending',
      }),
    });
    await loadRoutes();
  }, [selectedTechs, routeDate]);

  const handleUnassign = useCallback(async (orderId: number) => {
    setSummary((prev) => {
      if (!prev) return prev;
      let removed: ExternalOrder | undefined;
      const nextTechs: Record<string, ExternalOrder[]> = {};
      for (const [k, list] of Object.entries(prev.technicians || {})) {
        const hit = list.find((s) => s.id === orderId);
        if (hit) removed = hit;
        nextTechs[k] = list.filter((s) => s.id !== orderId);
      }
      if (!removed) return prev;
      return {
        ...prev,
        technicians: nextTechs,
        unassigned: [...prev.unassigned, { ...removed, technician: '', route_order: 0, status: 'pending_route' }],
      };
    });
    await apiJson(`/api/externos/orders/${orderId}`, {
      method: 'PUT',
      body: JSON.stringify({ technician: '', route_order: 0, status: 'pending_route' }),
    });
    await loadRoutes();
  }, []);

  const handleMoveStep = useCallback(async (techName: string, idx: number, dir: -1 | 1) => {
    const stops = [...(techColumns[techName] || [])];
    const target = idx + dir;
    if (target < 0 || target >= stops.length) return;
    const reordered = arrayMove(stops, idx, target);
    setSummary((prev) => (prev ? { ...prev, technicians: { ...prev.technicians, [techName]: reordered } } : prev));
    await saveTechStopsOrder(techName, reordered);
  }, [techColumns]);

  const handleSaveNotes = useCallback(async (orderId: number, notes: string) => {
    await apiJson(`/api/externos/orders/${orderId}`, {
      method: 'PUT',
      body: JSON.stringify({ tasks_notes: notes }),
    });
    onToast('Observação da parada atualizada!');
  }, [onToast]);

  const handleDragStart = (e: DragStartEvent) => {
    const order = e.active.data.current?.order as ExternalOrder | undefined;
    if (order) setActiveOrder(order);
  };

  const handleDragEnd = async (e: DragEndEvent) => {
    setActiveOrder(null);
    const { active, over } = e;
    if (!over) return;

    const activeData = active.data.current as { order: ExternalOrder; sourceZone: string } | undefined;
    if (!activeData) return;

    const { order, sourceZone } = activeData;
    const overId = String(over.id);

    // Determinar zona de destino
    let targetZone = '';
    if (overId === 'zone-unassigned') {
      targetZone = 'unassigned';
    } else if (overId.startsWith('zone-tech-')) {
      targetZone = overId.replace('zone-tech-', '');
    } else if (over.data.current?.sourceZone) {
      targetZone = String(over.data.current.sourceZone);
    }
    if (!targetZone) return;

    if (targetZone === 'unassigned') {
      if (sourceZone !== 'unassigned') {
        onToast('Chamado devolvido para Aguardando Distribuição.');
        await handleUnassign(order.id);
      }
      return;
    }

    const currentTargetStops = [...(techColumns[targetZone] || [])];
    if (sourceZone === targetZone) {
      const oldIdx = currentTargetStops.findIndex((s) => `order-${s.id}` === String(active.id));
      const newIdx = currentTargetStops.findIndex((s) => `order-${s.id}` === overId);
      if (oldIdx !== -1 && newIdx !== -1 && oldIdx !== newIdx) {
        const reordered = arrayMove(currentTargetStops, oldIdx, newIdx);
        setSummary((prev) => (prev ? { ...prev, technicians: { ...prev.technicians, [targetZone]: reordered } } : prev));
        await saveTechStopsOrder(targetZone, reordered);
      }
      return;
    }

    // Movendo de unassigned ou de outro técnico para targetZone (otimista imediato)
    const overIdx = currentTargetStops.findIndex((s) => `order-${s.id}` === overId);
    const insertAt = overIdx >= 0 ? overIdx : currentTargetStops.length;
    const nextStops = [...currentTargetStops];
    nextStops.splice(insertAt, 0, { ...order, technician: targetZone });
    setSummary((prev) => {
      if (!prev) return prev;
      const nextTechs: Record<string, ExternalOrder[]> = {};
      for (const [k, list] of Object.entries(prev.technicians || {})) {
        nextTechs[k] = list.filter((s) => s.id !== order.id);
      }
      nextTechs[targetZone] = nextStops;
      return {
        ...prev,
        unassigned: prev.unassigned.filter((o) => o.id !== order.id),
        technicians: nextTechs,
      };
    });
    onToast(`✅ Chamado movido para ${targetZone}!`);
    await saveTechStopsOrder(targetZone, nextStops);
  };

  const handleSaveAll = async (finalize: boolean) => {
    if (
      finalize &&
      !window.confirm(
        `Deseja FINALIZAR e LIBERAR as rotas de ${routeDate} para a Recepção?`,
      )
    ) {
      return;
    }

    const assignments: Array<{ id: number; technician: string; route_order: number; tasks_notes: string }> = [];
    for (const [tName, stops] of Object.entries(techColumns)) {
      stops.forEach((s, idx) => {
        assignments.push({
          id: s.id,
          technician: tName,
          route_order: idx + 1,
          tasks_notes: s.tasks_notes || '',
        });
      });
    }

    const res = await apiJson<{ success: boolean; error?: string }>('/api/externos/routes/save', {
      method: 'POST',
      body: JSON.stringify({
        date: routeDate,
        shift: 'geral',
        assignments,
        finalize,
        director_name: 'Sr. Jacson',
      }),
    });
    if (res.ok && res.data.success) {
      await loadRoutes();
      if (finalize) {
        setPreviewModalOpen(true);
        onToast('✅ Rota liberada para a Recepção!');
      } else {
        onToast('💾 Rascunho da rota salvo.');
      }
    } else {
      onToast(res.data.error || 'Erro ao salvar rotas.');
    }
  };

  const handleCreateTask = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!taskClient.trim() && !taskNotes.trim()) {
      onToast('Informe ao menos o Cliente ou a Descrição da Tarefa.');
      return;
    }
    const res = await apiJson<{ success: boolean; error?: string }>('/api/externos/orders', {
      method: 'POST',
      body: JSON.stringify({
        client_name: taskClient.trim() || 'TAREFA DE CAMPO',
        os_number: taskOs.trim(),
        sector: taskSector.trim(),
        tasks_notes: taskNotes.trim(),
        technician: taskTech,
        route_date: routeDate,
        route_shift: 'geral',
        open_date: new Date().toLocaleDateString('pt-BR'),
      }),
    });
    if (res.ok && res.data.success) {
      setTaskModalOpen(false);
      setTaskClient('');
      setTaskOs('');
      setTaskSector('');
      setTaskNotes('');
      setTaskTech('');
      onToast('Tarefa adicionada à rota!');
      await loadRoutes();
    } else {
      onToast(res.data.error || 'Erro ao cadastrar tarefa.');
    }
  };

  const unassigned = summary?.unassigned || [];
  const activeRouteEntries = Object.entries(techColumns).filter(([, stops]) => stops.length > 0);
  const formattedDate = routeDate.split('-').reverse().join('/');

  const capturePreviewImage = async (action: 'copy' | 'download') => {
    const cleanDate = routeDate.split('-').reverse().join('-');
    await exportCompactRoutePng({
      title: 'ROTA DE CAMPO',
      shiftLabel: '',
      dateFormatted: formattedDate,
      techGroups: activeRouteEntries,
      filename: `ROTA_CONJUNTA_${cleanDate}.png`,
      action,
      saveOnServer: false,
      onToast,
    });
  };

  const renderFinalizedSheet = () => (
    <div className="flex justify-center">
      <RouteCompactCard
        title="ROTA DE CAMPO"
        dateFormatted={formattedDate}
        techGroups={activeRouteEntries}
      />
    </div>
  );

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: MOTION_EASE }}
      className="space-y-4"
    >
      {/* BARRA SUPERIOR DA MONTAGEM DE ROTAS */}
      <div className="modernize-card p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-blue-500/12 border border-blue-500/25 flex items-center justify-center text-blue-600 dark:text-sky-400 shrink-0">
            <Truck className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm font-extrabold uppercase tracking-wider text-zinc-900 dark:text-white">
                Organização de Rotas de Campo
              </h2>
              <span
                className={`text-[10px] font-mono px-2.5 py-0.5 rounded-full font-bold border ${
                  summary?.status === 'finalized'
                    ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30'
                    : summary?.status === 'pending_director'
                      ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30'
                      : 'bg-slate-200 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border-slate-300 dark:border-zinc-700'
                }`}
              >
                {summary?.status === 'finalized'
                  ? '✅ Rota Liberada'
                  : summary?.status === 'pending_director'
                    ? '🔔 Enviado pela Recepção'
                    : '⏳ Rascunho'}
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400">
              Arraste os chamados ou atribua diretamente a cada técnico e libere a rota.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-2.5 py-1.5">
            <Calendar className="w-3.5 h-3.5 text-blue-500" />
            <input
              type="date"
              value={routeDate}
              onChange={(e) => setRouteDate(e.target.value)}
              className="bg-transparent text-xs font-bold text-zinc-900 dark:text-white focus:outline-none"
            />
          </div>

          <button
            type="button"
            onClick={() => setTaskModalOpen(true)}
            className="btn-modernize-light px-3.5 py-2 text-xs flex items-center gap-1.5 cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Tarefa Avulsa</span>
          </button>

          <button
            type="button"
            onClick={() => handleSaveAll(false)}
            className="btn-ember-dark px-3.5 py-2 text-xs flex items-center gap-1.5 cursor-pointer"
          >
            <Save className="w-3.5 h-3.5" />
            <span>Salvar Rascunho</span>
          </button>

          <button
            type="button"
            onClick={() => handleSaveAll(true)}
            className={`px-4 py-2 rounded-full text-xs font-black flex items-center gap-1.5 transition cursor-pointer ${
              summary?.status === 'finalized'
                ? 'bg-emerald-600/20 border-2 border-emerald-500 text-emerald-700 dark:text-emerald-300'
                : 'btn-modernize-primary'
            }`}
          >
            <Send className="w-3.5 h-3.5" />
            <span>
              {summary?.status === 'finalized'
                ? '✅ Rota Liberada'
                : 'Finalizar e Liberar Rota'}
            </span>
          </button>

          <button
            type="button"
            onClick={loadRoutes}
            title="Recarregar rotas"
            className="p-2 rounded-xl border border-slate-200 dark:border-zinc-700 text-slate-600 dark:text-zinc-300 hover:bg-slate-100 dark:hover:bg-zinc-800 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* BARRA DE SELEÇÃO DE TÉCNICOS */}
      <div className="modernize-card p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-extrabold uppercase text-slate-500 dark:text-zinc-400 mr-1">
            Técnicos na tela:
          </span>
          {allChipTechs.map((tName) => {
            const active = Boolean(techColumns[tName]);
            const count = (techColumns[tName] || []).length;
            return (
              <motion.button
                key={tName}
                type="button"
                whileTap={{ scale: 0.95 }}
                transition={SPRING_SNAPPY}
                onClick={() => toggleTechChip(tName)}
                className={`px-3 py-1.5 rounded-full text-xs font-extrabold flex items-center gap-1.5 border transition cursor-pointer ${
                  active
                    ? 'bg-blue-600 text-white border-blue-500 shadow-sm'
                    : 'bg-slate-100 dark:bg-zinc-900 text-slate-600 dark:text-zinc-300 border-slate-200 dark:border-zinc-700 hover:border-blue-400'
                }`}
              >
                {active ? <Check className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                <span>{tName}</span>
                {count > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full bg-white/25 text-[10px] font-mono">
                    {count}
                  </span>
                )}
              </motion.button>
            );
          })}
          <button
            type="button"
            onClick={addCustomTech}
            className="px-3 py-1.5 rounded-full text-xs font-bold bg-blue-500/10 text-blue-600 dark:text-sky-400 border border-blue-500/25 hover:bg-blue-500/20 flex items-center gap-1 cursor-pointer"
          >
            <UserPlus className="w-3.5 h-3.5" />
            <span>Outro Técnico</span>
          </button>
        </div>

        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={() => setCollapsedTechs(new Set())}
            className="px-2.5 py-1.5 rounded-xl text-[11px] font-bold bg-slate-100 dark:bg-zinc-900 text-slate-600 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700 hover:bg-slate-200 flex items-center gap-1 cursor-pointer"
          >
            <ChevronsDown className="w-3.5 h-3.5" />
            <span>Expandir</span>
          </button>
          <button
            type="button"
            onClick={() => setCollapsedTechs(new Set(Object.keys(techColumns)))}
            className="px-2.5 py-1.5 rounded-xl text-[11px] font-bold bg-slate-100 dark:bg-zinc-900 text-slate-600 dark:text-zinc-300 border border-slate-200 dark:border-zinc-700 hover:bg-slate-200 flex items-center gap-1 cursor-pointer"
          >
            <ChevronsUp className="w-3.5 h-3.5" />
            <span>Recolher</span>
          </button>
        </div>
      </div>

      {/* GRID PRINCIPAL DE DRAG & DROP */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-start">
          {/* ESQUERDA: AGUARDANDO DISTRIBUIÇÃO */}
          <div className="lg:col-span-5 modernize-card p-4 space-y-3">
            <div className="flex items-center justify-between pb-2.5 border-b border-slate-200/80 dark:border-zinc-800">
              <h3 className="text-xs font-black uppercase tracking-wider text-amber-600 dark:text-amber-400">
                Chamados Aguardando Distribuição
              </h3>
              <span className="font-mono text-xs font-black px-2.5 py-0.5 rounded-full bg-amber-500 text-slate-950">
                {unassigned.length}
              </span>
            </div>

            <UnassignedDropZone
              orders={unassigned}
              techOptions={allChipTechs}
              onQuickAssign={handleQuickAssign}
            />
          </div>

          {/* DIREITA: COLUNAS POR TÉCNICO */}
          <div className="lg:col-span-7 space-y-4">
            {Object.keys(techColumns).length === 0 ? (
              <div className="modernize-card p-8 text-center space-y-3 border-dashed border-2">
                <div className="w-12 h-12 rounded-2xl bg-blue-500/12 text-blue-600 dark:text-sky-400 flex items-center justify-center mx-auto">
                  <UserCheck className="w-6 h-6" />
                </div>
                <h4 className="text-sm font-black uppercase text-zinc-900 dark:text-white">
                  Nenhum Técnico Selecionado na Tela
                </h4>
                <p className="text-xs text-slate-500 dark:text-zinc-400 max-w-md mx-auto">
                  Clique nos nomes acima (ex: <strong>EDSON</strong>, <strong>ANTONIO</strong>,{' '}
                  <strong>ENZO</strong>) ou atribua um chamado diretamente pela lista da esquerda.
                </p>
              </div>
            ) : (
              Object.entries(techColumns).map(([tName, stops]) => (
                <TechDropZone
                  key={tName}
                  techName={tName}
                  stops={stops}
                  collapsed={collapsedTechs.has(tName)}
                  onToggleCollapse={handleToggleCollapseTech}
                  onRemoveTech={toggleTechChip}
                  onMoveStep={handleMoveStep}
                  onUnassign={handleUnassign}
                  onSaveNotes={handleSaveNotes}
                />
              ))
            )}
          </div>
        </div>

        <DragOverlay dropAnimation={ROUTE_DROP_ANIMATION}>
          {activeOrder ? (
            <div className="p-3.5 rounded-2xl bg-white dark:bg-zinc-900 border-2 border-blue-500 shadow-2xl max-w-sm rotate-1">
              <div className="font-black text-xs text-zinc-900 dark:text-white">
                {activeOrder.client_name}
              </div>
              <div className="text-[11px] font-mono text-blue-600 dark:text-sky-400 mt-0.5">
                {activeOrder.os_number ? `O.S. ${activeOrder.os_number}` : 'S/N'} •{' '}
                {activeOrder.equipment_model || activeOrder.sector}
              </div>
            </div>
          ) : null}
        </DragOverlay>
      </DndContext>

      {/* PAINEL PERSISTENTE QUANDO A ROTA JÁ ESTÁ FINALIZADA */}
      {summary?.status === 'finalized' && activeRouteEntries.length > 0 && (
        <div className="modernize-card p-5 space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h3 className="text-sm font-black uppercase text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" /> Espelho da Rota Pronta e Liberada
              </h3>
              <p className="text-xs text-slate-500 dark:text-zinc-400">
                A Recepção já consegue copiar esta rota e gerar os cards individuais por técnico.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setPreviewModalOpen(true)}
              className="btn-modernize-light px-4 py-2 text-xs cursor-pointer"
            >
              Ampliar / Exportar PNG
            </button>
          </div>
          {renderFinalizedSheet()}
        </div>
      )}

      {/* MODAL: NOVA TAREFA AVULSA */}
      <AnimatePresence>
        {taskModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={() => setTaskModalOpen(false)}
          >
            <motion.form
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              transition={{ duration: 0.22, ease: MOTION_EASE }}
              onClick={(e) => e.stopPropagation()}
              onSubmit={handleCreateTask}
              className="modernize-card max-w-lg w-full p-5 space-y-4"
            >
              <div className="flex items-center justify-between border-b border-slate-200 dark:border-zinc-800 pb-3">
                <h3 className="text-sm font-black uppercase text-zinc-900 dark:text-white">
                  Nova Tarefa / Parada Avulsa
                </h3>
                <button
                  type="button"
                  onClick={() => setTaskModalOpen(false)}
                  className="p-1.5 rounded-xl text-slate-400 hover:bg-slate-100 dark:hover:bg-zinc-800 cursor-pointer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <label className="block font-bold text-slate-600 dark:text-zinc-400 mb-1">
                    Cliente / Local / Bairro:
                  </label>
                  <input
                    type="text"
                    value={taskClient}
                    onChange={(e) => setTaskClient(e.target.value)}
                    placeholder="Ex: DB CAMPOS ELÍSEOS, BARATEIRO TEFÉ..."
                    className="w-full bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-2 text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block font-bold text-slate-600 dark:text-zinc-400 mb-1">
                      Nº O.S. (Opcional):
                    </label>
                    <input
                      type="text"
                      value={taskOs}
                      onChange={(e) => setTaskOs(e.target.value)}
                      placeholder="Ex: 26784"
                      className="w-full bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-2 text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                  <div>
                    <label className="block font-bold text-slate-600 dark:text-zinc-400 mb-1">
                      Setor / Equipamento:
                    </label>
                    <input
                      type="text"
                      value={taskSector}
                      onChange={(e) => setTaskSector(e.target.value)}
                      placeholder="Ex: FLV / PRIX 5 AZUL"
                      className="w-full bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-2 text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
                    />
                  </div>
                </div>

                <div>
                  <label className="block font-bold text-slate-600 dark:text-zinc-400 mb-1">
                    Tarefa Especial / Observação:
                  </label>
                  <input
                    type="text"
                    value={taskNotes}
                    onChange={(e) => setTaskNotes(e.target.value)}
                    placeholder="Ex: PEGAR ASS/CARIMBO, DEVOLVER BALANÇA..."
                    className="w-full bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-2 font-bold text-rose-600 dark:text-rose-400 focus:outline-none focus:border-blue-500"
                  />
                </div>

                <div>
                  <label className="block font-bold text-slate-600 dark:text-zinc-400 mb-1">
                    Atribuir para:
                  </label>
                  <select
                    value={taskTech}
                    onChange={(e) => setTaskTech(e.target.value)}
                    className="w-full bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-2 font-bold text-zinc-900 dark:text-white"
                  >
                    <option value="">-- Deixar em Aguardando --</option>
                    {allChipTechs.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2 border-t border-slate-200 dark:border-zinc-800">
                <button
                  type="button"
                  onClick={() => setTaskModalOpen(false)}
                  className="px-4 py-2 rounded-xl text-xs font-bold text-slate-600 dark:text-zinc-400 hover:bg-slate-100 dark:hover:bg-zinc-800 cursor-pointer"
                >
                  Cancelar
                </button>
                <button type="submit" className="btn-modernize-primary px-5 py-2 text-xs cursor-pointer">
                  Adicionar à Rota
                </button>
              </div>
            </motion.form>
          </motion.div>
        )}
      </AnimatePresence>

      {/* MODAL: PREVIEW DA ROTA FINALIZADA (PNG / CLIPBOARD) */}
      <AnimatePresence>
        {previewModalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4"
            onClick={() => setPreviewModalOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.96, y: 12 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.96, y: 8 }}
              onClick={(e) => e.stopPropagation()}
              className="modernize-card max-w-5xl w-full max-h-[92vh] flex flex-col overflow-hidden"
            >
              <div className="px-5 py-4 border-b border-slate-200 dark:border-zinc-800 flex flex-wrap items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-2xl bg-emerald-500/15 text-emerald-600 flex items-center justify-center">
                    <CheckCircle2 className="w-5 h-5" />
                  </div>
                  <div>
                    <h3 className="text-sm sm:text-base font-black uppercase text-zinc-900 dark:text-white">
                      Rota Pronta e Enviada ({formattedDate})
                    </h3>
                    <p className="text-xs text-slate-500 dark:text-zinc-400">
                      Copie a imagem direta para colar no WhatsApp ou baixe em alta resolução.
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-2 flex-wrap">
                  <button
                    type="button"
                    onClick={() => capturePreviewImage('copy')}
                    className="btn-modernize-primary px-4 py-2 text-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <Copy className="w-3.5 h-3.5" />
                    <span>Copiar Imagem (Ctrl+V)</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => capturePreviewImage('download')}
                    className="btn-ember-dark px-4 py-2 text-xs flex items-center gap-1.5 cursor-pointer"
                  >
                    <Download className="w-3.5 h-3.5" />
                    <span>Baixar PNG</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setPreviewModalOpen(false)}
                    className="p-2 rounded-xl text-slate-400 hover:bg-slate-100 dark:hover:bg-zinc-800 cursor-pointer"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>

              <div className="p-4 sm:p-6 overflow-y-auto flex-1 bg-slate-100/70 dark:bg-zinc-950/70">
                {renderFinalizedSheet()}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.section>
  );
};
