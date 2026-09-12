export interface ImagePrompts {
  reference: string;
  comparison: Record<string, string>;
}
export function validPrompts(prompts: ImagePrompts) {
  return [prompts.reference, ...Object.values(prompts.comparison)].every(
    (value) =>
      value.trim().length > 0 &&
      Array.from(value).length <= 12000 &&
      new TextEncoder().encode(value).length <= 32768 &&
      !/[a-z][a-z0-9+.-]*:\/\/|www\./i.test(value) &&
      !/\p{C}/u.test(value.replace(/[\r\n\t]/g, " ")),
  );
}
