"use client";

import { useSpring } from "@usefluid/motion/react";
import { type ReactNode, useEffect, useRef, useState } from "react";
import styles from "./IslandToast.module.css";

const BODY = { w: 16, z: 0.8 };
const DROP = { w: 18, z: 0.72 };

const CHECK = (
  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </svg>
);

type Props = {
  message: string | null;
  icon?: ReactNode;
};

export function IslandToast({ message, icon = CHECK }: Props) {
  const body = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState<string | null>(message);
  const measure = useRef<HTMLSpanElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    if (message) setShown(message);
  }, [message]);

  useEffect(() => {
    if (measure.current) setWidth(measure.current.offsetWidth);
  }, [shown]);

  const open = Boolean(message);
  useSpring(
    { w: open ? Math.max(120, width) : 40, h: open ? 52 : 36 },
    ({ w, h }) => {
      if (!body.current) return;
      body.current.style.width = `${w}px`;
      body.current.style.height = `${h}px`;
    },
    BODY,
  );
  useSpring(
    { y: open ? 0 : -72 },
    ({ y }) => { if (body.current) body.current.style.translate = `0 ${y}px`; },
    DROP,
  );

  return (
    <div className={styles.slot}>
      <span ref={measure} className={styles.measure} aria-hidden>
        <span className={styles.row}>{icon && <span className={styles.icon}>{icon}</span>}{shown}</span>
      </span>
      <div ref={body} className={styles.island} data-open={open}>
        <span className={styles.row} role="status">
          {icon && <span className={styles.icon} aria-hidden>{icon}</span>}
          {open ? shown : ""}
        </span>
      </div>
    </div>
  );
}
