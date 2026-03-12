import { useEffect, useRef, useState } from 'react'

interface UseIntersectionObserverOptions extends IntersectionObserverInit {
  freezeOnceVisible?: boolean
}

export function useIntersectionObserver(
  options: UseIntersectionObserverOptions = {}
): [React.RefCallback<Element>, boolean] {
  const { threshold = 0, root = null, rootMargin = '0px', freezeOnceVisible = false } = options
  const [isVisible, setIsVisible] = useState(false)
  const frozen = useRef(false)
  const observerRef = useRef<IntersectionObserver | null>(null)

  const ref: React.RefCallback<Element> = (node) => {
    if (observerRef.current) observerRef.current.disconnect()
    if (!node) return

    observerRef.current = new IntersectionObserver(
      ([entry]) => {
        if (frozen.current) return
        setIsVisible(entry.isIntersecting)
        if (entry.isIntersecting && freezeOnceVisible) {
          frozen.current = true
          observerRef.current?.disconnect()
        }
      },
      { threshold, root, rootMargin }
    )
    observerRef.current.observe(node)
  }

  return [ref, isVisible]
}
