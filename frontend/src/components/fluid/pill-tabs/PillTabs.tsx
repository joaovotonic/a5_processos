"use client";

import { useSpring } from "@usefluid/motion/react";
import { type KeyboardEvent, type ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import styles from "./PillTabs.module.css";

const LEAD = { w: 30, z: 0.82 };
const TRAIL = { w: 16, z: 0.8 };

type Tab = { value: string; label: ReactNode; count?: number };
type Props = { label: string; tabs: Tab[]; value: string; onChange(value: string): void };

export function PillTabs({ label, tabs, value, onChange }: Props) {
  const list = useRef<HTMLDivElement>(null);
  const pill = useRef<HTMLSpanElement>(null);
  const [box, setBox] = useState<{ left: number; right: number } | null>(null);
  const last = useRef({ left: 0, placed: false });

  useLayoutEffect(() => {
    const measure = () => {
      const el = list.current?.querySelector<HTMLElement>('[aria-selected="true"]');
      if (el) setBox({ left: el.offsetLeft, right: el.offsetLeft + el.offsetWidth });
    };
    measure();
    const observer = new ResizeObserver(measure);
    if (list.current) observer.observe(list.current);
    return () => observer.disconnect();
  }, [value]);

  useEffect(() => {
    if (box) last.current = { left: box.left, placed: true };
  }, [box]);

  const right = !box || box.left >= last.current.left;
  const immediate = !last.current.placed;
  const edges = useRef({ left: 0, right: 0 });
  const paint = () => {
    if (!pill.current) return;
    pill.current.style.transform = `translateX(${edges.current.left}px)`;
    pill.current.style.width = `${Math.max(0, edges.current.right - edges.current.left)}px`;
  };
  useSpring({ v: box?.left ?? 0 }, ({ v }) => { edges.current.left = v; paint(); }, { ...(right ? TRAIL : LEAD), immediate });
  useSpring({ v: box?.right ?? 0 }, ({ v }) => { edges.current.right = v; paint(); }, { ...(right ? LEAD : TRAIL), immediate });

  const move = (e: KeyboardEvent, i: number) => {
    const d = e.key === "ArrowRight" ? 1 : e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const next = (i + d + tabs.length) % tabs.length;
    onChange(tabs[next].value);
    list.current?.querySelectorAll<HTMLElement>('[role="tab"]')[next]?.focus();
  };

  return (
    <div ref={list} role="tablist" aria-label={label} className={styles.list}>
      <span ref={pill} className={styles.pill} data-on={box ? "" : undefined} aria-hidden />
      {tabs.map((tab, i) => (
        <button
          key={tab.value}
          type="button"
          role="tab"
          aria-selected={tab.value === value}
          tabIndex={tab.value === value ? 0 : -1}
          className={styles.tab}
          onClick={() => onChange(tab.value)}
          onKeyDown={(e) => move(e, i)}
        >
          {tab.label}
          {tab.count !== undefined && <span className={styles.count}>{tab.count}</span>}
        </button>
      ))}
    </div>
  );
}
