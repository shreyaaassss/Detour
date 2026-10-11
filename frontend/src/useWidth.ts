import { useEffect, useRef, useState, type RefObject } from 'react'

/** Width of an element, kept current as the window resizes. */
export function useWidth<T extends HTMLElement>(): [RefObject<T | null>, number] {
  const ref = useRef<T | null>(null)
  const [w, setW] = useState(900)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([e]) => setW(Math.max(320, Math.floor(e.contentRect.width))))
    ro.observe(el)
    setW(Math.max(320, Math.floor(el.getBoundingClientRect().width)))
    return () => ro.disconnect()
  }, [])
  return [ref, w]
}
