"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { CityIndex, CityIndexEntry } from "@/lib/types";

interface Props {
  index: CityIndex | null;
  current: CityIndexEntry | null;
  onChoose: (slug: string) => void;
}

function fold(s: string) {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Searchable dropdown of the 50 cities, ordered by rank. */
export default function CityPicker({ index, current, onChoose }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const list = useRef<HTMLUListElement>(null);

  const results = useMemo(() => {
    const all = index?.cities ?? [];
    const q = fold(query.trim());
    if (!q) return all;
    return all.filter((c) => fold(c.name).includes(q) || fold(c.country).includes(q) || fold(c.un_name).includes(q));
  }, [index, query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setActive(Math.max(0, (index?.cities ?? []).findIndex((c) => c.slug === current?.slug)));
    const id = window.setTimeout(() => input.current?.focus(), 30);
    const onDown = (e: PointerEvent) => {
      if (root.current && !root.current.contains(e.target as Node)) setOpen(false);
    };
    window.addEventListener("pointerdown", onDown);
    return () => {
      window.clearTimeout(id);
      window.removeEventListener("pointerdown", onDown);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    list.current?.querySelector<HTMLElement>(`[data-i="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active, open]);

  const choose = (c: CityIndexEntry) => {
    if (c.status === "missing") return;
    setOpen(false);
    onChoose(c.slug);
  };

  return (
    <div className="picker" ref={root}>
      <button className="picker-btn" aria-haspopup="listbox" aria-expanded={open} onClick={() => setOpen((o) => !o)} disabled={!index}>
        {current ? (
          <>
            <span className="rank">#{current.rank}</span>
            <span className="picker-name">{current.name}</span>
            <span className="picker-country">{current.country}</span>
          </>
        ) : (
          <span className="picker-name">Choose a city</span>
        )}
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
          <path d="M2 4l4 4 4-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>
      {open && (
        <div className="picker-pop">
          <input
            ref={input}
            className="picker-search"
            placeholder="Search 50 cities…"
            value={query}
            aria-label="Search cities"
            onChange={(e) => {
              setQuery(e.target.value);
              setActive(0);
            }}
            onKeyDown={(e) => {
              if (e.key === "ArrowDown") {
                e.preventDefault();
                setActive((a) => Math.min(results.length - 1, a + 1));
              } else if (e.key === "ArrowUp") {
                e.preventDefault();
                setActive((a) => Math.max(0, a - 1));
              } else if (e.key === "Enter" && results[active]) {
                choose(results[active]);
              } else if (e.key === "Escape") {
                setOpen(false);
              }
            }}
          />
          <ul className="picker-list" role="listbox" ref={list}>
            {results.map((c, i) => (
              <li
                key={c.slug}
                data-i={i}
                role="option"
                aria-selected={c.slug === current?.slug}
                className={`${i === active ? "active" : ""} ${c.status === "missing" ? "disabled" : ""}`}
                onPointerEnter={() => setActive(i)}
                onClick={() => choose(c)}
              >
                <span className="rank">{c.rank}</span>
                <span className="li-name">
                  {c.name}
                  <small>{c.country}</small>
                </span>
                {c.status === "partial" && <span className="badge">partial</span>}
                {c.status === "missing" && <span className="badge">no data</span>}
                <span className="li-pop">{(c.population_2025 / 1e6).toFixed(1)} M</span>
              </li>
            ))}
            {!results.length && <li className="empty">No city matches “{query}”.</li>}
          </ul>
          <div className="picker-foot">Ranked by 2025 population · UN World Urbanization Prospects 2025</div>
        </div>
      )}
    </div>
  );
}
