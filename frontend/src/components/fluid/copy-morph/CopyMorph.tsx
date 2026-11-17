"use client";

import { MorphPath, useSpring } from "@usefluid/motion/react";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import styles from "./CopyMorph.module.css";

const COPY = "M44 14h48a14 14 0 0 1 14 14v48H92V28H44z M28 40h44a14 14 0 0 1 14 14v44a14 14 0 0 1-14 14H28a14 14 0 0 1-14-14V54a14 14 0 0 1 14-14z";
const CHECK = "M14 62L30 46L50 66L90 26L106 42L50 98Z";

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.cssText = "position:fixed;opacity:0;pointer-events:none";
    document.body.append(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

type Props = {
  text: string;
  label?: string;
  doneLabel?: string;
  done?: boolean;
  compact?: boolean;
  className?: string;
};

export function CopyMorph({ text, label = "Copy", doneLabel = "Copied", done: forced, compact = false, className = "" }: Props) {
  const [copied, setCopied] = useState(false);
  const done = forced ?? copied;
  const button = useRef<HTMLButtonElement>(null);
  const measure = useRef<HTMLSpanElement>(null);
  const [widths, setWidths] = useState({ idle: 0, done: 0 });

  useLayoutEffect(() => {
    const spans = measure.current?.children;
    if (!spans) return;
    setWidths({ idle: (spans[0] as HTMLElement).offsetWidth, done: (spans[1] as HTMLElement).offsetWidth });
  }, [label, doneLabel]);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(false), 1800);
    return () => clearTimeout(timer);
  }, [copied]);

  useSpring(
    { w: done ? widths.done : widths.idle },
    ({ w }) => { if (button.current && w > 0) button.current.style.width = `${w}px`; },
    { w: 18, z: 0.8, immediate: widths.idle === 0 },
  );

  const content = (word: string) => (
    <>
      <span className={styles.icon} />
      {word}
    </>
  );

  return (
    <>
      <span ref={measure} className={styles.measure} aria-hidden>
        <span className={styles.inner}>{content(label)}</span>
        <span className={styles.inner}>{content(doneLabel)}</span>
      </span>
      <button
        ref={button}
        type="button"
        className={`${styles.button} ${className}`}
        data-done={done}
        data-compact={compact}
        onClick={async (e) => {
          e.stopPropagation();
          if (await copy(text)) setCopied(true);
        }}
      >
        <span className={styles.inner}>
          <svg viewBox="0 0 120 120" aria-hidden className={styles.icon}>
            <MorphPath d={done ? CHECK : COPY} fill="currentColor" config={{ w: 20, z: 0.76, points: 96 }} />
          </svg>
          <span aria-live="polite">{done ? doneLabel : label}</span>
        </span>
      </button>
    </>
  );
}
