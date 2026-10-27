import { z } from "zod";

/** Zod 3 records an upper-bound issue but still parses every array element.
 * Admit the existing bound before parsing; preserve the original schema below it.
 * Keep this wrapper outside min/max/length so later array modifiers cannot bypass it.
 */
export function boundedArray<T extends z.ZodTypeAny, C extends z.ArrayCardinality>(schema: z.ZodArray<T, C>) {
  const { maxLength, exactLength } = schema._def;
  const bounds = [maxLength, exactLength].filter(bound => bound !== null);
  if (!bounds.length || bounds.some(bound => !Number.isSafeInteger(bound.value) || bound.value < 0))
    throw new Error("Array schema requires a finite upper bound");
  const maximum = Math.min(...bounds.map(bound => bound.value));
  return z.preprocess((value, context) => {
    if (Array.isArray(value) && value.length > maximum) {
      const exact = exactLength !== null && exactLength.value === maximum;
      context.addIssue({ code: z.ZodIssueCode.too_big, maximum, type: "array", inclusive: true,
        exact, message: (exact ? exactLength : maxLength)?.message, fatal: true });
      return z.NEVER;
    }
    return value;
  // The preprocessor only rejects oversize arrays; every admitted input is
  // passed unchanged to schema. Preserve its input type for kvBody inference.
  }, schema) as z.ZodEffects<z.ZodArray<T, C>, z.output<z.ZodArray<T, C>>, z.input<z.ZodArray<T, C>>>;
}
