import React, { createContext, useContext, useEffect, useState } from 'react';

export type ThemeMode = 'clean' | 'dark';

interface ThemeContextValue {
  theme: ThemeMode;
  toggleTheme: () => void;
  setTheme: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextValue>({
  theme: 'clean',
  toggleTheme: () => {},
  setTheme: () => {},
});

export const ThemeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    try {
      const saved = localStorage.getItem('a5_theme');
      if (saved === 'dark' || saved === 'clean') return saved;
    } catch {
      // Ignore storage errors
    }
    return 'clean';
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark', 'dark-mode');
      root.classList.remove('clean-mode');
    } else {
      root.classList.remove('dark', 'dark-mode');
      root.classList.add('clean-mode');
    }
    try {
      localStorage.setItem('a5_theme', theme);
    } catch {
      // Ignore
    }
  }, [theme]);

  const toggleTheme = () => setThemeState((t) => (t === 'dark' ? 'clean' : 'dark'));

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme: setThemeState }}>
      {children}
    </ThemeContext.Provider>
  );
};

export function useTheme() {
  return useContext(ThemeContext);
}
