import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react'
import {
  fetchCurrentUser,
  loginUser,
  registerUser,
  type RegistrationDetails,
} from '../api/auth.ts'
import { ApiError, setUnauthorizedHandler } from '../api/client.ts'
import { AuthContext, type AuthContextValue, type AuthSession } from './AuthContext.ts'
import { clearStoredAccessToken, readStoredAccessToken, storeAccessToken } from './tokenStorage.ts'

const UNAUTHENTICATED: AuthSession = { status: 'unauthenticated', user: null, accessToken: null }
const LOADING: AuthSession = { status: 'loading', user: null, accessToken: null }

export default function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthSession>(() =>
    readStoredAccessToken() === null ? UNAUTHENTICATED : LOADING,
  )

  // Restore the session after a page load by asking the server who owns the stored token.
  useEffect(() => {
    const storedAccessToken = readStoredAccessToken()
    if (storedAccessToken === null) {
      return
    }

    let isCurrent = true
    fetchCurrentUser(storedAccessToken)
      .then((user) => {
        if (isCurrent) {
          setSession({ status: 'authenticated', user, accessToken: storedAccessToken })
        }
      })
      .catch((error: unknown) => {
        // Only a definite rejection discards the token. After a network
        // failure it is kept, so the next page load can try again.
        if (error instanceof ApiError && error.status === 401) {
          clearStoredAccessToken()
        }
        if (isCurrent) {
          setSession(UNAUTHENTICATED)
        }
      })

    return () => {
      isCurrent = false
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token: accessToken, user } = await loginUser(email, password)
    storeAccessToken(accessToken)
    setSession({ status: 'authenticated', user, accessToken })
    return user
  }, [])

  const register = useCallback(
    async (details: RegistrationDetails) => {
      await registerUser(details)
      return login(details.email, details.password)
    },
    [login],
  )

  const logout = useCallback(() => {
    clearStoredAccessToken()
    setSession(UNAUTHENTICATED)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const contextValue = useMemo<AuthContextValue>(
    () => ({ ...session, login, register, logout }),
    [session, login, register, logout],
  )

  return <AuthContext value={contextValue}>{children}</AuthContext>
}
