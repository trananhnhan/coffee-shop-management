import { create } from "zustand"
import { persist } from "zustand/middleware"
import { api } from "@/lib/api"
import { API_BASE_URL } from "@/config/env"

export type UserRole = "owner" | "manager" | "cashier" | "kitchen"

export interface User {
  id: string
  username: string
  role: UserRole
  branch: string | null
  isActive: boolean
  createdAt: string
  updatedAt: string
}

interface AuthState {
  accessToken: string | null
  refreshToken: string | null
  user: User | null
  isAuthenticated: boolean

  login: (username: string, password: string) => Promise<void>
  fetchMe: () => Promise<void>
  logout: () => Promise<void>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      accessToken: null,
      refreshToken: null,
      user: null,
      isAuthenticated: false,

      login: async (username: string, password: string) => {
        const { data } = await api.post(`${API_BASE_URL}/login/`, {
          username,
          password,
        })

        set({
          accessToken: data.access,
          refreshToken: data.refresh,
        })

        await get().fetchMe()
      },

      fetchMe: async () => {
        const { data } = await api.get<User>("/users/me/")
        set({
          user: data,
          isAuthenticated: true,
        })
      },

      logout: async () => {
        const refreshToken = get().refreshToken
        try {
          if (refreshToken) {
            await api.post(`${API_BASE_URL}/logout/`, { refresh: refreshToken })
          }
        } catch {
          // dù blacklist lỗi hay không, vẫn clear phía client
        }

        set({
          accessToken: null,
          refreshToken: null,
          user: null,
          isAuthenticated: false,
        })
      },
    }),
    {
      name: "auth-storage",
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)