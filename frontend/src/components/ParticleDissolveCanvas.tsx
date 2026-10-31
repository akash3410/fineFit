import { useEffect, useRef } from 'react'

/* ────────────────────────────────────────────────────────────────────────────
 * ParticleDissolveCanvas — turns a photograph into falling snow.
 *
 * The image is drawn into a small offscreen canvas, its pixels are read back,
 * and each surviving sample becomes a single particle that inherits that pixel's
 * colour. Because the particles start exactly where their pixels were, the
 * canvas reproduces the photograph on the first frame and the transition out of
 * the real <img> is seamless — the picture simply comes apart.
 *
 * Two-phase lifecycle
 * -------------------
 * The canvas is mounted a whole phase before it is needed (during `stay`) and
 * only prepares: it decodes the photograph, samples it and builds the particle
 * field, then waits. The first snowflake therefore moves on the very first frame
 * of the dissolve, with no decode or `getImageData` cost inside the transition —
 * the old version started sampling after the photograph had already begun to
 * fade, which could leave a dim, almost-empty frame on slower devices.
 *
 * Organic motion
 * --------------
 * Nothing about the field is uniform: particles are jittered off the sampling
 * grid, a fraction of cells are dropped so holes open unevenly, and each
 * particle carries its own depth, terminal speed, sway, spin, lifetime and
 * softness. Depth is the organising idea — far fragments are small, slow, dim
 * and blurred; near ones are larger, brighter and quicker, so the fall has real
 * parallax instead of reading as one flat sheet.
 *
 * Everything renders into one canvas: no DOM nodes are created per particle, no
 * React state is touched while it runs, and the component tears down its frame,
 * canvas size and buffers when it unmounts. The fall fades out over its last
 * half-second, so the slide can unmount without a single flake popping away.
 *
 * If the pixels cannot be read (cross-origin image without CORS headers) the
 * canvas stays empty and the photograph's own fade carries the sequence.
 * ──────────────────────────────────────────────────────────────────────── */

interface ParticleDissolveCanvasProps {
  /** Photograph to break apart. Same-origin, or served with CORS headers. */
  imageSrc: string
  /** CSS `object-position` the <img> uses; the live value is read from the DOM. */
  imagePosition?: string
  /** True once the sequence enters its dissolve phase. */
  active: boolean
  /** Length of the dissolve phase in ms. The snow is gone when it ends. */
  duration: number
  className?: string
}

interface Particle {
  /** Position in CSS pixels. */
  x: number
  y: number
  vx: number
  vy: number
  /** Speed the particle eases towards, px/s. */
  terminal: number
  /** 0 = deep background, 1 = close to the lens. Drives size, speed and blur. */
  depth: number
  size: number
  /** Pre-built `rgb(...)` string inherited from the photograph. */
  color: string
  alpha: number
  /** Milliseconds of stillness before the particle lets go. */
  delay: number
  /** Soft, round snowflake rather than a square grain. */
  flake: boolean
  /** Which softness sprite the flake draws with. */
  sprite: number
  rotation: number
  spin: number
  /** Milliseconds at full opacity before it starts to thin out. */
  life: number
  /** Phase offset so neighbouring particles do not sway in lockstep. */
  seed: number
  swayAmp: number
  swayFreq: number
  dead: boolean
}

const WIND = 22 /* px per second, steady sideways drift */
const GUST = 15 /* px per second of slow wind swell */
const AIR = 2.4 /* how quickly a particle settles to its terminal speed */
const FADE_MS = 620 /* per-particle fade once its life is spent */
const TAIL_MS = 520 /* global fade at the end of the dissolve */
const SPRITE_SCALE = 1.9

/** Parses a CSS `object-position` into fractional anchors. */
function parsePosition(value: string | undefined): { x: number; y: number } {
  const tokens = (value ?? 'center').trim().split(/\s+/)
  const resolve = (token: string | undefined): number => {
    if (!token) return 0.5
    const lower = token.toLowerCase()
    if (lower === 'left' || lower === 'top') return 0
    if (lower === 'right' || lower === 'bottom') return 1
    if (lower === 'center') return 0.5
    if (lower.endsWith('%')) {
      const value = Number.parseFloat(lower)
      return Number.isFinite(value) ? Math.min(1, Math.max(0, value / 100)) : 0.5
    }
    return 0.5
  }
  /* A single value positions the x axis and centres y, per the CSS spec. */
  return { x: resolve(tokens[0]), y: resolve(tokens[1]) }
}

/** Source rectangle that `object-fit: cover` shows for the given box. */
function coverSourceRect(
  imageWidth: number,
  imageHeight: number,
  boxWidth: number,
  boxHeight: number,
  anchorX: number,
  anchorY: number,
) {
  const scale = Math.max(boxWidth / imageWidth, boxHeight / imageHeight)
  const visibleWidth = boxWidth / scale
  const visibleHeight = boxHeight / scale
  return {
    sx: (imageWidth - visibleWidth) * anchorX,
    sy: (imageHeight - visibleHeight) * anchorY,
    sw: visibleWidth,
    sh: visibleHeight,
  }
}

/**
 * Soft white dots, reused by every snowflake. Three softness levels are baked
 * once, so depth blur costs one `drawImage` instead of a per-frame canvas filter.
 */
function createFlakeSprites(): HTMLCanvasElement[] {
  return [0.12, 0.48, 0.86].map((softness) => {
    const size = 32
    const sprite = document.createElement('canvas')
    sprite.width = size
    sprite.height = size

    const context = sprite.getContext('2d')
    if (context) {
      const radius = size / 2
      const gradient = context.createRadialGradient(radius, radius, 0, radius, radius, radius)
      gradient.addColorStop(0, 'rgba(255, 255, 255, 1)')
      gradient.addColorStop(
        Math.max(0.18, 1 - softness * 0.62),
        `rgba(255, 255, 255, ${0.8 - softness * 0.32})`,
      )
      gradient.addColorStop(1, 'rgba(255, 255, 255, 0)')
      context.fillStyle = gradient
      context.fillRect(0, 0, size, size)
    }
    return sprite
  })
}

export function ParticleDissolveCanvas({
  imageSrc,
  imagePosition,
  active,
  duration,
  className,
}: ParticleDissolveCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null)
  /** Latest `active`, readable from the (async) preparation. */
  const activeRef = useRef(active)
  /** Handles into the prepared engine, so the phase change can start it. */
  const engineRef = useRef<{ start: () => void; stop: () => void } | null>(null)

  /* Preparation: decode, sample, build the field. Runs once per photograph,
   * while the slide is still fully on screen. */
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const context = canvas.getContext('2d', { alpha: true })
    if (!context) return

    let cancelled = false
    let frame = 0
    let running = false
    let particles: Particle[] | null = null
    let width = 0
    let height = 0
    let startedAt = 0
    let last = 0
    let sprites: HTMLCanvasElement[] = []

    const stop = () => {
      running = false
      if (frame) cancelAnimationFrame(frame)
      frame = 0
    }

    const clear = () => {
      context.setTransform(1, 0, 0, 1, 0, 0)
      context.globalAlpha = 1
      context.clearRect(0, 0, canvas.width, canvas.height)
    }

    const start = () => {
      if (running || cancelled || !particles || !particles.length) return
      running = true
      startedAt = performance.now()
      last = startedAt
      frame = requestAnimationFrame(draw)
    }

    const draw = (now: number) => {
      if (cancelled || !particles) return

      const elapsed = now - startedAt
      /* A long frame (tab wake, GC) must not teleport the whole field. */
      const delta = Math.min(48, now - last) / 1000
      last = now

      if (elapsed >= duration) {
        stop()
        clear()
        return
      }

      context.clearRect(0, 0, width, height)

      /* One wind system shared by the field, so the whole fall leans the same
       * way the way real weather does — each particle merely rides it by its
       * own weight. */
      const wind =
        WIND + Math.sin(elapsed / 1900) * GUST + Math.sin(elapsed / 730 + 1.7) * GUST * 0.35

      /* The snow fades out before the phase ends, so nothing pops on unmount. */
      const tailStart = duration - TAIL_MS
      const tail = elapsed <= tailStart ? 0 : Math.min(1, (elapsed - tailStart) / TAIL_MS)
      const outro = 1 - tail * tail * (3 - 2 * tail)

      let alive = 0

      for (let i = 0; i < particles.length; i++) {
        const particle = particles[i]
        if (particle.dead) continue

        const age = elapsed - particle.delay

        if (age <= 0) {
          /* Still part of the photograph: hold its pixel in place. */
          const holding = particle.alpha * outro
          if (holding <= 0.01) continue
          alive++
          context.globalAlpha = holding
          if (particle.flake) {
            const size = particle.size * SPRITE_SCALE
            const sprite = sprites[particle.sprite]
            context.drawImage(sprite, particle.x - size / 2, particle.y - size / 2, size, size)
          } else {
            context.fillStyle = particle.color
            context.fillRect(particle.x, particle.y, particle.size, particle.size)
          }
          continue
        }

        /* Ease towards a terminal speed rather than accelerating forever: snow
         * picks up speed, meets the air, then drifts. */
        particle.vy += (particle.terminal - particle.vy) * Math.min(1, AIR * delta)
        particle.x += (particle.vx + wind * (0.55 + particle.depth * 0.9)) * delta
        particle.y += particle.vy * delta
        particle.rotation += particle.spin * delta

        const fade = age > particle.life ? Math.max(0, 1 - (age - particle.life) / FADE_MS) : 1
        const sway = Math.sin(elapsed * particle.swayFreq + particle.seed) * particle.swayAmp
        const x = particle.x + sway
        const y = particle.y
        const alpha = particle.alpha * fade * outro

        if (y - particle.size * 3 > height) {
          particle.dead = true
          continue
        }
        if (fade <= 0) {
          particle.dead = true
          continue
        }
        if (alpha <= 0.01) continue

        alive++
        context.globalAlpha = alpha

        if (particle.flake) {
          const size = particle.size * SPRITE_SCALE
          const sprite = sprites[particle.sprite]
          context.save()
          context.translate(x, y)
          context.rotate(particle.rotation)
          context.drawImage(sprite, -size / 2, -size / 2, size, size)
          context.restore()
        } else {
          context.fillStyle = particle.color
          context.fillRect(x, y, particle.size, particle.size)
        }
      }

      context.globalAlpha = 1

      if (alive === 0) {
        stop()
        clear()
        return
      }

      frame = requestAnimationFrame(draw)
    }

    engineRef.current = { start, stop }

    const prepare = async () => {
      const box = canvas.getBoundingClientRect()
      const boxWidth = Math.round(box.width)
      const boxHeight = Math.round(box.height)
      if (boxWidth < 40 || boxHeight < 40) return

      /* Bound the backing store. Snow is soft by nature, so a 1.25× buffer is
       * indistinguishable from 3× while costing a fraction of the fill rate —
       * clearing a full-retina hero every frame is the single most expensive
       * thing this effect could do. */
      const dpr = Math.min(window.devicePixelRatio || 1, 1.25)
      canvas.width = Math.round(boxWidth * dpr)
      canvas.height = Math.round(boxHeight * dpr)
      context.setTransform(dpr, 0, 0, dpr, 0, 0)
      width = boxWidth
      height = boxHeight

      /* Sample the photograph the slide is actually showing: `<picture>` may
       * have picked the portrait crop, and the resolved `object-position`
       * differs per breakpoint. Reading them from the DOM keeps the snow on
       * top of exactly the pixels it is replacing. */
      const slide = canvas.closest('[data-hero-slide]')
      const img = slide?.querySelector('img')
      const src = img?.currentSrc || img?.src || imageSrc
      const livePosition = img ? window.getComputedStyle(img).objectPosition : ''
      const anchor = parsePosition(livePosition || imagePosition)

      /* Sample coarsely: one read per particle-sized cell, not per screen pixel. */
      const sampleWidth = Math.round(Math.min(300, Math.max(140, width / 5)))
      const sampleHeight = Math.max(40, Math.round((sampleWidth * height) / width))

      const image = new Image()
      image.decoding = 'async'
      image.src = src

      try {
        if (!image.complete) {
          await new Promise<void>((resolve, reject) => {
            image.onload = () => resolve()
            image.onerror = () => reject(new Error('image failed to load'))
          })
        }
        await image.decode?.()
      } catch {
        return /* no pixels to sample; the slide's fade still runs */
      }
      if (cancelled) return

      const sampleCanvas = document.createElement('canvas')
      sampleCanvas.width = sampleWidth
      sampleCanvas.height = sampleHeight
      const sampleContext = sampleCanvas.getContext('2d', { willReadFrequently: true })
      if (!sampleContext || !image.naturalWidth) return

      const source = coverSourceRect(
        image.naturalWidth,
        image.naturalHeight,
        width,
        height,
        anchor.x,
        anchor.y,
      )
      sampleContext.drawImage(
        image,
        source.sx,
        source.sy,
        source.sw,
        source.sh,
        0,
        0,
        sampleWidth,
        sampleHeight,
      )

      let pixels: Uint8ClampedArray
      try {
        pixels = sampleContext.getImageData(0, 0, sampleWidth, sampleHeight).data
      } catch {
        return /* tainted canvas: fall back to the plain fade */
      }
      if (cancelled) return

      /* Particle budget: thousands on desktop, far fewer on phones. */
      const target =
        width < 768 ? 780 : Math.min(4600, Math.max(2600, Math.round(width * 3.2)))
      const step = Math.max(1, Math.round(Math.sqrt((sampleWidth * sampleHeight) / target)))

      /* Match the photograph's on-screen scale (the slow push-in that runs
       * through the stay phase), so particles sit exactly over the pixels they
       * replace instead of shrinking the picture on the hand-off. The floor
       * matters for a dissolve started mid-entrance (manual navigation): the
       * photograph is still small then and would otherwise drag the snow with
       * it, when in fact it keeps growing as it fades. */
      const photo = canvas.parentElement?.querySelector('[data-hero-photo]')
      const photoWidth = photo?.getBoundingClientRect().width ?? width
      const scale = Math.min(1.12, Math.max(0.92, photoWidth / width))
      const centerX = width / 2
      const centerY = height / 2
      const projectX = (value: number) => centerX + (value - centerX) * scale
      const projectY = (value: number) => centerY + (value - centerY) * scale

      const cellWidth = width / sampleWidth
      const cellHeight = height / sampleHeight
      const field: Particle[] = []

      for (let y = 0; y < sampleHeight; y += step) {
        for (let x = 0; x < sampleWidth; x += step) {
          const index = (y * sampleWidth + x) * 4
          if (pixels[index + 3] < 40) continue

          /* Uneven density: dropping a few cells means the photograph opens
           * holes at different rates as it breaks, rather than thinning out
           * everywhere at once. */
          if (Math.random() < 0.07) continue

          /* Jitter off the sampling grid so the fall never reveals a lattice. */
          const normalizedX = (x + Math.random()) / sampleWidth
          const normalizedY = (y + Math.random()) / sampleHeight

          /* Most fragments sit far back; a few are close to the lens. */
          const depth = 0.25 + Math.pow(Math.random(), 1.3) * 0.75
          const flake = Math.random() > 0.92

          const grainSize = flake ? 1.7 + Math.random() * 2.3 : 0.9 + Math.random() * 1.7

          field.push({
            x: projectX((x + Math.random()) * cellWidth),
            y: projectY((y + Math.random()) * cellHeight),
            /* Only used once the particle lets go. */
            vx: (Math.random() - 0.5) * 30 * (0.4 + depth),
            vy: 6 + Math.random() * 40,
            terminal: (30 + Math.random() * 60) * (0.4 + depth * 1.5),
            depth,
            size: Math.max(0.8, grainSize * (0.55 + depth * 1.05)),
            color: `rgb(${pixels[index]},${pixels[index + 1]},${pixels[index + 2]})`,
            alpha: flake
              ? (0.18 + Math.random() * 0.22) * (0.55 + depth * 0.7)
              : (0.72 + Math.random() * 0.28) * (0.5 + depth * 0.5),
            /* The frame lets go from the top-left first and works its way
             * across and down, the way wind peels paint — never all at once. */
            delay:
              Math.pow(Math.random(), 1.4) * 520 + normalizedY * 190 + normalizedX * 90,
            flake,
            sprite: Math.min(2, Math.floor((1 - depth) * 3 + Math.random() * 0.8)),
            rotation: Math.random() * Math.PI * 2,
            spin: flake ? (Math.random() - 0.5) * 3.6 : 0,
            life: 620 + Math.random() * 780,
            seed: Math.random() * Math.PI * 2,
            swayAmp: (6 + Math.random() * 18) * (0.5 + depth * 0.8),
            swayFreq: 0.0009 + Math.random() * 0.0018,
            dead: false,
          })
        }
      }

      if (!field.length || cancelled) return

      /* Far to near, so closer fragments occlude the ones behind them. */
      field.sort((a, b) => a.depth - b.depth)
      particles = field
      sprites = getFlakeSprites()

      /* Prepared during the stay phase, so this is already true by the time the
       * dissolve starts — the hand-off costs zero frames. */
      if (activeRef.current) start()
    }

    void prepare()

    return () => {
      cancelled = true
      stop()
      engineRef.current = null
      particles = null
      clear()
    }
  }, [imageSrc, imagePosition, duration])

  /* Phase change only starts or stops the prepared field — no re-sampling. */
  useEffect(() => {
    activeRef.current = active
    const engine = engineRef.current
    if (!engine) return
    if (active) engine.start()
    else engine.stop()
  }, [active])

  return (
    <canvas
      ref={canvasRef}
      className={className}
      aria-hidden="true"
      data-particle-dissolve=""
    />
  )
}

/* Softness sprites are built once and reused by every dissolve in the session. */
let flakeSprites: HTMLCanvasElement[] | null = null
const getFlakeSprites = () => (flakeSprites ??= createFlakeSprites())
