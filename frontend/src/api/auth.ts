import { apiRequest } from './client.ts'

export type UserRole = 'CUSTOMER' | 'FARMER' | 'ADMIN'

/** Roles a visitor may choose when creating an account. */
export type RegistrableRole = Exclude<UserRole, 'ADMIN'>

export type User = {
  id: number
  name: string
  email: string
  role: UserRole
  created_at: string
  updated_at: string
}

export type RegistrationDetails = {
  name: string
  email: string
  password: string
  role: RegistrableRole
}

export type LoginResult = {
  access_token: string
  token_type: 'bearer'
  user: User
}

export function registerUser(details: RegistrationDetails): Promise<User> {
  return apiRequest<User>('/api/auth/register', { method: 'POST', body: details })
}

export function loginUser(email: string, password: string): Promise<LoginResult> {
  return apiRequest<LoginResult>('/api/auth/login', { method: 'POST', body: { email, password } })
}

export function fetchCurrentUser(accessToken: string): Promise<User> {
  return apiRequest<User>('/api/auth/me', { accessToken })
}
