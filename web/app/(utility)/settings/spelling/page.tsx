"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  SettingRow,
  SettingSection,
  SettingsPageHeader,
} from "@/components/settings/shared";
import { apiFetch, apiUrl } from "@/lib/api";

interface PackSummary {
  id: string;
  name: string;
  language: string;
  word_count: number;
  curated: boolean;
}

interface CustomList {
  id: string;
  name: string;
  language: string;
  word_count: number;
  curated: boolean;
  created_at?: number;
  updated_at?: number;
}

interface ListResponse {
  curated: PackSummary[];
  custom: CustomList[];
}

export default function SpellingSettingsPage() {
  const { t } = useTranslation();
  const [curated, setCurated] = useState<PackSummary[]>([]);
  const [custom, setCustom] = useState<CustomList[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // New-list form state
  const [newName, setNewName] = useState("");
  const [newWords, setNewWords] = useState("");

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await apiFetch(apiUrl("/api/v1/wordlists"));
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = (await resp.json()) as ListResponse;
      setCurated(data.curated ?? []);
      setCustom(data.custom ?? []);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const createList = useCallback(async () => {
    const name = newName.trim();
    if (!name) return;
    const words = newWords
      .split(/[,\n]/)
      .map((w) => w.trim())
      .filter(Boolean);
    try {
      const resp = await apiFetch(apiUrl("/api/v1/wordlists"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, language: "en", words }),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      setNewName("");
      setNewWords("");
      void reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [newName, newWords, reload]);

  const deleteList = useCallback(
    async (id: string) => {
      try {
        const resp = await apiFetch(apiUrl(`/api/v1/wordlists/${id}`), {
          method: "DELETE",
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        void reload();
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [reload],
  );

  return (
    <div data-tour="tour-spelling">
      <SettingsPageHeader
        title={t("Spelling")}
        description={t(
          "Manage spelling word lists. Curated packs ship ready to use; create custom lists for this week's words. Practice via mastery_path with the Spelling topic.",
        )}
      />

      {loading ? (
        <p className="py-8 text-center text-[13px] text-[var(--muted-foreground)]">
          {t("Loading...")}
        </p>
      ) : null}

      {error ? (
        <div className="mb-4 rounded-lg border border-red-500/40 bg-red-500/5 px-3 py-2 text-[12.5px] text-red-600 dark:text-red-400">
          {error}
        </div>
      ) : null}

      <SettingSection
        title={t("Curated Packs")}
        description={t(
          "Ready-to-use word packs for young ESL learners. Read-only — create a custom list to add your own words.",
        )}
      >
        {curated.length === 0 ? (
          <p className="py-3 text-[12.5px] text-[var(--muted-foreground)]">
            {t("No curated packs available.")}
          </p>
        ) : (
          <div className="flex flex-col gap-1.5 py-1">
            {curated.map((pack) => (
              <SettingRow
                key={pack.id}
                title={pack.name}
                description={`${pack.word_count} ${t("words")}`}
                control={
                  <button
                    type="button"
                    onClick={() =>
                      void navigator.clipboard?.writeText(pack.name)
                    }
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-[12px] text-[var(--foreground)] transition-colors hover:bg-[var(--muted)]"
                    title={t("Copy name to use in mastery_path")}
                  >
                    {pack.id}
                  </button>
                }
              />
            ))}
          </div>
        )}
      </SettingSection>

      <SettingSection
        title={t("Custom Lists")}
        description={t(
          "Your own word lists. Use these in mastery_path by their name or id.",
        )}
      >
        <div className="mb-4 rounded-xl border border-[var(--border)] bg-[var(--card)]/40 p-3">
          <div className="mb-2 flex flex-col gap-2 sm:flex-row">
            <input
              type="text"
              placeholder={t("List name (e.g. This Week's Words)")}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="flex-1 rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 text-[13px] text-[var(--foreground)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
            />
            <button
              type="button"
              onClick={() => void createList()}
              disabled={!newName.trim()}
              className="rounded-md bg-[var(--primary)] px-3 py-1.5 text-[12.5px] font-medium text-[var(--primary-foreground)] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {t("Create")}
            </button>
          </div>
          <textarea
            placeholder={t("Words, separated by commas (cat, dog, bird)")}
            value={newWords}
            onChange={(e) => setNewWords(e.target.value)}
            rows={2}
            className="w-full resize-y rounded-md border border-[var(--border)] bg-[var(--card)] px-2.5 py-1.5 text-[13px] text-[var(--foreground)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
          />
        </div>

        {custom.length === 0 ? (
          <p className="py-3 text-[12.5px] text-[var(--muted-foreground)]">
            {t("No custom lists yet. Create one above.")}
          </p>
        ) : (
          <div className="flex flex-col gap-1.5 py-1">
            {custom.map((list) => (
              <SettingRow
                key={list.id}
                title={list.name}
                description={`${list.word_count} ${t("words")} · ${list.id}`}
                control={
                  <button
                    type="button"
                    onClick={() => void deleteList(list.id)}
                    className="rounded-md border border-[var(--border)] px-2.5 py-1 text-[12px] text-[var(--muted-foreground)] transition-colors hover:border-red-500/40 hover:text-red-500"
                  >
                    {t("Delete")}
                  </button>
                }
              />
            ))}
          </div>
        )}
      </SettingSection>
    </div>
  );
}
