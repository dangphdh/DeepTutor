"use client";

import { useTranslation } from "react-i18next";

import { useSettings } from "@/components/settings/SettingsContext";
import { ThemePreviewCard } from "@/components/settings/ThemePreviewCard";
import {
  SettingRow,
  SettingSection,
  SettingsPageHeader,
} from "@/components/settings/shared";

export default function AppearanceSettingsPage() {
  const { t } = useTranslation();
  const {
    theme,
    language,
    kidMode,
    hintMode,
    maxHints,
    updateTheme,
    updateLanguage,
    updateKidMode,
    updateHintMode,
  } = useSettings();

  return (
    <div data-tour="tour-appearance">
      <SettingsPageHeader
        title={t("Appearance")}
        description={t(
          "Tune the visual theme and interface language. Changes apply immediately and are stored in your account.",
        )}
      />

      <SettingSection
        title={t("Language")}
        description={t("Choose the interface language.")}
      >
        <SettingRow
          title={t("Interface language")}
          description={t(
            "Affects the UI only. Model output language is controlled by your prompt.",
          )}
          control={
            <div className="flex gap-0.5 rounded-lg bg-[var(--muted)] p-0.5">
              {(["en", "zh", "vi"] as const).map((v) => (
                <button
                  key={v}
                  onClick={() => updateLanguage(v)}
                  className={`rounded-md px-2.5 py-1 text-[12px] transition-all ${
                    language === v
                      ? "bg-[var(--card)] font-medium text-[var(--foreground)] shadow-sm"
                      : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {v === "en"
                    ? t("language.english")
                    : v === "zh"
                      ? t("language.chinese")
                      : t("language.vietnamese")}
                </button>
              ))}
            </div>
          }
        />
      </SettingSection>

      <SettingSection
        title={t("Kid Mode")}
        description={t(
          "Kid Mode adapts the tutor's voice for a young child: short sentences, warm encouragement, simple words, and one idea at a time. The mastery bar stays the same — only the voice changes.",
        )}
      >
        <SettingRow
          title={t("Kid Mode")}
          description={t(
            "When on, the tutor speaks to a young child in a warm, simple voice across every capability (chat, mastery, deep solve).",
          )}
          control={
            <button
              type="button"
              role="switch"
              aria-checked={kidMode}
              onClick={() => updateKidMode(!kidMode)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] ${
                kidMode
                  ? "bg-[var(--primary)]"
                  : "bg-[var(--muted)]"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  kidMode ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          }
        />
      </SettingSection>

      <SettingSection
        title={t("Hint Mode")}
        description={t(
          "When on, the tutor gives Socratic hints instead of the answer, with a deterministic budget in deep_solve and mastery_path. After the hint budget runs out, the full answer is revealed. In plain chat it is a strong prompt directive only.",
        )}
      >
        <SettingRow
          title={t("Hint Mode")}
          description={t(
            "Coaches the learner to think. Works in deep_solve, mastery_path, and chat.",
          )}
          control={
            <button
              type="button"
              role="switch"
              aria-checked={hintMode}
              onClick={() => updateHintMode(!hintMode)}
              className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] ${
                hintMode ? "bg-[var(--primary)]" : "bg-[var(--muted)]"
              }`}
            >
              <span
                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                  hintMode ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          }
        />
        <SettingRow
          title={t("Max hints before revealing the answer")}
          description={t(
            "How many hints the tutor gives before showing the full step-by-step answer. Default is 3.",
          )}
          control={
            <input
              type="number"
              min={1}
              max={10}
              value={maxHints}
              disabled={!hintMode}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v) && v >= 1 && v <= 10) {
                  updateHintMode(hintMode, Math.round(v));
                }
              }}
              className={`w-20 rounded-md border border-[var(--border)] bg-[var(--card)] px-2 py-1 text-[13px] text-[var(--foreground)] outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] ${
                !hintMode ? "cursor-not-allowed opacity-50" : ""
              }`}
            />
          }
        />
      </SettingSection>

      <SettingSection
        title={t("Theme")}
        description={t(
          "Pick the colour palette and interface style. Each tile previews the theme it applies.",
        )}
      >
        <div className="py-4">
          {/* Order is intentional: Default (pure-white neutral, the default
              selection; theme id "snow" kept for stored preferences) →
              warm-light Cream → warm-dark Dark → cool-dark Glass. */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {(
              [
                { id: "snow", label: t("Default") },
                { id: "light", label: t("Cream") },
                { id: "dark", label: t("Dark") },
                { id: "glass", label: t("Glass") },
              ] as const
            ).map(({ id, label }) => (
              <ThemePreviewCard
                key={id}
                theme={id}
                label={label}
                selected={theme === id}
                onSelect={updateTheme}
              />
            ))}
          </div>
          <p className="mt-4 text-[11.5px] leading-relaxed text-[var(--muted-foreground)]/80">
            {t(
              "Default is a clean pure-white theme with a blue accent. Cream is warm and paper-like with a terracotta accent. Dark keeps Cream's warmth on near-black. Glass adds translucent purple panels on a deep gradient.",
            )}
          </p>
        </div>
      </SettingSection>
    </div>
  );
}
