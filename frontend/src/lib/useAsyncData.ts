import { useCallback, useEffect, useState } from 'react'
import { describeApiError } from '../api/errors.ts'

export type AsyncData<Data> =
  | { status: 'loading' }
  | { status: 'failed'; message: string }
  | { status: 'loaded'; data: Data }

/**
 * Loads data when a component mounts and tracks whether it is loading, loaded
 * or failed. `load` must keep the same identity between renders (wrap it in
 * useCallback), because a new function is taken as a request to load again.
 */
export function useAsyncData<Data>(load: () => Promise<Data>) {
  const [state, setState] = useState<AsyncData<Data>>({ status: 'loading' })
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let isCurrent = true
    load()
      .then((data) => {
        if (isCurrent) {
          setState({ status: 'loaded', data })
        }
      })
      .catch((error: unknown) => {
        if (isCurrent) {
          setState({ status: 'failed', message: describeApiError(error) })
        }
      })
    return () => {
      isCurrent = false
    }
  }, [load, attempt])

  const reload = useCallback(() => {
    setState({ status: 'loading' })
    setAttempt((current) => current + 1)
  }, [])

  /** Changes the loaded data in place, for example after saving one item of a list. */
  const updateData = useCallback((update: (current: Data) => Data) => {
    setState((current) =>
      current.status === 'loaded' ? { status: 'loaded', data: update(current.data) } : current,
    )
  }, [])

  return { state, reload, updateData }
}
