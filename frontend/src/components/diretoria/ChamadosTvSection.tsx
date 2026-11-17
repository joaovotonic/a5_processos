import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  CheckCircle2,
  ClipboardList,
  Mic,
  MicOff,
  Radio,
  RefreshCw,
  Send,
  ShieldAlert,
  Sparkles,
  UserCheck,
  Volume2,
  Wrench,
} from 'lucide-react';
import type { BoardData, CallTarget, KanbanCard } from '../../types';
import { apiJson } from '../../lib/api';
import { CountUpValue, BentoItem, StaggerContainer } from '../motion/MotionPrimitives';
import { MOTION_EASE, SPRING_SNAPPY } from '../motion/motionTokens';

interface ChamadosTvSectionProps {
  callTargets: CallTarget[];
  board: BoardData | null;
  onRefreshBoard: () => void;
  onToast: (msg: string) => void;
}

export const ChamadosTvSection: React.FC<ChamadosTvSectionProps> = ({
  callTargets,
  board,
  onRefreshBoard,
  onToast,
}) => {
  const [isUrgent, setIsUrgent] = useState(false);
  const [customMsg, setCustomMsg] = useState('');
  const [voiceTarget, setVoiceTarget] = useState('TODOS (OFICINA TODA)');
  const [isRecording, setIsRecording] = useState(false);
  const [recordSeconds, setRecordSeconds] = useState(0);
  const [lastCalled, setLastCalled] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<BlobPart[]>([]);
  const timerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timerRef.current) window.clearInterval(timerRef.current);
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  const emitDirectorCall = async (target: string, message: string, audioBase64?: string) => {
    const res = await apiJson<{ success: boolean; error?: string }>('/api/director/call', {
      method: 'POST',
      body: JSON.stringify({
        tech_name: target,
        message,
        is_urgent: isUrgent,
        audio_base64: audioBase64 || null,
        sender: 'Sr. Jacson',
      }),
    });
    if (!res.ok) {
      onToast(res.data?.error || 'Erro ao disparar chamado na TV.');
      return false;
    }
    setLastCalled(target);
    window.setTimeout(() => setLastCalled((curr) => (curr === target ? null : curr)), 2400);
    return true;
  };

  const handleQuickCall = async (person: CallTarget) => {
    const msg = isUrgent
      ? 'Favor comparecer urgente na sala do Sr. Jacson.'
      : 'Favor comparecer à sala do Sr. Jacson.';
    const ok = await emitDirectorCall(person.target, msg);
    if (ok) onToast(`📢 Chamado emitido na TV para: ${person.name}!`);
  };

  const handleSendCustom = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = customMsg.trim();
    if (!clean) {
      onToast('Escreva uma mensagem antes de enviar para a TV.');
      return;
    }
    const ok = await emitDirectorCall('TODOS (OFICINA TODA)', clean);
    if (ok) {
      setCustomMsg('');
      onToast('📢 Mensagem transmitida para a TV da oficina!');
    }
  };

  const startVoiceRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      chunksRef.current = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunksRef.current.push(ev.data);
      };
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        if (timerRef.current) {
          window.clearInterval(timerRef.current);
          timerRef.current = null;
        }
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' });
        if (blob.size < 400) {
          onToast('Áudio muito curto. Tente falar novamente.');
          return;
        }
        const reader = new FileReader();
        reader.onloadend = () => {
          const dataUrl = String(reader.result || '');
          if (dataUrl) {
            emitDirectorCall(
              voiceTarget,
              'Mensagem de voz ao vivo da Diretoria.',
              dataUrl,
            );
            onToast(`🎙️ Áudio transmitido na TV para: ${voiceTarget}!`);
          }
        };
        reader.readAsDataURL(blob);
      };
      mediaRecorderRef.current = recorder;
      recorder.start();
      setIsRecording(true);
      setRecordSeconds(0);
      timerRef.current = window.setInterval(() => setRecordSeconds((s) => s + 1), 1000);
    } catch {
      onToast('Microfone indisponível neste navegador/dispositivo.');
    }
  };

  const stopVoiceRecording = () => {
    setIsRecording(false);
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === 'recording') {
      mediaRecorderRef.current.stop();
    }
  };

  // Deriva métricas ao vivo da oficina a partir do quadro Kanban
  const lists = board?.lists || [];
  const orcList =
    lists.find((l) => l.role === 'orcamento' || (l.title || '').toUpperCase() === 'ORÇAMENTOS') || {
      cards: [] as KanbanCard[],
    };
  const orcCards = orcList.cards || [];

  const techLists = lists.filter(
    (l) => l.is_tech === 1 || (l.title || '').toUpperCase().startsWith('TEC.'),
  );
  const activeTechCount = techLists.reduce((acc, l) => acc + (l.cards?.length || 0), 0);

  const aprList =
    lists.find(
      (l) => l.role === 'aprovada' || (l.title || '').toUpperCase().includes('APROVAD'),
    ) || { cards: [] as KanbanCard[] };
  const aprCards = aprList.cards || [];

  return (
    <motion.section
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3, ease: MOTION_EASE }}
      className="modernize-card p-5 sm:p-6 space-y-5"
    >
      {/* CABEÇALHO DA CENTRAL DE CHAMADOS */}
      <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-slate-200/80 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-blue-500 to-blue-700 text-white flex items-center justify-center shadow-lg shadow-blue-600/25 shrink-0">
            <Volume2 className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h2 className="text-sm sm:text-base font-extrabold tracking-tight text-zinc-900 dark:text-white">
                Central de Chamados na TV
              </h2>
              <span className="inline-flex items-center gap-1 text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-blue-500/12 text-blue-600 dark:text-sky-400 border border-blue-500/25">
                <Sparkles className="w-3 h-3" /> Audio Ducking Ativo
              </span>
            </div>
            <p className="text-xs text-slate-500 dark:text-zinc-400 mt-0.5">
              Abaixa o som do YouTube na TV automaticamente e chama a equipe em 1 clique.
            </p>
          </div>
        </div>

        {/* TOGGLE DE URGÊNCIA */}
        <motion.button
          type="button"
          whileTap={{ scale: 0.96 }}
          onClick={() => setIsUrgent((u) => !u)}
          className={`px-4 py-2 rounded-full text-xs font-extrabold border flex items-center gap-2 transition cursor-pointer ${
            isUrgent
              ? 'border-rose-500 bg-rose-500/15 text-rose-600 dark:text-rose-300 shadow-md shadow-rose-500/15'
              : 'border-slate-200 dark:border-zinc-700 bg-slate-100 dark:bg-zinc-900 text-slate-700 dark:text-zinc-300 hover:border-rose-400'
          }`}
        >
          <span
            className={`w-2.5 h-2.5 rounded-full ${
              isUrgent ? 'bg-rose-500 animate-ping' : 'bg-slate-400 dark:bg-zinc-500'
            }`}
          />
          <ShieldAlert className="w-3.5 h-3.5" />
          <span>{isUrgent ? 'URGENTE ATIVADO' : 'Chamado Normal'}</span>
        </motion.button>
      </div>

      {/* GRID BENTO DE BOTÕES DE 1 CLIQUE */}
      <StaggerContainer className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3">
        {callTargets.map((person) => {
          const isAdm = person.role === 'ADM';
          const justCalled = lastCalled === person.target;
          return (
            <BentoItem key={person.target} hoverLift>
              <motion.button
                type="button"
                whileTap={{ scale: 0.95 }}
                transition={SPRING_SNAPPY}
                onClick={() => handleQuickCall(person)}
                className={`w-full h-full min-h-[104px] p-4 rounded-2xl border text-left flex flex-col justify-between transition cursor-pointer relative overflow-hidden group ${
                  justCalled
                    ? 'border-emerald-500 bg-emerald-500/15 shadow-lg shadow-emerald-500/15'
                    : isAdm
                      ? 'border-indigo-300/60 dark:border-indigo-500/25 bg-indigo-50/70 dark:bg-indigo-950/25 hover:border-indigo-500'
                      : 'border-blue-300/60 dark:border-sky-500/25 bg-blue-50/70 dark:bg-sky-950/25 hover:border-blue-500'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span
                    className={`text-[10px] font-black uppercase tracking-wider px-2 py-0.5 rounded-full ${
                      isAdm
                        ? 'bg-indigo-500/15 text-indigo-700 dark:text-indigo-300'
                        : 'bg-blue-500/15 text-blue-700 dark:text-sky-300'
                    }`}
                  >
                    {person.role}
                  </span>
                  <span
                    className={`w-8 h-8 rounded-xl flex items-center justify-center transition-transform group-hover:scale-110 ${
                      isAdm
                        ? 'bg-indigo-500/15 text-indigo-600 dark:text-indigo-400'
                        : 'bg-blue-500/15 text-blue-600 dark:text-sky-400'
                    }`}
                  >
                    {isAdm ? <UserCheck className="w-4 h-4" /> : <Wrench className="w-4 h-4" />}
                  </span>
                </div>
                <div className="pt-2">
                  <strong className="text-sm font-black uppercase tracking-tight text-zinc-900 dark:text-white block truncate">
                    {person.name}
                  </strong>
                  <span className="text-[10px] font-semibold text-slate-500 dark:text-zinc-400">
                    {justCalled ? '✓ Chamado enviado' : 'Clique p/ chamar'}
                  </span>
                </div>
              </motion.button>
            </BentoItem>
          );
        })}
      </StaggerContainer>

      {/* COMUNICAÇÃO PERSONALIZADA (VOZ AO VIVO + TEXTO TTS) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 pt-1">
        {/* MENSAGEM TTS */}
        <form onSubmit={handleSendCustom} className="lg:col-span-7 bento-inner-tile p-3.5 flex flex-col sm:flex-row gap-2.5 items-stretch sm:items-center">
          <input
            type="text"
            value={customMsg}
            onChange={(e) => setCustomMsg(e.target.value)}
            placeholder="Digite uma mensagem para a TV ler em voz alta (TTS)..."
            className="flex-1 bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3.5 py-2.5 text-xs font-medium text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
          />
          <button
            type="submit"
            className="btn-modernize-primary px-5 py-2.5 text-xs flex items-center justify-center gap-2 shrink-0 cursor-pointer"
          >
            <Send className="w-3.5 h-3.5" />
            <span>Falar na TV</span>
          </button>
        </form>

        {/* MICROFONE AO VIVO */}
        <div className="lg:col-span-5 bento-inner-tile p-3.5 flex flex-wrap items-center gap-2.5">
          <select
            value={voiceTarget}
            onChange={(e) => setVoiceTarget(e.target.value)}
            disabled={isRecording}
            className="flex-1 min-w-[130px] bg-white dark:bg-zinc-900 border border-slate-200 dark:border-zinc-700 rounded-xl px-3 py-2 text-xs font-bold text-zinc-900 dark:text-white focus:outline-none focus:border-blue-500"
          >
            <option value="TODOS (OFICINA TODA)">📢 Toda a Oficina</option>
            {callTargets.map((t) => (
              <option key={t.target} value={t.target}>
                🎙️ {t.name}
              </option>
            ))}
          </select>

          <AnimatePresence mode="wait">
            {!isRecording ? (
              <motion.button
                key="mic-idle"
                initial={{ opacity: 0.85 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                type="button"
                onClick={startVoiceRecording}
                className="btn-ember-dark px-4 py-2 text-xs flex items-center gap-2 cursor-pointer"
              >
                <Mic className="w-3.5 h-3.5 text-sky-400" />
                <span>Gravar Voz</span>
              </motion.button>
            ) : (
              <motion.button
                key="mic-rec"
                initial={{ scale: 0.96 }}
                animate={{ scale: 1 }}
                exit={{ scale: 0.96 }}
                type="button"
                onClick={stopVoiceRecording}
                className="px-4 py-2 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-black flex items-center gap-2 shadow-lg shadow-rose-500/30 animate-pulse cursor-pointer"
              >
                <MicOff className="w-3.5 h-3.5" />
                <span className="tabular-nums">Enviar ({recordSeconds}s)</span>
              </motion.button>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* VISÃO RÁPIDA DA OFICINA EM TEMPO REAL */}
      <div className="pt-3 border-t border-slate-200/80 dark:border-zinc-800 space-y-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h3 className="text-xs font-black uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
              Visão Rápida da Oficina (Tempo Real)
            </h3>
          </div>
          <button
            type="button"
            onClick={onRefreshBoard}
            className="text-xs font-bold text-blue-600 dark:text-sky-400 hover:underline flex items-center gap-1 cursor-pointer"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Atualizar</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* 1. PARA ORÇAMENTO */}
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/6 dark:bg-amber-950/15 p-3.5 flex flex-col">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-amber-500/20">
              <span className="text-[11px] font-black uppercase text-amber-700 dark:text-amber-400 flex items-center gap-1.5">
                <ClipboardList className="w-3.5 h-3.5" />
                <span>Para Orçamento</span>
              </span>
              <span className="font-mono text-xs font-black px-2.5 py-0.5 rounded-full bg-amber-500 text-slate-950">
                <CountUpValue value={orcCards.length} />
              </span>
            </div>
            <div className="space-y-1.5 max-h-[190px] overflow-y-auto pr-1 text-xs">
              {orcCards.length === 0 ? (
                <p className="text-[11px] text-slate-400 dark:text-zinc-500 py-4 text-center">
                  Nenhuma balança aguardando orçamento.
                </p>
              ) : (
                orcCards.map((c) => (
                  <div
                    key={c.id}
                    className="px-2.5 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200/80 dark:border-zinc-800 flex items-center justify-between gap-2 shadow-2xs"
                  >
                    <div className="min-w-0">
                      <span className="font-mono font-black text-[11px] text-amber-600 dark:text-amber-400">
                        OS {c.os_number}
                      </span>
                      <span className="font-bold text-[11px] text-zinc-800 dark:text-zinc-100 ml-1.5 truncate block sm:inline">
                        {c.client_name}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 dark:text-zinc-400 truncate max-w-[100px] shrink-0">
                      {c.equipment_model || c.equipment_type}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* 2. TÉCNICOS NA BANCADA */}
          <div className="rounded-2xl border border-blue-500/30 bg-blue-500/6 dark:bg-sky-950/15 p-3.5 flex flex-col">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-blue-500/20">
              <span className="text-[11px] font-black uppercase text-blue-700 dark:text-sky-400 flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5" />
                <span>Técnicos na Bancada</span>
              </span>
              <span className="font-mono text-xs font-black px-2.5 py-0.5 rounded-full bg-blue-600 text-white">
                <CountUpValue value={activeTechCount} />
              </span>
            </div>
            <div className="space-y-1.5 max-h-[190px] overflow-y-auto pr-1 text-xs">
              {techLists.length === 0 ? (
                <p className="text-[11px] text-slate-400 dark:text-zinc-500 py-4 text-center">
                  Nenhum técnico listado.
                </p>
              ) : (
                techLists.map((tl) => {
                  const techName = (tl.title || '').replace(/^TEC\.\s*/i, '').trim();
                  const cards = tl.cards || [];
                  if (cards.length === 0) {
                    return (
                      <div
                        key={tl.id}
                        className="px-2.5 py-1.5 rounded-xl bg-white/70 dark:bg-zinc-900/50 border border-slate-200/70 dark:border-zinc-800 flex items-center justify-between gap-2 opacity-75"
                      >
                        <span className="font-bold text-[11px] text-slate-700 dark:text-zinc-300">
                          🔧 {techName}
                        </span>
                        <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-slate-200 dark:bg-zinc-800 text-slate-600 dark:text-zinc-400">
                          Livre
                        </span>
                      </div>
                    );
                  }
                  return cards.map((c) => {
                    const isMaint = c.pipeline_phase === 'EM_MANUTENCAO';
                    return (
                      <div
                        key={`${tl.id}-${c.id}`}
                        className="px-2.5 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-blue-500/30 space-y-0.5 shadow-2xs"
                      >
                        <div className="flex items-center justify-between gap-1.5">
                          <span className="font-black text-[11px] text-blue-600 dark:text-sky-400 truncate">
                            👨‍🔧 {techName}
                          </span>
                          <span
                            className={`text-[9px] font-black uppercase px-2 py-0.5 rounded-full shrink-0 ${
                              isMaint
                                ? 'bg-emerald-500 text-slate-950'
                                : 'bg-amber-500 text-slate-950'
                            }`}
                          >
                            {isMaint ? '🔧 Consertando' : '🔬 Orçamentando'}
                          </span>
                        </div>
                        <div className="flex items-center justify-between gap-2 text-[11px]">
                          <span className="font-bold text-zinc-900 dark:text-white truncate">
                            <strong className="font-mono text-blue-600 dark:text-sky-400">
                              OS {c.os_number}
                            </strong>{' '}
                            • {c.client_name}
                          </span>
                          <span className="text-[10px] text-slate-400 shrink-0 truncate max-w-[85px]">
                            {c.equipment_model}
                          </span>
                        </div>
                      </div>
                    );
                  });
                })
              )}
            </div>
          </div>

          {/* 3. APROVADOS PARA CONSERTO */}
          <div className="rounded-2xl border border-emerald-500/30 bg-emerald-500/6 dark:bg-emerald-950/15 p-3.5 flex flex-col">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-emerald-500/20">
              <span className="text-[11px] font-black uppercase text-emerald-700 dark:text-emerald-400 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" />
                <span>Aprovados</span>
              </span>
              <span className="font-mono text-xs font-black px-2.5 py-0.5 rounded-full bg-emerald-500 text-slate-950">
                <CountUpValue value={aprCards.length} />
              </span>
            </div>
            <div className="space-y-1.5 max-h-[190px] overflow-y-auto pr-1 text-xs">
              {aprCards.length === 0 ? (
                <p className="text-[11px] text-slate-400 dark:text-zinc-500 py-4 text-center">
                  Nenhuma balança aprovada aguardando.
                </p>
              ) : (
                aprCards.map((c) => (
                  <div
                    key={c.id}
                    className="px-2.5 py-2 rounded-xl bg-white dark:bg-zinc-900 border border-slate-200/80 dark:border-zinc-800 flex items-center justify-between gap-2 shadow-2xs"
                  >
                    <div className="min-w-0">
                      <span className="font-mono font-black text-[11px] text-emerald-600 dark:text-emerald-400">
                        OS {c.os_number}
                      </span>
                      <span className="font-bold text-[11px] text-zinc-800 dark:text-zinc-100 ml-1.5 truncate block sm:inline">
                        {c.client_name}
                      </span>
                    </div>
                    <span className="text-[10px] text-slate-500 dark:text-zinc-400 truncate max-w-[100px] shrink-0">
                      {c.equipment_model || c.equipment_type}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </motion.section>
  );
};
