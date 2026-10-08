import { createContext } from 'react'
import type { RegistrationDetails, User } from '../api/auth.ts'

export type AuthSession =
  /** A stored token is being checked against the server. */
  | { status: 'loading'; user: null; accessToken: null }
  | { status: 'unauthenticated'; user: null; accessToken: null }
  | { status: 'authenticated'; user: User; accessToken: string }

export type AuthContextValue = AuthSession & {
  login: (email: string, password: string) => Promise<User>
  /** Creates the account and signs the new user in. */
  register: (details: RegistrationDetails) => Promise<User>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
