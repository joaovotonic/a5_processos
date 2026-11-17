import React from 'react';
import type { ExternalOrder } from '../types';

interface RouteCompactCardProps {
  title: string;
  shiftLabel?: string;
  dateFormatted: string;
  techGroups: Array<[string, ExternalOrder[]]>;
  showAttendanceActions?: boolean;
  onAttendance?: (order: ExternalOrder, attended: boolean) => void;
}

export const RouteCompactCard: React.FC<RouteCompactCardProps> = ({
  title,
  shiftLabel = '',
  dateFormatted,
  techGroups,
  showAttendanceActions = false,
  onAttendance,
}) => {
  const nonEmpty = techGroups.filter(([, stops]) => stops && stops.length > 0);
  const cleanShift = shiftLabel.trim();
  const hasShift = Boolean(cleanShift && cleanShift.toUpperCase() !== 'GERAL');

  return (
    <div className="w-full max-w-[480px] rounded-2xl overflow-hidden border border-slate-300 dark:border-zinc-700 bg-white dark:bg-zinc-900 shadow-sm">
      {/* Cabeçalho compacto estilo cartão WhatsApp */}
      <div className="px-3.5 py-2.5 bg-slate-900 text-white border-b-2 border-blue-500 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="font-black text-xs uppercase tracking-wider truncate">
            A5 TECNOLOGIA • {title}
          </div>
          {hasShift && (
            <div className="text-[10px] font-bold text-sky-400 uppercase">
              TURNO: {cleanShift}
            </div>
          )}
        </div>
        <span className="font-mono text-[11px] font-bold text-slate-200 shrink-0">
          {dateFormatted}
        </span>
      </div>

      <div className="p-2.5 space-y-3 bg-slate-50/60 dark:bg-zinc-950/60">
        {nonEmpty.length === 0 ? (
          <p className="text-center py-6 text-xs text-slate-500 font-semibold">
            Nenhuma parada atribuída nesta data.
          </p>
        ) : (
          nonEmpty.map(([tName, stops]) => (
            <div key={tName} className="space-y-1.5">
              <div className="px-3 py-1.5 rounded-xl bg-blue-700 text-white flex items-center justify-between text-xs font-black uppercase">
                <span>🔧 TÉCNICO: {tName}</span>
                <span className="font-mono text-blue-100 text-[11px]">
                  {stops.length} parada{stops.length > 1 ? 's' : ''}
                </span>
              </div>

              <div className="space-y-1.5">
                {stops.map((s, idx) => (
                  <div
                    key={s.id}
                    className="p-2.5 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-800 space-y-1"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="w-6 h-6 rounded-md bg-blue-600 text-white font-mono font-black text-[11px] flex items-center justify-center shrink-0">
                          {idx + 1}º
                        </span>
                        <strong className="text-xs font-black uppercase text-slate-900 dark:text-white leading-snug break-words">
                          {s.client_name}
                        </strong>
                      </div>
                      <span className="px-2 py-0.5 rounded-md bg-blue-50 dark:bg-blue-950/50 border border-blue-200 dark:border-blue-800 font-mono text-[10.5px] font-black text-blue-700 dark:text-sky-300 shrink-0">
                        {s.os_number ? `OS ${s.os_number}` : 'S/N'}
                      </span>
                    </div>

                    {(s.sector || s.equipment_model) && (
                      <div className="text-[11px] font-semibold text-slate-600 dark:text-zinc-300 pl-8">
                        {s.sector ? `Setor: ${s.sector}` : ''}
                        {s.sector && s.equipment_model ? ' • ' : ''}
                        {s.equipment_model ? `Equip: ${s.equipment_model}` : ''}
                      </div>
                    )}

                    {s.reported_defect && (
                      <div className="text-[11px] font-semibold text-slate-800 dark:text-zinc-200 pl-8">
                        Defeito: {s.reported_defect}
                      </div>
                    )}

                    {s.tasks_notes && (
                      <div className="ml-8 px-2 py-1 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-900/50 text-rose-700 dark:text-rose-300 font-extrabold text-[11px] uppercase">
                        ⚠️ {s.tasks_notes}
                      </div>
                    )}

                    {showAttendanceActions && onAttendance && (
                      <div className="pt-1 pl-8 flex items-center gap-1.5">
                        <button
                          type="button"
                          onClick={() => onAttendance(s, true)}
                          className={`px-2.5 py-1 rounded-lg text-[10.5px] font-bold cursor-pointer ${
                            s.attendance_status === 'attended'
                              ? 'bg-emerald-600 text-white'
                              : 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200'
                          }`}
                        >
                          ✓ Atendido
                        </button>
                        <button
                          type="button"
                          onClick={() => onAttendance(s, false)}
                          className="px-2.5 py-1 rounded-lg text-[10.5px] font-bold bg-rose-100 text-rose-700 hover:bg-rose-200 cursor-pointer"
                        >
                          ✕ Não Atendido
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
