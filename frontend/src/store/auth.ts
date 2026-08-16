import { create } from 'zustand'

import { api, tokenStore } from '@/lib/api'
import type { User } from '@/lib/types'

interface AuthState {
  user: User | null
  loading: boolean
  initialised: boolean
  error: string | null
  bootstrap: () => Promise<void>
  login: (email: string, password: string) => Promise<User>
  register: (payload: {
    email: string; password: string; full_name: string; phone?: string
  }) => Promise<User>
  logout: () => void
  refreshUser: () => Promise<void>
}

export const useAuth = create<AuthState>((set) => ({
  user: null,
  loading: false,
  initialised: false,
  error: null,

  /** Restore the session on page load if a token survives in localStorage. */
  async bootstrap() {
    if (!tokenStore.access()) {
      set({ initialised: true })
      return
    }
    set({ loading: true })
    try {
      set({ user: await api.me(), initialised: true, loading: false })
    } catch {
      tokenStore.clear()
      set({ user: null, initialised: true, loading: false })
    }
  },

  async login(email, password) {
    set({ loading: true, error: null })
    try {
      const { user, tokens } = await api.login(email, password)
      tokenStore.set(tokens.access_token, tokens.refresh_token)
      set({ user, loading: false })
      return user
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Sign-in failed.'
      set({ loading: false, error: message })
      throw error
    }
  },

  async register(payload) {
    set({ loading: true, error: null })
    try {
      const { user, tokens } = await api.register(payload)
      tokenStore.set(tokens.access_token, tokens.refresh_token)
      set({ user, loading: false })
      return user
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Registration failed.'
      set({ loading: false, error: message })
      throw error
    }
  },

  logout() {
    tokenStore.clear()
    set({ user: null, error: null })
  },

  async refreshUser() {
    try {
      set({ user: await api.me() })
    } catch {
      /* keep the current user on a transient failure */
    }
  },
}))

export const STAFF_ROLES = ['agent', 'supervisor', 'admin'] as const

export function isStaff(user: User | null): boolean {
  return !!user && (STAFF_ROLES as readonly string[]).includes(user.role)
}
