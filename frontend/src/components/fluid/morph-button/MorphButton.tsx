"use client";

import { shapes } from "@usefluid/motion";
import { MorphPath, useSpring } from "@usefluid/motion/react";
import { type ButtonHTMLAttributes, useEffect, useLayoutEffect, useRef, useState } from "react";
import styles from "./MorphButton.module.css";

const ARROW = "M14 52h62L54 30l12-12 42 42-42 42-12-12 22-22H14z";
const CHECK = "M18 62L32 48L50 66L88 28L102 42L50 94Z";
const SENDING = [shapes.circle, shapes.square, shapes.triangle, shapes.flower];
const ROUND = 48;

export type MorphButtonState = "idle" | "loading" | "done";

type Props = Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> & {
  state: MorphButtonState;
  labels?: { idle: string; loading?: string; done: string };
};

export function MorphButton({ state, labels = { idle: "Send", done: "Sent" }, className, onClick, ...props }: Props) {
  const button = useRef<HTMLButtonElement>(null);
  const measure = useRef<HTMLSpanElement>(null);
  const [widths, setWidths] = useState({ idle: 0, done: 0 });
  const [tick, setTick] = useState(0);

  useLayoutEffect(() => {
    const spans = measure.current?.children;
    if (!spans) return;
    setWidths({ idle: (spans[0] as HTMLElement).offsetWidth, done: (spans[1] as HTMLElement).offsetWidth });
  }, [labels.idle, labels.done]);

  useEffect(() => {
    if (state !== "loading") return;
    const timer = setInterval(() => setTick((t) => t + 1), 360);
    return () => clearInterval(timer);
  }, [state]);

  const width = state === "loading" ? ROUND : state === "done" ? widths.done : widths.idle;
  useSpring(
    { w: width },
    ({ w }) => { if (button.current && w > 0) button.current.style.width = `${w}px`; },
    { w: 18, z: 0.8, immediate: widths.idle === 0 },
  );

  const icon = state === "loading" ? SENDING[tick % SENDING.length] : state === "done" ? CHECK : ARROW;
  const text = state === "loading" ? (labels.loading ?? "Sending") : labels[state];

  return (
    <>
      <span ref={measure} className={styles.measure} aria-hidden>
        <span className={styles.inner}><span className={styles.iconBox} />{labels.idle}</span>
        <span className={styles.inner}><span className={styles.iconBox} />{labels.done}</span>
      </span>
      <button
        {...props}
        ref={button}
        type={props.type ?? "button"}
        className={[styles.button, className].filter(Boolean).join(" ")}
        data-state={state}
        aria-busy={state === "loading"}
        aria-disabled={state === "loading" || undefined}
        onClick={(e) => {
          if (state === "loading") return;
          onClick?.(e);
        }}
      >
        <span className={styles.inner} aria-hidden>
          <svg viewBox="0 0 120 120" className={styles.iconBox}>
            <MorphPath d={icon} fill="currentColor" config={{ w: 20, z: 0.76, points: 96 }} />
          </svg>
          <span className={styles.label}>{text}</span>
        </span>
        <span className={styles.srOnly}>{text}</span>
      </button>
      <span className={styles.srOnly} role="status">{state === "idle" ? "" : text}</span>
    </>
  );
}
