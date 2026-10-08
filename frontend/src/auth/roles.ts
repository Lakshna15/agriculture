import type { UserRole } from '../api/auth.ts'

/** Where a signed-in user lands. Administrators have no dashboard yet. */
export function dashboardPathForRole(role: UserRole): string {
  switch (role) {
    case 'CUSTOMER':
      return '/customer'
    case 'FARMER':
      return '/farmer'
    case 'ADMIN':
      return '/'
  }
}
