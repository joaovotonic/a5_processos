import React, { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import {
  Activity,
  Award,
  CheckCircle,
  Clock,
  FileSpreadsheet,
  Filter,
  Hourglass,
  RefreshCw,
  Search,
  Timer,
  Wrench,
} from 'lucide-react';
import type { DirectorReport } from '../../types';
import { SegmentedPicker } from '../fluid/segmented-picker/SegmentedPicker';
import {
  AnimatedProgressBar,
  AnimatedRing,
  BentoItem,
  CountUpValue,
  StaggerContainer,
} from '../motion/MotionPrimitives';
import { MOTION_EASE } from '../motion/motionTokens';

interface RelatoriosSectionProps {
  period: 'today' | 'week' | 'month' | 'all';
  onPeriodChange: (p: 'today' | 'week' | 'month' | 'all') => void;
  techFilter: string;
  onTechFilterChange: (t: string) => void;
  technicianOptions: string[];
  report: DirectorReport | null;
  loading: boolean;
  onRefresh: () => void;
}

const PHASE_BADGE: Record<string, string> = {
  PRONTAS: 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30',
  EM_ORCAMENTO: 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30',
  EM_MANUTENCAO: 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300 border-indigo-500/30',
  ORCAMENTOS_ENVIADOS: 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30',
};

export const RelatoriosSection: React.FC<RelatoriosSectionProps> = ({
  period,
  onPeriodChange,
  techFilter,
  onTechFilterChange,
  technicianOptions,
  report,
  loading,
  onRefresh,
}) => {
  const [osQuery, setOsQuery] = useState('');

  const k = report?.kpis || {
    total_prontas: 0,
    total_orcamentos_feitos: 0,
    tempo_medio_orcamento_str: '0m',
    tempo_medio_manutencao_str: '0m',
    balancas_aguardando_cliente: 0,
  };

  const techsPerf = report?.technicians_performance || [];
  const maxTechTotal = useMemo(() => {
    const m = Math.max(1, ...techsPerf.map((t) => (t.prontas_count || 0) + (t.orcamentos_count || 0)));
    return m;
  }, [techsPerf]);

  const filteredOs = useMemo(() => {
    const rows = report?.os_details || [];
    const q = osQuery.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((c) =>
      `${c.os_number} ${c.client_name} ${c.equipment_model} ${c.tech_name}`.toLowerCase().includes(q),
    );
  }, [report?.os_details, osQuery]);

  const completionPct = useMemo(() => {
    const totalFlow = k.total_prontas + k.balancas_aguardando_cliente;
    if (totalFlow === 0) return 100;
    return Math.round((k.total_prontas / totalFlow) * 100);
  }, [k.total_prontas, k.balancas_aguardando_cliente]);

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: MOTION_EASE }}
      className="space-y-4"
    >
      {/* BARRA DE FILTROS BENTO */}
      <div className="modernize-card p-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-xs font-extrabold uppercase tracking-wider text-slate-500 dark:text-zinc-400 flex items-center gap-1.5">
            <Filter className="w-3.5 h-3.5 text-blue-600 dark:text-sky-400" />
            <span>Período:</span>
          </span>
          <SegmentedPicker
            label="Período do relatório"
            value={period}
            onChange={(val) => onPeriodChange(val as 'today' | 'week' | 'month' | 'all')}
            options={[
              { value: 'today', label: 'Hoje' },
              { value: 'week', label: 'Semana' },
              { value: 'month', label: 'Este Mês' },
              { value: 'all', label: 'Geral' },
            ]}
          />
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <label htmlFor="diretoriaTechFilter" className="text-xs font-bold text-slate-500 dark:text-zinc-400">
            Técnico:
          </label>
          <select
            id="diretoriaTechFilter"
            value={techFilter}
            onChange={(e) => onTechFilterChange(e.target.value)}
            className="bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-1.5 text-xs font-bold text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
          >
            <option value="">TODOS OS TÉCNICOS</option>
            {technicianOptions.map((tech) => (
              <option key={tech} value={tech}>
                {tech}
              </option>
            ))}
          </select>

          <button
            type="button"
            onClick={onRefresh}
            title="Atualizar dados agora"
            className="btn-modernize-primary px-3.5 py-2 text-xs flex items-center gap-1.5 cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span className="hidden sm:inline">Atualizar</span>
          </button>
        </div>
      </div>

      {/* 5 CARDS DE KPIs BENTO COM MOTION COUNT-UP + RING */}
      <StaggerContainer className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3.5">
        <BentoItem hoverLift>
          <div className="ember-blue-card p-4 h-full flex flex-col justify-between">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10.5px] font-black uppercase tracking-wider text-white/85">
                Balanças Prontas
              </span>
              <div className="w-8 h-8 rounded-xl bg-white/15 flex items-center justify-center">
                <CheckCircle className="w-4 h-4 text-white" />
              </div>
            </div>
            <div className="flex items-end justify-between gap-2 pt-3">
              <div>
                <div className="text-3xl font-black tracking-tight tabular-nums">
                  <CountUpValue value={k.total_prontas} />
                </div>
                <p className="text-[11px] text-white/80 font-medium mt-0.5">
                  Concluídas na esteira
                </p>
              </div>
              <AnimatedRing
                percent={completionPct}
                size={46}
                strokeWidth={4.5}
                color="#ffffff"
                trackColor="rgba(255,255,255,0.25)"
              />
            </div>
          </div>
        </BentoItem>

        <BentoItem hoverLift>
          <div className="modernize-card p-4 h-full flex flex-col justify-between">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10.5px] font-black uppercase tracking-wider text-blue-600 dark:text-sky-400">
                Laudos Emitidos
              </span>
              <div className="w-8 h-8 rounded-xl bg-blue-500/12 text-blue-600 dark:text-sky-400 flex items-center justify-center">
                <FileSpreadsheet className="w-4 h-4" />
              </div>
            </div>
            <div className="pt-3">
              <div className="text-3xl font-black text-zinc-900 dark:text-white tabular-nums">
                <CountUpValue value={k.total_orcamentos_feitos} />
              </div>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400 mt-0.5">
                Orçamentos concluídos
              </p>
            </div>
          </div>
        </BentoItem>

        <BentoItem hoverLift>
          <div className="modernize-card p-4 h-full flex flex-col justify-between">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10.5px] font-black uppercase tracking-wider text-amber-600 dark:text-amber-400">
                Média Orçamento
              </span>
              <div className="w-8 h-8 rounded-xl bg-amber-500/12 text-amber-600 dark:text-amber-400 flex items-center justify-center">
                <Timer className="w-4 h-4" />
              </div>
            </div>
            <div className="pt-3">
              <div className="text-2xl sm:text-3xl font-black text-zinc-900 dark:text-white font-mono tabular-nums">
                {k.tempo_medio_orcamento_str || '0m'}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400 mt-0.5">
                Diagnóstico líquido
              </p>
            </div>
          </div>
        </BentoItem>

        <BentoItem hoverLift>
          <div className="modernize-card p-4 h-full flex flex-col justify-between">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10.5px] font-black uppercase tracking-wider text-indigo-600 dark:text-indigo-400">
                Média Conserto
              </span>
              <div className="w-8 h-8 rounded-xl bg-indigo-500/12 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
                <Wrench className="w-4 h-4" />
              </div>
            </div>
            <div className="pt-3">
              <div className="text-2xl sm:text-3xl font-black text-zinc-900 dark:text-white font-mono tabular-nums">
                {k.tempo_medio_manutencao_str || '0m'}
              </div>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400 mt-0.5">
                Manutenção líquida
              </p>
            </div>
          </div>
        </BentoItem>

        <BentoItem hoverLift>
          <div className="modernize-card p-4 h-full flex flex-col justify-between">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10.5px] font-black uppercase tracking-wider text-rose-600 dark:text-rose-400">
                Aguardando Cliente
              </span>
              <div className="w-8 h-8 rounded-xl bg-rose-500/12 text-rose-600 dark:text-rose-400 flex items-center justify-center">
                <Hourglass className="w-4 h-4" />
              </div>
            </div>
            <div className="pt-3">
              <div className="text-3xl font-black text-zinc-900 dark:text-white tabular-nums">
                <CountUpValue value={k.balancas_aguardando_cliente} />
              </div>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400 mt-0.5">
                Aprovação pendente
              </p>
            </div>
          </div>
        </BentoItem>
      </StaggerContainer>

      {/* RANKING DE TÉCNICOS COM EMBER HATCH PROGRESS BARS */}
      <div className="modernize-card p-5 space-y-3.5">
        <div className="flex items-center justify-between border-b border-slate-200/80 dark:border-zinc-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-blue-500/12 text-blue-600 dark:text-sky-400 flex items-center justify-center">
              <Award className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-zinc-900 dark:text-white">
                Desempenho por Técnico
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                Proporção de laudos e entregas concluídas no período
              </p>
            </div>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-zinc-400 border-b border-slate-200/80 dark:border-zinc-800">
                <th className="py-2.5 px-3">Técnico</th>
                <th className="py-2.5 px-3 text-center">Orçamentos</th>
                <th className="py-2.5 px-3 text-center">Prontas</th>
                <th className="py-2.5 px-3 hidden md:table-cell w-44">Ritmo</th>
                <th className="py-2.5 px-3 text-center">Tempo Médio</th>
                <th className="py-2.5 px-3 text-right">Tempo Líquido Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/60 dark:divide-zinc-800/70 text-xs">
              {techsPerf.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-slate-400 dark:text-zinc-500 font-semibold">
                    Nenhum registro para os filtros selecionados.
                  </td>
                </tr>
              ) : (
                techsPerf.map((t) => {
                  const score = (t.prontas_count || 0) + (t.orcamentos_count || 0);
                  const pct = Math.round((score / maxTechTotal) * 100);
                  return (
                    <tr key={t.name} className="hover:bg-slate-50/80 dark:hover:bg-zinc-900/60 transition">
                      <td className="py-3 px-3 font-extrabold text-zinc-900 dark:text-white flex items-center gap-2">
                        <span
                          className={`w-2.5 h-2.5 rounded-full ${
                            t.prontas_count > 0 ? 'bg-emerald-500' : 'bg-slate-400 dark:bg-zinc-600'
                          }`}
                        />
                        <span className="text-sm">{t.name}</span>
                      </td>
                      <td className="py-3 px-3 text-center font-mono font-bold text-blue-600 dark:text-sky-400 text-sm">
                        {t.orcamentos_count}
                      </td>
                      <td className="py-3 px-3 text-center font-mono font-black text-emerald-600 dark:text-emerald-400 text-sm">
                        {t.prontas_count}
                      </td>
                      <td className="py-3 px-3 hidden md:table-cell">
                        <AnimatedProgressBar percent={pct} heightClass="h-2.5" />
                      </td>
                      <td className="py-3 px-3 text-center font-mono text-slate-700 dark:text-zinc-300">
                        {t.tempo_medio_str || '-'}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-black text-amber-600 dark:text-amber-400">
                        {t.tempo_total_str || '0s'}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* TABELA ANALÍTICA DE O.S. */}
      <div className="modernize-card p-5 space-y-3.5">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200/80 dark:border-zinc-800 pb-3">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-2xl bg-indigo-500/12 text-indigo-600 dark:text-indigo-400 flex items-center justify-center">
              <Activity className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-extrabold text-zinc-900 dark:text-white">
                Rastreabilidade Analítica de O.S.
              </h3>
              <p className="text-[11px] text-slate-500 dark:text-zinc-400">
                Tempos exatos de orçamento, manutenção e status por equipamento
              </p>
            </div>
          </div>

          <div className="relative w-full sm:w-72">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={osQuery}
              onChange={(e) => setOsQuery(e.target.value)}
              placeholder="Buscar O.S., cliente ou técnico..."
              className="w-full bg-slate-50 dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl pl-8 pr-3 py-1.5 text-xs text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="text-[11px] font-extrabold uppercase tracking-wider text-slate-500 dark:text-zinc-400 border-b border-slate-200/80 dark:border-zinc-800">
                <th className="py-2.5 px-3">O.S.</th>
                <th className="py-2.5 px-3">Cliente</th>
                <th className="py-2.5 px-3">Modelo</th>
                <th className="py-2.5 px-3">Técnico</th>
                <th className="py-2.5 px-3 text-center">Tempo Orç.</th>
                <th className="py-2.5 px-3 text-center">Tempo Conserto</th>
                <th className="py-2.5 px-3 text-center">Total Líquido</th>
                <th className="py-2.5 px-3 text-right">Fase</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200/60 dark:divide-zinc-800/70 text-xs">
              {filteredOs.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-6 text-center text-slate-400 dark:text-zinc-500 font-semibold">
                    Nenhuma O.S. encontrada para o período ou filtro.
                  </td>
                </tr>
              ) : (
                filteredOs.map((c) => {
                  const badge =
                    PHASE_BADGE[c.phase] ||
                    'bg-slate-200/70 dark:bg-zinc-800 text-slate-700 dark:text-zinc-300 border-slate-300/60 dark:border-zinc-700';
                  return (
                    <tr
                      key={`${c.os_number}-${c.phase}`}
                      className="hover:bg-slate-50/80 dark:hover:bg-zinc-900/60 transition"
                    >
                      <td className="py-2.5 px-3 font-mono font-black text-blue-600 dark:text-sky-400">
                        OS {c.os_number}
                      </td>
                      <td className="py-2.5 px-3 font-bold text-zinc-900 dark:text-zinc-100 truncate max-w-[180px]">
                        {c.client_name}
                      </td>
                      <td className="py-2.5 px-3 text-slate-600 dark:text-zinc-400 truncate max-w-[150px]">
                        {c.equipment_model || 'Toledo Prix'}
                      </td>
                      <td className="py-2.5 px-3 font-semibold text-zinc-800 dark:text-zinc-200">
                        {c.tech_name || '-'}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono text-amber-600 dark:text-amber-300">
                        {c.tempo_orcamento_str}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono text-indigo-600 dark:text-indigo-300">
                        {c.tempo_manutencao_str}
                      </td>
                      <td className="py-2.5 px-3 text-center font-mono font-black text-emerald-600 dark:text-emerald-400 bg-emerald-500/5">
                        <span className="inline-flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          {c.tempo_liquido_str}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <span
                          className={`text-[10px] font-bold uppercase font-mono px-2.5 py-0.5 rounded-full border ${badge}`}
                        >
                          {(c.phase || '').replace(/_/g, ' ')}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </motion.section>
  );
};
