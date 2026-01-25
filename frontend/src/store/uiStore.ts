import { create } from 'zustand'

interface UIState {
  sidebarOpen: boolean
  sidebarCollapsed: boolean
  toggleSidebar: () => void
  closeSidebar: () => void
  toggleSidebarCollapse: () => void
}

// Load initial collapsed state from localStorage
const getInitialCollapsedState = (): boolean => {
  try {
    const stored = localStorage.getItem('sidebarCollapsed')
    return stored === 'true'
  } catch {
    return false
  }
}

export const useUIStore = create<UIState>((set) => ({
  sidebarOpen: false,
  sidebarCollapsed: getInitialCollapsedState(),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  closeSidebar: () => set({ sidebarOpen: false }),
  toggleSidebarCollapse: () => set((state) => {
    const newCollapsed = !state.sidebarCollapsed
    try {
      localStorage.setItem('sidebarCollapsed', String(newCollapsed))
    } catch {
      // Ignore localStorage errors
    }
    return { sidebarCollapsed: newCollapsed }
  }),
}))
