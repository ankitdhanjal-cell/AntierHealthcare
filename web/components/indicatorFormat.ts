import { fmtDuration } from "./ui";

/** One decimal at most, so 83.33 reads 83.3 */
export const n1 = (v: number) => Number(Number(v).toFixed(1));

/** Value text for an indicator: closure time as days or hours, percentages with %, everything else as a plain number. */
export const showValue = (i: any, v: number | null | undefined) => v == null ? "—" : i.key === "closure_time" ? fmtDuration(v) : `${n1(v)}${i.unit === "%" ? "%" : ""}`;
export const unitLabel = (i: any) => (i.key === "closure_time" || i.unit === "%" ? "" : i.unit);
