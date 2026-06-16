/** Inline Kubernetes wheel icon — simplified 7-spoke helm */
export function K8sIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      className={className}
    >
      <circle cx="12" cy="12" r="9" />
      <path d="M12 3v18" />
      <path d="M4.2 7.5h15.6" />
      <path d="M4.2 16.5h15.6" />
      <path d="M7.5 4.2l9 15.6" />
      <path d="M16.5 4.2l-9 15.6" />
    </svg>
  );
}
