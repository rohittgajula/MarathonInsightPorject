import { useEffect, useRef, useState, type ReactNode } from "react";

/* A short slide band at the foot of the hero.

   It exists to stop the hero growing every time something else is worth saying.
   Stacking the session detail and the closest achievement made the card tall enough
   that the session — the thing the page is for — stopped being the biggest element
   on screen.

   Three rules it follows, all of which are the difference between a slider and the
   kind of carousel people rightly complain about:

   - Nothing safety-critical goes in here. The readiness note stays pinned outside,
     because a message that says "do not train hard today" must not sit behind a
     slide the reader never advances to.
   - Auto-advance stops permanently the moment you interact, and pauses while the
     pointer or keyboard focus is inside. Text that moves while you are reading it
     is worse than text you had to click for.
   - With one slide it renders as plain content: no dots, no timer, no controls for
     a thing that cannot move. */

const INTERVAL_MS = 9000;

export function HeroSlides({ slides }: { slides: { key: string; node: ReactNode }[] }) {
  const [index, setIndex] = useState(0);
  const [held, setHeld] = useState(false);
  // Set once a human takes control; auto-advance never resumes after that.
  const [taken, setTaken] = useState(false);
  const region = useRef<HTMLDivElement>(null);

  const count = slides.length;
  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

  useEffect(() => {
    if (count < 2 || held || taken || reduced) return;
    const timer = window.setInterval(
      () => setIndex((i) => (i + 1) % count),
      INTERVAL_MS,
    );
    return () => window.clearInterval(timer);
  }, [count, held, taken, reduced]);

  if (count === 0) return null;
  if (count === 1) return <div className="hero-slides single">{slides[0].node}</div>;

  const go = (next: number) => {
    setTaken(true);
    setIndex(((next % count) + count) % count);
  };

  return (
    <div
      ref={region}
      className="hero-slides"
      role="group"
      aria-roledescription="carousel"
      aria-label="More about today"
      onMouseEnter={() => setHeld(true)}
      onMouseLeave={() => setHeld(false)}
      onFocusCapture={() => setHeld(true)}
      onBlurCapture={() => setHeld(false)}
      onKeyDown={(e) => {
        if (e.key === "ArrowRight") { e.preventDefault(); go(index + 1); }
        if (e.key === "ArrowLeft") { e.preventDefault(); go(index - 1); }
      }}
    >
      {/* The clip has to happen at the content box. Clipping on the padded outer
          element lets the next slide show through the padding at the right edge. */}
      <div className="hero-viewport">
      <div className="hero-track" style={{ transform: `translateX(-${index * 100}%)` }}>
        {slides.map((slide, i) => (
          <div
            key={slide.key}
            className="hero-slide"
            role="group"
            aria-roledescription="slide"
            aria-label={`${i + 1} of ${count}`}
            // Hidden slides are taken out of the tab order and off the screen
            // reader's path, so the band reads as one thing rather than three.
            aria-hidden={i !== index}
            {...(i !== index ? { inert: "" as unknown as boolean } : {})}
          >
            {slide.node}
          </div>
        ))}
      </div>
      </div>

      <div className="hero-dots">
        {slides.map((slide, i) => (
          <button
            key={slide.key}
            className={`hero-dot${i === index ? " on" : ""}`}
            aria-label={`Show slide ${i + 1} of ${count}`}
            aria-current={i === index}
            onClick={() => go(i)}
          />
        ))}
      </div>
    </div>
  );
}
