export function normalizeImageUrl(url: string | null | undefined): string | null {
  if (!url) return null
  try {
    const parsed = new URL(url, window.location.origin)
    if (parsed.pathname.startsWith("/media/")) return parsed.pathname + parsed.search
    return url
  } catch {
    return url
  }
}
