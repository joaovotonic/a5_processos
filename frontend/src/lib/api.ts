import { io, type Socket } from 'socket.io-client';
import type { A5BootConfig } from '../types';

declare global {
  interface Window {
    __A5_CONFIG__?: Partial<A5BootConfig>;
  }
}

export function getBootConfig(): A5BootConfig {
  const cfg = window.__A5_CONFIG__ || {};
  return {
    publicUrl: cfg.publicUrl || window.location.origin,
    localIp: cfg.localIp || window.location.hostname,
    port: cfg.port || 5000,
    tunnelMode: Boolean(cfg.tunnelMode),
    user: cfg.user ?? null,
    directorFirstAccessDone: Boolean(cfg.directorFirstAccessDone),
    directorSavedUser: cfg.directorSavedUser || '',
    usingDefaultPassword: Boolean(cfg.usingDefaultPassword),
    defaultPasswordUsers: cfg.defaultPasswordUsers || [],
    callTargets: cfg.callTargets || [
      { name: 'João Otoni', role: 'Técnico', target: 'João Otoni' },
      { name: 'Wisley', role: 'Técnico', target: 'Wisley' },
      { name: 'Guilherme', role: 'Técnico', target: 'Guilherme' },
      { name: 'Arthur', role: 'ADM', target: 'Arthur (ADM)' },
      { name: 'Priscila', role: 'ADM', target: 'Priscila (ADM)' },
      { name: 'Roosevelt', role: 'ADM', target: 'Roosevelt (ADM)' },
      { name: 'Iago', role: 'Técnico', target: 'Iago' },
      { name: 'Enzo', role: 'Técnico', target: 'Enzo' },
      { name: 'Edson', role: 'Técnico', target: 'Edson' },
      { name: 'Antonio', role: 'Técnico', target: 'Antonio' },
    ],
    page: cfg.page,
  };
}

let socketInstance: Socket | null = null;

export function getSocket(): Socket {
  if (!socketInstance) {
    socketInstance = io({
      transports: ['websocket', 'polling'],
    });
  }
  return socketInstance;
}

export async function apiJson<T = Record<string, unknown>>(
  url: string,
  init?: RequestInit,
): Promise<{ ok: boolean; status: number; data: T }> {
  const isForm = init?.body instanceof FormData;
  const response = await fetch(url, {
    credentials: 'same-origin',
    ...init,
    headers: {
      ...(init?.body && !isForm ? { 'Content-Type': 'application/json' } : {}),
      ...(init?.headers || {}),
    },
  });

  let parsed: unknown = {};
  try {
    parsed = await response.json();
  } catch {
    parsed = {};
  }

  if (response.status === 401 && !url.startsWith('/api/auth/')) {
    window.location.href = '/login';
  }

  return {
    ok: response.ok,
    status: response.status,
    data: parsed as T,
  };
}

export function localTodayISO(): string {
  const d = new Date();
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

let doorbellAudio: HTMLAudioElement | null = null;

function playDoorbellSynthFallback(): void {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioCtx();
    const now = ctx.currentTime;
    const chime = (freq: number, start: number, dur: number) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'sine';
      osc.frequency.setValueAtTime(freq, start);
      gain.gain.setValueAtTime(0.001, start);
      gain.gain.exponentialRampToValueAtTime(0.28, start + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.001, start + dur);
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start(start);
      osc.stop(start + dur);
    };
    chime(659.25, now, 0.35);
    chime(523.25, now + 0.25, 0.55);
  } catch {
    // Ignore audio errors if blocked by browser autoplay policy
  }
}

export function playDoorbellSound(): void {
  try {
    if (!doorbellAudio) {
      doorbellAudio = new Audio('/static/sounds/campainha.wav');
    }
    doorbellAudio.currentTime = 0;
    doorbellAudio.volume = 0.85;
    doorbellAudio.play().catch(() => playDoorbellSynthFallback());
  } catch {
    playDoorbellSynthFallback();
  }
}

export function playNotificationBeep(): void {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    const ctx = new AudioCtx();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = 'triangle';
    osc.frequency.setValueAtTime(880, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(1174, ctx.currentTime + 0.14);
    gain.gain.setValueAtTime(0.18, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.22);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.22);
  } catch {
    // Ignore audio errors
  }
}

function getToleranceInfo(nominal: number, unit: string): { div: number; tol: number } {
  if (unit === 'g') {
    const div = nominal >= 500 ? 0.05 : 0.01;
    return { div, tol: +(div * 2).toFixed(4) };
  }
  const div = nominal <= 6 ? 0.002 : nominal <= 15 ? 0.005 : 0.01;
  return { div, tol: +(div * 2).toFixed(4) };
}

export interface WeightDiffResult {
  nominal: number;
  actual: number;
  unit: string;
  diff: number;
  tol: number;
  isDiff: boolean;
}

export function analyzeWeightDiff(weightKey: string, rawVal: string): WeightDiffResult | null {
  if (!rawVal || !String(rawVal).trim()) return null;
  const actual = parseFloat(String(rawVal).replace(',', '.'));
  const match = weightKey.match(/^(\d+(?:\.\d+)?)(kg|g)$/i);
  if (!match || Number.isNaN(actual)) return null;
  const nominal = parseFloat(match[1]);
  const unit = match[2].toLowerCase();
  const diff = Math.abs(actual - nominal);
  const { tol } = getToleranceInfo(nominal, unit);
  return {
    nominal,
    actual,
    unit,
    diff,
    tol,
    isDiff: diff > tol + 1e-6,
  };
}

