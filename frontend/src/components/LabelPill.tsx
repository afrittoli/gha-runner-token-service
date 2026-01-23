interface LabelPillProps {
  label: string
}

export default function LabelPill({ label }: LabelPillProps) {
  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gh-gray-100 text-gh-gray-700 border border-gh-gray-200">
      {label}
    </span>
  )
}
