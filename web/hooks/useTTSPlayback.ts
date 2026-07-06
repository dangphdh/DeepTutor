"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { apiFetch, apiUrl } from "@/lib/api";

/**
 * Reusable TTS playback hook — fetches audio for a given text from the
 * `/api/v1/voice/tts` endpoint and plays it, managing object URLs and
 * audio element lifecycle.
 *
 * Extracted from the PlayAudioButton component so the spelling trainer
 * (and any other surface) can trigger speech on demand:
 *
 *   const { play, playing, loading } = useTTSPlayback();
 *   <button onClick={() => play("school")}>🔊</button>
 *
 * Calling play() while another utterance is active stops the old one first.
 */
export function useTTSPlayback() {
  const [state, setState] = useState<"idle" | "loading" | "playing">("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const urlRef = useRef<string | null>(null);

  const cleanup = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (urlRef.current) {
      URL.revokeObjectURL(urlRef.current);
      urlRef.current = null;
    }
  }, []);

  const play = useCallback(
    async (text: string) => {
      const trimmed = (text || "").trim();
      if (!trimmed) return;
      setState("loading");
      try {
        const resp = await apiFetch(apiUrl("/api/v1/voice/tts"), {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: trimmed }),
        });
        if (!resp.ok) {
          cleanup();
          setState("idle");
          return;
        }
        const blob = await resp.blob();
        cleanup();
        const url = URL.createObjectURL(blob);
        urlRef.current = url;
        const audio = new Audio(url);
        audioRef.current = audio;
        audio.onended = () => {
          setState("idle");
          cleanup();
        };
        audio.onerror = () => {
          setState("idle");
          cleanup();
        };
        await audio.play();
        setState("playing");
      } catch {
        cleanup();
        setState("idle");
      }
    },
    [cleanup],
  );

  const stop = useCallback(() => {
    cleanup();
    setState("idle");
  }, [cleanup]);

  // Clean up on unmount.
  useEffect(() => cleanup, [cleanup]);

  return { play, stop, playing: state === "playing", loading: state === "loading" };
}
