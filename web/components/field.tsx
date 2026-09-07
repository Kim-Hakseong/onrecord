"use client";

import { useEffect, useRef } from "react";

/** Grid spacing in CSS pixels. Larger = fewer dots = cheaper.
 *  Fine enough that the grid reads as a material rather than as polka dots. */
const SPACING = 16;
/** Rendered diameter of one dot, in CSS pixels. */
const DOT = 5;
/** How far the pointer reaches, in CSS pixels. */
const REACH = 170;
/** Peak displacement a dot takes when the pointer is right on top of it. */
const PUSH = 16;

type Dot = { x: number; y: number; phase: number };

/**
 * The background dot field.
 *
 * This is the surface's one authored moment. Everything else in the product
 * moves only when something actually happened — a verdict landed, a filter
 * changed — because a screen that animates while nothing is happening is
 * making a claim about state, which is the exact failure the product is about.
 * So the field claims nothing: it is a material, it drifts slowly, and it
 * reacts to the pointer, which is a real input rather than a fabricated event.
 *
 * Drawn on a canvas rather than in the DOM because a few thousand nodes with
 * transforms is how a demo machine starts dropping frames. Colour comes from
 * the theme's CSS variables, read once per resize, so light and dark stay one
 * system.
 */
export function Field() {
  const ref = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const context = ref.current?.getContext("2d", { alpha: true });
    if (!context) return;
    // Annotated so the narrowing survives into the closures below; TypeScript
    // does not carry a guard's narrowing into hoisted function declarations.
    const ctx: CanvasRenderingContext2D = context;
    const surface: HTMLCanvasElement = ctx.canvas;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

    let dots: Dot[] = [];
    let width = 0;
    let height = 0;
    let ratio = 1;
    let sprite: HTMLCanvasElement | null = null;
    let frame = 0;
    let running = true;

    // Where the pointer is, and where the field currently believes it is.
    // Lerping the second toward the first keeps the push from snapping.
    const target = { x: -9999, y: -9999 };
    const eased = { x: -9999, y: -9999 };

    function readColor() {
      const styles = getComputedStyle(document.documentElement);
      const rgb = styles.getPropertyValue("--field-dot").trim() || "123, 92, 214";
      const alpha = Number(styles.getPropertyValue("--field-alpha")) || 0.3;
      return { rgb, alpha };
    }

    /** One soft dot, drawn once and stamped thousands of times. */
    function buildSprite() {
      const { rgb, alpha } = readColor();
      const size = DOT;
      const off = document.createElement("canvas");
      off.width = off.height = size * ratio;
      const octx = off.getContext("2d");
      if (!octx) return null;
      octx.scale(ratio, ratio);
      const gradient = octx.createRadialGradient(
        size / 2,
        size / 2,
        0,
        size / 2,
        size / 2,
        size / 2,
      );
      gradient.addColorStop(0, `rgba(${rgb}, ${alpha})`);
      gradient.addColorStop(0.55, `rgba(${rgb}, ${alpha * 0.55})`);
      gradient.addColorStop(1, `rgba(${rgb}, 0)`);
      octx.fillStyle = gradient;
      octx.fillRect(0, 0, size, size);
      return off;
    }

    function layout() {
      // The field is a soft, blurred texture, so it does not need full retina
      // fill. Capping the backing store here is most of its frame cost.
      ratio = Math.min(window.devicePixelRatio || 1, 1.5);
      width = window.innerWidth;
      height = window.innerHeight;
      surface.width = Math.floor(width * ratio);
      surface.height = Math.floor(height * ratio);
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

      dots = [];
      // Keep the dot count bounded so a large display does not cost frames.
      const step = Math.max(
        SPACING,
        Math.ceil(Math.sqrt(((width + 2 * SPACING) * (height + 2 * SPACING)) / 5200)),
      );
      // Bleed one row and column past each edge so the field has no border.
      for (let y = -step; y < height + step; y += step) {
        for (let x = -step; x < width + step; x += step) {
          dots.push({ x, y, phase: (x + y) * 0.012 });
        }
      }
      sprite = buildSprite();
    }

    function draw(time: number) {
      if (!sprite) return;
      ctx.clearRect(0, 0, width, height);

      eased.x += (target.x - eased.x) * 0.12;
      eased.y += (target.y - eased.y) * 0.12;

      const t = time * 0.00022;
      const unit = sprite.width / ratio;
      const half = unit / 2;
      // Compare squared distances and take the root only for the few dots that
      // are actually inside the pointer's reach.
      const reachSq = REACH * REACH;

      for (const dot of dots) {
        // Two crossed sines stand in for noise: cheap, and at this amplitude
        // indistinguishable from the real thing.
        const wave =
          Math.sin(dot.x * 0.006 + t + dot.phase) +
          Math.sin(dot.y * 0.008 - t * 1.3 + dot.phase);
        let x = dot.x + wave * 2.2;
        let y = dot.y + wave * 2.8;

        const dx = x - eased.x;
        const dy = y - eased.y;
        const lengthSq = dx * dx + dy * dy;
        let scale = 1;
        if (lengthSq < reachSq) {
          const distance = Math.sqrt(lengthSq);
          // Squared falloff: a firm centre that fades out rather than a
          // hard-edged circle following the cursor around.
          const strength = (1 - distance / REACH) ** 2;
          const push = (PUSH * strength) / (distance || 1);
          x += dx * push;
          y += dy * push;
          scale = 1 + strength * 1.1;
        }

        // Anything pushed off-screen costs a draw call for nothing.
        if (x < -unit || y < -unit || x > width + unit || y > height + unit) continue;

        const size = unit * scale;
        ctx.drawImage(sprite, x - half * scale, y - half * scale, size, size);
      }
    }

    // Half the display's cadence. The drift is slow and the pointer push is
    // eased, so 30fps is indistinguishable here and costs half the fill --
    // and it stays vsync-aligned, which an arbitrary interval would not.
    let tick = 0;
    function loop(time: number) {
      if (!running) return;
      if (tick++ % 2 === 0) draw(time);
      frame = requestAnimationFrame(loop);
    }

    function start() {
      if (running) return;
      running = true;
      frame = requestAnimationFrame(loop);
    }

    function stop() {
      running = false;
      cancelAnimationFrame(frame);
    }

    function onPointer(event: PointerEvent) {
      if (reduced.matches) return;
      target.x = event.clientX;
      target.y = event.clientY;
    }

    function onLeave() {
      target.x = -9999;
      target.y = -9999;
    }

    function onVisibility() {
      // A loop nobody can see is just heat.
      if (document.hidden) stop();
      else start();
    }

    function onMotionPreference() {
      if (reduced.matches) {
        stop();
        onLeave();
        eased.x = eased.y = -9999;
        draw(0); // one still frame: the texture stays, the movement goes
      } else {
        start();
      }
    }

    function onResize() {
      layout();
      if (reduced.matches) draw(0);
    }

    layout();
    if (reduced.matches) {
      running = false;
      draw(0);
    } else {
      frame = requestAnimationFrame(loop);
    }

    window.addEventListener("resize", onResize);
    window.addEventListener("pointermove", onPointer, { passive: true });
    window.addEventListener("pointerleave", onLeave);
    document.addEventListener("visibilitychange", onVisibility);
    reduced.addEventListener("change", onMotionPreference);

    // The theme toggle swaps the CSS variables the sprite was built from.
    const observer = new MutationObserver(() => {
      sprite = buildSprite();
      if (reduced.matches) draw(0);
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    return () => {
      stop();
      window.removeEventListener("resize", onResize);
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("pointerleave", onLeave);
      document.removeEventListener("visibilitychange", onVisibility);
      reduced.removeEventListener("change", onMotionPreference);
      observer.disconnect();
    };
  }, []);

  return <canvas ref={ref} className="field" aria-hidden="true" />;
}

/** Fine grain over everything, cards included. Pure CSS; see `.grain`. */
export function Grain() {
  return <div className="grain" aria-hidden="true" />;
}
