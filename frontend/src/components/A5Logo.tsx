import React, { useId } from 'react';

interface A5LogoProps {
  variant?: 'icon' | 'full';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const A5_MONOGRAM =
  'M 27.1 8.2 L 29.8 8.2 L 46.7 48.3 C 47.6 50.4 49.1 51.3 52.6 51.6 L 52.6 53.7 L 30.5 53.7 L 30.5 51.6 C 34.6 51.3 36.2 50.5 35.4 48.2 L 32.0 38.2 L 18.7 38.2 L 15.5 48.2 C 14.8 50.5 16.4 51.3 20.8 51.6 L 20.8 53.7 L 4.2 53.7 L 4.2 51.6 C 7.6 51.3 9.3 50.4 10.3 48.0 Z M 25.3 20.8 L 20.1 34.5 L 30.6 34.5 Z M 60.1 9.6 L 74.8 9.6 C 76.8 9.6 78.3 9.1 79.5 8.3 L 80.3 8.3 L 77.7 17.2 L 62.6 17.2 L 61.8 26.2 C 64.2 25.1 66.9 24.6 69.8 24.6 C 77.4 24.6 82.4 29.8 82.4 38.0 C 82.4 47.8 75.3 54.8 65.1 54.8 C 58.4 54.8 54.1 52.1 54.1 49.0 C 54.1 46.7 55.8 45.3 58.0 45.3 C 60.1 45.3 61.4 46.5 62.7 48.6 C 63.9 50.6 65.3 51.5 67.2 51.5 C 72.3 51.5 75.6 47.6 75.6 41.7 C 75.6 35.9 72.0 32.8 66.2 32.8 C 63.5 32.8 61.1 33.6 59.5 35.3 L 58.5 34.6 Z';

export const A5Logo: React.FC<A5LogoProps> = ({ variant = 'icon', size = 'md', className = '' }) => {
  const gradId = useId();
  const dim =
    size === 'sm' ? 'h-8 w-auto' : size === 'lg' ? 'h-12 w-auto' : 'h-10 w-auto';

  if (variant === 'icon') {
    return (
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 90 62"
        fill="none"
        role="img"
        aria-label="A5 Tecnologia"
        className={`${dim} ${className}`}
      >
        <defs>
          <linearGradient id={gradId} x1="1" y1="3" x2="89" y2="59" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#3B82F6" />
            <stop offset="100%" stopColor="#1D4ED8" />
          </linearGradient>
        </defs>
        <rect x="1" y="3" width="88" height="56" rx="12" fill={`url(#${gradId})`} />
        <rect x="1.5" y="3.5" width="87" height="55" rx="11.5" stroke="#ffffff" strokeOpacity="0.25" />
        <path d={A5_MONOGRAM} fill="#ffffff" fillRule="evenodd" />
      </svg>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2.5 select-none ${className}`}>
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 90 62"
        fill="none"
        role="img"
        aria-label="A5 Tecnologia"
        className={dim}
      >
        <defs>
          <linearGradient id={gradId} x1="1" y1="3" x2="89" y2="59" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#5D87FF" />
            <stop offset="100%" stopColor="#1D4ED8" />
          </linearGradient>
        </defs>
        <rect x="1" y="3" width="88" height="56" rx="12" fill={`url(#${gradId})`} />
        <rect x="1.5" y="3.5" width="87" height="55" rx="11.5" stroke="#ffffff" strokeOpacity="0.25" />
        <path d={A5_MONOGRAM} fill="#ffffff" fillRule="evenodd" />
      </svg>
      <div className="leading-none">
        <span className="block text-[15px] font-extrabold tracking-tight text-zinc-900 dark:text-white">
          A5 <span className="text-blue-600 dark:text-sky-400">Tecnologia</span>
        </span>
        <span className="block text-[10px] font-semibold tracking-wider uppercase text-slate-500 dark:text-zinc-400 mt-0.5">
          Balanças &amp; Esteira
        </span>
      </div>
    </div>
  );
};
