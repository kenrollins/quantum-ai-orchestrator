"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./demos.module.css";

interface ShellProps {
  crumb?: string;
  active?: "catalog" | "demo" | "learn";
  children: ReactNode;
}

export function DemosShell({ crumb, active = "catalog", children }: ShellProps) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <span className={styles.title}>quantum-ai-orchestrator</span>
        {crumb && <span className={styles.crumb}>{crumb}</span>}
        <nav className={styles.nav}>
          <Link href="/demos" className={active === "catalog" ? styles.active : ""}>
            Demos
          </Link>
          <Link href="/learn" className={active === "learn" ? styles.active : ""}>
            Learn
          </Link>
          <Link href="/orchestrator">Orchestrator</Link>
        </nav>
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}

interface DemoPageProps {
  title: string;
  hook: string;
  cardNumber: number;
  totalCards: number;
  children: ReactNode;
}

/** Wrap a single demo page with consistent crumbs + title + hook. */
export function DemoPage({ title, hook, cardNumber, totalCards, children }: DemoPageProps) {
  return (
    <DemosShell crumb={`Demo ${cardNumber} / ${totalCards}`} active="demo">
      <div className={styles.demoPage}>
        <div className={styles.crumbs}>
          <Link href="/demos">← All demos</Link>
        </div>
        <h1 className={styles.demoTitle}>{title}</h1>
        <p className={styles.demoHook}>{hook}</p>
        {children}
      </div>
    </DemosShell>
  );
}

interface SectionProps {
  title: string;
  children: ReactNode;
}

export function DemoSection({ title, children }: SectionProps) {
  return (
    <section className={styles.demoSection}>
      <h2>{title}</h2>
      {children}
    </section>
  );
}

interface CodeBlockProps {
  language?: string;
  filepath?: string;
  children: string;
}

export function CodeBlock({ language = "python", filepath, children }: CodeBlockProps) {
  return (
    <div className={styles.codeBlock}>
      {(filepath || language) && (
        <div className={styles.codeHeader}>
          {filepath && <span className={styles.filepath}>{filepath}</span>}
          {!filepath && language && <span>{language}</span>}
          {filepath && language && <span>{language}</span>}
        </div>
      )}
      <pre>{children}</pre>
    </div>
  );
}

interface AiCalloutProps {
  children: ReactNode;
}

export function AiCallout({ children }: AiCalloutProps) {
  return (
    <div className={styles.aiCallout}>
      <div className={styles.label}>Where AI fits</div>
      <p>{children}</p>
    </div>
  );
}

interface MetricProps {
  label: string;
  value: ReactNode;
}

export function MiniMetric({ label, value }: MetricProps) {
  return (
    <span className={styles.miniMetric}>
      <span className={styles.miniLabel}>{label}</span>
      <span className={styles.miniValue}>{value}</span>
    </span>
  );
}

interface StubProps {
  children: ReactNode;
}

export function StubNote({ children }: StubProps) {
  return (
    <div className={styles.stubBox}>
      <span className={styles.stubLabel}>Coming next</span>
      {children}
    </div>
  );
}
