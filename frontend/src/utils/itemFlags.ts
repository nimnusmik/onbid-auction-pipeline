export function isNewToday(firstCollected: string): boolean {
  const today = new Date().toISOString().slice(0, 10);
  return firstCollected.slice(0, 10) === today;
}
