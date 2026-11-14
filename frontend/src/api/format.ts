import type { LanguageCode } from './types';
export function paise(value: number, language: LanguageCode = 'en') {
  if (!Number.isSafeInteger(value)) throw new RangeError('Money must be safe integer paise');
  const amount = BigInt(value);
  const whole = amount / 100n;
  const fraction = ((amount < 0n ? -amount : amount) % 100n).toString().padStart(2, '0');
  return new Intl.NumberFormat(`${language}-IN`, {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
    .formatToParts(whole === 0n && amount < 0n ? -0 : whole)
    .map((part) => (part.type === 'fraction' ? fraction : part.value))
    .join('');
}
export const stamp = (value: string, language: LanguageCode) =>
  new Date(value).toLocaleString(`${language}-IN`, { dateStyle: 'medium', timeStyle: 'short' });
