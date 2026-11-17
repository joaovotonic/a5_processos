import React, { memo, useEffect, useState } from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { FileText, Flame, Image as ImageIcon, Printer, Scale, Trash2, Unlock, CheckCircle, XCircle, Send, PackageCheck, GripVertical } from 'lucide-react';
import type { KanbanCard } from '../../types';
import { analyzeWeightDiff } from '../../lib/api';
import { CopyMorph } from '../fluid/copy-morph/CopyMorph';

interface KanbanCardItemProps {
  card: KanbanCard;
  isOverlay?: boolean;
  onOpenDetail: (osNumber: string) => void;
  onAdvanceAdmin: (osNumber: string, action: string) => void;
  onDeleteRequest: (card: KanbanCard) => void;
}

const KanbanCardItemBase: React.FC<KanbanCardItemProps> = ({
  card,
  isOverlay = false,
  onOpenDetail,
  onAdvanceAdmin,
  onDeleteRequest,
}) => {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: `card-${card.id}`,
    data: { type: 'card', card },
    disabled: isOverlay,
  });

  const [timerStr, setTimerStr] = useState<string>('');

  useEffect(() => {
    if (!card.timer_end_at) {
      setTimerStr('');
      return;
    }
    const tick = () => {
      const diffSec = Math.floor((new Date(card.timer_end_at!).getTime() - Date.now()) / 1000);
      if (diffSec <= 0) {
        setTimerStr('00:00');
      } else {
        const m = String(Math.floor(diffSec / 60)).padStart(2, '0');
        const s = String(diffSec % 60).padStart(2, '0');
        setTimerStr(`${m}:${s}`);
      }
    };
    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [card.timer_end_at]);

  const style: React.CSSProperties = isOverlay
    ? {
        transform: 'scale(1.02) rotate(1deg)',
        boxShadow: '0 22px 44px -10px rgba(37, 99, 235, 0.32)',
        willChange: 'transform',
      }
    : {
        transform: CSS.Translate.toString(transform),
        transition: transition ?? undefined,
        willChange: isDragging ? 'transform' : undefined,
      };

  const photoCount =
    (card.entry_photos?.length || 0) +
    (card.exit_photos?.length || 0) +
    (card.label_before_photos?.length || 0) +
    (card.label_after_photos?.length || 0) +
    (card.quote_photos?.length || 0);

  let hasWeightDiff = false;
  const wi = card.quote_data?.weights_initial || {};
  for (const [k, v] of Object.entries(wi)) {
    const d = analyzeWeightDiff(k, v);
    if (d?.isDiff) {
      hasWeightDiff = true;
      break;
    }
  }

  const phase = card.pipeline_phase || '';
  const listUpper = (card.list_title || '').toUpperCase();
  const isTech = Boolean(card.list_is_tech || listUpper.startsWith('TEC.'));

  let phasePill: { text: string; cls: string } | null = null;
  if (phase === 'EM_MANUTENCAO') {
    phasePill = { text: 'Finalizando', cls: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30' };
  } else if (phase === 'EM_ORCAMENTO' || (isTech && phase !== 'FINALIZADAS' && !card.finished_at)) {
    phasePill = { text: 'Orçamentando', cls: 'bg-amber-500/15 text-amber-600 dark:text-amber-400 border-amber-500/30' };
  } else if (card.list_role === 'pronta' || listUpper.includes('PRONTA') || phase === 'FINALIZADAS' || card.finished_at) {
    phasePill = { text: 'Pronta', cls: 'bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 border-emerald-500/30' };
  } else if (phase === 'ORCAMENTOS_FEITOS') {
    phasePill = { text: 'Orç. Feito', cls: 'bg-sky-500 text-slate-950 border-sky-400 font-black' };
  } else if (phase === 'ORCAMENTOS_ENVIADOS') {
    phasePill = { text: 'Enviado', cls: 'bg-blue-500/15 text-blue-600 dark:text-sky-400 border-blue-500/30' };
  } else if (phase === 'APROVADOS') {
    phasePill = { text: 'Aprovado', cls: 'bg-emerald-500 text-slate-950 border-emerald-400 font-black' };
  } else if (phase === 'BALANCAS_PENDENTES' || listUpper.includes('PENDENTE')) {
    phasePill = { text: 'Pendente Peça', cls: 'bg-orange-500/20 text-orange-600 dark:text-orange-400 border-orange-500/30' };
  }

  const isPlaceholder = isDragging && !isOverlay;

  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      onClick={() => !isOverlay && !isPlaceholder && onOpenDetail(card.os_number)}
      className={`group kanban-card-surface rounded-2xl p-3.5 border transition-colors duration-150 select-none ${
        isPlaceholder
          ? 'border-2 border-dashed border-blue-500/70 ember-hatch-blue cursor-grabbing'
          : isOverlay
          ? 'bg-white dark:bg-[#18181C] border-blue-500 ring-2 ring-blue-500/30 cursor-grabbing'
          : card.reopen_requested === 1
          ? 'bg-white dark:bg-[#18181C] border-amber-500 ring-2 ring-amber-500/25 cursor-pointer'
          : card.sla_expired
          ? 'bg-white dark:bg-[#18181C] border-sky-500 sla-pulse cursor-pointer'
          : 'bg-white dark:bg-[#18181C] border-slate-200/90 dark:border-zinc-800 hover:border-blue-500/60 hover:shadow-md hover:shadow-blue-500/10 cursor-pointer'
      }`}
    >
      <div className={isPlaceholder ? 'opacity-15 pointer-events-none' : undefined}>
      {/* Labels */}
      {card.labels && card.labels.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {card.labels.map((l, idx) => (
            <span
              key={`${l.name}-${idx}`}
              className="px-2 py-0.5 rounded-full text-[9.5px] font-extrabold uppercase tracking-wider shadow-xs"
              style={{ background: l.color, color: l.text_color || '#fff' }}
            >
              {l.name}
            </span>
          ))}
        </div>
      )}

      {/* Top row: OS badge + drag handle + status pills */}
      <div className="flex items-start justify-between gap-1.5 mb-2">
        <div className="flex items-center gap-1.5 min-w-0">
          <button
            type="button"
            {...listeners}
            onClick={(e) => e.stopPropagation()}
            aria-label="Arrastar cartão"
            className="p-0.5 -ml-1 rounded text-slate-400 hover:text-blue-500 cursor-grab active:cursor-grabbing shrink-0"
          >
            <GripVertical className="w-3.5 h-3.5" />
          </button>
          <span className="font-mono tabular-nums text-[11px] font-extrabold px-2 py-0.5 rounded-lg bg-slate-100 dark:bg-zinc-800/90 text-zinc-900 dark:text-zinc-100 border border-slate-200/80 dark:border-zinc-700/70">
            OS {card.os_number}
          </span>
        </div>

        <div className="flex flex-wrap gap-1 justify-end items-center">
          {card.reopen_requested === 1 && (
            <span className="text-[9.5px] bg-amber-500 text-slate-950 px-1.5 py-0.5 rounded-full font-black animate-pulse inline-flex items-center gap-0.5">
              <Unlock className="w-2.5 h-2.5" /> Reabrir
            </span>
          )}
          {phasePill && (
            <span className={`text-[9.5px] px-2 py-0.5 rounded-full font-bold border ${phasePill.cls}`}>
              {phasePill.text}
            </span>
          )}
          {hasWeightDiff && (
            <span className="text-[9.5px] bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/30 px-1.5 py-0.5 rounded-full font-bold inline-flex items-center gap-0.5">
              <Scale className="w-2.5 h-2.5" /> Dif.
            </span>
          )}
          {card.timer_end_at && (
            <span className="text-[9.5px] font-mono tabular-nums bg-sky-500/15 text-sky-600 dark:text-sky-400 border border-sky-500/30 px-1.5 py-0.5 rounded-full font-extrabold inline-flex items-center gap-0.5 animate-pulse">
              <Flame className="w-2.5 h-2.5" /> {timerStr || 'Estufa'}
            </span>
          )}
          {card.sla_expired && (
            <span className="text-[9.5px] font-mono tabular-nums bg-blue-500/10 text-blue-600 dark:text-sky-400 border border-blue-500/30 px-1.5 py-0.5 rounded-full font-bold">
              +{card.hours_in_stage}h
            </span>
          )}
        </div>
      </div>

      {/* Client & Equipment */}
      <h4 className="font-extrabold text-xs uppercase leading-snug text-zinc-900 dark:text-zinc-100 break-words">
        {card.client_name}
      </h4>
      <p className="text-[11px] text-slate-500 dark:text-zinc-400 truncate mt-0.5">
        {card.equipment_type}
        {card.equipment_model ? ` • ${card.equipment_model}` : ''}
      </p>

      {(card.admin_notes || card.reported_defect) && (
        <p
          className="mt-1.5 text-[10.5px] font-semibold text-amber-700 dark:text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1 truncate"
          title={card.admin_notes || card.reported_defect}
        >
          {card.admin_notes || card.reported_defect}
        </p>
      )}

      {/* Tech active banner */}
      {(isTech || phase === 'EM_ORCAMENTO' || phase === 'EM_MANUTENCAO') && !card.finished_at && phase !== 'FINALIZADAS' && (
        <div
          className={`mt-2 px-2.5 py-1 rounded-xl border text-[10.5px] font-extrabold flex items-center justify-between ${
            phase === 'EM_MANUTENCAO'
              ? 'bg-emerald-500/12 border-emerald-500/30 text-emerald-700 dark:text-emerald-300'
              : 'bg-amber-500/12 border-amber-500/30 text-amber-700 dark:text-amber-300'
          }`}
        >
          <span className="flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full animate-pulse ${phase === 'EM_MANUTENCAO' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span>{phase === 'EM_MANUTENCAO' ? 'FINALIZANDO BALANÇA' : 'ORÇAMENTANDO'}</span>
          </span>
        </div>
      )}

      {/* INMETRO seal with CopyMorph */}
      {card.inmetro_seal && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="mt-2 flex items-center justify-between gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/8 px-2.5 py-1.5"
        >
          <div className="min-w-0">
            <div className="text-[9px] font-extrabold uppercase tracking-wider text-emerald-600 dark:text-emerald-400">
              Lacre IPEM
            </div>
            <div className="text-[11px] font-bold font-mono tabular-nums text-zinc-900 dark:text-white truncate">
              {card.inmetro_seal}
            </div>
          </div>
          <CopyMorph text={card.inmetro_seal} label="Copiar" doneLabel="Copiado!" compact />
        </div>
      )}

      {/* Footer row */}
      <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-zinc-800/80 flex items-center justify-between gap-2 text-[10.5px] text-slate-400 dark:text-zinc-500">
        <span className="font-mono tabular-nums truncate">
          {card.created_at ? card.created_at.slice(0, 10) : ''}
        </span>
        <div className="flex items-center gap-1.5 shrink-0">
          {card.admin_notes && <FileText className="w-3.5 h-3.5 text-blue-500" />}
          {photoCount > 0 && (
            <span className="inline-flex items-center gap-0.5 font-mono tabular-nums">
              <ImageIcon className="w-3.5 h-3.5" />
              {photoCount}
            </span>
          )}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              window.open(`/etiqueta/${encodeURIComponent(card.os_number)}`, '_blank', 'width=450,height=380');
            }}
            aria-label="Imprimir etiqueta térmica"
            className="p-1 rounded-lg hover:bg-blue-500/15 hover:text-blue-600 dark:hover:text-sky-400 transition cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5" />
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onDeleteRequest(card);
            }}
            aria-label="Excluir O.S."
            className="p-1 rounded-lg hover:bg-rose-500/15 hover:text-rose-500 transition cursor-pointer"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Inline pipeline action buttons */}
      {(phase === 'ORCAMENTOS_FEITOS' || listUpper.includes('FEITA') || listUpper.includes('FEITO')) && (
        <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-zinc-800/80">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAdvanceAdmin(card.os_number, 'enviar_cliente');
            }}
            className="w-full py-1.5 px-3 rounded-full btn-modernize-primary text-[11px] flex items-center justify-center gap-1.5 cursor-pointer"
          >
            <Send className="w-3 h-3" />
            <span>OK (Enviar ao Cliente)</span>
          </button>
        </div>
      )}

      {(phase === 'ORCAMENTOS_ENVIADOS' || listUpper.includes('ENVIAD')) && (
        <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-zinc-800/80 grid grid-cols-2 gap-1.5">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAdvanceAdmin(card.os_number, 'aprovar');
            }}
            className="py-1.5 px-2 rounded-full bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white font-bold text-[10.5px] flex items-center justify-center gap-1 shadow-sm transition cursor-pointer"
          >
            <CheckCircle className="w-3 h-3" />
            <span>APROVADO</span>
          </button>
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAdvanceAdmin(card.os_number, 'nao_autorizado');
            }}
            className="py-1.5 px-2 rounded-full bg-rose-600 hover:bg-rose-500 active:scale-95 text-white font-bold text-[10.5px] flex items-center justify-center gap-1 shadow-sm transition cursor-pointer"
          >
            <XCircle className="w-3 h-3" />
            <span>NÃO AUT.</span>
          </button>
        </div>
      )}

      {(phase === 'NAO_AUTORIZADO' || listUpper.includes('NÃO AUTORIZAD') || listUpper.includes('NAO AUTORIZAD')) && (
        <div className="mt-2.5 pt-2 border-t border-slate-100 dark:border-zinc-800/80">
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              onAdvanceAdmin(card.os_number, 'fechar_balanca');
            }}
            className="w-full py-1.5 px-3 rounded-full bg-rose-700 hover:bg-rose-600 active:scale-95 text-white font-bold text-[11px] flex items-center justify-center gap-1.5 shadow transition cursor-pointer"
          >
            <PackageCheck className="w-3.5 h-3.5" />
            <span>FECHAR BALANÇA</span>
          </button>
        </div>
      )}
      </div>
    </div>
  );
};

export const KanbanCardItem = memo(KanbanCardItemBase);
