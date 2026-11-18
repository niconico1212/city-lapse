"use client";

import { useMemo } from "react";
import { formatYear, type Timeline } from "@/lib/timeline";
import type { CityData } from "@/lib/types";

interface Props {
  city: CityData;
  timeline: Timeline;
  seconds: number;
  year: number;
  playing: boolean;
  speed: number;
  speeds: number[];
  onTogglePlay: () => void;
  onSeek: (seconds: number) => void;
  onSpeed: (speed: number) => void;
}

const STEPS = 2000;

export default function BottomBar({ city, timeline, seconds, year, playing, speed, speeds, onTogglePlay, onSeek, onSpeed }: Props) {
  const frac = (y: number) => timeline.secondsAt(y) / timeline.duration;
  const progress = seconds / timeline.duration;
  const ended = !playing && progress >= 0.999;
  const ghslStart = city.start_year < 1975 ? frac(1975) : 0;

  const milestones = useMemo(
    () => city.milestones.map((m) => ({ ...m, left: (timeline.secondsAt(m.year) / timeline.duration) * 100 })),
    [city, timeline],
  );

  return (
    <footer className="bottombar">
      <div className="controls">
        <button className="play" onClick={onTogglePlay} aria-label={playing ? "Pause" : ended ? "Replay" : "Play"}>
          {playing ? (
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
              <rect x="3.5" y="2.5" width="4" height="13" rx="1" fill="currentColor" />
              <rect x="10.5" y="2.5" width="4" height="13" rx="1" fill="currentColor" />
            </svg>
          ) : ended ? (
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
              <path d="M9 3a6 6 0 1 1-5.6 3.9" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
              <path d="M2.2 2.6v4.6h4.6" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          ) : (
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden>
              <path d="M5 2.8v12.4a.6.6 0 0 0 .9.5l10-6.2a.6.6 0 0 0 0-1L5.9 2.3a.6.6 0 0 0-.9.5z" fill="currentColor" />
            </svg>
          )}
        </button>
        <div className="year" aria-live="off">
          {formatYear(year)}
        </div>
        <div className="speed" role="group" aria-label="Playback speed">
          {speeds.map((s) => (
            <button key={s} className={s === speed ? "on" : ""} onClick={() => onSpeed(s)} aria-pressed={s === speed}>
              {s}×
            </button>
          ))}
        </div>
      </div>

      <div className="scrub">
        <div className="track">
          {ghslStart > 0 && <div className="track-recon" style={{ width: `${ghslStart * 100}%` }} title="Footprint reconstructed (before 1975)" />}
          <div className="track-real" style={{ left: `${ghslStart * 100}%` }} title="Footprint from GHSL satellite data (1975 onward)" />
          <div className="track-fill" style={{ width: `${progress * 100}%` }} />
          {milestones.map((m, i) => (
            <span key={i} className={`tick ${m.year <= year ? "past" : ""}`} style={{ left: `${m.left}%` }} title={`${formatYear(m.year)} · ${m.title}`} />
          ))}
          <div className="thumb" style={{ left: `${progress * 100}%` }} />
          <input
            type="range"
            min={0}
            max={STEPS}
            step={1}
            value={Math.round(progress * STEPS)}
            aria-label="Timeline"
            aria-valuetext={formatYear(year)}
            onChange={(e) => onSeek((Number(e.target.value) / STEPS) * timeline.duration)}
          />
        </div>
        <div className="ticks" aria-hidden>
          {timeline.ticks.map((y) => (
            <span key={y} style={{ left: `${frac(y) * 100}%` }}>
              {formatYear(y)}
            </span>
          ))}
        </div>
        <div className="scrub-key" aria-hidden>
          {ghslStart > 0 && (
            <span>
              <i className="k recon" /> reconstructed footprint
            </span>
          )}
          <span>
            <i className="k real" /> GHSL satellite record
          </span>
          <span>
            <i className="k tickk" /> milestone
          </span>
          <span className="warp-note">Early centuries are compressed</span>
        </div>
      </div>
    </footer>
  );
}
