import { useState, useRef, useEffect } from 'react'

export interface ActionItem {
  label: string
  onClick: () => void
  disabled?: boolean
  disabledTitle?: string
  variant?: 'default' | 'danger'
}

export interface IconAction {
  label: string
  title: string
  onClick: () => void
  disabled?: boolean
  disabledTitle?: string
  icon: React.ReactNode
}

interface ActionMenuProps {
  /** Primary icon-button actions (shown directly in the row) */
  iconActions?: IconAction[]
  /** Additional actions shown in the ⋮ dropdown */
  menuItems?: ActionItem[]
}

/**
 * ActionMenu — a compact row of icon buttons with an optional overflow menu.
 *
 * Use `iconActions` for frequent, non-destructive operations (≤3 recommended).
 * Use `menuItems` for infrequent or destructive operations (e.g. Deactivate).
 */
export default function ActionMenu({ iconActions = [], menuItems = [] }: ActionMenuProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  return (
    <div className="flex items-center justify-end gap-1" ref={ref}>
      {iconActions.map((action) => (
        <button
          key={action.label}
          onClick={action.onClick}
          disabled={action.disabled}
          title={action.disabled ? action.disabledTitle ?? action.title : action.title}
          className="p-1.5 rounded text-gray-500 hover:text-gray-900 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-gh-blue focus:ring-offset-1"
          aria-label={action.title}
        >
          {action.icon}
        </button>
      ))}

      {menuItems.length > 0 && (
        <div className="relative">
          <button
            onClick={() => setOpen((v) => !v)}
            title="More actions"
            className="p-1.5 rounded text-gray-500 hover:text-gray-900 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gh-blue focus:ring-offset-1"
            aria-label="More actions"
            aria-haspopup="true"
            aria-expanded={open}
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M6 10a2 2 0 11-4 0 2 2 0 014 0zm6 0a2 2 0 11-4 0 2 2 0 014 0zm6 0a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </button>

          {open && (
            <div className="absolute right-0 mt-1 w-44 rounded-md shadow-lg bg-white ring-1 ring-black ring-opacity-5 z-10">
              <div className="py-1" role="menu">
                {menuItems.map((item) => (
                  <button
                    key={item.label}
                    onClick={() => {
                      if (!item.disabled) {
                        setOpen(false)
                        item.onClick()
                      }
                    }}
                    disabled={item.disabled}
                    title={item.disabledTitle}
                    role="menuitem"
                    className={`w-full text-left px-4 py-2 text-sm disabled:opacity-40 disabled:cursor-not-allowed ${
                      item.variant === 'danger'
                        ? 'text-red-700 hover:bg-red-50'
                        : 'text-gray-700 hover:bg-gray-100'
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
