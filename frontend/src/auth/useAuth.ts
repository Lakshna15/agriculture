import { useContext } from 'react'
import { AuthContext, type AuthContextValue } from './AuthContext.ts'

export function useAuth(): AuthContextValue {
  const contextValue = useContext(AuthContext)
  if (contextValue === null) {
    throw new Error('useAuth must be used inside an AuthProvider')
  }
  return contextValue
}

/** The access token of the signed-in user, for pages that are only shown behind RequireRole. */
export function useAccessToken(): string {
  const auth = useAuth()
  if (auth.status !== 'authenticated') {
    throw new Error('useAccessToken must be used on a page that requires a signed-in user')
  }
  return auth.accessToken
}
