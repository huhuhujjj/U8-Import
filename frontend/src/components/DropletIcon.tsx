interface DropletIconProps {
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

export function DropletIcon({ size = 'sm' }: DropletIconProps) {
  const sizeMap = {
    sm: '16px',   // 1rem
    md: '24px',   // 1.5rem
    lg: '32px',   // 2rem
    xl: '48px',   // 3rem
  };

  const pixelSize = sizeMap[size];

  return (
    <svg
      width={pixelSize}
      height={pixelSize}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      xmlns="http://www.w3.org/2000/svg"
      style={{ display: 'inline-block' }}
    >
      {/* Arrow pointing down into container */}
      <path d="M12 3v13m0 0l-4-4m4 4l4-4" />
      {/* Container/tray at bottom */}
      <path d="M3 19h18v2a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1v-2z" />
      <path d="M5 19V9a1 1 0 0 1 1-1h12a1 1 0 0 1 1 1v10" />
    </svg>
  );
}
