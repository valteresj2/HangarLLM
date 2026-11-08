"use client";

import { createElement } from "react";
import { useTranslation } from "react-i18next";
import type { ParseKeys } from "i18next";
import { uiHref } from "@/utils/uiHref";
import { HANGAR_ICON_PROPS, HangarIcons } from "@/components/hangar/icons";
import { HangarMark } from "@/components/hangar/HangarLogo";

type QuickLink = { route: string; label: ParseKeys; icon: keyof typeof HangarIcons };

const QUICK_LINKS: readonly QuickLink[] = [
  { route: "models-and-endpoints", label: "home.hero.links.models", icon: "models" },
  { route: "agents", label: "home.hero.links.agents", icon: "agents" },
  { route: "mcp-servers", label: "home.hero.links.mcp", icon: "mcp" },
  { route: "guardrails", label: "home.hero.links.guardrails", icon: "guardrails" },
];

export function HangarWelcome() {
  const { t } = useTranslation();
  return (
    <section
      aria-labelledby="hangar-welcome-title"
      className="relative overflow-hidden rounded-xl border border-hangar-line bg-hangar-navy px-5 py-5 text-white sm:px-6"
    >
      <HangarMark className="pointer-events-none absolute -right-6 -bottom-10 size-48 opacity-15" />
      <div className="relative flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="max-w-xl">
          <h2 id="hangar-welcome-title" className="text-lg font-semibold">
            {t("home.hero.title")}
          </h2>
          <p className="mt-1 text-sm text-hangar-slate">{t("home.hero.subtitle")}</p>
        </div>
        <nav aria-label={t("home.hero.linksLabel")} className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
          {QUICK_LINKS.map(({ route, label, icon }) => (
            <a
              key={route}
              href={uiHref(route)}
              className="inline-flex items-center gap-2 rounded-md border border-hangar-line bg-hangar-navy-850 px-3 py-2 text-sm font-medium text-white transition-colors hover:border-hangar-amber hover:text-hangar-amber focus-visible:outline-2 focus-visible:outline-hangar-amber"
            >
              {createElement(HangarIcons[icon], { ...HANGAR_ICON_PROPS, className: "size-4 text-hangar-amber" })}
              {t(label)}
            </a>
          ))}
        </nav>
      </div>
    </section>
  );
}
