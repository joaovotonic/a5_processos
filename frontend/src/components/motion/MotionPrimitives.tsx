import React, { useEffect, useRef, useState } from 'react';
import { motion, animate, AnimatePresence, type HTMLMotionProps } from 'motion/react';
import { A5Logo } from '../A5Logo';
import { MOTION_EASE } from './motionTokens';

interface CountUpValueProps {
  value: number;
  duration?: number;
  decimals?: number;
  padZero?: number;
  prefix?: string;
  suffix?: string;
  locale?: string;
  className?: string;
}

export const CountUpValue: React.FC<CountUpValueProps> = ({
  value,
  duration = 0.75,
  decimals = 0,
  padZero,
  prefix = '',
  suffix = '',
  locale = 'pt-BR',
  className = '',
}) => {
  const safeTarget = Number.isFinite(value) ? value : 0;
  const [display, setDisplay] = useState<number>(safeTarget);
  const prevRef = useRef<number>(0);

  useEffect(() => {
    const startVal = prevRef.current;
    const controls = animate(startVal, safeTarget, {
      duration,
      ease: MOTION_EASE,
      onUpdate: (latest) => setDisplay(latest),
      onComplete: () => {
        prevRef.current = safeTarget;
        setDisplay(safeTarget);
      },
    });
    return () => controls.stop();
  }, [safeTarget, duration]);

  const formatted = padZero
    ? String(Math.round(display)).padStart(padZero, '0')
    : display.toLocaleString(locale, {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      });

  return (
    <span className={`tabular-nums ${className}`}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
};

interface StaggerContainerProps extends HTMLMotionProps<'div'> {
  stagger?: number;
  delayChildren?: number;
}

export const StaggerContainer: React.FC<StaggerContainerProps> = ({
  children,
  stagger = 0.045,
  delayChildren = 0.02,
  className = '',
  ...rest
}) => (
  <motion.div
    initial="hidden"
    animate="visible"
    variants={{
      hidden: {},
      visible: {
        transition: { staggerChildren: stagger, delayChildren },
      },
    }}
    className={className}
    {...rest}
  >
    {children}
  </motion.div>
);

interface BentoItemProps extends HTMLMotionProps<'div'> {
  hoverLift?: boolean;
}

export const BentoItem: React.FC<BentoItemProps> = ({
  children,
  hoverLift = true,
  className = '',
  ...rest
}) => (
  <motion.div
    variants={{
      hidden: { opacity: 0, y: 12, scale: 0.985 },
      visible: {
        opacity: 1,
        y: 0,
        scale: 1,
        transition: { duration: 0.36, ease: MOTION_EASE },
      },
    }}
    whileHover={hoverLift ? { y: -3, transition: { duration: 0.18, ease: MOTION_EASE } } : undefined}
    className={className}
    {...rest}
  >
    {children}
  </motion.div>
);

interface AnimatedProgressBarProps {
  percent: number;
  targetLabel?: string;
  heightClass?: string;
  trackClass?: string;
  fillClass?: string;
}

export const AnimatedProgressBar: React.FC<AnimatedProgressBarProps> = ({
  percent,
  targetLabel,
  heightClass = 'h-2.5',
  trackClass = 'ember-hatch',
  fillClass = 'bg-gradient-to-r from-[#5D87FF] via-[#3B82F6] to-[#2563EB]',
}) => {
  const clamped = Math.max(0, Math.min(100, percent));

  return (
    <div className="relative w-full">
      {targetLabel && (
        <motion.div
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.25, duration: 0.3, ease: MOTION_EASE }}
          style={{ left: `${Math.min(88, Math.max(12, clamped))}%` }}
          className="absolute -top-6 -translate-x-1/2 z-10 pointer-events-none"
        >
          <span className="inline-flex items-center px-2 py-0.5 rounded-full bg-zinc-900 dark:bg-white text-white dark:text-zinc-950 text-[10px] font-bold shadow whitespace-nowrap tabular-nums">
            {targetLabel}
          </span>
        </motion.div>
      )}
      <div className={`w-full ${heightClass} ${trackClass} rounded-full overflow-hidden p-0.5`}>
        <motion.div
          initial={{ width: '0%' }}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.75, ease: MOTION_EASE, delay: 0.1 }}
          className={`h-full rounded-full ${fillClass} shadow-[0_0_12px_rgba(59,130,246,0.4)]`}
        />
      </div>
    </div>
  );
};

interface AnimatedRingProps {
  percent: number;
  size?: number;
  strokeWidth?: number;
  color?: string;
  trackColor?: string;
  label?: string;
  sublabel?: string;
}

export const AnimatedRing: React.FC<AnimatedRingProps> = ({
  percent,
  size = 54,
  strokeWidth = 5,
  color = '#3B82F6',
  trackColor = 'rgba(148,163,184,0.2)',
  label,
  sublabel,
}) => {
  const clamped = Math.max(0, Math.min(100, percent));
  const r = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * r;
  const targetOffset = circumference - (clamped / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          <circle cx={size / 2} cy={size / 2} r={r} stroke={trackColor} strokeWidth={strokeWidth} fill="transparent" />
          <motion.circle
            cx={size / 2}
            cy={size / 2}
            r={r}
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            initial={{ strokeDashoffset: circumference }}
            animate={{ strokeDashoffset: targetOffset }}
            transition={{ duration: 0.8, ease: MOTION_EASE, delay: 0.12 }}
            fill="transparent"
          />
        </svg>
        <span className="absolute text-[11px] font-extrabold text-zinc-900 dark:text-zinc-100 tabular-nums">
          {label ?? `${Math.round(clamped)}%`}
        </span>
      </div>
      {sublabel && (
        <span className="text-[10px] font-semibold text-slate-500 dark:text-zinc-400 text-center leading-tight">
          {sublabel}
        </span>
      )}
    </div>
  );
};

interface EmberRevealShellProps {
  revealKey: number;
  ready?: boolean;
  minDurationMs?: number;
  subtitle?: string;
  children: React.ReactNode;
}

export const EmberRevealShell: React.FC<EmberRevealShellProps> = ({
  revealKey,
  ready = true,
  minDurationMs = 1550,
  subtitle = 'Carregando painel...',
  children,
}) => {
  const [phase, setPhase] = useState<'loading' | 'revealing' | 'done'>('loading');
  const startTimeRef = useRef<number>(
    typeof window !== 'undefined' && (window as unknown as { __A5_BOOT_AT__?: number }).__A5_BOOT_AT__ &&
      !(window as unknown as { __A5_BOOT_CONSUMED__?: boolean }).__A5_BOOT_CONSUMED__
      ? ((window as unknown as { __A5_BOOT_AT__: number }).__A5_BOOT_AT__)
      : performance.now(),
  );

  // Remove pré-loader estático do index.html assim que o shell React assume o controle visual
  useEffect(() => {
    const preloader = document.getElementById('a5-initial-loader');
    if (preloader) preloader.remove();
    (window as unknown as { __A5_BOOT_CONSUMED__?: boolean }).__A5_BOOT_CONSUMED__ = true;
  }, []);

  // Ao trocar de tela (ex: login -> painel), reinicia cronômetro da transição
  const prevRevealKeyRef = useRef<number>(revealKey);
  useEffect(() => {
    if (prevRevealKeyRef.current !== revealKey) {
      prevRevealKeyRef.current = revealKey;
      startTimeRef.current = performance.now();
      setPhase('loading');
    }
  }, [revealKey]);

  // Aguarda tempo mínimo proposital + dados reais (sem somar espera extra caso o Cloudflare já tenha levado mais tempo)
  useEffect(() => {
    if (phase !== 'loading') return;

    const elapsed = performance.now() - startTimeRef.current;
    const remaining = Math.max(0, minDurationMs - elapsed);

    if (ready) {
      const t = window.setTimeout(() => setPhase('revealing'), remaining);
      return () => window.clearTimeout(t);
    }

    // Failsafe caso uma resposta demore além de 7.5s em conexão instável
    const failsafe = window.setTimeout(() => setPhase('revealing'), Math.max(remaining, 7500));
    return () => window.clearTimeout(failsafe);
  }, [ready, minDurationMs, phase, revealKey]);

  const showOverlay = phase !== 'done';

  return (
    <div className="relative min-h-screen">
      <AnimatePresence>
        {showOverlay && (
          <motion.div
            key={`backdrop-${revealKey}`}
            initial={{ opacity: 1 }}
            animate={{ opacity: phase === 'revealing' ? 0 : 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.45, delay: phase === 'revealing' ? 0.25 : 0, ease: MOTION_EASE }}
            className="fixed inset-0 z-[90] bg-gradient-to-br from-[#F4F6FA] via-white to-[#E6F0FF] dark:from-[#09090B] dark:via-[#0F1117] dark:to-[#0A192F] flex items-center justify-center pointer-events-none select-none overflow-hidden"
          >
            <motion.div
              animate={{ scale: [1, 1.08, 1], opacity: [0.3, 0.48, 0.3] }}
              transition={{ duration: 2.6, repeat: Infinity, ease: 'easeInOut' }}
              className="absolute -top-24 -left-24 w-[480px] h-[480px] rounded-full blur-3xl"
              style={{ background: 'radial-gradient(circle, #3B82F6 0%, transparent 70%)' }}
            />
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 6 }}
              animate={{
                scale: phase === 'revealing' ? 1.04 : 1,
                opacity: phase === 'revealing' ? 0 : 1,
                y: 0,
              }}
              transition={{ duration: 0.32, ease: MOTION_EASE }}
              className="flex flex-col items-center gap-3 relative z-10"
            >
              <motion.div
                animate={{ scale: [1, 1.035, 1] }}
                transition={{ duration: 1.8, repeat: Infinity, ease: 'easeInOut' }}
              >
                <A5Logo variant="icon" size="lg" />
              </motion.div>
              <span className="text-zinc-900 dark:text-white font-bold text-sm tracking-tight">
                A5 <span className="text-blue-600 dark:text-sky-400">Tecnologia</span>
              </span>
              <div className="w-36 h-1 rounded-full bg-blue-500/15 overflow-hidden">
                <motion.div
                  initial={{ x: '-100%' }}
                  animate={{ x: '220%' }}
                  transition={{ duration: 1.15, repeat: Infinity, ease: 'easeInOut' }}
                  className="h-full w-16 rounded-full bg-gradient-to-r from-[#5D87FF] via-[#3B82F6] to-[#2563EB]"
                />
              </div>
              <span className="text-[11px] font-medium text-slate-500 dark:text-zinc-400 tracking-tight">
                {ready ? 'Abrindo ambiente...' : subtitle}
              </span>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div
        key={`reveal-${revealKey}`}
        initial={{ clipPath: 'circle(0% at 50% 48%)', opacity: 0.85 }}
        animate={
          phase === 'loading'
            ? { clipPath: 'circle(0% at 50% 48%)', opacity: 0.85 }
            : { clipPath: 'circle(160% at 50% 48%)', opacity: 1 }
        }
        transition={{ duration: 0.68, ease: MOTION_EASE }}
        onAnimationComplete={() => {
          if (phase === 'revealing') setPhase('done');
        }}
        style={phase === 'done' ? { clipPath: 'none' } : undefined}
        className="relative z-10 min-h-screen"
      >
        {children}
      </motion.div>
    </div>
  );
};
