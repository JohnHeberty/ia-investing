"use client";

import { Suspense } from "react";
import { Rss } from "lucide-react";
import Link from "next/link";
import type { Route } from "next";
import { NewsDataContext, useNewsValue } from "@/hooks/use-news";
import { AsOfIndicator } from "@/components/domain";
import { LoadingSkeleton } from "@/components/data-state-components";
import { SourcesTable } from "@/components/news/SourcesTable";

function SourcesContent() {
  const { sources, stats } = useNewsValue();

  return (
    <div className="section-gap">
      <header className="page-head">
        <div className="eyebrow">
          <Link href={"/news" as Route} className="text-accent">
            <Rss size={14} /> Noticias
          </Link>
          {" / Fontes"}
        </div>
        <h1>Fontes de Noticias</h1>
        <div className="subtitle">
          Gerencie fontes RSS e provedores de dados.
          <AsOfIndicator />
        </div>
      </header>

      <SourcesTable sources={sources} stats={stats} />
    </div>
  );
}

export default function NewsSourcesPage() {
  return (
    <Suspense fallback={<LoadingSkeleton lines={8} />}>
      <NewsDataProvider />
    </Suspense>
  );
}

function NewsDataProvider() {
  const value = useNewsValue();
  return (
    <NewsDataContext.Provider value={value}>
      <SourcesContent />
    </NewsDataContext.Provider>
  );
}
