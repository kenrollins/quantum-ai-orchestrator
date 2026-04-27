"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import styles from "./learn.module.css";

interface Props {
  crumb: string;
  active: string;
  children: ReactNode;
}

/**
 * Shared chrome for Learn pages: header with breadcrumb + back-to-dashboard
 * link, sidebar table of contents, main article column.
 */
export default function LearnShell({ crumb, active, children }: Props) {
  return (
    <div className={styles.shell}>
      <header className={styles.header}>
        <div className={styles.title}>quantum-ai-orchestrator · Learn</div>
        <div className={styles.crumb}>{crumb}</div>
        <Link href="/" className={styles.back}>
          ← Back to dashboard
        </Link>
      </header>

      <aside className={styles.side}>
        <Link
          href="/learn"
          className={`${styles.tocItem}${active === "index" ? " " + styles.active : ""}`}
        >
          Overview
        </Link>

        <div className={styles.section}>QEC track</div>
        <Link
          href="/learn/qec"
          className={`${styles.tocItem}${active.startsWith("qec") ? " " + styles.active : ""}`}
        >
          Quantum error correction
        </Link>

        <div className={styles.section}>Orchestration track</div>
        <Link
          href="/learn/orchestration"
          className={`${styles.tocItem}${active.startsWith("orch") ? " " + styles.active : ""}`}
        >
          The orchestration pattern
        </Link>

        <div className={styles.section}>Architecture</div>
        <Link
          href="/learn/architecture"
          className={`${styles.tocItem}${active.startsWith("arch") ? " " + styles.active : ""}`}
        >
          How this is built
        </Link>
      </aside>

      <main className={styles.main}>
        <article className={styles.article}>{children}</article>
      </main>
    </div>
  );
}
