import { useEffect } from "react";

/* Writes the pointer position onto each .card as --mx/--my so the CSS sheen can
   follow it. Done with a delegated listener and CSS custom properties rather than
   per-card React state — moving the mouse should never trigger a re-render. */
export function usePointerGlow() {
  useEffect(() => {
    let frame = 0;
    const onMove = (e: MouseEvent) => {
      if (frame) return;
      frame = requestAnimationFrame(() => {
        frame = 0;
        const card = (e.target as HTMLElement)?.closest?.(".card") as HTMLElement | null;
        if (!card) return;
        const r = card.getBoundingClientRect();
        card.style.setProperty("--mx", `${e.clientX - r.left}px`);
        card.style.setProperty("--my", `${e.clientY - r.top}px`);
      });
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onMove);
      if (frame) cancelAnimationFrame(frame);
    };
  }, []);
}
