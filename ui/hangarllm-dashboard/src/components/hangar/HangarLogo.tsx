import { cn } from "@/lib/cva.config";

export const HANGAR_MARK_PATH = "M10 52V25L32 13.5 54 25V52H44.5V32H19.5V52Z";

interface HangarMarkProps {
  className?: string;
  title?: string;
}

export function HangarMark({ className, title }: HangarMarkProps) {
  return (
    <svg
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role={title ? "img" : undefined}
      aria-hidden={title ? undefined : true}
      className={cn("size-6 shrink-0 text-hangar-amber", className)}
    >
      {title ? <title>{title}</title> : null}
      <path d={HANGAR_MARK_PATH} stroke="currentColor" strokeWidth={5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

interface HangarLogoProps {
  className?: string;
  markClassName?: string;
  compact?: boolean;
}

export function HangarLogo({ className, markClassName, compact = false }: HangarLogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2 select-none", className)}>
      <HangarMark className={markClassName} title={compact ? "HangarLLM" : undefined} />
      {!compact && (
        <span className="text-[17px] font-semibold leading-none tracking-tight text-foreground">
          Hangar
          <span className="text-hangar-amber-ink dark:text-hangar-amber">LLM</span>
        </span>
      )}
    </span>
  );
}

export default HangarLogo;
