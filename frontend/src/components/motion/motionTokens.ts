/** Curva suave estilo Ember/Apple para transições fluidas sem atrasar a operação. */
export const MOTION_EASE = [0.22, 1, 0.36, 1] as const;

export const SPRING_SNAPPY = {
  type: 'spring' as const,
  stiffness: 420,
  damping: 32,
  mass: 0.85,
};

export const SPRING_SOFT = {
  type: 'spring' as const,
  stiffness: 280,
  damping: 26,
};
